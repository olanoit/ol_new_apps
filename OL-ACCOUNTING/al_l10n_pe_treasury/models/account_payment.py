# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

#: Tabla 1 de SUNAT: efectivo (008 sin obligación de medio de pago, 009 los demás casos).
CASH_PAYMENT_CODES = ('008', '009')


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_pe_treasury_transfer_id = fields.Many2one(
        'l10n_pe.treasury.transfer', string='Transferencia de tesorería', readonly=True, copy=False,
        index='btree_not_null', check_company=True)
    l10n_pe_treasury_plan_id = fields.Many2one(
        'l10n_pe.treasury.payment.plan', string='Programación de pagos', readonly=True, copy=False,
        index='btree_not_null', check_company=True)
    l10n_pe_bancarization_warning = fields.Char(
        string='Aviso de bancarización', compute='_compute_l10n_pe_bancarization_warning')

    def _l10n_pe_itf_applies(self):
        # Una transferencia entre cuentas propias no está gravada (lo excluye
        # al_l10n_pe_itf), salvo que tesorería marque que el banco lo cobró.
        self.ensure_one()
        transfer = self.l10n_pe_treasury_transfer_id
        if transfer:
            charged = transfer.itf_from if self.payment_type == 'outbound' else transfer.itf_to
            return bool(charged and self.journal_id.l10n_pe_itf_applies and self.journal_id.type == 'bank')
        return super()._l10n_pe_itf_applies()

    # ------------------------------------------------------------------
    # Bancarización (art. 4 del TUO de la Ley 28194; montos del DL 1529)
    # ------------------------------------------------------------------
    def _l10n_pe_is_cash_payment(self):
        self.ensure_one()
        # El medio de pago SUNAT manda; sin él, un diario de caja es efectivo.
        # El 008 («sin obligación de medio de pago») tampoco vale desde el umbral.
        if self.pe_payment_method_id:
            return self.pe_payment_method_id.code in CASH_PAYMENT_CODES
        return self.journal_id.type == 'cash'

    def _l10n_pe_bancarization_threshold(self):
        """Monto desde el que el pago debe hacerse con medio de pago, en la moneda
        del pago (S/ o US$; otras monedas, el equivalente de los US$)."""
        self.ensure_one()
        company = self.company_id.root_id
        currency = self.currency_id
        if currency == company.currency_id:
            return company.l10n_pe_bancarization_amount_pen
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        if currency == usd or not usd:
            return company.l10n_pe_bancarization_amount_usd
        return usd._convert(company.l10n_pe_bancarization_amount_usd, currency, company,
                            self.date or fields.Date.context_today(self))

    def _l10n_pe_bancarization_breach(self):
        self.ensure_one()
        if self.company_id.root_id.l10n_pe_bancarization_mode == 'none' or self.l10n_pe_treasury_transfer_id:
            return False
        if self.partner_id == self.company_id.partner_id or not self._l10n_pe_is_cash_payment():
            return False
        return self.currency_id.compare_amounts(self.amount, self._l10n_pe_bancarization_threshold()) >= 0

    @api.depends('amount', 'currency_id', 'journal_id', 'pe_payment_method_id', 'date', 'partner_id')
    def _compute_l10n_pe_bancarization_warning(self):
        for payment in self:
            payment.l10n_pe_bancarization_warning = self.env._(
                'Pago en efectivo desde %(amount)s %(currency)s: la ley obliga a usar medios de pago '
                '(depósito, transferencia, cheque…). Sin ellos no se deduce el gasto ni el crédito fiscal.',
                amount=payment._l10n_pe_bancarization_threshold(), currency=payment.currency_id.name,
            ) if payment.currency_id and payment._l10n_pe_bancarization_breach() else False

    def action_post(self):
        for payment in self:
            if payment._l10n_pe_bancarization_breach() and \
                    payment.company_id.root_id.l10n_pe_bancarization_mode == 'block':
                raise UserError(payment.l10n_pe_bancarization_warning)
        res = super().action_post()
        for payment in self.filtered('l10n_pe_bancarization_warning'):
            payment.message_post(body=payment.l10n_pe_bancarization_warning)
        return res
