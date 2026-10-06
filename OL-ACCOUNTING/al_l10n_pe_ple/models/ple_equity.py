# -*- coding: utf-8 -*-
from odoo import api, fields, models


class L10nPePleEquity(models.Model):
    """Captura del PLE 3.19 — Estado de cambios en el patrimonio neto.
    Una fila por rubro (tabla 34) con las doce columnas monetarias que
    exige el Anexo 2; se prepara a partir del EEFF aprobado."""
    _name = 'l10n_pe.ple.equity'
    _description = 'PLE 3.19 - Cambios en el patrimonio neto'
    _order = 'date, id'

    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    date = fields.Date(
        string='Fecha del EEFF', required=True, index=True,
        help='Fecha de los estados financieros (normalmente 31/12); el '
             'wizard exporta las filas cuya fecha coincide con la fecha de '
             'balance elegida.')
    rubric_id = fields.Many2one(
        'l10n_pe_reports_lib.financial.rubric', string='Rubro EEFF (T34)',
        required=True,
        help='Rubro del estado de cambios en el patrimonio neto según la '
             'tabla 34 de SUNAT (catálogo = sector del rubro).')
    catalog_code = fields.Char(
        string='Catálogo (T22)', compute='_compute_catalog_code',
        store=True, readonly=False, size=2,
        help='Código del catálogo de EEFF (tabla 22); se propone el sector '
             'del rubro elegido.')
    capital = fields.Monetary(string='Capital')
    investment_shares = fields.Monetary(string='Acciones de inversión')
    additional_capital = fields.Monetary(string='Capital adicional')
    unrealized_results = fields.Monetary(string='Resultados no realizados')
    legal_reserves = fields.Monetary(string='Reservas legales')
    other_reserves = fields.Monetary(string='Otras reservas')
    retained_earnings = fields.Monetary(string='Resultados acumulados')
    conversion_diff = fields.Monetary(string='Diferencia de conversión')
    equity_adjustments = fields.Monetary(string='Ajustes al patrimonio')
    net_result = fields.Monetary(string='Resultado neto del ejercicio')
    revaluation_surplus = fields.Monetary(string='Excedente de revaluación')
    period_result = fields.Monetary(string='Resultado del ejercicio')

    EQUITY_COLUMNS = (
        'capital', 'investment_shares', 'additional_capital',
        'unrealized_results', 'legal_reserves', 'other_reserves',
        'retained_earnings', 'conversion_diff', 'equity_adjustments',
        'net_result', 'revaluation_surplus', 'period_result')

    @api.depends('rubric_id')
    def _compute_catalog_code(self):
        for record in self:
            record.catalog_code = (
                record.rubric_id.sector or record.catalog_code or '01')
