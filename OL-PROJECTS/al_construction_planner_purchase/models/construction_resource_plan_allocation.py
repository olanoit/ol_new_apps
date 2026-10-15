# -*- coding: utf-8 -*-
"""Asignaciones de la compra masiva (requerimiento de compra de OCA) y del
requerimiento de obra (fase 4, en su puente desde la v1.7)."""
from collections import defaultdict
from datetime import date

from odoo import api, fields, models

from odoo.addons.al_construction_planner.models.construction_resource_plan_allocation import (
    distribute,
)

# Ubicaciones de consumo: lo que sale de la obra hacia ellas es «Consumo en obra».
CONSUMPTION_USAGES = ('production',)


class ConstructionResourcePlanAllocation(models.Model):
    _inherit = 'construction.resource.plan.allocation'

    kind = fields.Selection(selection_add=[
        ('purchase_request', 'Compra masiva'),
        ('material_request', 'Requerimiento de obra'),
    ], ondelete={'purchase_request': 'cascade', 'material_request': 'cascade'})
    purchase_request_line_id = fields.Many2one(
        'purchase.request.line', string='Línea de requerimiento de compra',
        ondelete='cascade', index='btree_not_null', check_company=True)
    material_request_line_id = fields.Many2one(
        'construction.material.request.line', string='Línea de requerimiento de obra',
        ondelete='cascade', index='btree_not_null', check_company=True)

    @api.model
    def _kind_fields(self):
        return dict(super()._kind_fields(), purchase_request='purchase_request_line_id',
                    material_request='material_request_line_id')

    @api.model
    def _kind_done_measures(self):
        return dict(super()._kind_done_measures(), material_request='dispatched')

    def _document_record(self):
        if self.kind in ('purchase_request', 'material_request'):
            return self._document().request_id
        return super()._document_record()

    @api.depends('purchase_request_line_id.request_id', 'material_request_line_id.request_id')
    def _compute_document_name(self):
        return super()._compute_document_name()

    @api.depends('purchase_request_line_id.cancelled', 'purchase_request_line_id.request_state',
                 'purchase_request_line_id.purchase_lines.state',
                 'material_request_line_id.cancelled', 'material_request_line_id.line_state',
                 'material_request_line_id.request_id.state')
    def _compute_state(self):
        return super()._compute_state()

    @staticmethod
    def _confirmed_purchase_qty(pr_line):
        """Cantidad de la línea OCA en OC confirmadas, en su unidad: su parte
        de la línea de OC según la tabla de asignación de OCA, no la línea
        entera (la compra masiva consolidada suma varias solicitudes, M16-01)."""
        return pr_line._al_ordered_qty(states=('purchase', 'done'))

    def _get_document_state(self, now):
        if self.kind == 'purchase_request':
            line = self.purchase_request_line_id
            if line.cancelled or line.request_state == 'rejected':
                return 'cancel'
            confirmed = self._confirmed_purchase_qty(line)
            if line.request_state == 'done' or (
                    line.product_uom_id and line.product_uom_id.compare(
                        confirmed, line.product_qty) >= 0):
                return 'done'
            return 'open'
        if self.kind == 'material_request':
            line = self.material_request_line_id
            request_state = line.request_id.state
            if line.cancelled or request_state in ('cancel', 'rejected'):
                return 'cancel'
            if request_state == 'done' or line.line_state == 'done':
                return 'done'
            return 'open'
        return super()._get_document_state(now)

    def _get_document_totals(self):
        if self.kind == 'purchase_request':
            line = self.purchase_request_line_id
            confirmed = self._confirmed_purchase_qty(line)
            active = not (line.cancelled or line.request_state == 'rejected')
            # La compra masiva sube el comprado al crearse (especificación,
            # P-10); si se cancela, queda solo lo que ya llegó a una OC.
            purchased = max(line.product_qty, confirmed) if active else confirmed
            return {'purchased': self._to_uom(purchased, line.product_uom_id),
                    'done': self._to_uom(confirmed, line.product_uom_id)}
        if self.kind == 'material_request':
            line = self.material_request_line_id
            return {'purchased': self._to_uom(line.qty_purchased, line.product_uom_id),
                    'dispatched': self._to_uom(line.qty_received_on_site, line.product_uom_id)}
        return super()._get_document_totals()

    @api.depends('purchase_request_line_id.product_qty', 'purchase_request_line_id.cancelled',
                 'purchase_request_line_id.request_state',
                 'purchase_request_line_id.purchase_lines.state',
                 'material_request_line_id.qty_purchased',
                 'material_request_line_id.qty_received_on_site')
    def _compute_quantities(self):
        return super()._compute_quantities()

    def _get_extra_measures(self):
        result = super()._get_extra_measures()
        for allocation, qty in self._get_site_consumption().items():
            result.setdefault(allocation, {})['consumed'] = qty
        return result

    def _get_site_consumption(self):
        """Consumo en obra de las asignaciones de requerimientos de obra:
        movimientos hechos desde la ubicación de la obra hacia una ubicación
        de consumo (menos las devoluciones), por obra y producto, repartidos
        entre todas las asignaciones de esa obra y producto."""
        allocations = self.filtered(lambda a: a.kind == 'material_request')
        result = {}
        if not allocations:
            return result
        groups = defaultdict(lambda: self.browse())
        for allocation in allocations:
            site = allocation.material_request_line_id.request_id.location_dest_id
            product = allocation.plan_line_id.product_id
            if site and product:
                groups[(site, product)] |= allocation
        Move = self.env['stock.move']
        date_to = self._construction_date_to()
        date_domain = [('date', '<=', date_to)] if date_to else []
        for (site, product), _group in groups.items():
            siblings = self.search([
                ('kind', '=', 'material_request'),
                ('material_request_line_id.request_id.location_dest_id', '=', site.id),
                ('plan_line_id.product_id', '=', product.id),
            ]) | _group
            consumed = 0.0
            for moves, sign in (
                (Move.search([('state', '=', 'done'), ('product_id', '=', product.id),
                              ('location_id', 'child_of', site.id),
                              ('location_dest_id.usage', 'in', CONSUMPTION_USAGES)]
                             + date_domain), 1),
                (Move.search([('state', '=', 'done'), ('product_id', '=', product.id),
                              ('location_dest_id', 'child_of', site.id),
                              ('location_id.usage', 'in', CONSUMPTION_USAGES)]
                             + date_domain), -1),
            ):
                consumed += sign * sum(
                    m.product_uom._compute_quantity(m.quantity, product.uom_id,
                                                    rounding_method='HALF-UP')
                    for m in moves)
            ordered = siblings.sorted(lambda a: (a.date_needed or date.max, a.id))
            shares = distribute(consumed, [(a, a._to_product_uom(a.qty_allocated))
                                           for a in ordered])
            result.update(shares)
        return result

    def _get_requested_qty(self):
        # La compra masiva es stock general: no es lo pedido por la obra.
        if self.kind == 'purchase_request':
            return 0.0
        return super()._get_requested_qty()

    def _get_open_document_dates(self):
        result = super()._get_open_document_dates()
        if self.kind == 'material_request':
            request = self.material_request_line_id.request_id
            result.append((request, request.date_required))
        elif self.kind == 'purchase_request':
            pr_line = self.purchase_request_line_id
            result.append((pr_line.request_id, pr_line.date_required))
            for po_line in pr_line.purchase_lines.filtered(
                    lambda l: l.state not in ('cancel', 'done')):
                result.append((po_line.order_id, po_line.date_planned))
        return result

    def _is_purchasing(self):
        return self.kind == 'purchase_request' or (
            self.kind == 'material_request'
            and self.material_request_line_id.line_state == 'purchasing') or super()._is_purchasing()
