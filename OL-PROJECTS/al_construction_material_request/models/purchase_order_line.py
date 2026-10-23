# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.tools.misc import formatLang


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

    @api.onchange('product_qty', 'product_uom_id', 'product_id')
    def _onchange_construction_whole_sheet(self):
        """Planchas enteras (paquete 1.11, M111-12): una compra manual de un
        tablero indivisible con fracción avisa, sin impedirla."""
        product = self.product_id
        company = self.order_id.company_id or self.env.company
        if not (product and self.product_uom_id and product._construction_is_whole(company)):
            return None
        qty = self.product_uom_id._compute_quantity(
            self.product_qty, product.uom_id, round=False)
        whole = product._construction_whole_qty(qty, company)
        if product.uom_id.compare(qty, whole) == 0:
            return None
        return {'warning': {
            'title': self.env._('Plancha entera'),
            'message': self.env._(
                '%(product)s se compra en planchas enteras: se sugiere %(whole)s en lugar de '
                '%(qty)s.', product=product.display_name,
                whole=formatLang(self.env, whole, digits=0),
                qty=formatLang(self.env, qty, digits=2)),
        }}


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
