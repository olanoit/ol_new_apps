# -*- coding: utf-8 -*-
"""Adicionales, deductivos y dependencias de terceros (v1.5, fase 19:
M15-12, M15-13 y P-32).

Un **cambio** de obra (``construction.change.order``) junta lo que se agrega
o se quita de una o varias unidades después de aprobado el plan: adicional,
deductivo, neto (agrega y quita) o rehacer (costo propio, no se cobra). Cada
línea dice qué recurso cambia y en qué cantidad (negativa en lo que se
quita); la regla de precio al cliente se propone según el estado de la
unidad:

* aún no producida → **diferencia** de precio;
* producida o en obra → **pieza suelta**;
* instalada o entregada → **reinstalación** (pieza más desmontaje y
  reinstalación).

Al aprobarlo, sus líneas entran al plan vigente con origen «Cambio» y su
monto se suma al presupuesto analítico del plan.

Una **dependencia** (``construction.dependency``) es lo que un tercero debe
entregar antes de empezar una etapa: encimera, electrodomésticos, frente
liberado, piloto aprobado o instalaciones. Mientras está abierta, la etapa de
las unidades que cubre no admite avances, el cronograma la marca y no se
puede programar antes de la fecha prevista.
"""
from datetime import timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .common import (
    PROJECT_HEAD_GROUPS, RESOURCE_TYPES, UNIT_STATE_RANK, UNIT_STATES, stage_selection,
)

CHANGE_KINDS = [
    ('additional', 'Adicional'),
    ('deductive', 'Deductivo'),
    ('net', 'Neto'),
    ('rework', 'Rehacer'),
]
CHANGE_STATES = [
    ('draft', 'Borrador'),
    ('approved', 'Aprobado'),
    ('cancel', 'Anulado'),
]
PRICE_RULES = [
    ('difference', 'Diferencia de precio'),
    ('loose_part', 'Pieza suelta'),
    ('reinstall', 'Reinstalación'),
    ('new_price', 'Precio nuevo'),
]
DEPENDENCY_KINDS = [
    ('countertop', 'Encimera'),
    ('appliances', 'Electrodomésticos'),
    ('front', 'Frente liberado'),
    ('pilot', 'Piloto aprobado'),
    ('mep', 'Instalaciones (eléctricas y sanitarias)'),
]
DEPENDENCY_STATES = [
    ('open', 'Abierta'),
    ('done', 'Cumplida'),
    ('cancel', 'Anulada'),
]


def _price_rule_for_state(state):
    """Regla de precio que se propone según el estado de la unidad."""
    rank = UNIT_STATE_RANK.get(state or 'planned', 0)
    if rank >= UNIT_STATE_RANK['installed']:
        return 'reinstall'
    if rank >= UNIT_STATE_RANK['produced']:
        return 'loose_part'
    return 'difference'


class ConstructionChangeOrder(models.Model):
    _name = 'construction.change.order'
    _description = 'Cambio de obra (adicional o deductivo)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', required=True, readonly=True, copy=False, default='/')
    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, index=True, check_company=True,
        domain="[('is_construction_site', '=', True)]", tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', compute='_compute_company_id', store=True, index=True,
        precompute=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan', compute='_compute_plan_id', store=True,
        readonly=False, check_company=True, domain="[('project_id', '=', project_id)]",
        help='El plan vigente de la obra: allí entran las líneas al aprobar el cambio.')
    contract_id = fields.Many2one(
        'construction.contract', string='Contrato', check_company=True,
        domain="[('project_id', '=', project_id)]",
        help='Contrato con el cliente al que se suma lo que se cobra del cambio.')
    kind = fields.Selection(CHANGE_KINDS, string='Tipo', required=True, default='additional',
                            tracking=True)
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    requested_by = fields.Selection(
        [('client', 'Cliente'), ('internal', 'Interno'), ('contractor', 'Contrata')],
        string='Lo pide', required=True, default='client')
    client_order_ref = fields.Char(
        string='Orden del cliente', help='Referencia de la orden o carta del cliente que pide el '
                                         'cambio.')
    task_ids = fields.Many2many(
        'project.task', string='Unidades', compute='_compute_task_ids', store=True,
        help='Unidades que toca el cambio (las de sus líneas).')
    reason = fields.Text(string='Motivo', required=True)
    state = fields.Selection(CHANGE_STATES, string='Estado', required=True, default='draft',
                             tracking=True, copy=False)
    line_ids = fields.One2many('construction.change.order.line', 'change_id', string='Líneas',
                               copy=True)
    plan_line_ids = fields.One2many(
        'construction.resource.plan.line', 'change_id', string='Líneas del plan', readonly=True)
    amount_cost = fields.Monetary(
        string='Costo', compute='_compute_amounts', store=True,
        help='Lo que el cambio suma (o resta) al costo planificado.')
    amount_sale = fields.Monetary(
        string='Precio al cliente', compute='_compute_amounts', store=True,
        help='Lo que se cobra (o se descuenta) al cliente. Rehacer no se cobra.')
    approved_by_id = fields.Many2one('res.users', string='Aprobado por', readonly=True,
                                     copy=False)
    date_approved = fields.Datetime(string='Aprobado el', readonly=True, copy=False)

    @api.depends('project_id.company_id')
    def _compute_company_id(self):
        for change in self:
            change.company_id = change.project_id.company_id or change.company_id \
                or self.env.company

    @api.depends('line_ids.task_id')
    def _compute_task_ids(self):
        for change in self:
            tasks = change.line_ids.task_id
            change.task_ids = tasks.construction_apartment_task_id | tasks.filtered(
                lambda t: t.construction_level in ('group', 'floor', 'apartment'))

    @api.depends('project_id')
    def _compute_plan_id(self):
        for change in self:
            change.plan_id = change.project_id._construction_current_plan() \
                if change.project_id else False

    @api.depends('line_ids.amount_cost', 'line_ids.amount_sale', 'kind')
    def _compute_amounts(self):
        for change in self:
            change.amount_cost = sum(change.line_ids.mapped('amount_cost'))
            change.amount_sale = 0.0 if change.kind == 'rework' else sum(
                change.line_ids.mapped('amount_sale'))

    @api.constrains('kind', 'line_ids')
    def _check_signs(self):
        for change in self:
            lines = change.line_ids
            if change.kind in ('additional', 'rework') and lines.filtered(lambda l: l.qty < 0):
                raise ValidationError(self.env._(
                    'Un adicional o un rehacer solo agrega: %s tiene cantidades negativas.',
                    change.display_name))
            if change.kind == 'deductive' and lines.filtered(lambda l: l.qty > 0):
                raise ValidationError(self.env._(
                    'Un deductivo solo quita: use cantidades negativas en %s.',
                    change.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'construction.change.order') or '/'
        return super().create(vals_list)

    def action_approve(self):
        """Aprueba el cambio: sus líneas entran al plan vigente con origen
        «Cambio» y su costo se suma al presupuesto analítico del plan."""
        if not self.env.user.has_groups(PROJECT_HEAD_GROUPS):
            raise UserError(self.env._('Solo la jefatura de proyectos aprueba cambios.'))
        for change in self:
            if change.state != 'draft':
                raise UserError(self.env._('%s ya no está en borrador.', change.display_name))
            if not change.line_ids:
                raise UserError(self.env._('%s no tiene líneas.', change.display_name))
            plan = change.plan_id
            if not plan or plan.state not in ('approved', 'in_progress', 'draft'):
                raise UserError(self.env._(
                    'La obra %s no tiene un plan vigente ni en preparación.',
                    change.project_id.display_name))
            lines = change._create_plan_lines(plan)
            if plan.budget_analytic_id:
                plan._construction_add_to_budget(lines)
            change.write({'state': 'approved', 'approved_by_id': self.env.user.id,
                          'date_approved': fields.Datetime.now()})
            change.message_post(body=self.env._(
                '%(count)s líneas entraron al plan %(plan)s (costo %(amount)s).',
                count=len(lines), plan=plan.display_name,
                amount=change.currency_id.format(change.amount_cost)))
        return True

    def _create_plan_lines(self, plan):
        self.ensure_one()
        vals_list = [line._plan_line_vals(plan) for line in self.line_ids]
        # Las líneas de un plan aprobado no se editan: el cambio aprobado es
        # la vía para sumarlas (como la replanificación).
        lines = self.env['construction.resource.plan.line'].with_context(
            construction_plan_force=True).create(vals_list)
        lines._apply_analytic_rules()
        if plan.state != 'draft':
            for line in lines:
                line.with_context(construction_plan_force=True).amount_budgeted = \
                    line.amount_planned
        return lines

    def action_cancel(self):
        if self.filtered(lambda c: c.state == 'approved'):
            raise UserError(self.env._(
                'Un cambio aprobado ya está en el plan: regístrelo al revés con otro cambio.'))
        self.state = 'cancel'

    def action_draft(self):
        self.filtered(lambda c: c.state == 'cancel').state = 'draft'

    def action_view_plan_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Líneas del plan · %s', self.name),
            'res_model': 'construction.resource.plan.line',
            'view_mode': 'list',
            'domain': [('change_id', '=', self.id)],
        }


class ConstructionChangeOrderLine(models.Model):
    _name = 'construction.change.order.line'
    _inherit = ['construction.resource.type.mixin']
    _description = 'Línea del cambio de obra'
    _order = 'change_id, sequence, id'
    _check_company_auto = True

    change_id = fields.Many2one('construction.change.order', string='Cambio', required=True,
                                ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    project_id = fields.Many2one(related='change_id.project_id', store=True)
    company_id = fields.Many2one(related='change_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='change_id.currency_id')
    task_id = fields.Many2one(
        'project.task', string='Nivel', required=True, check_company=True,
        domain="[('project_id', '=', project_id), ('construction_level', '!=', False)]",
        help='Unidad, ambiente, mueble o módulo al que se agrega o del que se quita.')
    unit_state = fields.Selection(
        UNIT_STATES, string='Estado de la unidad', compute='_compute_unit_state',
        help='El más avanzado de los módulos del nivel.')
    resource_type = fields.Selection(RESOURCE_TYPES, string='Comportamiento', required=True,
                                     default='material')
    stage = fields.Selection(stage_selection, string='Etapa')
    product_id = fields.Many2one('product.product', string='Producto', check_company=True)
    activity_id = fields.Many2one('construction.labor.activity', string='Actividad (driver)',
                                  check_company=True)
    partner_id = fields.Many2one('res.partner', string='Contrata o proveedor',
                                 check_company=True)
    product_uom_id = fields.Many2one(
        'uom.uom', string='Unidad', compute='_compute_product_uom_id', store=True,
        readonly=False)
    qty = fields.Float(string='Cantidad', digits='Product Unit', required=True, default=1.0,
                       help='Negativa en lo que se quita.')
    price_unit = fields.Monetary(string='Costo unitario', currency_field='currency_id')
    amount_cost = fields.Monetary(string='Costo', compute='_compute_amounts', store=True,
                                  currency_field='currency_id')
    price_rule = fields.Selection(
        PRICE_RULES, string='Regla de precio', compute='_compute_price_rule', store=True,
        readonly=False, help='Propuesta según el estado de la unidad; se puede cambiar.')
    sale_price_unit = fields.Monetary(
        string='Precio unitario al cliente', currency_field='currency_id',
        help='Diferencia de precio: lo que cuesta de más (o de menos) la pieza nueva. Pieza '
             'suelta, reinstalación y precio nuevo: el precio de la pieza.')
    reinstall_amount = fields.Monetary(
        string='Desmontaje y reinstalación', currency_field='currency_id',
        help='Solo con la regla «Reinstalación»: lo que se cobra por desmontar y volver a '
             'instalar.')
    amount_sale = fields.Monetary(string='Precio al cliente', compute='_compute_amounts',
                                  store=True, currency_field='currency_id')

    @api.depends('task_id', 'task_id.construction_unit_state')
    def _compute_unit_state(self):
        Task = self.env['project.task']
        for line in self:
            task = line.task_id
            if not task:
                line.unit_state = False
                continue
            modules = task if task.construction_level == 'module' else Task.search([
                ('id', 'child_of', task.id), ('construction_level', '=', 'module')])
            states = [m.construction_unit_state or 'planned' for m in modules]
            line.unit_state = max(states, key=lambda s: UNIT_STATE_RANK[s]) if states \
                else 'planned'

    @api.depends('task_id', 'task_id.construction_unit_state')
    def _compute_price_rule(self):
        for line in self:
            line.price_rule = _price_rule_for_state(line.unit_state)

    @api.depends('product_id', 'activity_id')
    def _compute_product_uom_id(self):
        for line in self:
            line.product_uom_id = line.product_id.uom_id or line.activity_id.uom_id \
                or line.product_uom_id

    @api.depends('qty', 'price_unit', 'sale_price_unit', 'reinstall_amount', 'price_rule')
    def _compute_amounts(self):
        for line in self:
            line.amount_cost = line.qty * line.price_unit
            sale = line.qty * line.sale_price_unit
            if line.price_rule == 'reinstall':
                sale += line.reinstall_amount
            line.amount_sale = sale

    @api.constrains('resource_type', 'product_id', 'activity_id', 'qty')
    def _check_resource(self):
        for line in self:
            if line.resource_type == 'contract' and not line.activity_id:
                raise ValidationError(self.env._(
                    'La línea de contrata de %s necesita la actividad.', line.change_id.name))
            if line.resource_type in ('material', 'service', 'equipment') and not line.product_id:
                raise ValidationError(self.env._(
                    'La línea de %s necesita el producto.', line.change_id.name))
            if not line.qty:
                raise ValidationError(self.env._(
                    'Las líneas de %s necesitan una cantidad distinta de cero.',
                    line.change_id.name))

    def _plan_line_vals(self, plan):
        self.ensure_one()
        uom = self.product_uom_id or self.product_id.uom_id or self.activity_id.uom_id \
            or self.env.ref('uom.product_uom_unit')
        return {
            'plan_id': plan.id,
            'task_id': self.task_id.id,
            'resource_type': self.resource_type,
            'resource_type_id': self.resource_type_id.id,
            'stage': self.stage,
            'product_id': self.product_id.id,
            'activity_id': self.activity_id.id,
            'partner_id': self.partner_id.id,
            'product_uom_id': uom.id,
            'qty_planned': self.qty,
            'price_unit_planned': self.price_unit,
            'source': 'change',
            'source_ref': self.change_id.name,
            'change_id': self.change_id.id,
        }


class ConstructionDependency(models.Model):
    _name = 'construction.dependency'
    _description = 'Dependencia de terceros en la obra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'state, date_expected, id'
    _check_company_auto = True

    name = fields.Char(string='Descripción', required=True)
    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, index=True, check_company=True,
        domain="[('is_construction_site', '=', True)]")
    company_id = fields.Many2one(
        'res.company', string='Compañía', compute='_compute_company_id', store=True, index=True,
        precompute=True)
    kind = fields.Selection(DEPENDENCY_KINDS, string='Tipo', required=True, default='countertop')
    partner_id = fields.Many2one(
        'res.partner', string='Responsable', check_company=True,
        help='El tercero que debe cumplirla: el cliente, su proveedor u otra contrata.')
    task_ids = fields.Many2many(
        'project.task', string='Niveles', check_company=True,
        domain="[('project_id', '=', project_id), "
               "('construction_level', 'in', ('group', 'floor', 'apartment', 'space'))]",
        help='Agrupadores, pisos, unidades o ambientes que espera. Vacío: toda la obra.')
    stage = fields.Selection(
        stage_selection, string='Etapa que bloquea', required=True, default='installation')
    date_expected = fields.Date(
        string='Fecha prevista', tracking=True,
        help='Desde cuándo se espera cumplida: la etapa no se programa antes.')
    date_done = fields.Date(string='Cumplida el', readonly=True, copy=False)
    state = fields.Selection(DEPENDENCY_STATES, string='Estado', required=True, default='open',
                             tracking=True, copy=False)
    note = fields.Text(string='Nota')
    stage_count = fields.Integer(string='Etapas bloqueadas', compute='_compute_stage_count')

    @api.depends('project_id.company_id')
    def _compute_company_id(self):
        for dependency in self:
            dependency.company_id = dependency.project_id.company_id or dependency.company_id \
                or self.env.company

    def _stages_domain(self):
        self.ensure_one()
        domain = [('project_id', '=', self.project_id.id), ('stage', '=', self.stage)]
        if self.task_ids:
            domain.append(('space_task_id', 'child_of', self.task_ids.ids))
        return domain

    def _blocked_stages(self):
        Stage = self.env['construction.space.stage']
        stages = Stage.browse()
        for dependency in self.filtered(lambda d: d.state == 'open'):
            stages |= Stage.search(dependency._stages_domain())
        return stages

    def _compute_stage_count(self):
        for dependency in self:
            dependency.stage_count = len(dependency._blocked_stages())

    def _covers(self, task):
        """La dependencia alcanza a ``task`` (sus niveles o uno de sus
        ancestros)."""
        self.ensure_one()
        if task.project_id != self.project_id:
            return False
        if not self.task_ids:
            return True
        node = task
        while node:
            if node in self.task_ids:
                return True
            node = node.parent_id
        return False

    @api.model
    def _open_for(self, task, stage):
        """Dependencias abiertas que bloquean la etapa ``stage`` de ``task``."""
        if not task or not stage:
            return self.browse()
        dependencies = self.search([('project_id', '=', task.project_id.id),
                                    ('stage', '=', stage), ('state', '=', 'open')])
        return dependencies.filtered(lambda d: d._covers(task))

    def action_done(self):
        self.write({'state': 'done', 'date_done': fields.Date.context_today(self)})

    def action_cancel(self):
        self.state = 'cancel'

    def action_reopen(self):
        self.write({'state': 'open', 'date_done': False})

    def action_view_stages(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Etapas bloqueadas · %s', self.name),
            'res_model': 'construction.space.stage',
            'view_mode': 'list',
            'domain': self._stages_domain(),
        }

    def action_shift_schedule(self):
        """Corre al día hábil siguiente a la fecha prevista las etapas que
        bloquea y que empiezan antes; cada una conserva sus días hábiles y
        empuja las siguientes de su ambiente."""
        moved = self.env['construction.space.stage']
        for dependency in self.filtered(lambda d: d.state == 'open'):
            if not dependency.date_expected:
                raise UserError(self.env._(
                    'Indique la fecha prevista de %s para mover el cronograma.', dependency.name))
            limit = dependency.date_expected
            for stage in dependency._blocked_stages().filtered(lambda s: s.date_start <= limit):
                company = stage._company_for_days()
                days = company._construction_count_site_days(stage.date_start, stage.date_end)
                start = company._construction_next_site_day(limit + timedelta(days=1))
                end = company._construction_add_site_days(start, days)
                stage.with_context(construction_dependency_shift=True).action_gantt_reschedule(
                    start, end, chain=True)
                moved |= stage
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'success' if moved else 'info', 'sticky': False,
                       'message': self.env._('%s etapas movidas.', len(moved))},
        }


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    source = fields.Selection(selection_add=[('change', 'Cambio')],
                              ondelete={'change': 'set default'})
    change_id = fields.Many2one('construction.change.order', string='Cambio', readonly=True,
                                index='btree_not_null', copy=False, check_company=True)


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def _construction_add_to_budget(self, lines):
        """Suma ``lines`` al presupuesto analítico del plan: a la línea de
        presupuesto de su misma combinación de cuentas o, si no existe, a una
        nueva."""
        self.ensure_one()
        Account = self.env['account.analytic.account']
        project_account = self.project_id.account_id
        default = {str(project_account.id): 100.0} if project_account else {}
        combos = {}
        for line in lines:
            for key, percentage in (line.analytic_distribution or default).items():
                accounts = Account.browse(int(a) for a in key.split(',') if a).exists()
                combo = tuple(sorted((a.root_plan_id._column_name(), a.id) for a in accounts))
                if combo:
                    combos[combo] = combos.get(combo, 0.0) + \
                        line.amount_planned * percentage / 100.0
        # sudo: la jefatura que aprueba el cambio no suele tener permisos de
        # contabilidad; el presupuesto es consecuencia de la aprobación y sus
        # valores salen del plan.
        budget_sudo = self.budget_analytic_id.sudo()
        for combo, amount in combos.items():
            values = dict(combo)
            match = budget_sudo.budget_line_ids.filtered(lambda b: all(
                b[fname].id == values.get(fname) for fname in b._get_plan_fnames()))
            if match:
                match[0].budget_amount += self.currency_id.round(amount)
            else:
                budget_sudo.write({'budget_line_ids': [Command.create(
                    dict(values, budget_amount=self.currency_id.round(amount)))]})


class ConstructionSpaceStage(models.Model):
    _inherit = 'construction.space.stage'

    dependency_ids = fields.Many2many(
        'construction.dependency', string='Dependencias abiertas',
        compute='_compute_dependency_ids')
    blocked = fields.Boolean(string='Bloqueada', compute='_compute_dependency_ids')

    def _compute_dependency_ids(self):
        Dependency = self.env['construction.dependency']
        for record in self:
            record.dependency_ids = Dependency._open_for(record.space_task_id, record.stage)
            record.blocked = bool(record.dependency_ids)

    @api.model
    def action_gantt_reschedule(self, date_start, date_end, chain=False):
        start = fields.Date.to_date(date_start)
        if start and not self.env.context.get('construction_dependency_shift'):
            for dependency in self.env['construction.dependency']._open_for(
                    self.space_task_id, self.stage):
                if dependency.date_expected and start <= dependency.date_expected:
                    raise UserError(self.env._(
                        '%(stage)s espera «%(dependency)s» hasta el %(date)s: programe la '
                        'etapa después.', stage=self.display_name, dependency=dependency.name,
                        date=fields.Date.to_string(dependency.date_expected)))
        return super().action_gantt_reschedule(date_start, date_end, chain=chain)


class ConstructionTaskProgress(models.Model):
    _inherit = 'construction.task.progress'

    @api.model_create_multi
    def create(self, vals_list):
        progresses = super().create(vals_list)
        Dependency = self.env['construction.dependency']
        for progress in progresses:
            dependencies = Dependency._open_for(progress.task_id,
                                                progress.plan_line_id.stage)
            if dependencies:
                raise UserError(self.env._(
                    'La etapa de %(task)s está bloqueada por %(dependencies)s: no admite '
                    'avances hasta que se cumpla.', task=progress.task_id.display_name,
                    dependencies=', '.join(dependencies.mapped('name'))))
        return progresses


class ConstructionContract(models.Model):
    _inherit = 'construction.contract'

    change_order_ids = fields.One2many('construction.change.order', 'contract_id',
                                       string='Cambios')
    amount_changes = fields.Monetary(
        string='Adicionales y deductivos', compute='_compute_amount_changes',
        help='Precio al cliente de los cambios aprobados del contrato.')

    @api.depends('change_order_ids.state', 'change_order_ids.amount_sale')
    def _compute_amount_changes(self):
        for contract in self:
            contract.amount_changes = sum(contract.change_order_ids.filtered(
                lambda c: c.state == 'approved').mapped('amount_sale'))


class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_contract_id = fields.Many2one(
        'construction.contract', string='Contrato', compute='_compute_construction_contract_id',
        help='Contrato de obra vigente (o en borrador) que cubre la unidad.')

    def _compute_construction_contract_id(self):
        Contract = self.env['construction.contract']
        for task in self:
            unit = task if task.construction_level == 'apartment' \
                else task.construction_apartment_task_id
            # Tarea nueva o sin unidad: sin contrato (y no la tarea vacía).
            unit_ids = unit._origin.ids
            task.construction_contract_id = Contract.search([
                ('task_ids', 'in', unit_ids), ('state', 'in', ('active', 'draft'))],
                order='state, id', limit=1) if unit_ids else Contract

