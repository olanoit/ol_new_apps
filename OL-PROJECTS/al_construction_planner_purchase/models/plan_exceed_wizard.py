# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ConstructionPlanExceedWizard(models.TransientModel):
    _inherit = 'construction.plan.exceed.wizard'

    material_request_id = fields.Many2one(
        'construction.material.request', string='Requerimiento de obra', readonly=True)

    @api.depends('material_request_id')
    def _compute_lines(self):
        return super()._compute_lines()

    def _exceed_lines(self):
        # El residente no ve el plan: la política y el saldo se leen sin sus
        # permisos, solo para mostrarlos.
        request_sudo = self.material_request_id.sudo()
        if not request_sudo:
            return super()._exceed_lines()
        lines = []
        for line in request_sudo._construction_exceeding_lines():
            uom = line.product_id.uom_id
            excess = uom._compute_quantity(line._construction_get_excess(), line.product_uom_id)
            lines.append({
                'product_id': line.product_id.id,
                'product_uom_id': line.product_uom_id.id,
                'qty_remaining': line.construction_plan_remaining,
                'qty_requested': line.product_qty,
                'qty_excess': excess,
            })
        return request_sudo.construction_plan_id.exceed_policy, lines

    def _confirm_document(self, reason):
        if not self.material_request_id:
            return super()._confirm_document(reason)
        request = self.material_request_id
        request.construction_exceed_reason = reason or request.construction_exceed_reason
        return request.with_context(construction_exceed_checked=True).action_request_approval()
