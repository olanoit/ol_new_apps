# -*- coding: utf-8 -*-
from odoo import api, models


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    @api.model_create_multi
    def create(self, vals_list):
        """La devolución a la tarjeta llega del TPV con la referencia de su
        transacción (``transaction_id``): se enlaza el pago contable que creó la
        pasarela, sin el cual Odoo no acepta un pago en línea."""
        Method = self.env['pos.payment.method']
        for vals in vals_list:
            if vals.get('online_account_payment_id') or not vals.get('transaction_id'):
                continue
            method = Method.browse(vals.get('payment_method_id'))
            if method.is_online_payment and (vals.get('amount') or 0) < 0:
                account_payment = self._al_refund_account_payment(method, vals)
                if account_payment:
                    vals['online_account_payment_id'] = account_payment.id
        return super().create(vals_list)

    def _al_refund_account_payment(self, method, vals):
        # sudo: el cajero no lee pasarelas ni transacciones de pago; se busca
        # solo la devolución confirmada con esa referencia, de una pasarela del
        # método.
        method_sudo = method.sudo()
        refund_tx_sudo = self.env['payment.transaction'].sudo().search([
            ('reference', '=', vals['transaction_id']),
            ('operation', '=', 'refund'),
            ('state', '=', 'done'),
            ('provider_id', 'in', method_sudo.online_payment_provider_ids.ids),
        ], limit=1)
        account_payment = refund_tx_sudo.payment_id
        if not account_payment or refund_tx_sudo.currency_id.compare_amounts(
                refund_tx_sudo.amount, vals['amount']):
            return self.env['account.payment']
        if self.sudo().search_count([('online_account_payment_id', '=', account_payment.id)]):
            return self.env['account.payment']  # ya usada en otra devolución
        return account_payment
