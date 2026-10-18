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
        if site and direct_lines and site in direct_lines.mapped(
                lambda l: l._get_site_location()):
            vals['location_dest_id'] = site.id
        return vals


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _al_requests_origin(self):
        """Origen de una orden que atiende solicitudes de compra: todas las
        solicitudes con su obra, por ejemplo «PR00005 (ACACIAS 353), PR00006
        (TORRE A)» (compra masiva consolidada, v1.6, M16-01)."""
        self.ensure_one()
        labels = []
        for request in self.order_line.purchase_request_lines.request_id.sorted('name'):
            site = request._al_site_name()
            labels.append('%s (%s)' % (request.name, site) if site else request.name)
        return ', '.join(labels)
