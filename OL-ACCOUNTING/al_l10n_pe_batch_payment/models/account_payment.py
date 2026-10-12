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
