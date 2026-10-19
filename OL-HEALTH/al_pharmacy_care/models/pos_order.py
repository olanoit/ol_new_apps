# -*- coding: utf-8 -*-
from odoo import api, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _process_order(self, order, existing_order):
        order_id = super()._process_order(order, existing_order)
        pos_order = self.browse(order_id)
        if pos_order.state in ('paid', 'done') and pos_order.partner_id:
            self.env['pharmacy.treatment']._update_for_partners(
                pos_order.partner_id, pos_order.lines.product_id, pos_order.company_id)
        return order_id
