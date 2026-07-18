# -*- coding: utf-8 -*-
from odoo import api, fields, models

MONTHS = [('%02d' % m, '%02d' % m) for m in range(1, 13)]


class L10nPePleCostSales(models.Model):
    """PLE 10.1 — Estado de costo de ventas anual (captura: sin MRP no hay
    datos de producción en Odoo; con contabilidad analítica/MRP futuros se
    podrá poblar automáticamente)."""
    _name = 'l10n_pe.ple.cost.sales'
    _description = 'PLE 10.1 - Costo de ventas anual'
    _order = 'year, id'

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    year = fields.Integer(string='Ejercicio', required=True, index=True)
    initial_finished = fields.Monetary(
        string='Inventario inicial de productos terminados')
    production_cost = fields.Monetary(
        string='Costo de producción de productos terminados')
    final_finished = fields.Monetary(
        string='Inventario final de productos terminados',
        help='En positivo: el TXT lo emite en negativo (campo 4).')
    adjustments = fields.Monetary(string='Ajustes diversos')

    _year_company_uniq = models.Constraint(
        'unique (company_id, year)',
        'Solo puede existir un estado de costo de ventas por ejercicio.')


class L10nPePleCostElement(models.Model):
    """PLE 10.2 — Elementos del costo mensual (una fila por mes dentro del
    archivo anual)."""
    _name = 'l10n_pe.ple.cost.element'
    _description = 'PLE 10.2 - Elementos del costo mensual'
    _order = 'year, month, id'

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    year = fields.Integer(string='Ejercicio', required=True, index=True)
    month = fields.Selection(MONTHS, string='Mes', required=True)
    direct_materials = fields.Monetary(
        string='Materiales y suministros directos')
    direct_labor = fields.Monetary(string='Mano de obra directa')
    other_direct = fields.Monetary(string='Otros costos directos')
    gif_materials = fields.Monetary(string='GIF: materiales indirectos')
    gif_labor = fields.Monetary(string='GIF: mano de obra indirecta')
    other_gif = fields.Monetary(string='Otros gastos indirectos de fabricación')

    ELEMENT_COLUMNS = (
        'direct_materials', 'direct_labor', 'other_direct',
        'gif_materials', 'gif_labor', 'other_gif')

    _month_company_uniq = models.Constraint(
        'unique (company_id, year, month)',
        'Solo puede existir una fila de elementos del costo por mes.')


class L10nPePleCostProduction(models.Model):
    """PLE 10.3 — Costo de producción valorizado anual (una fila por
    proceso productivo)."""
    _name = 'l10n_pe.ple.cost.production'
    _description = 'PLE 10.3 - Costo de producción valorizado anual'
    _order = 'year, id'

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    year = fields.Integer(string='Ejercicio', required=True, index=True)
    process_code = fields.Char(
        string='Código del proceso', size=10, required=True)
    process_name = fields.Char(
        string='Descripción del proceso', size=100, required=True)
    direct_materials = fields.Monetary(
        string='Materiales y suministros directos')
    direct_labor = fields.Monetary(string='Mano de obra directa')
    other_direct = fields.Monetary(string='Otros costos directos')
    gif_materials = fields.Monetary(string='GIF: materiales indirectos')
    gif_labor = fields.Monetary(string='GIF: mano de obra indirecta')
    other_gif = fields.Monetary(string='Otros gastos indirectos de fabricación')
    initial_wip = fields.Monetary(
        string='Inventario inicial de productos en proceso')
    final_wip = fields.Monetary(
        string='Inventario final de productos en proceso',
        help='En positivo: el TXT lo emite en negativo (campo 11).')
    grouping_code = fields.Char(
        string='Código de agrupamiento (T21)', size=1, required=True,
        help='Código de agrupamiento de costos según la tabla 21 del '
             'Anexo 3 de SUNAT.')


class L10nPePleCostCenter(models.Model):
    """PLE 10.4 — Centros de costos del ejercicio (puede precargarse desde
    las cuentas analíticas)."""
    _name = 'l10n_pe.ple.cost.center'
    _description = 'PLE 10.4 - Centro de costos'
    _order = 'year, id'

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    year = fields.Integer(string='Ejercicio', required=True, index=True)
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Cuenta analítica',
        help='Opcional: propone el código y la descripción del centro de '
             'costos desde la cuenta analítica.')
    operation_unit_code = fields.Char(
        string='Código de la unidad de operación', size=24)
    operation_unit_name = fields.Char(
        string='Descripción de la unidad', size=100)
    cost_center_code = fields.Char(
        string='Código del centro de costos', size=24,
        compute='_compute_from_analytic', store=True, readonly=False)
    cost_center_name = fields.Char(
        string='Descripción del centro de costos', size=100,
        compute='_compute_from_analytic', store=True, readonly=False)

    @api.depends('analytic_account_id')
    def _compute_from_analytic(self):
        for record in self:
            account = record.analytic_account_id
            if account:
                record.cost_center_code = (
                    account.code or str(account.id))[:24]
                record.cost_center_name = (account.name or '')[:100]
