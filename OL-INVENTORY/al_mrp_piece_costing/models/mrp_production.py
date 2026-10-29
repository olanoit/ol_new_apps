# -*- coding: utf-8 -*-
"""Costeo por medida de la orden de corte (especificación de costeo de piezas
CNC v1.4, §4).

La orden reparte su costo total entre las piezas que produce. Antes del
cálculo nativo (``_cal_price``) se escribe el ``cost_share`` de cada
subproducto, como dato de reporte; después se fija el costo unitario exacto
de cada salida, porque el nativo descarta participaciones menores al 0.005 %
y redondea el residuo del principal (prueba del 23-set-2026 con 1,729
piezas). El producto principal absorbe el residuo.

Bolsas del reparto:

* tapacanto: el valor consumido de los productos marcados como tapacanto, por
  metros de tapacanto de cada pieza;
* una por tablero: su valor consumido, por área, solo entre las piezas
  cortadas de él;
* general: lo demás (mano de obra, costo extra, insumos y tableros sin
  pieza), por área entre todas las salidas."""
from odoo import api, fields, models
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    piece_costing = fields.Boolean(
        string='Costeo por medida', compute='_compute_piece_costing', store=True,
        readonly=False, copy=False,
        help='Reparte el costo de la orden entre las piezas por su área, su tablero y sus '
             'metros de tapacanto. Lo propone el tipo de operación; sin la marca, la orden se '
             'costea como el estándar.')
    piece_currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    piece_total_cost = fields.Monetary(
        string='Costo total de la orden', currency_field='piece_currency_id',
        compute='_compute_piece_balance',
        help='Consumos valorizados, costo de las órdenes de trabajo y costo extra: los mismos '
             'sumandos del cálculo nativo.')
    piece_output_value = fields.Monetary(
        string='Suma de las piezas', currency_field='piece_currency_id',
        compute='_compute_piece_balance')
    piece_balance_diff = fields.Monetary(
        string='Diferencia de cuadre', currency_field='piece_currency_id',
        compute='_compute_piece_balance',
        help='Suma de las piezas menos el costo total. Sale del redondeo por pieza; la '
             'tolerancia es de una unidad de moneda por orden.')
    piece_has_manual_value = fields.Boolean(
        string='Con ajuste manual de valor', compute='_compute_piece_balance',
        help='Hay ajustes manuales de valor sobre movimientos de la orden: priman sobre el '
             'reparto y explican una diferencia de cuadre.')
    piece_manual_value_detail = fields.Text(
        string='Ajustes manuales', compute='_compute_piece_balance')

    @api.depends('picking_type_id')
    def _compute_piece_costing(self):
        for production in self:
            production.piece_costing = production.picking_type_id.piece_costing_default

    # ------------------------------------------------------------------
    # Reparto
    # ------------------------------------------------------------------
    def _piece_costing_active(self):
        self.ensure_one()
        # La subcontratación fija su costo con mrp_subcontracting_account.
        return self.piece_costing and not (
            'subcontractor_id' in self._fields and self.subcontractor_id)

    def _piece_output_moves(self):
        """Salidas que entran al reparto, con el filtro del cálculo nativo.
        Las de costo fijo (retazos) van aparte."""
        self.ensure_one()
        return self.move_finished_ids.filtered(
            lambda m: m.state not in ('done', 'cancel')
            and m.uom_id.compare(m.quantity, 0) > 0
            and not m.construction_fixed_cost)

    def _piece_fixed_moves(self):
        """Retazos declarados (paquete 1.11, M111-12): su costo es el área
        por el costo de la plancha y se descuenta antes del reparto."""
        self.ensure_one()
        return self.move_finished_ids.filtered(
            lambda m: m.state not in ('done', 'cancel')
            and m.uom_id.compare(m.quantity, 0) > 0
            and m.construction_fixed_cost)

    @staticmethod
    def _piece_product_qty(move):
        return move.uom_id._compute_quantity(move.quantity, move.product_id.uom_id)

    def _piece_measures(self, move):
        """(área, tapacanto) del movimiento: medida de una pieza por cantidad."""
        qty = self._piece_product_qty(move)
        product = move.product_id
        return product.piece_area_m2 * qty, product.piece_edge_ml * qty

    def _cal_price(self, consumed_moves):
        costs = {}
        if self._piece_costing_active():
            costs = self._piece_compute_costs(consumed_moves)
        res = super()._cal_price(consumed_moves)
        if costs:
            self._piece_set_unit_prices(costs)
        return res

    def _piece_set_unit_prices(self, costs):
        """Costo unitario exacto de cada salida: el kárdex toma quantity ×
        price_unit (``_get_value_from_production``). Solo en costo promedio o
        FIFO, igual que el nativo."""
        for move, cost in costs.items():
            if move.product_id.cost_method not in ('fifo', 'average'):
                continue
            qty = self._piece_product_qty(move)
            if qty:
                move.price_unit = cost / qty

    def _piece_compute_costs(self, consumed_moves):
        """Escribe el ``cost_share`` de los subproductos y devuelve {movimiento:
        costo} de todas las salidas, principal incluido."""
        self.ensure_one()
        outputs = self._piece_output_moves()
        main = outputs.filtered(lambda m: m.product_id == self.product_id)
        byproducts = outputs - main
        fixed = self._piece_fixed_moves()
        if not byproducts and not fixed:
            return {}

        # Costo total con los sumandos del nativo (en Enterprise, _cal_cost de
        # la orden de trabajo ya incluye la mano de obra de los empleados).
        main_qty = sum(self._piece_product_qty(m) for m in main)
        total_cost = (sum(m.value for m in consumed_moves)
                      + sum(wo._cal_cost() for wo in self.workorder_ids)
                      + self.extra_cost * main_qty)
        measures = {move: self._piece_measures(move) for move in outputs}
        total_area = sum(area for area, _edge in measures.values())
        total_edge = sum(edge for _area, edge in measures.values())
        # Sin costo o sin área, el reparto no interviene: sigue el nativo.
        if self.company_id.currency_id.is_zero(total_cost) or total_area <= 0:
            return {}

        edge_pool = sum(m.value for m in consumed_moves if m.product_id.piece_is_edge_banding)
        if total_edge <= 0:
            # Hay tapacanto consumido pero ninguna pieza declara metros: va a
            # la bolsa general para no perder costo.
            edge_pool = 0.0
        area_by_material = {}
        for move in outputs:
            material = move.product_id.piece_material_id
            if material:
                area_by_material[material] = area_by_material.get(material, 0.0) \
                    + measures[move][0]
        material_pools = {}
        for move in consumed_moves:
            product = move.product_id
            if not product.piece_is_edge_banding and area_by_material.get(product):
                material_pools[product] = material_pools.get(product, 0.0) + move.value
        # Los retazos salen del valor de su tablero (o de la bolsa general si
        # ninguna pieza se corta de él) y no entran al reparto.
        fixed_costs = {move: move.construction_fixed_cost for move in fixed}
        for move, cost in fixed_costs.items():
            board = move.product_id.construction_remnant_source_tmpl_id.product_variant_id
            if board in material_pools:
                material_pools[board] -= cost
        total_cost -= sum(fixed_costs.values())
        general_pool = total_cost - edge_pool - sum(material_pools.values())

        def cost_of(move):
            area, edge = measures[move]
            material = move.product_id.piece_material_id
            cost = general_pool * area / total_area
            if material in material_pools:
                cost += material_pools[material] * area / area_by_material[material]
            if total_edge:
                cost += edge_pool * edge / total_edge
            return cost

        costs = {}
        full_cost = total_cost + sum(fixed_costs.values())
        for move, cost in fixed_costs.items():
            costs[move] = cost
            move.cost_share = cost / full_cost * 100
        for move in byproducts:
            costs[move] = cost_of(move)
            # Dato de reporte: el valor lo fija _piece_set_unit_prices. Suma
            # menos de 100 porque el principal tiene área (se valida al
            # confirmar), así que _check_byproducts no se dispara.
            move.cost_share = costs[move] / full_cost * 100
        assigned = sum(cost for move, cost in costs.items() if move not in fixed_costs)
        for move in main:
            costs[move] = (total_cost - assigned) * self._piece_product_qty(move) / (main_qty or 1.0)
        return costs

    # ------------------------------------------------------------------
    # Cuadre de la orden cerrada
    # ------------------------------------------------------------------
    @api.depends('state', 'piece_costing', 'extra_cost', 'move_raw_ids.value',
                 'move_finished_ids.value')
    def _compute_piece_balance(self):
        # Los ajustes manuales de valor son de Contabilidad: se leen solo
        # para avisar en la orden.
        ManualValue_sudo = self.env['product.value'].sudo()
        for production in self:
            values = dict.fromkeys(
                ('piece_total_cost', 'piece_output_value', 'piece_balance_diff'), 0.0)
            values.update(piece_has_manual_value=False, piece_manual_value_detail=False)
            if production.piece_costing and production.state == 'done':
                consumed = production.move_raw_ids.filtered(lambda m: m.state == 'done')
                outputs = production.move_finished_ids.filtered(lambda m: m.state == 'done')
                main_qty = sum(production._piece_product_qty(m) for m in outputs
                               if m.product_id == production.product_id)
                total = (sum(consumed.mapped('value'))
                         + sum(wo._cal_cost() for wo in production.workorder_ids)
                         + production.extra_cost * main_qty)
                output_value = sum(outputs.mapped('value'))
                adjustments = ManualValue_sudo.search(
                    [('move_id', 'in', (consumed | outputs).ids)], order='date desc')
                values.update(
                    piece_total_cost=total, piece_output_value=output_value,
                    piece_balance_diff=output_value - total,
                    piece_has_manual_value=bool(adjustments),
                    piece_manual_value_detail='\n'.join(self.env._(
                        '%(product)s: valor ajustado a %(value)s por %(user)s el %(date)s',
                        product=adjustment.move_id.product_id.display_name,
                        value=adjustment.company_id.currency_id.format(adjustment.value),
                        user=adjustment.user_id.name, date=adjustment.date)
                        for adjustment in adjustments) or False)
            production.update(values)

    # ------------------------------------------------------------------
    # Controles
    # ------------------------------------------------------------------
    def _get_backorder_mo_vals(self):
        # Toda orden pendiente pasa por aquí.
        if self._piece_costing_active():
            raise UserError(self.env._(
                'La orden %s se costea por medida y no admite entregas parciales: ciérrela con '
                'las cantidades producidas y lleve lo no cortado a una orden nueva.',
                self.display_name))
        return super()._get_backorder_mo_vals()

    def action_confirm(self):
        res = super().action_confirm()
        self.filtered('piece_costing')._piece_check_order()
        return res

    def _piece_check_order(self):
        for production in self:
            # Un kit trae su propio line_cost_share y desarma el reparto.
            kits = production.move_raw_ids.filtered(
                lambda m: m.bom_line_id.bom_id.type == 'phantom')
            if kits:
                raise UserError(self.env._(
                    'La orden %(production)s se costea por medida y tiene componentes de una '
                    'lista de materiales tipo kit (%(products)s): use los componentes sueltos.',
                    production=production.display_name,
                    products=', '.join(kits.product_id.mapped('display_name'))))
            outputs = production._piece_output_moves()
            # Sin área la pieza entraría al kárdex en cero.
            without_area = outputs.filtered(lambda m: m.product_id.piece_area_m2 <= 0)
            if without_area:
                raise UserError(self.env._(
                    'La orden %(production)s se costea por medida pero estas piezas no tienen '
                    'área: %(products)s. Complete el producto desde el despiece.',
                    production=production.display_name,
                    products=', '.join(without_area.product_id.mapped('display_name'))))
            # El tablero de la pieza tiene que estar entre los componentes; si
            # no, su costo sale solo de la bolsa general.
            missing = outputs.product_id.piece_material_id - production.move_raw_ids.product_id
            if missing:
                raise UserError(self.env._(
                    'La orden %(production)s se costea por medida pero no consume el tablero de '
                    'algunas piezas: %(materials)s. Agréguelo a los componentes o corrija el '
                    'tablero de las piezas.',
                    production=production.display_name,
                    materials=', '.join(missing.mapped('display_name'))))
