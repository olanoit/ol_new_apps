# -*- coding: utf-8 -*-
from odoo import models


class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'

    def order_receipt_generate_data(self, basic_receipt=False):
        data = super().order_receipt_generate_data(basic_receipt)
        data['extra_data']['al_seller_name'] = self.seller_id.name or False
        return data
