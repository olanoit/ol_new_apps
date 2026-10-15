# -*- coding: utf-8 -*-
"""Asignaciones de la orden de fabricación (fase 4, en su puente desde la v1.7)."""
from odoo import api, fields, models


class ConstructionResourcePlanAllocation(models.Model):
    _inherit = 'construction.resource.plan.allocation'

    kind = fields.Selection(selection_add=[('production', 'Orden de fabricación')],
                            ondelete={'production': 'cascade'})
    production_id = fields.Many2one(
        'mrp.production', string='Orden de fabricación', ondelete='cascade',
        index='btree_not_null', check_company=True)

    @api.model
    def _kind_fields(self):
        return dict(super()._kind_fields(), production='production_id')

    @api.model
    def _kind_done_measures(self):
        return dict(super()._kind_done_measures(), production='consumed')

    @api.depends('production_id.state')
    def _compute_state(self):
        return super()._compute_state()

    def _get_document_state(self, now):
        if self.kind == 'production':
            return {'cancel': 'cancel', 'done': 'done'}.get(self.production_id.state, 'open')
        return super()._get_document_state(now)

    def _get_document_key(self):
        """La OF se reparte por componente."""
        if self.kind == 'production':
            return ('production', self.production_id.id, self.plan_line_id.product_id.id)
        return super()._get_document_key()

    def _get_document_totals(self):
        if self.kind == 'production':
            product = self.plan_line_id.product_id
            date_to = self._construction_date_to()
            moves = self.production_id.move_raw_ids.filtered(
                lambda m: m.state == 'done' and m.product_id == product
                and (not date_to or m.date <= date_to))
            consumed = sum(self._to_uom(m.quantity, m.product_uom) for m in moves)
            # Lo que la OF consume ya se entregó en planta.
            return {'dispatched': consumed, 'consumed': consumed}
        return super()._get_document_totals()

    @api.depends('production_id.move_raw_ids.state', 'production_id.move_raw_ids.quantity')
    def _compute_quantities(self):
        return super()._compute_quantities()
