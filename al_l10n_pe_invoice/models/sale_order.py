# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def _prepare_invoice_values(self, order, so_lines):
        res = super()._prepare_invoice_values(order, so_lines)
        res['sale_id'] = order.id
        return res


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    external_purchase = fields.Char(
        string='OC. externa', copy=False, help='Orden de compra externa')

    def _prepare_invoice(self):
        res = super()._prepare_invoice()
        res['sale_id'] = self.id
        if self.external_purchase:
            res['external_purchase'] = self.external_purchase
        return res
