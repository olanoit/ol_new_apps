# -*- coding: utf-8 -*-
from odoo import models
from odoo.fields import Domain

from odoo.addons.al_construction_planner.models.construction_resource_plan import OPEN_STATES


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _construction_plan_allocation_domain(self):
        """Asignaciones del plan que cambian al terminar estos movimientos.
        Aquí, las de los requerimientos de obra; los consumos de las OF los
        agrega al_construction_planner_mrp_request (este módulo no depende de
        Fabricación, CR-16)."""
        return Domain('kind', '=', 'material_request') \
            & Domain('plan_line_id.product_id', 'in', self.product_id.ids)

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        # Llegadas a obra, consumos en obra y consumos de las OF cambian lo
        # despachado y consumido de las líneas del plan. Quien valida en el
        # almacén no ve el plan: solo se actualiza su control.
        done = moves.filtered(lambda m: m.state == 'done')
        if done:
            allocations_sudo = self.env['construction.resource.plan.allocation'].sudo().search(
                Domain('plan_id.state', 'in', OPEN_STATES)
                & done._construction_plan_allocation_domain())
            allocations_sudo._refresh_plan_lines()
        return moves
