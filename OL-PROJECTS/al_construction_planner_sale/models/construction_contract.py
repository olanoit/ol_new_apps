# -*- coding: utf-8 -*-
"""Contrato de obra e hitos de cobro (v1.5, fase 14: M15-05, M15-06, M15-07).

Una obra puede tener varios contratos: suministro en dólares e instalación en
soles, uno por familia (cocinas, closets) o uno por parte del edificio (pisos
pares, una torre). Cada contrato lleva su cliente, su orden de venta, su
moneda, las unidades que cubre y sus condiciones (adelanto, fondo de
garantía, fiel cumplimiento, detracción, periodicidad, penalidades y
documentos que habilitan la valorización).

El cobro al cliente va por hitos: una plantilla (80/15/5, 40/40/15/5…) se
aplica a cada unidad cubierta y da un hito por unidad y precio con su monto
(precio de la unidad × factor de descuento × % del hito) y su avance, que
sale del disparador del hito (etapa terminada, llegada a obra, acta de
entrega o manual). La valorización por hitos lleva lo ganado a las partidas
de la orden de venta: el envío, la conformidad y la factura son los de la
valorización de siempre, y un hito puede cobrarse en dos valorizaciones.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.al_construction_planner.models.common import UNIT_STATE_RANK, stage_selection

CONTRACT_SCOPES = [
    ('supply', 'Suministro'),
    ('installation', 'Instalación'),
    ('both', 'Suministro e instalación'),
    ('service', 'Solo servicio'),
]
VALUATION_FREQUENCIES = [
    ('weekly', 'Semanal'),
    ('biweekly', 'Quincenal'),
    ('monthly', 'Mensual'),
]
MILESTONE_TRIGGERS = [
    ('stage_done', 'Etapa terminada'),
    ('material_arrival', 'Llegada a obra'),
    ('delivery', 'Acta de entrega'),
    ('after_sales', 'Postventa'),
    ('manual', 'Manual'),
]
CONTRACT_STATES = [
    ('draft', 'Borrador'),
    ('active', 'Vigente'),
    ('closed', 'Cerrado'),
    ('cancel', 'Anulado'),
]


class ConstructionMilestoneTemplate(models.Model):
    _name = 'construction.milestone.template'
    _description = 'Plantilla de hitos de cobro'
    _order = 'sequence, name, id'

    name = fields.Char(string='Plantilla', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    line_ids = fields.One2many(
        'construction.milestone.template.line', 'template_id', string='Hitos', copy=True)
    total_pct = fields.Float(string='Total %', compute='_compute_total_pct')
    summary = fields.Char(string='Reparto', compute='_compute_total_pct')

    @api.depends('line_ids.pct')
    def _compute_total_pct(self):
        for template in self:
            pcts = template.line_ids.sorted('sequence').mapped('pct')
            template.total_pct = sum(pcts)
            template.summary = ' / '.join('%g' % pct for pct in pcts)

    @api.constrains('line_ids')
    def _check_total(self):
        for template in self:
            if template.line_ids and round(template.total_pct, 2) != 100:
                raise ValidationError(self.env._(
                    'Los hitos de la plantilla %(template)s suman %(total)s %%: deben sumar 100 %%.',
                    template=template.name, total=round(template.total_pct, 2)))


class ConstructionMilestoneTemplateLine(models.Model):
    _name = 'construction.milestone.template.line'
    _description = 'Hito de la plantilla de cobro'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one(
        'construction.milestone.template', string='Plantilla', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(string='Orden', default=10)
    name = fields.Char(string='Hito', required=True, translate=True)
    pct = fields.Float(string='%', required=True, digits=(16, 2))
    trigger = fields.Selection(
        MILESTONE_TRIGGERS, string='Disparador', required=True, default='stage_done',
        help='Etapa terminada: el avance de esa etapa en la unidad. Llegada a obra: módulos en '
             'obra o más allá. Acta de entrega: módulos entregados. Postventa y manual: se '
             'escribe el avance en el hito de cada unidad.')
    stage = fields.Selection(stage_selection, string='Etapa', help='Solo con «Etapa terminada».')

    @api.constrains('trigger', 'stage')
    def _check_stage(self):
        for line in self:
            if line.trigger == 'stage_done' and not line.stage:
                raise ValidationError(self.env._(
                    'El hito %s se dispara con una etapa: indique cuál.', line.name))


class ConstructionContract(models.Model):
    _name = 'construction.contract'
    _description = 'Contrato de obra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'project_id, name, id'
    _check_company_auto = True

    name = fields.Char(string='Contrato', required=True, tracking=True)
    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, index=True, check_company=True,
        domain=[('is_construction_site', '=', True)], tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True, store=True,
        compute='_compute_company_id', precompute=True, readonly=False,
        default=lambda self: self.env.company)
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True, check_company=True, tracking=True)
    sale_order_id = fields.Many2one(
        'sale.order', string='Orden de venta', check_company=True, tracking=True,
        domain="[('partner_id', 'child_of', partner_id)]",
        help='Una orden por contrato, con una línea por partida (D23): la valorización factura '
             'desde ella.')
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True,
        default=lambda self: self.env.company.currency_id, tracking=True)
    scope = fields.Selection(
        CONTRACT_SCOPES, string='Alcance', required=True, default='both', tracking=True)
    state = fields.Selection(
        CONTRACT_STATES, string='Estado', required=True, default='draft', tracking=True,
        copy=False)
    typology_ids = fields.Many2many(
        'construction.typology', string='Tipologías', check_company=True,
        domain="[('project_id', '=', project_id)]",
        help='Las que cubre el contrato (p. ej. solo cocinas). Vacío: todas.')
    task_ids = fields.Many2many(
        'project.task', 'construction_contract_task_rel', 'contract_id', 'task_id',
        string='Unidades cubiertas', check_company=True,
        domain="[('project_id', '=', project_id), ('construction_level', '=', 'apartment')]",
        help='Unidades del contrato: pisos pares o impares, una torre, una lista. Use '
             '«Marcar unidades».')
    unit_count = fields.Integer(string='Unidades', compute='_compute_unit_count')
    price_line_ids = fields.One2many(
        'construction.contract.price', 'contract_id', string='Precios por tipología', copy=True)
    milestone_template_id = fields.Many2one(
        'construction.milestone.template', string='Hitos de cobro', tracking=True,
        help='Plantilla del contrato; cada precio por tipología puede llevar la suya (una por '
             'familia).')
    discount_factor = fields.Float(
        string='Factor de descuento', default=1.0, digits=(16, 4), tracking=True,
        help='Multiplica el precio de cada unidad (p. ej. 0.95 por un descuento del 5 %).')
    milestone_ids = fields.One2many(
        'construction.unit.milestone', 'contract_id', string='Hitos por unidad')
    milestone_count = fields.Integer(string='Hitos', compute='_compute_unit_count')
    # Condiciones (M15-07).
    advance_pct = fields.Float(string='Adelanto %', digits=(16, 2), tracking=True)
    advance_bond = fields.Boolean(string='Carta fianza del adelanto', tracking=True)
    guarantee_pct = fields.Float(string='Fondo de garantía %', digits=(16, 2), tracking=True)
    guarantee_base = fields.Selection(
        [('with_tax', 'Con IGV'), ('without_tax', 'Sin IGV')], string='Base del fondo',
        default='without_tax', tracking=True)
    performance_bond_pct = fields.Float(string='Fiel cumplimiento %', digits=(16, 2), tracking=True)
    detraction_pct = fields.Float(string='Detracción %', digits=(16, 2), tracking=True)
    valuation_frequency = fields.Selection(
        VALUATION_FREQUENCIES, string='Valorización', default='weekly', required=True,
        tracking=True)
    penalty_daily_pct = fields.Float(
        string='Penalidad diaria %', digits=(16, 3), tracking=True,
        help='Por día de atraso sobre el monto del contrato (p. ej. 0.5).')
    penalty_cap_pct = fields.Float(
        string='Tope de la penalidad %', digits=(16, 2), tracking=True,
        help='Penalidad máxima sobre el monto del contrato (p. ej. 10).')
    document_ids = fields.One2many(
        'construction.contract.document', 'contract_id', string='Documentos', copy=True,
        help='Dossier de calidad, anexo PLAFT…: sin el documento recibido no se envía la '
             'valorización que lo exige.')
    term_conflicts = fields.Text(
        string='Diferencias entre documentos',
        help='Lo que dicen distinto la cotización, la orden y el contrato (adelanto, hitos, '
             'plazos): queda escrito y avisa en el contrato.')
    amount_total = fields.Monetary(
        string='Monto por hitos', compute='_compute_amounts', currency_field='currency_id')
    amount_earned = fields.Monetary(
        string='Ganado a hoy', compute='_compute_amounts', currency_field='currency_id')
    amount_billed = fields.Monetary(
        string='Cobrado', compute='_compute_amounts', currency_field='currency_id')
    valuation_ids = fields.One2many('construction.valuation', 'contract_id', string='Valorizaciones')

    @api.depends('project_id')
    def _compute_company_id(self):
        for contract in self:
            contract.company_id = contract.project_id.company_id or contract.company_id \
                or self.env.company

    @api.depends('task_ids', 'milestone_ids')
    def _compute_unit_count(self):
        for contract in self:
            contract.unit_count = len(contract.task_ids)
            contract.milestone_count = len(contract.milestone_ids)

    @api.depends('milestone_ids.amount', 'milestone_ids.progress_pct', 'milestone_ids.billed_pct')
    def _compute_amounts(self):
        for contract in self:
            milestones = contract.milestone_ids
            contract.amount_total = sum(milestones.mapped('amount'))
            contract.amount_earned = sum(m.amount * m.progress_pct / 100 for m in milestones)
            contract.amount_billed = sum(m.amount * m.billed_pct / 100 for m in milestones)

    @api.constrains('discount_factor', 'advance_pct', 'guarantee_pct', 'penalty_cap_pct')
    def _check_conditions(self):
        for contract in self:
            if contract.discount_factor <= 0:
                raise ValidationError(self.env._('El factor de descuento debe ser mayor que cero.'))
            for field in ('advance_pct', 'guarantee_pct', 'penalty_cap_pct'):
                if not 0 <= contract[field] <= 100:
                    raise ValidationError(self.env._(
                        '%s debe estar entre 0 y 100.', contract._fields[field].string))

    # ------------------------------------------------------------------
    # Unidades e hitos
    # ------------------------------------------------------------------
    def _covered_units(self):
        self.ensure_one()
        if self.task_ids:
            return self.task_ids
        return self.env['project.task'].search([
            ('project_id', '=', self.project_id.id), ('construction_level', '=', 'apartment')])

    def _unit_spaces(self, unit):
        spaces = self.env['project.task'].search([
            ('construction_apartment_task_id', '=', unit.id), ('construction_level', '=', 'space')])
        if self.typology_ids:
            spaces = spaces.filtered(lambda s: s.construction_typology_id in self.typology_ids)
        return spaces

    def action_generate_milestones(self):
        """Hitos por unidad: por cada unidad cubierta y cada precio de sus
        tipologías, un hito por línea de la plantilla con su monto. Los hitos
        ya cobrados (aunque sea en parte) no se tocan; los demás se rehacen."""
        Milestone = self.env['construction.unit.milestone']
        for contract in self:
            prices = {price.typology_id: price for price in contract.price_line_ids}
            if not prices:
                raise UserError(self.env._(
                    'El contrato %s no tiene precios por tipología.', contract.display_name))
            keep = contract.milestone_ids.filtered(lambda m: m.billed_pct)
            (contract.milestone_ids - keep).unlink()
            existing = {(m.task_id.id, m.price_line_id.id, m.template_line_id.id) for m in keep}
            vals_list = []
            for unit in contract._covered_units():
                count = {}
                for space in contract._unit_spaces(unit):
                    price = prices.get(space.construction_typology_id)
                    if price:
                        count[price] = count.get(price, 0) + 1
                for price, qty in count.items():
                    template = price.milestone_template_id or contract.milestone_template_id
                    if not template:
                        raise UserError(self.env._(
                            'El contrato %s no tiene plantilla de hitos de cobro.',
                            contract.display_name))
                    for line in template.line_ids:
                        if (unit.id, price.id, line.id) in existing:
                            continue
                        vals_list.append({
                            'contract_id': contract.id, 'task_id': unit.id,
                            'price_line_id': price.id, 'template_line_id': line.id,
                            'amount': contract.currency_id.round(
                                price.unit_price * qty * contract.discount_factor * line.pct / 100),
                        })
            Milestone.create(vals_list)
        return True

    def action_open_unit_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Marcar unidades'),
            'res_model': 'construction.contract.unit.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_contract_id': self.id},
        }

    def action_activate(self):
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_view_milestones(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Hitos de %s', self.display_name),
            'res_model': 'construction.unit.milestone',
            'view_mode': 'list,pivot',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id, 'search_default_group_template': 1},
        }

    def action_prepare_valuation(self):
        """Valorización por hitos al día de hoy (P-20 con hitos)."""
        self.ensure_one()
        valuation = self.env['construction.valuation']._create_from_milestones(
            self, fields.Date.context_today(self))
        return {
            'type': 'ir.actions.act_window', 'res_model': 'construction.valuation',
            'res_id': valuation.id, 'view_mode': 'form',
        }

    def _missing_documents(self):
        """Documentos exigidos que aún no se reciben."""
        self.ensure_one()
        return self.document_ids.filtered(lambda d: d.required and not d.received)


class ConstructionContractPrice(models.Model):
    """Precio de una tipología en el contrato (y la partida de la orden de
    venta donde se cobra)."""
    _name = 'construction.contract.price'
    _description = 'Precio por tipología del contrato'
    _order = 'contract_id, sequence, id'
    _check_company_auto = True

    contract_id = fields.Many2one(
        'construction.contract', string='Contrato', required=True, ondelete='cascade', index=True,
        check_company=True)
    company_id = fields.Many2one(related='contract_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='contract_id.currency_id', string='Moneda')
    sequence = fields.Integer(default=10)
    typology_id = fields.Many2one(
        'construction.typology', string='Tipología', required=True, check_company=True,
        domain="[('project_id', '=', parent.project_id)]")
    unit_price = fields.Monetary(string='Precio por ambiente', currency_field='currency_id')
    sale_line_id = fields.Many2one(
        'sale.order.line', string='Partida', check_company=True,
        domain="[('order_id', '=', parent.sale_order_id), ('display_type', '=', False)]",
        help='Línea de la orden de venta donde se valoriza y factura.')
    milestone_template_id = fields.Many2one(
        'construction.milestone.template', string='Hitos de cobro',
        help='Vacía: la del contrato. Una plantilla distinta por familia (cocinas 80/15/5, '
             'closets 90/10).')


class ConstructionContractDocument(models.Model):
    _name = 'construction.contract.document'
    _description = 'Documento del contrato'
    _order = 'contract_id, sequence, id'

    contract_id = fields.Many2one(
        'construction.contract', string='Contrato', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='contract_id.company_id', store=True, index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Documento', required=True, help='Dossier de calidad, anexo PLAFT…')
    required = fields.Boolean(
        string='Habilita la valorización', default=True,
        help='Sin este documento recibido no se envía la valorización.')
    received = fields.Boolean(string='Recibido')
    date_received = fields.Date(string='Fecha de recepción')
    attachment_ids = fields.Many2many('ir.attachment', string='Archivo')
    source = fields.Char(string='De dónde sale', help='Cláusula o documento que lo exige.')


class ConstructionUnitMilestone(models.Model):
    """Hito de cobro de una unidad (M15-06)."""
    _name = 'construction.unit.milestone'
    _description = 'Hito de cobro por unidad'
    _order = 'contract_id, task_id, template_line_id'
    _check_company_auto = True

    contract_id = fields.Many2one(
        'construction.contract', string='Contrato', required=True, ondelete='cascade', index=True,
        check_company=True)
    company_id = fields.Many2one(related='contract_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='contract_id.currency_id', string='Moneda')
    task_id = fields.Many2one(
        'project.task', string='Unidad', required=True, index=True, check_company=True)
    price_line_id = fields.Many2one(
        'construction.contract.price', string='Precio', required=True, ondelete='cascade',
        index=True)
    typology_id = fields.Many2one(related='price_line_id.typology_id', store=True, index=True)
    sale_line_id = fields.Many2one(related='price_line_id.sale_line_id', store=True, index=True)
    template_line_id = fields.Many2one(
        'construction.milestone.template.line', string='Hito', required=True, index=True)
    trigger = fields.Selection(related='template_line_id.trigger', string='Disparador')
    pct = fields.Float(related='template_line_id.pct', string='%')
    amount = fields.Monetary(string='Monto', currency_field='currency_id')
    manual_pct = fields.Float(
        string='Avance manual %', digits=(16, 2),
        help='Para hitos de postventa o manuales: el avance que se cobra.')
    progress_pct = fields.Float(
        string='Avance %', compute='_compute_progress_pct', digits=(16, 2),
        help='Etapa terminada: avance valorizado de esa etapa en la unidad. Llegada a obra y '
             'acta de entrega: módulos que llegaron o se entregaron.')
    billed_pct = fields.Float(
        string='Cobrado %', digits=(16, 2), readonly=True, copy=False,
        help='Lo cobrado en valorizaciones confirmadas: un hito puede cobrarse en dos.')

    @api.depends('trigger', 'manual_pct', 'task_id')
    def _compute_progress_pct(self):
        Plan = self.env['construction.resource.plan']
        Task = self.env['project.task']
        for milestone in self:
            line = milestone.template_line_id
            unit = milestone.task_id
            if line.trigger in ('after_sales', 'manual'):
                milestone.progress_pct = milestone.manual_pct
                continue
            if line.trigger == 'stage_done':
                plan = unit.project_id._construction_current_plan()
                domain = [('plan_id', '=', plan.id), ('apartment_task_id', '=', unit.id),
                          ('stage', '=', line.stage)]
                if milestone.typology_id:
                    domain.append(('space_task_id.construction_typology_id', '=',
                                   milestone.typology_id.id))
                amounts = Plan._progress_amounts(domain)
                milestone.progress_pct = round(Plan._progress_ratio(amounts, False) * 100, 2)
                continue
            modules = Task.search([('construction_apartment_task_id', '=', unit.id),
                                   ('construction_level', '=', 'module')])
            if milestone.typology_id:
                modules = modules.filtered(
                    lambda m: m.construction_space_task_id.construction_typology_id
                    == milestone.typology_id)
            target = 'on_site' if line.trigger == 'material_arrival' else 'delivered'
            done = modules.filtered(lambda m: UNIT_STATE_RANK.get(m.construction_unit_state, 0)
                                    >= UNIT_STATE_RANK[target])
            milestone.progress_pct = round(len(done) / len(modules) * 100, 2) if modules else 0.0
