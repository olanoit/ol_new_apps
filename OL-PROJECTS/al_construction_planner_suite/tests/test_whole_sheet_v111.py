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
            # Con aviso de consumo, como las listas de Allcenter.
            'consumption': 'warning',
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

    def test_mark_done_without_consumption_warning(self):
        """La plancha entera no es un desvío de la lista de materiales."""
        production = self._production([(self.board, 7.2)])
        picking = self._dispatch_qty(production)[1].picking_id
        picking.action_assign()
        picking.move_ids.picked = True
        picking.button_validate()
        with Form(production) as form:
            form.qty_producing = 1.0
        self.assertIs(production.button_mark_done(), True)
        self.assertEqual(production.state, 'done')
        self.assertEqual(self._board_moves(production).quantity, 8.0)

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
class TestRemnantV111(TestWholeSheetV111):
    """Fase B: cubrir con retazo, quitarlo y declarar sobrantes (casos 12 a
    16 y criterios de la fase B)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        category = cls.env['product.category'].create({
            'name': 'Tableros (test)', 'property_cost_method': 'average'})
        (cls.board | cls.kitchen).categ_id = category
        cls.board.default_code = '3101508'
        cls.board.product_tmpl_id.action_construction_create_remnant()
        cls.remnant_tmpl = cls.board.construction_remnant_tmpl_id
        cls.pool = cls.env['stock.location'].create({
            'name': 'Retazos (test)', 'usage': 'internal',
            'location_id': cls.warehouse.lot_stock_id.id, 'construction_remnant_pool': True})
        cls.warehouse.construction_remnant_location_id = cls.pool
        cls.r25 = cls.board._construction_remnant_variant('r25')
        cls.lot = cls.env['stock.lot'].create({
            'name': '3101508-R25-1200x900-0001', 'product_id': cls.r25.id,
            'company_id': cls.company.id,
            'construction_length_mm': 1200, 'construction_width_mm': 900})
        cls.env['stock.quant']._update_available_quantity(cls.r25, cls.pool, 1, lot_id=cls.lot)

    def _cover(self, production):
        dispatch = self._dispatch_qty(production)[1]
        self.assertTrue(dispatch.construction_can_cover)
        dispatch.action_construction_cover_remnant()
        wizard = self.env['construction.remnant.cover.wizard'].with_context(
            default_move_id=dispatch.id).create({})
        self.assertAlmostEqual(wizard.fraction_to_cover, 0.2)
        self.assertAlmostEqual(wizard.area_to_cover_m2, 1.04, places=2)
        self.assertEqual(wizard.line_ids.lot_id, self.lot)
        wizard.line_ids.selected = True
        with self.assertRaises(UserError):
            wizard.action_assign()
        wizard.fit_confirmed = True
        wizard.action_assign()
        return dispatch

    def test_remnant_variants(self):
        self.assertTrue(self.remnant_tmpl.construction_is_remnant)
        self.assertEqual(self.remnant_tmpl.tracking, 'lot')
        self.assertEqual(sorted(self.remnant_tmpl.product_variant_ids.mapped(
            'construction_remnant_band')), ['r25', 'r50', 'r75', 'r99'])
        self.assertAlmostEqual(self.lot.construction_area_m2, 1.08)
        self.assertAlmostEqual(self.lot.construction_sheet_pct, 20.7, places=1)
        self.assertEqual(self.lot.construction_band, 'r25')

    # 12 y criterio B1
    def test_cover_with_remnant(self):
        production = self._production([(self.board, 7.2)])
        dispatch = self._cover(production)
        board_move = self._board_moves(production)
        self.assertEqual(board_move.product_uom_qty, 7.0)
        self.assertAlmostEqual(board_move.construction_covered_qty, 0.21)
        self.assertEqual(dispatch.product_uom_qty, 7.0)
        remnant_pick = dispatch.picking_id.move_ids.filtered(lambda m: m.product_id == self.r25)
        self.assertEqual(remnant_pick.move_line_ids.lot_id, self.lot)
        self.assertEqual(remnant_pick.quantity, 1.0)
        remnant_raw = production.move_raw_ids.filtered(lambda m: m.product_id == self.r25)
        self.assertEqual(remnant_raw.construction_covers_move_id, board_move)
        self.assertIn(self.lot.name, production.message_ids[0].body)
        # 7 + 0.21 − 7.2 = 0.01 (ejemplo de la sección 7.4).
        self.assertAlmostEqual(production.construction_sheet_rounding, 0.01)

    # 13
    def test_remove_remnant(self):
        production = self._production([(self.board, 7.2)])
        dispatch = self._cover(production)
        remnant_pick = dispatch.picking_id.move_ids.filtered(lambda m: m.product_id == self.r25)
        remnant_pick.action_construction_remove_remnant()
        self.assertEqual(self._board_moves(production).product_uom_qty, 8.0)
        self.assertEqual(self._dispatch_qty(production)[0], 8.0)
        quant = self.env['stock.quant'].search([('lot_id', '=', self.lot.id),
                                                ('location_id', '=', self.pool.id)])
        self.assertEqual(quant.reserved_quantity, 0.0)

    def _closing(self, production, untouched=0, remnants=()):
        action = production.action_construction_cut_closing()
        wizard = self.env['construction.cut.closing.wizard'].with_context(
            action['context']).create({})
        line = wizard.line_ids
        line.untouched_sheets = untouched
        line.remnant_ids = [Command.create({'length_mm': length, 'width_mm': width, 'qty': qty})
                            for length, width, qty in remnants]
        return wizard, line

    # 14 y criterios B2 y B3
    def test_declare_leftovers(self):
        production = self._production([(self.board, 7.2)])
        picking = self._dispatch_qty(production)[1].picking_id
        picking.action_assign()
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        wizard, line = self._closing(production, untouched=1, remnants=[(1830, 1200, 1)])
        self.assertEqual(line.delivered_sheets, 8.0)
        self.assertAlmostEqual(line.pieces_area_m2, 7.2 * 5.2216, places=2)
        self.assertEqual(line.remnant_ids.band, 'r50')
        # Con las piezas de la necesidad no cabe una plancha sin tocar.
        self.assertFalse(line.balance_ok)
        # Área de piezas del despiece (ilustrativa, P8): 33.20 m².
        line.pieces_area_m2 = 33.2
        self.assertTrue(line.balance_ok)
        self.assertAlmostEqual(line.scrap_area_m2, 8 * 5.2216 - 33.2 - 2.196 - 5.2216, places=1)
        wizard.action_confirm()
        self.assertTrue(production.construction_cut_closed)
        self.assertEqual(self._board_moves(production).product_uom_qty, 7.0)
        returned = self.env['stock.picking'].search([
            ('return_id', '=', picking.id)])
        self.assertEqual(returned.move_ids.product_uom_qty, 1.0)
        r50 = self.board._construction_remnant_variant('r50')
        remnant_move = production.move_finished_ids.filtered(lambda m: m.product_id == r50)
        lot = remnant_move.move_line_ids.lot_id
        self.assertRegex(lot.name, r'^3101508-R50-1830x1200-\d{4}$')
        self.assertEqual(lot.construction_origin_production_id, production)
        cost = 1.83 * 1.2 * 150.0 / 5.2216
        self.assertAlmostEqual(remnant_move.construction_fixed_cost, cost, places=2)
        closing = production.construction_cut_closing_ids
        self.assertEqual(closing.untouched_sheets, 1)
        self.assertAlmostEqual(closing.remnant_area_m2, 2.196, places=3)
        # Terminar: el retazo sale a su costo y las piezas llevan el resto.
        with Form(production) as form:
            form.qty_producing = 1.0
        production.button_mark_done()
        self.assertEqual(production.state, 'done')
        remnant_move = production.move_finished_ids.filtered(lambda m: m.product_id == r50)
        main = production.move_finished_ids.filtered(lambda m: m.product_id == self.kitchen)
        consumed = sum(production.move_raw_ids.filtered(lambda m: m.state == 'done').mapped('value'))
        self.assertAlmostEqual(remnant_move.value, cost, places=1)
        self.assertAlmostEqual(main.value + remnant_move.value, consumed, places=1)

    def test_remnant_destination_by_band(self):
        """Pool con sububicaciones por banda (Retazos General/R25…)."""
        general = self.env['stock.location'].create({
            'name': 'Retazos General (test)', 'usage': 'view',
            'location_id': self.warehouse.view_location_id.id})
        r50 = self.env['stock.location'].create({
            'name': 'R50', 'usage': 'internal', 'location_id': general.id,
            'construction_remnant_pool': True})
        self.warehouse.construction_remnant_location_id = general
        self.assertEqual(self.warehouse._construction_remnant_destination('r50'), r50)
        with self.assertRaisesRegex(UserError, 'R25'):
            self.warehouse._construction_remnant_destination('r25')

    # 15
    def test_declare_more_than_delivered(self):
        production = self._production([(self.board, 7.2)])
        wizard, line = self._closing(production, untouched=0,
                                     remnants=[(2440, 2140, 1), (2000, 1000, 1)])
        self.assertFalse(line.balance_ok)
        with self.assertRaisesRegex(UserError, 'supera lo entregado'):
            wizard.action_confirm()

    # 16
    def test_closing_required_blocks_done(self):
        self.company.construction_cut_closing_required = True
        production = self._production([(self.board, 1.0)])
        with self.assertRaisesRegex(UserError, 'Declare los sobrantes'):
            production.button_mark_done()


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
for _name in dir(TestWholeSheetV111):
    if _name.startswith('test_') and callable(getattr(TestWholeSheetV111, _name)) \
            and _name not in vars(TestRemnantV111):
        setattr(TestRemnantV111, _name, None)
for _name in dir(TestProductionExcess):
    if _name.startswith('test_') and callable(getattr(TestProductionExcess, _name)) \
            and _name not in vars(TestWholeSheetVersusV111):
        setattr(TestWholeSheetVersusV111, _name, None)
