# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_pe_cash_advance_account_id = fields.Many2one(
        'account.account', string='Cuenta de entregas a rendir', check_company=True,
        help='Cuenta por cobrar al responsable (PCGE 1413 Personal - Entregas a rendir '
             'cuenta). Vacía: la 1413 del plan contable.')
    l10n_pe_petty_cash_account_id = fields.Many2one(
        'account.account', string='Cuenta de caja chica', check_company=True,
        help='Cuenta del fondo fijo a cargo del custodio. Debe ser conciliable (p. ej. una '
             'subcuenta de la 1413 o de la 1691). Vacía: la de entregas a rendir.')
    l10n_pe_cash_settlement_journal_id = fields.Many2one(
        'account.journal', string='Diario de rendiciones', check_company=True,
        domain="[('type', '=', 'general')]",
        help='Diario de los asientos de rendición. Vacío: el primer diario de operaciones '
             'varias.')
    l10n_pe_mobility_account_id = fields.Many2one(
        'account.account', string='Cuenta de gastos de movilidad', check_company=True,
        help='Gasto de las planillas de movilidad. Vacía: la 63112 (transporte de pasajeros) '
             'del plan contable.')
    l10n_pe_rmv_amount = fields.Monetary(
        string='Remuneración mínima vital', currency_field='currency_id', default=1130.0,
        help='RMV vigente: el tope diario de la planilla de movilidad es un porcentaje de ella '
             '(D.S. 006-2024-TR: S/ 1 130 desde el 1 de enero de 2025).')
    l10n_pe_mobility_limit_pct = fields.Float(
        string='Tope diario de movilidad (% de la RMV)', default=4.0,
        help='Art. 37 inciso a1) del TUO de la Ley del Impuesto a la Renta: los gastos de '
             'movilidad sustentados con planilla no pueden superar por día y por trabajador el '
             '4 % de la RMV.')

    def _l10n_pe_cash_fund_account(self, fund_type):
        """Cuenta del fondo según su tipo, con la 1413 del PCGE de respaldo."""
        self.ensure_one()
        default = self.l10n_pe_cash_advance_account_id or self.env.ref(
            'account.%s_chart1413' % self.id, raise_if_not_found=False) or self.env['account.account']
        if fund_type == 'petty_cash':
            return self.l10n_pe_petty_cash_account_id or default
        return default

    def _l10n_pe_cash_settlement_journal(self):
        self.ensure_one()
        return self.l10n_pe_cash_settlement_journal_id or self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self),
            ('type', '=', 'general')], limit=1)

    def _l10n_pe_mobility_account(self):
        self.ensure_one()
        return self.l10n_pe_mobility_account_id or self.env.ref(
            'account.%s_chart63112' % self.id, raise_if_not_found=False) or self.env['account.account']

    def _l10n_pe_mobility_daily_limit(self):
        self.ensure_one()
        return self.currency_id.round(self.l10n_pe_rmv_amount * self.l10n_pe_mobility_limit_pct / 100.0)
