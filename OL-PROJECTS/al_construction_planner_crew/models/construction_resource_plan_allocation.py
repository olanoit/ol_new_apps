# -*- coding: utf-8 -*-
"""Asignaciones del turno de la cuadrilla (fase 7, en su puente desde la v1.7)."""
from odoo import api, fields, models


class ConstructionResourcePlanAllocation(models.Model):
    _inherit = 'construction.resource.plan.allocation'

    kind = fields.Selection(selection_add=[('planning_slot', 'Turno')],
                            ondelete={'planning_slot': 'cascade'})
    slot_id = fields.Many2one(
        'planning.slot', string='Turno', ondelete='cascade', index='btree_not_null',
        check_company=True)

    @api.model
    def _kind_fields(self):
        return dict(super()._kind_fields(), planning_slot='slot_id')

    @api.depends('slot_id.end_datetime')
    def _compute_state(self):
        return super()._compute_state()

    def _get_document_state(self, now):
        if self.kind == 'planning_slot':
            end = self.slot_id.end_datetime
            return 'done' if end and end <= now else 'open'
        return super()._get_document_state(now)
