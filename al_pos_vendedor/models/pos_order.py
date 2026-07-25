# -*- coding: utf-8 -*-

from odoo import fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    seller_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Vendedor',
    )
