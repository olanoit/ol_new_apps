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
            done._construction_client_supply_received()
        return moves

    def _construction_client_supply_received(self):
        """Lo que el cliente entrega en la obra suma a «Recibido del cliente»
        de las líneas de suministro del cliente del plan; lo que se le
        devuelve, resta (CR-06)."""
        Project = self.env['project.project'].sudo()
        for move in self:
            partner = move.picking_id.partner_id.commercial_partner_id
            if move.location_id.usage in ('customer', 'supplier'):
                site_location, sign = move.location_dest_id, 1
            elif move.location_dest_id.usage in ('customer', 'supplier'):
                site_location, sign = move.location_id, -1
            else:
                continue
            # sudo: quien valida en el almacén no ve las obras ni el plan.
            project = Project.search([
                ('construction_location_id', 'parent_of', site_location.id)], limit=1)
            if not project:
                continue
            from_client = (move.location_id if sign > 0 else move.location_dest_id).usage \
                == 'customer' or (partner and partner == project.partner_id.commercial_partner_id)
            if not from_client:
                continue
            lines = project._construction_current_plan().line_ids.filtered(
                lambda l: l.is_client_supply and l.product_id == move.product_id)
            if lines:
                lines._construction_add_client_received(
                    move.uom_id._compute_quantity(
                        move.quantity, lines[0].product_uom_id or move.uom_id,
                        round=False) * sign)


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    def _construction_add_client_received(self, qty):
        """Reparte lo recibido del cliente (o, negativo, lo devuelto) entre
        estas líneas de suministro del cliente, en orden, hasta lo
        planificado; lo que sobra va a la última (CR-06)."""
        # El plan aprobado admite este control (lo escribe el almacén).
        lines = self.with_context(construction_plan_force=True)
        if qty < 0:
            for line in reversed(lines):
                take = min(-qty, line.qty_client_received)
                line.qty_client_received -= take
                qty += take
                if qty >= 0:
                    break
            return
        for index, line in enumerate(lines):
            room = max(line.qty_planned - line.qty_client_received, 0.0)
            take = qty if index == len(lines) - 1 else min(qty, room)
            line.qty_client_received += take
            qty -= take
            if qty <= 0:
                break
