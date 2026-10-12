# -*- coding: utf-8 -*-
from odoo import api, models


class AccountPaymentMethod(models.Model):
    _inherit = 'account.payment.method'

    @api.model
    def _get_payment_method_information(self):
        res = super()._get_payment_method_information()
        res['pe_bank_txt'] = {
            'mode': 'multi',
            'type': ('bank',),
            'currency_ids': (self.env.ref('base.PEN') | self.env.ref('base.USD')).ids,
            'country_id': self.env.ref('base.pe').id,
        }
        return res
