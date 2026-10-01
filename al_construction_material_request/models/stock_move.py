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
