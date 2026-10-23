# -*- coding: utf-8 -*-
"""Requerimiento al almacén en planchas enteras (paquete 1.11, M111-12, fase A).

La orden de corte guarda en cada componente indivisible la necesidad en
fracción (la del sistema matriz o la de la lista de materiales) y, al
confirmar, pide planchas enteras: el redondeo se hace por producto en toda la
orden y la diferencia va al movimiento con mayor necesidad, sin fusionar
movimientos (cada uno conserva su etapa y su línea de lista). El despacho a
producción nativo nace de esos movimientos ya en enteros. El control de exceso
y la comparación siguen midiendo la necesidad."""
from collections import defaultdict

from odoo import api, fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    construction_sheet_need = fields.Float(
        string='Necesidad de tableros (planchas)', digits='Product Unit',
        compute='_compute_construction_sheet')
    construction_sheet_to_deliver = fields.Float(
        string='Planchas a entregar', digits='Product Unit',
        compute='_compute_construction_sheet')
    construction_sheet_rounding = fields.Float(
        string='Redondeo a plancha entera', digits='Product Unit',
        compute='_compute_construction_sheet')

    @api.depends('move_raw_ids.construction_need_qty', 'move_raw_ids.product_uom_qty',
                 'move_raw_ids.state')
    def _compute_construction_sheet(self):
        for production in self:
            need = deliver = covered = 0.0
            for move in production.move_raw_ids.filtered('construction_need_qty'):
                uom = move.product_id.uom_id
                need += move.product_uom._compute_quantity(
                    move.construction_need_qty, uom, round=False)
                covered += move.product_uom._compute_quantity(
                    move._construction_covered_qty(), uom, round=False)
                if move.state != 'cancel':
                    deliver += move.product_uom._compute_quantity(
                        move.product_uom_qty, uom, round=False)
            production.construction_sheet_need = need
            production.construction_sheet_to_deliver = deliver
            production.construction_sheet_rounding = deliver + covered - need if need else 0.0

    def _construction_whole_moves(self):
        """Componentes indivisibles que se redondean (no los retazos)."""
        self.ensure_one()
        return self.move_raw_ids.filtered(
            lambda m: m.state not in ('done', 'cancel')
            and m.product_id._construction_is_whole(self.company_id)
            and not m._construction_is_remnant())

    def _construction_round_whole_sheets(self):
        for production in self:
            if not production.company_id.construction_whole_sheet:
                continue
            by_product = defaultdict(lambda: self.env['stock.move'])
            for move in production._construction_whole_moves():
                by_product[move.product_id] |= move
            for product, moves in by_product.items():
                uom = product.uom_id
                # 1. Necesidad de cada movimiento; si ya tiene, se conserva
                #    (vuelve a redondear tras un cambio de cantidad o un retazo).
                for move in moves:
                    if not move.construction_need_qty:
                        move.construction_need_qty = move.product_uom_qty
                own = {move: move.product_uom._compute_quantity(
                    move.construction_need_qty, uom, round=False) for move in moves}
                need = sum(own.values())
                covered = sum(move.product_uom._compute_quantity(
                    move._construction_covered_qty(), uom, round=False) for move in moves)
                whole = product._construction_whole_qty(need - covered, production.company_id)
                # 2. Cada movimiento vuelve a su necesidad y la diferencia va
                #    al de mayor necesidad (o se descuenta de él).
                delta = whole - need
                for move in moves.sorted(lambda m: -own[m]):
                    qty = max(own[move] + delta, 0.0)
                    delta -= qty - own[move]
                    new_qty = uom._compute_quantity(qty, move.product_uom, round=False)
                    if move.product_uom.compare(new_qty, move.product_uom_qty):
                        move.product_uom_qty = new_qty
                # 3. En 0: en borrador se dejan (guardan la necesidad); los
                #    confirmados se cancelan.
                moves.filtered(
                    lambda m: m.state != 'draft' and m.product_uom.is_zero(m.product_uom_qty)
                )._action_cancel()

    def _get_consumption_issues(self):
        """El aviso de consumo de Odoo compara con la lista de materiales: la
        plancha entera (y lo que cambian los retazos o las planchas sin tocar)
        no es un desvío si se consume lo que pide la orden."""
        issues = []
        for order, product, consumed, expected in super()._get_consumption_issues():
            moves = order.move_raw_ids.filtered(
                lambda m: m.product_id == product and m.state != 'cancel')
            if moves and all(m.construction_covers_move_id for m in moves):
                continue
            whole = moves.filtered('construction_need_qty')
            if whole and order.product_qty:
                planned = sum(m.product_uom._compute_quantity(
                    m.product_uom_qty, product.uom_id, round=False) for m in whole) \
                    * order.qty_producing / order.product_qty
                if product.uom_id.compare(consumed, planned) == 0:
                    continue
            issues.append((order, product, consumed, expected))
        return issues

    def _update_raw_moves(self, factor):
        """«Cambiar cantidad a producir»: la necesidad se reescala en la misma
        proporción y se vuelve a redondear."""
        for move in self.move_raw_ids.filtered(
                lambda m: m.construction_need_qty and m.state not in ('done', 'cancel')):
            move.construction_need_qty *= factor
        res = super()._update_raw_moves(factor)
        self.filtered(lambda p: p.state != 'draft')._construction_round_whole_sheets()
        return res


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _construction_is_remnant(self):
        """Retazo de un tablero (fase B): no se redondea."""
        self.ensure_one()
        return False

    def _construction_whole_scope(self):
        # El despacho a producción: abastece componentes de una orden.
        return super()._construction_whole_scope() or bool(
            self.move_dest_ids.raw_material_production_id)
