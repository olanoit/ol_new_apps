# -*- coding: utf-8 -*-
from odoo import api, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    @api.depends('journal_id', 'available_partner_bank_ids')
    def _compute_partner_bank_id(self):
        super()._compute_partner_bank_id()
        for wizard in self.filtered(lambda w: w.can_edit_wizard and w.payment_type == 'outbound'):
            wizard.partner_bank_id = wizard.available_partner_bank_ids._origin._l10n_pe_preferred(
                wizard.partner_bank_id._origin, wizard.journal_id, wizard.currency_id)

    def _create_payment_vals_from_batch(self, batch_result):
        # Pagos agrupados (varios proveedores): la cuenta de la factura, salvo
        # que el proveedor tenga una en el banco del diario.
        vals = super()._create_payment_vals_from_batch(batch_result)
        if vals.get('payment_type') == 'outbound':
            Bank = self.env['res.partner.bank']
            candidates = self._get_batch_available_partner_banks(batch_result, self.journal_id)
            vals['partner_bank_id'] = candidates._l10n_pe_preferred(
                Bank.browse(vals.get('partner_bank_id')), self.journal_id,
                self.env['res.currency'].browse(vals.get('currency_id'))).id or False
        return vals
