# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        """Los controlados no se venden por canales a distancia (BPOF
        7.5.5.1): ni tienda en línea ni delivery."""
        for order in self:
            remote = ('website_id' in order._fields and order.website_id) or \
                ('carrier_id' in order._fields and order.carrier_id)
            controlled = order.order_line.product_id.filtered('pharmacy_control_list')
            if remote and controlled:
                raise UserError(self.env._(
                    'Los productos controlados no se venden por internet ni por delivery: %s.',
                    ', '.join(controlled.mapped('display_name'))))
        return super().action_confirm()
