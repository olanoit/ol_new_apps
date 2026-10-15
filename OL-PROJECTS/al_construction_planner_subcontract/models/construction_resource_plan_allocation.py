# -*- coding: utf-8 -*-
"""Asignaciones de la OC de servicio de la contrata (fase 5, en su puente desde
la v1.7)."""
from odoo import api, fields, models


class ConstructionResourcePlanAllocation(models.Model):
    _inherit = 'construction.resource.plan.allocation'

    kind = fields.Selection(selection_add=[('service_order', 'OC de servicio')],
                            ondelete={'service_order': 'cascade'})
    purchase_line_id = fields.Many2one(
        'purchase.order.line', string='Línea de la OC', ondelete='cascade',
        index='btree_not_null', check_company=True)

    @api.model
    def _kind_fields(self):
        return dict(super()._kind_fields(), service_order='purchase_line_id')

    def _document_record(self):
        if self.kind == 'service_order':
            return self.purchase_line_id.order_id
        return super()._document_record()

    @api.depends('purchase_line_id.order_id')
    def _compute_document_name(self):
        return super()._compute_document_name()

    @api.depends('purchase_line_id.order_id.state', 'purchase_line_id.qty_received')
    def _compute_state(self):
        return super()._compute_state()

    def _get_document_state(self, now):
        if self.kind == 'service_order':
            line = self.purchase_line_id
            if line.order_id.state == 'cancel':
                return 'cancel'
            if line.product_uom_id.compare(line.qty_received, line.product_qty) >= 0:
                return 'done'
            return 'open'
        return super()._get_document_state(now)

    def _get_document_totals(self):
        if self.kind == 'service_order':
            line = self.purchase_line_id
            return {'done': self._to_uom(line.qty_received, line.product_uom_id)}
        return super()._get_document_totals()

    @api.depends('purchase_line_id.qty_received')
    def _compute_quantities(self):
        return super()._compute_quantities()

    def _get_open_document_dates(self):
        result = super()._get_open_document_dates()
        if self.kind == 'service_order':
            po_line = self.purchase_line_id
            result.append((po_line.order_id, po_line.date_planned))
        return result
