# -*- coding: utf-8 -*-
"""Necesidad y redondeo a plancha entera en los movimientos (paquete 1.11,
M111-12). El redondeo lo escribe quien entrega (la orden de fabricación o el
requerimiento de obra); aquí se guardan las cifras y se cuida que la reserva
y lo validado del almacén sean planchas enteras."""
import math

from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    construction_need_qty = fields.Float(
        string='Necesidad', digits='Product Unit', readonly=True, copy=False,
        help='Lo que se pidió en fracción (en la unidad del movimiento). La cantidad del '
             'movimiento es el entero a entregar.')
    construction_need_display = fields.Float(
        string='Necesidad del despacho', digits='Product Unit',
        compute='_compute_construction_need_display',
        help='La necesidad del movimiento o, en el despacho a producción, la de los '
             'componentes de la orden que abastece.')
    construction_rounding_qty = fields.Float(
        string='Redondeo a plancha entera', digits='Product Unit',
        compute='_compute_construction_need_display',
        help='A entregar (más lo cubierto con retazo) menos la necesidad.')

    # Retazos (M111-12, fase B): la salida con costo fijo (área × costo de la
    # plancha) se valoriza con él y queda fuera del reparto de las piezas.
    construction_fixed_cost = fields.Float(
        string='Costo fijo de la salida', digits='Product Price', copy=False,
        help='Costo total del subproducto, fijado al declararlo (retazo).')

    @api.depends('construction_need_qty', 'product_uom_qty', 'product_uom',
                 'move_dest_ids.construction_need_qty', 'move_dest_ids.product_uom')
    def _compute_construction_need_display(self):
        for move in self:
            need = move.construction_need_qty
            if not need:
                need = sum(dest.product_uom._compute_quantity(
                    dest.construction_need_qty, move.product_uom, round=False)
                    for dest in move.move_dest_ids if dest.construction_need_qty)
            move.construction_need_display = need
            move.construction_rounding_qty = (
                move.product_uom_qty + move._construction_covered_qty() - need) if need else 0.0

    def _construction_covered_qty(self):
        """Fracción de plancha cubierta con retazos (en la unidad del
        movimiento). Sin retazos, 0."""
        self.ensure_one()
        return 0.0

    # ------------------------------------------------------------------
    # Reserva y validación en planchas enteras
    # ------------------------------------------------------------------
    def _construction_whole_scope(self):
        """Alcance en que el movimiento entrega planchas enteras al que las
        pide (``production`` o ``request``, M111-19 D) o False: lo amplían los
        módulos que redondean (despacho a producción, requerimiento de obra).
        Los ajustes y traslados manuales quedan fuera."""
        self.ensure_one()
        return False

    def _construction_whole_controlled(self):
        self.ensure_one()
        scope = self._construction_whole_scope()
        return bool(scope and self.product_id
                    and self.product_id._construction_is_whole(self.company_id, scope))

    def _action_assign(self, force_qty=False):
        res = super()._action_assign(force_qty=force_qty)
        self._construction_floor_whole_reservation()
        return res

    def _construction_floor_whole_reservation(self):
        """Lo reservado de un producto indivisible baja al entero: con 7.6
        planchas libres y 8 pedidas se reservan 7."""
        for move in self.filtered(lambda m: m.state in ('partially_available', 'assigned')
                                  and not m.picked):
            if not move._construction_whole_controlled():
                continue
            uom = move.product_id.uom_id
            reserved = move.product_uom._compute_quantity(move.quantity, uom, round=False)
            excess = uom.round(reserved - math.floor(uom.round(reserved)))
            if uom.is_zero(excess):
                continue
            for line in move.move_line_ids.filtered(lambda l: not l.picked).sorted('quantity'):
                if uom.is_zero(excess):
                    break
                line_qty = line.product_uom_id._compute_quantity(line.quantity, uom, round=False)
                take = min(line_qty, excess)
                excess -= take
                if uom.compare(line_qty, take) <= 0:
                    line.unlink()
                else:
                    line.quantity = uom._compute_quantity(
                        line_qty - take, line.product_uom_id, round=False)
            move._recompute_state()
