# -*- coding: utf-8 -*-
from odoo import Command, api, fields, models


class PurchaseRequest(models.Model):
    _inherit = 'purchase.request'

    construction_request_id = fields.Many2one(
        'construction.material.request', string='Requerimiento de obra',
        index='btree_not_null', copy=False, readonly=True)

    def _al_site_name(self):
        """Obra de la solicitud, para el origen de la orden de compra
        consolidada. El planificador agrega la obra de su plan."""
        self.ensure_one()
        request = self.construction_request_id
        return (request.area_id.name if request.request_type == 'internal'
                else request.project_id.name) or ''


class PurchaseRequestLine(models.Model):
    _inherit = 'purchase.request.line'

    construction_request_line_id = fields.Many2one(
        'construction.material.request.line', string='Línea de requerimiento de obra',
        index='btree_not_null', copy=False, readonly=True)
    # Compra masiva consolidada (v1.6, M16-01): OCA trata como pendiente lo no
    # recibido, aunque ya esté en una cotización; una segunda compra masiva lo
    # volvía a comprar.
    al_qty_to_order = fields.Float(
        string='Por ordenar', digits='Product Unit of Measure',
        compute='_compute_al_qty_to_order', store=True,
        help='Lo solicitado menos lo que ya está en órdenes de compra no canceladas, según la '
             'tabla de asignación de la solicitud.')

    @api.depends('product_qty', 'cancelled', 'request_state',
                 'purchase_request_allocation_ids.requested_product_uom_qty',
                 'purchase_request_allocation_ids.purchase_line_id',
                 'purchase_request_allocation_ids.purchase_line_id.state')
    def _compute_al_qty_to_order(self):
        for line in self:
            if line.cancelled or line.request_state in ('rejected', 'done'):
                line.al_qty_to_order = 0.0
                continue
            ordered = 0.0
            for allocation in line.purchase_request_allocation_ids:
                if allocation.purchase_line_id and allocation.purchase_line_id.state != 'cancel':
                    ordered += allocation.product_uom_id._compute_quantity(
                        allocation.requested_product_uom_qty,
                        line.product_uom_id or allocation.product_uom_id)
            line.al_qty_to_order = max(line.product_qty - ordered, 0.0)

    def _al_ordered_qty(self, states=None):
        """Parte de la línea en órdenes de compra, en su unidad.

        Una línea de OC que atiende a varias solicitudes (compra masiva
        consolidada) se reparte en proporción a lo que la tabla de asignación
        de OCA registra para cada una: con 165 para 100, 40 y 25, cada
        solicitud se lleva su parte. Si la atiende sola, se lleva toda la
        línea (como OCA). Las líneas de OC enlazadas sin asignación cuentan
        enteras.

        :param tuple states: solo las OC en estos estados; por defecto, las no
            canceladas.
        """
        self.ensure_one()
        line_uom = self.product_uom_id
        qty = 0.0
        for po_line in self.purchase_lines:
            if po_line.state == 'cancel' or (states and po_line.state not in states):
                continue
            uom = line_uom or po_line.product_uom_id
            po_qty = po_line.product_uom_id._compute_quantity(po_line.product_qty, uom)
            allocations = po_line.purchase_request_allocation_ids
            own = allocations.filtered(lambda a: a.purchase_request_line_id == self)
            total = sum(a.product_uom_id._compute_quantity(a.requested_product_uom_qty, uom)
                        for a in allocations)
            if not own or not total:
                qty += po_qty
                continue
            share = sum(a.product_uom_id._compute_quantity(a.requested_product_uom_qty, uom)
                        for a in own)
            qty += po_qty * share / total
        return qty

    def _compute_purchased_qty(self):
        """Comprado de la línea: su parte de cada línea de OC, no la línea
        entera (OCA suma la línea de OC completa en cada solicitud que atiende,
        y la compra masiva consolidada mostraba 140 comprados en cada una)."""
        for line in self:
            line.purchased_qty = line._al_ordered_qty()

    def _calc_new_qty(self, request_line, po_line=None, new_pr_line=False):
        """Cantidad de la línea de OC: OCA suma las solicitudes enlazadas a la
        línea, pero al agregar una a una línea existente la enlaza después de
        sumar y deja fuera siempre la última (100 en vez de 140; 140 en vez de
        165). Se enlaza antes de sumar."""
        if po_line and request_line and request_line not in po_line.purchase_request_lines:
            po_line.purchase_request_lines = [Command.link(request_line.id)]
        return super()._calc_new_qty(request_line, po_line=po_line, new_pr_line=new_pr_line)
