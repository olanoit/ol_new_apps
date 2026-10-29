# -*- coding: utf-8 -*-
from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    # Ambos campos se copian para que los sigan las entregas parciales
    # (``_split`` crea el movimiento pendiente con ``copy_data``).
    construction_request_line_id = fields.Many2one(
        'construction.material.request.line', string='Línea de requerimiento de obra',
        index='btree_not_null')
    # En 19.0 stock.move no tiene analítica propia y un traslado interno no
    # genera líneas analíticas (plan, F0.3): se guarda solo como trazabilidad
    # para el consumo en obra. Nombre propio para no chocar con otros módulos.
    construction_analytic_distribution = fields.Json(string='Analítica de obra')
    # «Productos por despachar» (paquete 1.11, M111-08): se agrupa por el
    # requerimiento, no por el texto del documento origen.
    construction_request_id = fields.Many2one(
        related='picking_id.construction_request_id', string='Requerimiento de obra',
        store=True, index='btree_not_null')
    construction_project_id = fields.Many2one(
        related='construction_request_id.project_id', string='Obra', store=True)

    def _prepare_merge_moves_distinct_fields(self):
        # Un movimiento por línea del requerimiento: si se fusionan los del
        # mismo producto de dos niveles, lo validado cae entero en la primera
        # línea (H-21).
        return super()._prepare_merge_moves_distinct_fields() + ['construction_request_line_id']

    def _construction_whole_scope(self):
        # Planchas enteras (M111-12): el despacho del requerimiento de obra.
        return super()._construction_whole_scope() or (
            'request' if self.construction_request_line_id else False)

    def _construction_set_request_need(self):
        """Necesidad del movimiento de una línea indivisible (paquete 1.11,
        M111-22): la fracción pedida queda en el movimiento como en la orden
        de corte. El despacho lleva la parte que cubre y la entrega pendiente
        de compra, el resto; así el redondeo cae donde está la última plancha.
        Sin productos indivisibles no cambia nada."""
        for move in self:
            line = move.construction_request_line_id
            if not line or not move.product_id._construction_is_whole(move.company_id, 'request'):
                continue
            uom = line.product_uom_id
            need = line.product_qty
            others = sum(other.construction_need_qty for other in line.move_ids
                         if other != move and other.state != 'cancel')
            # Los movimientos de la línea van en su unidad.
            own = max(need - others, 0.0)
            if not move.created_purchase_request_line_id:
                own = min(own, move.product_uom_qty)
            move.construction_need_qty = uom._compute_quantity(own, move.uom_id, round=False)

    def _construction_request_line_qty(self, line_uom):
        """Lo que este movimiento hecho entrega a su línea, en ``line_uom``.
        Hook: el retazo entrega su fracción de plancha (M111-22)."""
        self.ensure_one()
        return self.uom_id._compute_quantity(
            self.quantity, line_uom, rounding_method='HALF-UP')

    def _get_account_move_line_vals(self):
        """Consumo interno (M111-10): el gasto lleva la analítica del área."""
        vals_list = super()._get_account_move_line_vals()
        line = self.construction_request_line_id
        expense_account = self.location_dest_id.valuation_account_id
        if line.request_id.request_type == 'internal' and line.analytic_distribution \
                and expense_account and self.location_dest_id.usage == 'inventory':
            for vals in vals_list:
                if vals['account_id'] == expense_account.id:
                    vals['analytic_distribution'] = line.analytic_distribution
        return vals_list

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        lines = (
            moves.construction_request_line_id
            | moves.purchase_request_allocation_ids.purchase_request_line_id
            .construction_request_line_id
        )
        # Quien valida la transferencia o la recepción (almacén) puede no
        # tener acceso a los requerimientos de obra: solo se cierra su estado.
        lines_sudo = lines.sudo()
        lines_sudo.request_id._check_done()
        return moves
