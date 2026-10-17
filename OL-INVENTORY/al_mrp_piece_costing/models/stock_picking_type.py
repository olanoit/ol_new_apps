# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    piece_costing_default = fields.Boolean(
        string='Costeo por medida',
        help='Las órdenes de fabricación de este tipo de operación nacen con el costeo por '
             'medida. Actívelo solo en el tipo de operación de corte.')
