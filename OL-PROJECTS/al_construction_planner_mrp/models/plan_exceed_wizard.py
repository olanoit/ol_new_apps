# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ConstructionPlanExceedWizard(models.TransientModel):
    _inherit = 'construction.plan.exceed.wizard'

    production_id = fields.Many2one(
        'mrp.production', string='Orden de fabricación', readonly=True)

    @api.depends('production_id')
    def _compute_lines(self):
        return super()._compute_lines()

    def _exceed_lines(self):
        # La planta no ve el plan: la política y el saldo se leen sin sus
        # permisos, solo para mostrarlos.
        production_sudo = self.production_id.sudo()
        if not production_sudo:
            return super()._exceed_lines()
        lines = [{
            'product_id': product.id,
            'product_uom_id': product.uom_id.id,
            'qty_remaining': balance,
            'qty_requested': qty,
            'qty_excess': excess,
        } for product, balance, qty, excess in production_sudo._construction_get_excess()]
        return production_sudo.construction_plan_id.exceed_policy, lines

    def _confirm_document(self, reason):
        if not self.production_id:
            return super()._confirm_document(reason)
        self._check_head_approval(self.production_id)
        self.production_id.write(self._exceed_values(reason))
        return self.production_id.with_context(construction_exceed_checked=True).action_confirm()
