# -*- coding: utf-8 -*-
from odoo import api, models


class PurchaseRequestLineMakePurchaseOrder(models.TransientModel):
    _inherit = 'purchase.request.line.make.purchase.order'

    @api.model
    def _prepare_item(self, line):
        """Cantidad sugerida: lo que falta poner en una orden, no lo que falta
        recibir (OCA proponía otra vez lo que ya estaba en una cotización)."""
        vals = super()._prepare_item(line)
        vals['product_qty'] = line.al_qty_to_order
        return vals

    def _al_is_general_stock(self, item):
        """La compra masiva entra como stock general (v1.6, M16-02): sin
        analítica de la obra. La entrega directa en obra conserva su destino y
        su analítica, y también la compra para el almacén si la compañía lo
        pide (CR-16)."""
        line = item.line_id
        if (line.company_id or self.env.company).construction_stock_purchase_analytic \
                and line.construction_request_line_id:
            return False
        return line.construction_request_line_id.supply_mode != 'direct'

    def _al_final_location(self, item):
        """Ubicación final de la entrega directa en obra (vacía: el almacén)."""
        line = item.line_id.construction_request_line_id
        return line._get_site_location() if line.supply_mode == 'direct' \
            else self.env['stock.location']

    @api.model
    def _prepare_purchase_order_line(self, po, item):
        vals = super()._prepare_purchase_order_line(po, item)
        site = self._al_final_location(item)
        if site:
            vals['location_final_id'] = site.id
        if self._al_is_general_stock(item):
            vals['analytic_distribution'] = False
        else:
            # La partida del requerimiento (CR-16, criterio 8).
            vals['construction_task_id'] = item.line_id.construction_request_line_id.task_id.id
        return vals

    @api.model
    def _get_order_line_search_domain(self, order, item):
        """No sumar en una misma línea de OC compras con destinos distintos
        (almacén central frente a cada obra con entrega directa). Las de stock
        general se suman aunque vengan de obras distintas: la línea no lleva
        analítica."""
        domain = super()._get_order_line_search_domain(order, item)
        if self._al_is_general_stock(item):
            domain = [leaf for leaf in domain
                      if not (isinstance(leaf, (list, tuple)) and leaf[0] == 'analytic_distribution')]
            domain.append(('analytic_distribution', '=', False))
        else:
            # Una línea de compra por partida.
            domain.append(('construction_task_id', '=',
                           item.line_id.construction_request_line_id.task_id.id))
        site = self._al_final_location(item)
        domain.append(('location_final_id', '=', site.id if site else False))
        return domain

    def make_purchase_order(self):
        """El origen de la orden nombra todas las solicitudes que atiende y sus
        obras (OCA deja solo el de la primera)."""
        action = super().make_purchase_order()
        order_ids = next((leaf[2] for leaf in action.get('domain') or []
                          if leaf[0] == 'id'), [])
        for order in self.env['purchase.order'].browse(set(order_ids)):
            order.origin = order._al_requests_origin() or order.origin
            order._al_set_request_project()
        return action
