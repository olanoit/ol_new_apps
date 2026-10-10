# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .common import RESOURCE_TYPES, STAGES

PLAN_STATES = [
    ('draft', 'Borrador'),
    ('to_approve', 'En aprobación'),
    ('approved', 'Aprobado'),
    ('in_progress', 'En ejecución'),
    ('closed', 'Cerrado'),
    ('replaced', 'Reemplazado'),
    ('cancel', 'Cancelado'),
]
# Estados en los que el plan es el vigente de la obra.
OPEN_STATES = ('approved', 'in_progress')
# Estados de una versión en preparación.
DRAFT_STATES = ('draft', 'to_approve')


class ConstructionResourcePlan(models.Model):
    """Plan de recursos de una obra (una versión). Sus líneas cuelgan de los
    niveles de la obra y se acumulan hacia arriba en el árbol."""
    _name = 'construction.resource.plan'
    _description = 'Plan de recursos de obra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'project_id, version desc'
    _check_company_auto = True

    name = fields.Char(string='Número', required=True, readonly=True, copy=False, default='/')
    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, index=True, check_company=True,
        domain=[('is_construction_site', '=', True)], tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True, store=True,
        compute='_compute_company_id', precompute=True, readonly=False,
        default=lambda self: self.env.company,
        help='La de la obra; si la obra es compartida entre compañías, la activa al crearlo.')
    currency_id = fields.Many2one(
        related='company_id.currency_id', string='Moneda', store=True)
    user_id = fields.Many2one(
        'res.users', string='Responsable', required=True, default=lambda self: self.env.user,
        tracking=True)
    version = fields.Integer(string='Versión', default=1, readonly=True, copy=False)
    parent_id = fields.Many2one(
        'construction.resource.plan', string='Versión anterior', readonly=True, copy=False,
        check_company=True)
    replan_reason = fields.Text(string='Motivo de la versión', tracking=True)
    state = fields.Selection(
        PLAN_STATES, string='Estado', required=True, default='draft', tracking=True, copy=False)
    date_start = fields.Date(string='Inicio', required=True, tracking=True)
    date_end = fields.Date(string='Fin', required=True, tracking=True)
    exceed_policy = fields.Selection(
        [('warn', 'Solo alerta'), ('approval', 'Aprobación adicional'), ('block', 'Bloquear')],
        string='Si se excede el saldo', required=True, default='approval', tracking=True,
        help='Qué pasa cuando un documento pide más de lo que queda en el plan.')
    exceed_tolerance = fields.Float(
        string='Tolerancia (%)', digits=(5, 2), default=0.0,
        help='Exceso permitido sobre el saldo antes de aplicar la política.')
    lead_days_material = fields.Integer(
        string='Anticipación de material (días)', default=7,
        help='Días antes del inicio de la tarea en que se necesita el material.')
    lead_days_contract = fields.Integer(string='Anticipación de contrata (días)', default=3)
    lead_days_production = fields.Integer(string='Anticipación de producción (días)', default=7)
    budget_analytic_id = fields.Many2one(
        'budget.analytic', string='Presupuesto analítico', readonly=True, copy=False,
        check_company=True, help='Lo crea la aprobación del plan.')
    line_ids = fields.One2many(
        'construction.resource.plan.line', 'plan_id', string='Líneas', copy=True)
    line_count = fields.Integer(string='Nº de líneas', compute='_compute_amounts', store=True)
    amount_material = fields.Monetary(
        string='Material', compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_service = fields.Monetary(
        string='Servicios', compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_contract = fields.Monetary(
        string='Contratas', compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_labor = fields.Monetary(
        string='Personal propio', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    amount_production = fields.Monetary(
        string='Producción', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    amount_total = fields.Monetary(
        string='Planificado', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    unstaged_line_count = fields.Integer(
        string='Líneas sin etapa', compute='_compute_warnings')
    unpriced_line_count = fields.Integer(
        string='Líneas sin costo', compute='_compute_warnings')

    @api.depends('project_id')
    def _compute_company_id(self):
        for record in self:
            record.company_id = (record.project_id.company_id or record.company_id
                                 or self.env.company)

    @api.depends('line_ids.amount_planned', 'line_ids.resource_type')
    def _compute_amounts(self):
        Line = self.env['construction.resource.plan.line']
        totals = {}
        if self.ids:
            for plan, rtype, amount, count in Line._read_group(
                    [('plan_id', 'in', self.ids)], groupby=['plan_id', 'resource_type'],
                    aggregates=['amount_planned:sum', '__count']):
                totals.setdefault(plan.id, {})[rtype] = (amount, count)
        for plan in self:
            data = totals.get(plan.id, {})
            if not plan.id or not data:
                # Registro nuevo o sin líneas en BD: suma en memoria.
                data = {}
                for line in plan.line_ids:
                    amount, count = data.get(line.resource_type, (0.0, 0))
                    data[line.resource_type] = (amount + line.amount_planned, count + 1)
            plan.amount_material = data.get('material', (0.0, 0))[0]
            plan.amount_service = data.get('service', (0.0, 0))[0]
            plan.amount_contract = data.get('contract', (0.0, 0))[0]
            plan.amount_labor = data.get('labor', (0.0, 0))[0]
            plan.amount_production = data.get('production', (0.0, 0))[0]
            plan.amount_total = sum(amount for amount, _count in data.values())
            plan.line_count = sum(count for _amount, count in data.values())

    def _compute_warnings(self):
        Line = self.env['construction.resource.plan.line']
        unstaged = dict(Line._read_group(
            [('plan_id', 'in', self.ids), ('stage', '=', False)], ['plan_id'], ['__count']))
        unpriced = dict(Line._read_group(
            [('plan_id', 'in', self.ids), ('price_unit_planned', '=', 0)], ['plan_id'],
            ['__count']))
        for plan in self:
            plan.unstaged_line_count = unstaged.get(plan, 0)
            plan.unpriced_line_count = unpriced.get(plan, 0)

    @api.constrains('project_id', 'state')
    def _check_single_version(self):
        """Por obra: una sola versión vigente (aprobada o en ejecución) y una
        sola en preparación (borrador o en aprobación)."""
        for plan in self:
            for states in (OPEN_STATES, DRAFT_STATES):
                if plan.state in states and self.search_count([
                        ('project_id', '=', plan.project_id.id),
                        ('state', 'in', states), ('id', '!=', plan.id)]):
                    raise ValidationError(self.env._(
                        'La obra %s ya tiene un plan %s.', plan.project_id.display_name,
                        'vigente' if states == OPEN_STATES else 'en preparación'))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for plan in self:
            if plan.date_start and plan.date_end and plan.date_start > plan.date_end:
                raise ValidationError(self.env._('El plan termina antes de empezar.'))

    @api.onchange('project_id')
    def _onchange_project_id(self):
        project = self.project_id
        if project:
            self.date_start = self.date_start or project.date_start or fields.Date.context_today(self)
            self.date_end = self.date_end or project.date or (
                self.date_start + timedelta(days=90))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'construction.resource.plan') or '/'
            project = self.env['project.project'].browse(vals.get('project_id'))
            if project and 'version' not in vals:
                last = self.with_context(active_test=False).search(
                    [('project_id', '=', project.id)], order='version desc', limit=1)
                vals['version'] = (last.version or 0) + 1
            if project:
                vals.setdefault('date_start', project.date_start or fields.Date.context_today(self))
                vals.setdefault('date_end', project.date or fields.Date.to_date(
                    vals['date_start']) + timedelta(days=90))
        return super().create(vals_list)

    @api.depends('name', 'project_id', 'version')
    def _compute_display_name(self):
        for plan in self:
            plan.display_name = '%s · v%s' % (plan.name, plan.version) if plan.name else ''

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def _check_draft(self):
        for plan in self:
            if plan.state != 'draft':
                raise UserError(self.env._(
                    'El plan %s ya no está en borrador: créele una versión nueva.', plan.name))

    def action_open_generate_wizard(self):
        self.ensure_one()
        self._check_draft()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Generar plan'),
            'res_model': 'construction.plan.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_plan_id': self.id},
        }

    def action_cancel(self):
        for plan in self:
            if plan.state not in ('draft', 'to_approve'):
                raise UserError(self.env._('Solo se cancela un plan que no se aprobó.'))
        self.write({'state': 'cancel'})

    def action_draft(self):
        self.filtered(lambda p: p.state == 'cancel').write({'state': 'draft'})

    def action_view_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Líneas de %s', self.display_name),
            'res_model': 'construction.resource.plan.line',
            'view_mode': 'list,pivot,form',
            'domain': [('plan_id', '=', self.id)],
            'context': {'default_plan_id': self.id, 'search_default_group_stage': 1},
        }


class ConstructionResourcePlanLine(models.Model):
    """Recurso planificado en un nivel de la obra: material, servicio,
    contrata, personal propio o producción."""
    _name = 'construction.resource.plan.line'
    _description = 'Línea del plan de recursos'
    _inherit = ['analytic.mixin']
    _order = 'plan_id, floor_task_id, apartment_task_id, space_task_id, module_task_id, stage, id'
    _check_company_auto = True

    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan', required=True, ondelete='cascade',
        index=True, check_company=True)
    plan_state = fields.Selection(related='plan_id.state', string='Estado del plan')
    project_id = fields.Many2one(
        related='plan_id.project_id', string='Obra', store=True, index=True)
    company_id = fields.Many2one(
        related='plan_id.company_id', string='Compañía', store=True, index=True)
    currency_id = fields.Many2one(related='plan_id.currency_id', string='Moneda')
    task_id = fields.Many2one(
        'project.task', string='Nivel', index=True, check_company=True,
        help='Tarea de piso, departamento, ambiente o módulo. Vacía: la obra.')
    task_level = fields.Selection(
        string='Tipo de nivel', related='task_id.construction_level', store=True)
    # Ancestros por nivel: base de la acumulación del árbol y del filtro por
    # selección (read_group por nivel, sin recursión en Python).
    floor_task_id = fields.Many2one(
        'project.task', string='Piso', compute='_compute_ancestors', store=True, index=True,
        check_company=True)
    apartment_task_id = fields.Many2one(
        'project.task', string='Departamento', compute='_compute_ancestors', store=True,
        index=True, check_company=True)
    space_task_id = fields.Many2one(
        'project.task', string='Ambiente', compute='_compute_ancestors', store=True, index=True,
        check_company=True)
    module_task_id = fields.Many2one(
        'project.task', string='Módulo', compute='_compute_ancestors', store=True, index=True,
        check_company=True)
    resource_type = fields.Selection(
        RESOURCE_TYPES, string='Tipo de recurso', required=True, default='material')
    stage = fields.Selection(STAGES, string='Etapa')
    product_id = fields.Many2one(
        'product.product', string='Producto', check_company=True, index=True)
    activity_id = fields.Many2one(
        'construction.labor.activity', string='Actividad (driver)', check_company=True,
        index=True)
    partner_id = fields.Many2one(
        'res.partner', string='Contrata o proveedor', check_company=True, index=True)
    role_id = fields.Many2one('planning.role', string='Rol')
    typology_id = fields.Many2one(
        'construction.typology', string='Tipología', check_company=True)
    product_uom_id = fields.Many2one('uom.uom', string='Unidad', required=True)
    qty_planned = fields.Float(string='Cantidad', digits='Product Unit', required=True)
    price_unit_planned = fields.Monetary(
        string='Costo unitario', currency_field='currency_id',
        help='Lo escribe el planificador después de revisar los precios de compra; en '
             'contratas, la tarifa vigente es la referencia.')
    amount_planned = fields.Monetary(
        string='Monto', compute='_compute_amount_planned', store=True,
        currency_field='currency_id')
    price_basis = fields.Char(
        string='Base del costo',
        help='Qué miró el planificador al fijar el costo (p. ej. «media móvil 4 semanas '
             'al 28/09: 122.84»).')
    price_basis_date = fields.Date(string='Fecha de la base')
    date_needed = fields.Date(
        string='Fecha de necesidad', compute='_compute_date_needed', store=True,
        readonly=False, help='Inicio de la tarea menos la anticipación del tipo de recurso.')
    supply_mode = fields.Selection(
        [('central', 'Almacén central'), ('direct', 'Directo a obra')],
        string='Abastecimiento', default='central')
    source = fields.Selection(
        [('generated', 'Generada'), ('manual', 'Manual'), ('replan', 'Replanificación')],
        string='Origen', default='manual', readonly=True)
    source_ref = fields.Char(string='Referencia del origen', readonly=True)
    previous_line_id = fields.Many2one(
        'construction.resource.plan.line', string='Línea anterior', readonly=True,
        check_company=True)
    line_state = fields.Selection(
        [('planned', 'Planificada'), ('partial', 'Parcial'), ('purchasing', 'En compra'),
         ('done', 'Completa'), ('exceeded', 'Excedida'), ('cancel', 'Cancelada')],
        string='Estado', default='planned', readonly=True)

    @api.depends('task_id', 'task_id.construction_level', 'task_id.construction_floor_task_id',
                 'task_id.construction_apartment_task_id', 'task_id.construction_space_task_id')
    def _compute_ancestors(self):
        for line in self:
            task = line.task_id
            line.floor_task_id = task.construction_floor_task_id
            line.apartment_task_id = task.construction_apartment_task_id
            line.space_task_id = task.construction_space_task_id
            line.module_task_id = task if task.construction_level == 'module' else False

    @api.depends('qty_planned', 'price_unit_planned')
    def _compute_amount_planned(self):
        for line in self:
            line.amount_planned = line.currency_id.round(line.qty_planned * line.price_unit_planned) \
                if line.currency_id else line.qty_planned * line.price_unit_planned

    @api.depends('task_id', 'resource_type', 'plan_id.date_start', 'plan_id.lead_days_material',
                 'plan_id.lead_days_contract', 'plan_id.lead_days_production')
    def _compute_date_needed(self):
        start_field = self.env['al.gantt.field.map'].get_map().get('date_start')
        for line in self:
            plan = line.plan_id
            start = line.task_id[start_field] if line.task_id and start_field else False
            start = fields.Date.to_date(start) if start else plan.date_start
            lead = {
                'material': plan.lead_days_material, 'service': plan.lead_days_material,
                'contract': plan.lead_days_contract, 'labor': plan.lead_days_contract,
                'production': plan.lead_days_production,
            }.get(line.resource_type, 0)
            line.date_needed = start - timedelta(days=lead or 0) if start else False

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id and not self.product_uom_id:
            self.product_uom_id = self.product_id.uom_id

    @api.onchange('activity_id')
    def _onchange_activity_id(self):
        activity = self.activity_id
        if activity:
            self.product_uom_id = activity.uom_id
            self.stage = self.stage or activity.stage
            self.product_id = self.product_id or activity.product_id
            if not self.price_unit_planned:
                self.price_unit_planned = activity._get_rate(
                    self.plan_id.project_id, self.partner_id)[0]

    @api.constrains('resource_type', 'activity_id')
    def _check_activity(self):
        for line in self:
            if line.resource_type in ('contract', 'labor') and not line.activity_id:
                raise ValidationError(self.env._(
                    'Las líneas de contrata y de personal propio necesitan su actividad (driver).'))

    @api.constrains('task_id', 'plan_id')
    def _check_task_project(self):
        for line in self:
            if line.task_id and line.task_id.project_id != line.plan_id.project_id:
                raise ValidationError(self.env._(
                    'El nivel %s no pertenece a la obra del plan.', line.task_id.display_name))

    # Líneas editables solo con el plan en borrador (especificación).
    _LOCKED_ALLOWED = {'date_needed', 'line_state'}

    def _check_plan_editable(self, vals=None):
        if self.env.context.get('construction_plan_force'):
            return
        if vals is not None and set(vals) <= self._LOCKED_ALLOWED:
            return
        locked = self.plan_id.filtered(lambda p: p.state != 'draft')
        if locked:
            raise UserError(self.env._(
                'Las líneas de %s no se pueden cambiar: el plan ya no está en borrador.',
                ', '.join(locked.mapped('name'))))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._check_plan_editable()
        return lines

    def write(self, vals):
        self._check_plan_editable(vals)
        return super().write(vals)

    def unlink(self):
        self._check_plan_editable()
        return super().unlink()
