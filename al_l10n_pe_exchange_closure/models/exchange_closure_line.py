# -*- coding: utf-8 -*-
"""Detalle del cierre: un renglón por cuenta (o por cuenta y socio).

Los importes se graban al calcular, no se recomputan: son la foto de los
saldos a la fecha de cierre y deben coincidir exactamente con el asiento
generado, aunque después se publiquen apuntes con fecha anterior.
"""
from odoo import _, fields, models


class L10nPeExchangeClosureLine(models.Model):
    _name = 'l10n_pe.exchange.closure.line'
    _inherit = ['analytic.mixin']
    _description = 'Detalle del cierre de tipo de cambio'
    _order = 'account_id, partner_id, id'
    _check_company_auto = True

    closure_id = fields.Many2one(
        'l10n_pe.exchange.closure', string='Cierre', required=True,
        ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='closure_id.company_id', store=True)
    company_currency_id = fields.Many2one(
        related='closure_id.company_currency_id')
    currency_id = fields.Many2one(related='closure_id.currency_id')
    account_id = fields.Many2one(
        'account.account', string='Cuenta', required=True,
        ondelete='restrict', check_company=True)
    partner_id = fields.Many2one('res.partner', string='Socio')

    amount_currency = fields.Monetary(
        string='Saldo en M.E.', currency_field='currency_id',
        help='Saldo acumulado en moneda extranjera a la fecha de cierre.')
    balance = fields.Monetary(
        string='Saldo contable', currency_field='company_currency_id',
        help='Saldo acumulado en moneda nacional según los apuntes '
             'publicados, incluidos los ajustes de cierres anteriores.')
    rate = fields.Float(string='T.C.', digits='Dual_Currency_TRM')
    rate_type = fields.Selection(
        selection=[('purchase', 'Compra'), ('sale', 'Venta')],
        string='Tipo de T.C.')
    balance_adjusted = fields.Monetary(
        string='Saldo revaluado', currency_field='company_currency_id',
        help='Saldo en M.E. convertido al tipo de cambio de cierre.')
    adjustment = fields.Monetary(
        string='Ajuste', currency_field='company_currency_id',
        help='Saldo revaluado menos saldo contable. Positivo se carga a la '
             'cuenta (ganancia en activos, pérdida en pasivos).')
    # `analytic_distribution` viene de analytic.mixin. Se graba al calcular y
    # el usuario puede corregirla antes de contabilizar: la lleva la línea de
    # resultado (676/776), no la de balance.
    analytic_distribution = fields.Json(
        string='Distribución analítica',
        help='Analítica que recibirá la ganancia o pérdida de este renglón. '
             'Editable mientras el cierre esté calculado.')

    def action_open_move_lines(self):
        """Abre los apuntes que componen el saldo de este renglón."""
        self.ensure_one()
        domain = self.closure_id._get_aml_domain(
            self.account_id.l10n_pe_exchange_closing)
        domain += [('account_id', '=', self.account_id.id)]
        if self.account_id.l10n_pe_exchange_closing == 'detail':
            domain += [('partner_id', '=', self.partner_id.id or False)]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Apuntes de %s', self.account_id.display_name),
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'create': False},
        }
