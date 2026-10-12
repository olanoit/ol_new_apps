# -*- coding: utf-8 -*-
from odoo import api, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.model
    def _get_method_codes_using_bank_account(self):
        return super()._get_method_codes_using_bank_account() + ['pe_bank_txt']

    @api.model
    def _get_method_codes_needing_bank_account(self):
        return super()._get_method_codes_needing_bank_account() + ['pe_bank_txt']

    @api.depends('available_partner_bank_ids', 'journal_id')
    def _compute_partner_bank_id(self):
        super()._compute_partner_bank_id()
        for pay in self.filtered(lambda p: p.payment_type == 'outbound'):
            pay.partner_bank_id = pay.available_partner_bank_ids._origin._l10n_pe_preferred(
                pay.partner_bank_id._origin, pay.journal_id, pay.currency_id)
