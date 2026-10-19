# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        result = super().action_confirm()
        Treatment = self.env['pharmacy.treatment']
        for order in self.filtered(lambda o: o.state == 'sale'):
            Treatment._update_for_partners(order.partner_id, order.order_line.product_id,
                                           order.company_id)
        return result
