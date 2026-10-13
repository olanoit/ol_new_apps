# -*- coding: utf-8 -*-
from odoo import fields, models


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    sale_order_id = fields.Many2one(
        'sale.order', string='Orden de venta', index='btree_not_null', check_company=True,
        ondelete='set null', copy=False)
