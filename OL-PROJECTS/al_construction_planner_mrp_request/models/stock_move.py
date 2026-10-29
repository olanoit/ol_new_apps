# -*- coding: utf-8 -*-
"""Retazo en el despacho del requerimiento de obra (paquete 1.11, M111-22).

El movimiento de una línea indivisible guarda su necesidad en fracción (la
escribe el requerimiento). Aquí se cubre esa fracción con un retazo del mismo
tablero, como en el despacho a producción: el retazo va en el mismo despacho
con su lote, la plancha se vuelve a redondear y la línea del requerimiento
cuenta el retazo por su fracción de plancha, no como una unidad."""
import math

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _construction_plan_allocation_domain(self):
        # Los consumos de las OF también cambian el plan (CR-16: vive aquí
        # porque el puente de compras no depende de Fabricación).
        return super()._construction_plan_allocation_domain() \
            | Domain('production_id', 'in', self.raw_material_production_id.ids)

    def _construction_is_request_board(self):
        """Movimiento plancha del despacho de un requerimiento (no un retazo)."""
        self.ensure_one()
        return bool(self.construction_request_line_id and self.construction_need_qty
                    and not self._construction_is_remnant()
                    and not self._construction_board_raw_moves())

    def _construction_cover_fraction(self):
        if not self._construction_is_request_board():
            return super()._construction_cover_fraction()
        uom = self.product_id.uom_id
        need = self.uom_id._compute_quantity(self.construction_need_qty, uom, round=False)
        covered = self.uom_id._compute_quantity(
            self.construction_covered_qty, uom, round=False)
        net = uom.round(max(need - covered, 0.0))
        return uom.round(net - math.floor(net))

    @api.depends('construction_need_qty', 'construction_request_line_id')
    def _compute_construction_can_cover(self):
        return super()._compute_construction_can_cover()

    def _construction_request_line_qty(self, line_uom):
        # El retazo entrega su fracción de plancha a la línea del tablero.
        lot = self.construction_remnant_lot_id
        board = self.construction_covers_move_id
        if lot and board.construction_request_line_id:
            fraction = lot.construction_sheet_pct / 100
            return board.product_id.uom_id._compute_quantity(fraction, line_uom, round=False)
        return super()._construction_request_line_qty(line_uom)

    # ------------------------------------------------------------------
    # Cubrir y quitar
    # ------------------------------------------------------------------
    def _construction_round_request_board(self):
        """La plancha del requerimiento pide las planchas enteras de su
        necesidad menos lo cubierto con retazos."""
        for move in self:
            uom = move.product_id.uom_id
            need = move.uom_id._compute_quantity(move.construction_need_qty, uom, round=False)
            covered = move.uom_id._compute_quantity(
                move.construction_covered_qty, uom, round=False)
            whole = move.product_id._construction_whole_qty(need - covered, move.company_id)
            new_qty = uom._compute_quantity(whole, move.uom_id, round=False)
            if move.uom_id.compare(new_qty, move.product_uom_qty):
                move._do_unreserve()
                move.product_uom_qty = new_qty
                if not move.uom_id.is_zero(new_qty):
                    move._action_assign()
            line = move.construction_request_line_id
            # La línea muestra el redondeo que queda después del retazo.
            line.qty_rounding = uom._compute_quantity(
                whole + covered - need, line.product_uom_id, round=False)

    def _construction_cover_request_with_remnants(self, quants):
        """Agrega los retazos al despacho de esta plancha, reservados con su
        lote, y vuelve a redondear la plancha."""
        self.ensure_one()
        picking = self.picking_id
        for quant in quants:
            variant = quant.product_id
            remnant = self.create({
                'product_id': variant.id,
                'uom_id': variant.uom_id.id,
                'product_uom_qty': 1.0,
                'location_id': quant.location_id.id,
                'location_dest_id': self.location_dest_id.id,
                'picking_id': picking.id,
                'picking_type_id': picking.picking_type_id.id,
                'company_id': self.company_id.id,
                'origin': self.origin,
                'reference_ids': [fields.Command.set(self.reference_ids.ids)],
                'construction_request_line_id': self.construction_request_line_id.id,
                'construction_analytic_distribution': self.construction_analytic_distribution,
                'construction_remnant_lot_id': quant.lot_id.id,
                'construction_covers_move_id': self.id,
            })
            remnant._action_confirm(merge=False, create_proc=False)
            # Lo reservado al confirmar puede ser otro lote: se reserva el elegido.
            remnant._do_unreserve()
            self.env['stock.move.line'].create({
                'move_id': remnant.id,
                'picking_id': picking.id,
                'product_id': variant.id,
                'uom_id': variant.uom_id.id,
                'lot_id': quant.lot_id.id,
                'quantity': 1.0,
                'location_id': quant.location_id.id,
                'location_dest_id': remnant.location_dest_id.id,
            })
        self.invalidate_recordset(['construction_covered_qty'])
        self._construction_round_request_board()

    def action_construction_remove_remnant(self):
        on_request = self.filtered(
            lambda m: m.construction_covers_move_id.construction_request_line_id
            and not m.move_dest_ids.filtered('construction_covers_move_id'))
        for move in on_request:
            if move.state in ('done', 'cancel'):
                raise UserError(self.env._('Este movimiento no es un retazo por despachar.'))
            board = move.construction_covers_move_id
            lot = move.construction_remnant_lot_id
            move._action_cancel()
            board.invalidate_recordset(['construction_covered_qty'])
            board._construction_round_request_board()
            body = self.env._(
                'Se quitó el retazo %(lot)s de [%(product)s]; la plancha se pide entera.',
                lot=lot.name, product=board.product_id.default_code or board.product_id.name)
            move.picking_id.message_post(body=body)
        rest = self - on_request
        return super(StockMove, rest).action_construction_remove_remnant() if rest else True
