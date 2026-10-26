# -*- coding: utf-8 -*-
from odoo import fields, models

ACCOUNT_KINDS = [
    ('checking', 'Cuenta corriente'),
    ('savings', 'Cuenta de ahorros'),
    ('detraction', 'Cuenta de detracciones (Banco de la Nación)'),
    ('collection', 'Cuenta recaudadora'),
    ('cash', 'Caja'),
    ('other', 'Otra'),
]


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # Los fondos restringidos (detracciones del BN) son los que el flujo de caja
    # ya marca como no disponibles: ``l10n_pe_forecast_exclude``.

    l10n_pe_treasury_kind = fields.Selection(
        ACCOUNT_KINDS, string='Tipo de cuenta',
        help='Clasifica la cuenta en la posición de tesorería.')
    l10n_pe_treasury_min_balance = fields.Monetary(
        string='Saldo mínimo', currency_field='l10n_pe_treasury_currency_id',
        help='Saldo que la empresa mantiene siempre en la cuenta (encaje propio, exigencia del '
             'banco): se descuenta del disponible.')
    l10n_pe_treasury_overdraft = fields.Monetary(
        string='Sobregiro autorizado', currency_field='l10n_pe_treasury_currency_id',
        help='Sobregiro que el banco autoriza en la cuenta: se suma al disponible.')
    l10n_pe_treasury_user_id = fields.Many2one(
        'res.users', string='Responsable de tesorería',
        help='Quien opera la cuenta; recibe los avisos de la posición.')
    l10n_pe_treasury_currency_id = fields.Many2one(
        'res.currency', string='Moneda de la cuenta', compute='_compute_l10n_pe_treasury_currency_id')

    def _compute_l10n_pe_treasury_currency_id(self):
        for journal in self:
            journal.l10n_pe_treasury_currency_id = journal.currency_id or journal.company_id.currency_id

    def _l10n_pe_treasury_currency(self):
        self.ensure_one()
        return self.currency_id or self.company_id.currency_id

    def _l10n_pe_treasury_outstanding_account(self, direction):
        """Cuenta en la que un movimiento de banco registrado desde tesorería
        (cuota de préstamo, comisión de carta fianza) espera al extracto: la de
        pagos (``outbound``) o cobros (``inbound``) pendientes del primer método
        del diario; sin ella, la cuenta del banco."""
        self.ensure_one()
        lines = self.outbound_payment_method_line_ids if direction == 'outbound' \
            else self.inbound_payment_method_line_ids
        account = lines.payment_account_id[:1]
        if not account:
            ref = 'account_journal_payment_credit_account_id' if direction == 'outbound' \
                else 'account_journal_payment_debit_account_id'
            account = self.env['account.chart.template'].with_context(
                allowed_company_ids=self.company_id.root_id.ids).ref(ref, raise_if_not_found=False) \
                or self.env['account.account']
        return account or self.default_account_id
