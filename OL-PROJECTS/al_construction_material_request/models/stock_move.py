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
        return super()._construction_whole_scope() or bool(self.construction_request_line_id)

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
