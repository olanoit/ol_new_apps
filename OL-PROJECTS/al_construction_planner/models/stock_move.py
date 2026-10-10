# -*- coding: utf-8 -*-
from odoo import models

from .construction_resource_plan import OPEN_STATES


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        # Llegadas a obra, consumos en obra y consumos de las OF cambian lo
        # despachado y consumido de las líneas del plan. Quien valida en el
        # almacén no ve el plan: solo se actualiza su control.
        done = moves.filtered(lambda m: m.state == 'done')
        if done:
            allocations_sudo = self.env['construction.resource.plan.allocation'].sudo().search([
                ('plan_id.state', 'in', OPEN_STATES),
                '|',
                '&', ('kind', '=', 'material_request'),
                ('plan_line_id.product_id', 'in', done.product_id.ids),
                ('production_id', 'in', done.raw_material_production_id.ids),
            ])
            allocations_sudo._refresh_plan_lines()
        return moves
