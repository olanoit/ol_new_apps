# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    pharmacy_cold_chain = fields.Boolean(
        string='Cadena de frío', compute='_compute_pharmacy_cold_chain', store=True,
        help='La entrega lleva productos que se conservan entre 2 y 8 °C: se reparte en caja '
             'térmica con refrigerante (BPOF 7.5.5).')

    @api.depends('move_ids.product_id.pharmacy_cold_chain')
    def _compute_pharmacy_cold_chain(self):
        for picking in self:
            picking.pharmacy_cold_chain = any(picking.move_ids.product_id.mapped('pharmacy_cold_chain'))
