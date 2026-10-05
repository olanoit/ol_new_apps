# -*- coding: utf-8 -*-
from odoo import models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        """Entrega directa en obra: la recepción de la línea va a la ubicación
        de la obra (``location_final_id``, puesto por el asistente de OCA)."""
        vals = super()._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)
        site = self.location_final_id
        direct_lines = self.purchase_request_lines.construction_request_line_id.filtered(
            lambda l: l.supply_mode == 'direct')
        if site and direct_lines and direct_lines.request_id.location_dest_id == site:
            vals['location_dest_id'] = site.id
        return vals
