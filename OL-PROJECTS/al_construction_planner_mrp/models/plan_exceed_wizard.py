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
        return production_sudo.construction_plan_id._exceed_policy_for('production'), lines

    def _confirm_document(self, reason):
        if not self.production_id:
            return super()._confirm_document(reason)
        self._check_head_approval(self.production_id)
        production = self.production_id
        rows = production.sudo()._construction_get_excess()
        production.write(self._exceed_values(reason))
        res = production.with_context(construction_exceed_checked=True).action_confirm()
        if self.policy == 'approval':
            # Registro del exceso autorizado por la jefatura (M18-05).
            plan = production.sudo().construction_plan_id
            self.env['construction.exceed.log']._log([{
                'kind': 'excess', 'plan_id': plan.id, 'project_id': plan.project_id.id,
                'company_id': plan.company_id.id, 'product_id': product.id, 'qty': excess,
                'uom_id': product.uom_id.id, 'reason': reason, 'document': production.name,
                'res_model': production._name, 'res_id': production.id,
            } for product, _balance, _qty, excess in rows])
        return res
