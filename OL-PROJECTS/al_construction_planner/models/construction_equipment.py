# -*- coding: utf-8 -*-
"""Equipos propios con tarifa interna (requerimiento CREVAL v1.0, 6.1).

La tarifa por hora-máquina sale del valor de reposición: depreciación,
interés, seguro y almacén, y mantenimiento por año entre las horas útiles
del año, más el combustible por hora. Es el costo del equipo en la receta y
en el plan, y cada uso en obra se carga a la cuenta analítica de la obra."""
from odoo import api, fields, models
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    construction_equipment_owned = fields.Boolean(
        string='Equipo propio',
        help='Equipo de la empresa (mezcladora, vibradora, andamio): su costo en la receta y en '
             'el plan es la tarifa interna y su uso se carga a la obra.')
    construction_replacement_value = fields.Float(
        string='Valor de reposición', digits='Product Price')
    construction_life_years = fields.Float(string='Vida útil (años)', default=5.0)
    construction_hours_year = fields.Float(string='Horas útiles por año', default=2000.0)
    construction_interest_pct = fields.Float(
        string='Interés, seguro y almacén (% anual)', digits=(16, 2))
    construction_maintenance_pct = fields.Float(
        string='Mantenimiento (% anual)', digits=(16, 2))
    construction_fuel_hour = fields.Float(
        string='Combustible por hora', digits='Product Price')
    construction_internal_rate = fields.Float(
        string='Tarifa interna por hora', digits='Product Price',
        compute='_compute_construction_internal_rate', store=True,
        help='(Valor ÷ vida útil + valor × (interés + mantenimiento) %) ÷ horas por año + '
             'combustible por hora.')

    @api.depends('construction_equipment_owned', 'construction_replacement_value',
                 'construction_life_years', 'construction_hours_year',
                 'construction_interest_pct', 'construction_maintenance_pct',
                 'construction_fuel_hour')
    def _compute_construction_internal_rate(self):
        for product in self:
            if not product.construction_equipment_owned or not product.construction_hours_year:
                product.construction_internal_rate = 0.0
                continue
            value = product.construction_replacement_value
            yearly = (value / product.construction_life_years
                      if product.construction_life_years else 0.0) \
                + value * (product.construction_interest_pct
                           + product.construction_maintenance_pct) / 100.0
            product.construction_internal_rate = \
                yearly / product.construction_hours_year + product.construction_fuel_hour


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    equipment_usage_ids = fields.One2many(
        'construction.equipment.usage', 'plan_line_id', string='Uso del equipo')
    is_owned_equipment = fields.Boolean(
        related='product_id.construction_equipment_owned', string='Equipo propio')

    def _construction_equipment_used(self):
        self.ensure_one()
        return sum(self.equipment_usage_ids.mapped('qty'))

    def _get_line_execution(self):
        """Equipo propio: el real es su uso registrado a la tarifa interna."""
        result = super()._get_line_execution()
        for line in self.filtered('is_owned_equipment'):
            committed, _actual = result.get(line, (0.0, 0.0))
            actual = sum(line.equipment_usage_ids.mapped('amount'))
            result[line] = (committed, line.currency_id.round(actual) if line.currency_id
                            else actual)
        return result

    @api.depends('equipment_usage_ids.qty')
    def _compute_progress_qty(self):
        super()._compute_progress_qty()
        for line in self.filtered('is_owned_equipment'):
            line.qty_executed = line._construction_equipment_used()
            line.progress_pct = min(line.qty_executed / line.qty_planned, 1.0) \
                if line.qty_planned else 0.0


class ConstructionEquipmentUsage(models.Model):
    """Uso de un equipo propio en la obra: un cargo interno a la cuenta
    analítica de la obra por las horas (o días) de uso a la tarifa interna."""
    _name = 'construction.equipment.usage'
    _description = 'Uso de equipo propio en la obra'
    _order = 'date desc, id desc'
    _check_company_auto = True

    plan_line_id = fields.Many2one(
        'construction.resource.plan.line', string='Línea del plan', required=True,
        ondelete='cascade', index=True, check_company=True,
        domain="[('is_owned_equipment', '=', True)]")
    company_id = fields.Many2one(related='plan_line_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='plan_line_id.currency_id')
    product_id = fields.Many2one(related='plan_line_id.product_id', string='Equipo')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    qty = fields.Float(string='Uso', digits='Product Unit', required=True,
                       help='En la unidad de la línea del plan (horas o días).')
    rate = fields.Float(string='Tarifa', digits='Product Price', required=True,
                        compute='_compute_rate', store=True, readonly=False, precompute=True)
    amount = fields.Monetary(string='Cargo', compute='_compute_amount', store=True,
                             precompute=True)
    analytic_line_id = fields.Many2one('account.analytic.line', string='Línea analítica',
                                       readonly=True, copy=False)
    note = fields.Char(string='Nota')

    _qty_positive = models.Constraint('CHECK(qty > 0)', 'El uso del equipo debe ser mayor que cero.')

    @api.depends('plan_line_id')
    def _compute_rate(self):
        for usage in self:
            line = usage.plan_line_id
            usage.rate = line.price_unit_planned or line.product_id.construction_internal_rate

    @api.depends('qty', 'rate')
    def _compute_amount(self):
        for usage in self:
            amount = usage.qty * usage.rate
            usage.amount = usage.currency_id.round(amount) if usage.currency_id else amount

    @api.model_create_multi
    def create(self, vals_list):
        usages = super().create(vals_list)
        usages._construction_charge()
        return usages

    def _construction_charge(self):
        """Cargo interno en la cuenta analítica de la obra."""
        for usage in self:
            project = usage.plan_line_id.plan_id.project_id
            account = project.account_id
            if not account:
                raise UserError(self.env._(
                    'La obra %s no tiene cuenta analítica para cargar el uso del equipo.',
                    project.display_name))
            # sudo: quien registra el uso no siempre escribe líneas
            # analíticas; solo se crea el cargo de este uso.
            line_sudo = self.env['account.analytic.line'].sudo().create({
                'name': self.env._('Uso de %(equipment)s: %(qty)s', equipment=usage.product_id.display_name,
                                   qty=round(usage.qty, 2)),
                'date': usage.date,
                'account_id': account.id,
                'amount': -usage.amount,
                'unit_amount': usage.qty,
                'product_uom_id': usage.plan_line_id.product_uom_id.id,
                'company_id': usage.company_id.id or project.company_id.id or self.env.company.id,
            })
            usage.analytic_line_id = line_sudo.id
        self.plan_line_id._refresh_control()

    def unlink(self):
        lines = self.plan_line_id
        # sudo: el cargo lo creó el sistema con el uso.
        self.analytic_line_id.sudo().unlink()
        res = super().unlink()
        lines._refresh_control()
        return res
