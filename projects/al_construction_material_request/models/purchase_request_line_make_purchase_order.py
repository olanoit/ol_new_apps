# -*- coding: utf-8 -*-
from odoo import api, models


class PurchaseRequestLineMakePurchaseOrder(models.TransientModel):
    _inherit = 'purchase.request.line.make.purchase.order'

    @api.model
    def _prepare_purchase_order_line(self, po, item):
        vals = super()._prepare_purchase_order_line(po, item)
        line = item.line_id.construction_request_line_id
        if line.supply_mode == 'direct':
            vals['location_final_id'] = line.request_id.location_dest_id.id
        return vals

    @api.model
    def _get_order_line_search_domain(self, order, item):
        """No sumar en una misma línea de OC compras con destinos distintos
        (almacén central frente a cada obra con entrega directa)."""
        domain = super()._get_order_line_search_domain(order, item)
        line = item.line_id.construction_request_line_id
        site = line.supply_mode == 'direct' and line.request_id.location_dest_id
        domain.append(('location_final_id', '=', site.id if site else False))
        return domain
