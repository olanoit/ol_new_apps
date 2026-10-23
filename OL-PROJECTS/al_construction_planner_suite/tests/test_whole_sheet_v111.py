# -*- coding: utf-8 -*-
"""Requerimiento al almacén en planchas enteras (paquete 1.11, M111-12, fase A).

Casos de la sección 12 del requerimiento: la orden de corte guarda la
necesidad en fracción y pide planchas enteras al confirmar; el despacho a
producción nace en enteros, la reserva y lo validado son enteros, y el
control de exceso sigue midiendo la necesidad."""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, tagged

from .test_production_excess_v19 import TestProductionExcess


@tagged('post_install', '-at_install')
class TestWholeSheetV111(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'construction_whole_sheet': True,
                           'construction_whole_sheet_tolerance': 0.0})
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        cls.warehouse.manufacture_steps = 'pbm'
        square_meter = cls.env.ref('uom.product_uom_square_meter')
        cls.uom_sheet = cls.env['uom.uom'].create({
            'name': 'Plancha 2.14×2.44 m (test)', 'relative_factor': 5.2216,
            'relative_uom_id': square_meter.id, 'construction_whole_sheet': True})
        Product = cls.env['product.product']
        cls.board = Product.create({
            'name': 'Melamina MDP blanco fantasía 18 mm (test)', 'is_storable': True,
            'uom_id': cls.uom_sheet.id, 'standard_price': 150.0})
        cls.edge = Product.create({
            'name': 'Tapacanto delgado blanco (test)', 'is_storable': True,
            'uom_id': cls.env.ref('uom.product_uom_meter').id})
        cls.kitchen = Product.create({'name': 'Cocina C07 (test)', 'is_storable': True})
        cls.stock = cls.warehouse.lot_stock_id
        cls.env['stock.quant']._update_available_quantity(cls.board, cls.stock, 40)
        cls.env['stock.quant']._update_available_quantity(cls.edge, cls.stock, 500)

    def _bom(self, lines, product=None):
        return self.env['mrp.bom'].create({
            'product_tmpl_id': (product or self.kitchen).product_tmpl_id.id,
            'product_qty': 1.0,
            'bom_line_ids': [Command.create({'product_id': p.id, 'product_qty': qty})
                             for p, qty in lines],
        })

    def _production(self, lines, product=None):
        bom = self._bom(lines, product)
        form = Form(self.env['mrp.production'])
        form.product_id = product or self.kitchen
        form.bom_id = bom
        production = form.save()
        production.action_confirm()
        return production

    def _board_moves(self, production):
        return production.move_raw_ids.filtered(lambda m: m.product_id == self.board)

    def _dispatch_qty(self, production):
        moves = self._board_moves(production).move_orig_ids.filtered(
            lambda m: m.state != 'cancel')
        return sum(moves.mapped('product_uom_qty')), moves

    # 1, 6 y P4
    def test_whole_sheet_on_confirm(self):
        production = self._production([(self.board, 7.2), (self.edge, 138.33)])
        move = self._board_moves(production)
        self.assertEqual(move.construction_need_qty, 7.2)
        self.assertEqual(move.product_uom_qty, 8.0)
        self.assertAlmostEqual(move.construction_rounding_qty, 0.8)
        qty, dispatch = self._dispatch_qty(production)
        self.assertEqual(qty, 8.0)
        self.assertEqual(dispatch.picking_type_id, self.warehouse.pbm_type_id)
        self.assertAlmostEqual(sum(dispatch.mapped('construction_need_display')), 7.2)
        self.assertAlmostEqual(production.construction_sheet_need, 7.2)
        self.assertEqual(production.construction_sheet_to_deliver, 8.0)
        self.assertAlmostEqual(production.construction_sheet_rounding, 0.8)
        # El tapacanto en metros no cambia.
        edge = production.move_raw_ids.filtered(lambda m: m.product_id == self.edge)
        self.assertEqual(edge.product_uom_qty, 138.33)
        self.assertFalse(edge.construction_need_qty)
        # P10: la impresión del despacho muestra necesidad y redondeo.
        html = self.env['ir.actions.report']._render_qweb_html(
            'stock.action_report_picking', dispatch.picking_id.ids)[0].decode()
        self.assertIn('Necesidad', html)
        self.assertIn('Redondeo', html)

    # 2
    def test_switch_off_keeps_fraction(self):
        self.company.construction_whole_sheet = False
        production = self._production([(self.board, 7.2)])
        move = self._board_moves(production)
        self.assertEqual(move.product_uom_qty, 7.2)
        self.assertFalse(move.construction_need_qty)
        self.assertEqual(self._dispatch_qty(production)[0], 7.2)

    # 3
    def test_two_lines_same_board(self):
        production = self._production([(self.board, 3.14), (self.board, 0.5)])
        moves = self._board_moves(production).sorted('construction_need_qty')
        self.assertEqual(moves.mapped('construction_need_qty'), [0.5, 3.14])
        self.assertEqual(moves.mapped('product_uom_qty'), [0.5, 3.5])
        self.assertEqual(self._dispatch_qty(production)[0], 4.0)

    # 4 y 5
    def test_whole_need_and_tolerance(self):
        production = self._production([(self.board, 1.0)])
        move = self._board_moves(production)
        self.assertEqual(move.product_uom_qty, 1.0)
        self.assertEqual(move.construction_rounding_qty, 0.0)
        self.company.construction_whole_sheet_tolerance = 0.1
        production = self._production([(self.board, 3.08)])
        move = self._board_moves(production)
        self.assertEqual(move.product_uom_qty, 3.0)
        self.assertAlmostEqual(move.construction_rounding_qty, -0.08)

    # 8
    def test_order_created_by_procurement(self):
        mto = self.env.ref('stock.route_warehouse0_mto')
        mto.active = True
        manufacture = self.env.ref('mrp.route_warehouse0_manufacture')
        package = self.env['product.product'].create({
            'name': 'Paquete de piezas C07 (test)', 'is_storable': True,
            'route_ids': [Command.set((mto | manufacture).ids)]})
        self._bom([(self.board, 7.2)], product=package)
        assembly = self._production([(package, 1.0)])
        cut = self.env['mrp.production'].search([
            ('product_id', '=', package.id), ('state', '=', 'confirmed')], order='id desc',
            limit=1)
        self.assertTrue(cut, assembly.name)
        move = self._board_moves(cut)
        self.assertEqual(move.construction_need_qty, 7.2)
        self.assertEqual(move.product_uom_qty, 8.0)

    # 9
    def test_change_quantity_rescales_need(self):
        production = self._production([(self.board, 7.2)])
        self.env['change.production.qty'].create({
            'mo_id': production.id, 'product_qty': 2.0}).change_prod_qty()
        move = self._board_moves(production)
        self.assertAlmostEqual(move.construction_need_qty, 14.4)
        self.assertEqual(move.product_uom_qty, 15.0)

    # 11 y reserva en enteros (8.3)
    def test_dispatch_in_whole_sheets(self):
        self.env['stock.quant']._update_available_quantity(self.board, self.stock, -32.4)
        self.assertAlmostEqual(self.board.with_context(location=self.stock.id).free_qty, 7.6)
        production = self._production([(self.board, 7.2)])
        dispatch = self._dispatch_qty(production)[1]
        dispatch.picking_id.action_assign()
        self.assertEqual(dispatch.quantity, 7.0, 'con 7.6 libres se reservan 7')
        self.env['stock.quant']._update_available_quantity(self.board, self.stock, 10)
        dispatch.picking_id.action_assign()
        self.assertEqual(dispatch.quantity, 8.0)
        dispatch.quantity = 7.5
        dispatch.picked = True
        with self.assertRaisesRegex(UserError, 'planchas enteras'):
            dispatch.picking_id.button_validate()

    # 18
    def test_unit_product_is_not_indivisible(self):
        self.assertFalse(self.edge.construction_is_indivisible)
        self.assertTrue(self.board.construction_is_indivisible)
        self.assertAlmostEqual(self.board.construction_sheet_area_m2, 5.2216)
        # El producto puede forzar la regla.
        self.edge.construction_indivisible_mode = 'yes'
        self.assertTrue(self.edge.construction_is_indivisible)
        self.board.construction_indivisible_mode = 'no'
        self.assertFalse(self.board.construction_is_indivisible)

    # 17 (8.5): la compra masiva redondeaba solo unidades «enteras»; la
    # plancha tiene referencia m² y ahora redondea por ser indivisible.
    def test_purchase_rounds_whole_sheets(self):
        Mixin = self.env['construction.plan.supply.mixin']
        self.assertFalse(Mixin._is_whole_uom(self.uom_sheet))
        self.assertTrue(self.board._construction_is_whole(self.company))
        self.assertEqual(self.board._construction_whole_qty(3.7, self.company), 4.0)
        order = self.env['purchase.order'].create({
            'partner_id': self.env['res.partner'].create({'name': 'Proveedor (test)'}).id})
        with Form(order) as form:
            with form.order_line.new() as line:
                line.product_id = self.board
                line.product_qty = 3.7
        self.assertEqual(order.order_line.product_qty, 3.7, 'solo avisa')
        warning = order.order_line._onchange_construction_whole_sheet()
        self.assertIn('se sugiere 4', warning['warning']['message'])


@tagged('post_install', '-at_install')
class TestWholeSheetVersusV111(TestProductionExcess):
    """7: la comparación mide la necesidad; el redondeo va en su columna."""

    def test_versus_uses_need(self):
        self.company.construction_whole_sheet = True
        self.p_white.construction_indivisible_mode = 'yes'
        production = self._production()
        production.action_confirm()
        white = production.construction_versus_ids.filtered(
            lambda r: r.product_id == self.p_white)
        move = self._move(production, self.p_white)
        self.assertEqual(sum(move.mapped('product_uom_qty')), 4.0)
        self.assertAlmostEqual(white.qty_required, white.qty_budget, places=2)
        self.assertFalse(white.change_type)
        self.assertAlmostEqual(white.qty_rounding, 4.0 - white.qty_required, places=2)
        self.assertEqual(production.construction_exceed_state, 'ok')


# Las pruebas heredadas ya corren en su clase.
for _name in dir(TestProductionExcess):
    if _name.startswith('test_') and callable(getattr(TestProductionExcess, _name)) \
            and _name not in vars(TestWholeSheetVersusV111):
        setattr(TestWholeSheetVersusV111, _name, None)
