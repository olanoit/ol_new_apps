# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .purchase_order import POLICY_RANK


class ConstructionPlanExceedWizard(models.TransientModel):
    _inherit = 'construction.plan.exceed.wizard'

    purchase_order_id = fields.Many2one(
        'purchase.order', string='Orden de compra', readonly=True)

    @api.depends('purchase_order_id')
    def _compute_lines(self):
        return super()._compute_lines()

    def _exceed_lines(self):
        # Quien compra no ve el plan: el presupuesto se lee sin sus permisos.
        order_sudo = self.purchase_order_id.sudo()
        if not order_sudo:
            return super()._exceed_lines()
        rows = order_sudo._construction_budget_excess()
        policies = [row[0].exceed_policy for row in rows]
        lines = [{
            'name': budget_line.display_name if budget_line else self.env._(
                '%s (combinación fuera del presupuesto)', plan.display_name),
            'qty_remaining': budget - used,
            'qty_requested': amount,
            'qty_excess': excess,
        } for plan, budget_line, budget, used, amount, excess in rows]
        return (max(policies, key=lambda p: POLICY_RANK[p]) if policies else False), lines

    def _confirm_document(self, reason):
        if not self.purchase_order_id:
            return super()._confirm_document(reason)
        order = self.purchase_order_id
        self._check_head_approval(order)
        values = self._exceed_values(reason)
        if self.policy == 'approval':
            # sudo: la jefatura del planificador aprueba el exceso sin ser
            # compradora; solo confirma la OC que Compras ya preparó.
            order_sudo = order.sudo().with_context(construction_exceed_checked=True)
            order_sudo.write(values)
            return order_sudo.button_confirm()
        order.write(values)
        return order.with_context(construction_exceed_checked=True).button_confirm()
