# -*- coding: utf-8 -*-
"""Paquete 1.11, verificación del 23-oct (M111-13 a M111-18) y opciones de
planchas y retazos (M111-19 D)."""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from .test_whole_sheet_v111 import TestRemnantV111, TestWholeSheetV111


@tagged('post_install', '-at_install')
class TestPackage111Observations(TestRemnantV111):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.board2 = cls.env['product.product'].create({
            'name': 'Melamina MDP roble 18 mm (test)', 'is_storable': True,
            'default_code': '3101522', 'uom_id': cls.uom_sheet.id, 'standard_price': 160.0,
            'categ_id': cls.board.categ_id.id})
        cls.env['stock.quant']._update_available_quantity(cls.board2, cls.stock, 10)

    def _cover_lot(self, dispatch, lot=None, fit=True):
        wizard = self.env['construction.remnant.cover.wizard'].with_context(
            default_move_id=dispatch.id).create({})
        wizard.line_ids.filtered(lambda l: l.lot_id == (lot or self.lot)).selected = True
        wizard.fit_confirmed = fit
        wizard.action_assign()
        return wizard

    def _validate_dispatch(self, production):
        picking = production.move_raw_ids.move_orig_ids.filtered(
            lambda m: m.state != 'cancel').picking_id
        picking.action_assign()
        picking.move_ids.picked = True
        picking.button_validate()
        return picking

    # M111-13: la fracción escrita sin marcar «Recogido» también se detiene.
    def test_fraction_without_picked(self):
        production = self._production([(self.board, 7.2)])
        dispatch = self._dispatch_qty(production)[1]
        dispatch.picking_id.action_assign()
        dispatch.move_line_ids.quantity = 3.5
        self.assertFalse(dispatch.picked)
        with self.assertRaisesRegex(UserError, 'planchas enteras: 3.50'):
            dispatch.picking_id.button_validate()

    # M111-14: el jefe de producción declara sin ser administrador, también
    # con un tablero cuyo producto retazo aún no existe.
    def test_cut_closing_as_production_user(self):
        head = new_test_user(self.env, 'jefe_corte_test',
                             groups='mrp.group_mrp_user,stock.group_stock_user')
        self.assertFalse(self.board2.construction_remnant_tmpl_id)
        production = self._production([(self.board2, 2.2)])
        self._validate_dispatch(production)
        action = production.with_user(head).action_construction_cut_closing()
        wizard = self.env['construction.cut.closing.wizard'].with_user(head).with_context(
            action['context']).create({})
        line = wizard.line_ids
        line.pieces_area_m2 = 8.0
        line.untouched_sheets = 1
        line.remnant_ids = [Command.create({'length_mm': 1830, 'width_mm': 1200, 'qty': 1})]
        self.assertTrue(line.balance_ok)
        wizard.action_confirm()
        self.assertTrue(production.construction_cut_closed)
        self.assertTrue(self.board2.construction_remnant_tmpl_id)
        self.assertEqual(production.construction_cut_closing_ids.declared_by, head)
        self.assertIn('corrigió las piezas de [3101522]', production.message_ids[0].body)

    # M111-15: el retazo no es material sin presupuesto.
    def test_remnant_out_of_component_qty(self):
        production = self._production([(self.board, 7.2)])
        self._cover_lot(self._dispatch_qty(production)[1])
        qty = production._construction_component_qty()
        self.assertNotIn(self.r25, qty)
        self.assertAlmostEqual(qty[self.board], 7.2)

    # M111-16: un retazo que cubre todo el tablero no cancela la plancha.
    def test_board_fully_covered(self):
        production = self._production([(self.board, 0.16)])
        dispatch = self._dispatch_qty(production)[1]
        self._cover_lot(dispatch)
        board_move = self._board_moves(production)
        self.assertNotEqual(board_move.state, 'cancel')
        self.assertEqual(board_move.product_uom_qty, 0.0)
        self.assertEqual(self._dispatch_qty(production)[0], 0.0)
        wizard = self.env['construction.cut.closing.wizard'].with_context(
            production.action_construction_cut_closing()['context']).create({})
        self.assertEqual(wizard.line_ids.product_id, self.board)
        self.assertAlmostEqual(wizard.line_ids.delivered_area_m2, 1.08, places=2)
        remnant_pick = dispatch.picking_id.move_ids.filtered(lambda m: m.product_id == self.r25)
        remnant_pick.action_construction_remove_remnant()
        self.assertEqual(self._board_moves(production).product_uom_qty, 1.0)
        self.assertEqual(self._dispatch_qty(production)[0], 1.0)

    # M111-17: los tableros sin entregar se declaran cuando lleguen.
    def test_undelivered_board(self):
        empty = self.env['product.product'].create({
            'name': 'Melamina sin stock (test)', 'is_storable': True,
            'uom_id': self.uom_sheet.id, 'categ_id': self.board.categ_id.id})
        self.company.construction_cut_closing_required = True
        production = self._production([(self.board, 7.2), (empty, 1.5)])
        self._dispatch_qty(production)[1].picking_id.action_assign()
        wizard = self.env['construction.cut.closing.wizard'].with_context(
            production.action_construction_cut_closing()['context']).create({})
        undelivered = wizard.line_ids.filtered('undelivered')
        self.assertEqual(undelivered.product_id, empty)
        self.assertTrue(undelivered.balance_ok)
        self.assertIn('Sin entregar', undelivered.balance_text)
        wizard.action_confirm()
        self.assertEqual(production.construction_cut_closing_ids.product_id, self.board)
        self.assertFalse(production.construction_cut_closed)
        self.assertIn('Sin entregar', production.message_ids[0].body)
        again = self.env['construction.cut.closing.wizard'].with_context(
            production.action_construction_cut_closing()['context']).create({})
        self.assertEqual(again.line_ids.product_id, empty)
        with self.assertRaisesRegex(UserError, 'se declaran cuando'):
            again.action_confirm()

    # M111-18, 3: tablero sin área.
    def test_cut_closing_without_area(self):
        self.edge.construction_indivisible_mode = 'yes'
        production = self._production([(self.edge, 2.5)])
        with self.assertRaisesRegex(UserError, 'no tiene área'):
            production.action_construction_cut_closing()

    # M111-18, 4: cambiar la cantidad no duplica el retazo.
    def test_change_quantity_keeps_remnant(self):
        production = self._production([(self.board, 7.2)])
        dispatch = self._dispatch_qty(production)[1]
        self._cover_lot(dispatch)
        self.env['change.production.qty'].create({
            'mo_id': production.id, 'product_qty': 2.0}).change_prod_qty()
        remnant_raw = production.move_raw_ids.filtered(lambda m: m.product_id == self.r25)
        self.assertEqual(remnant_raw.product_uom_qty, 1.0)
        remnant_picks = production.move_raw_ids.move_orig_ids.filtered(
            lambda m: m.product_id == self.r25 and m.state != 'cancel')
        self.assertEqual(sum(remnant_picks.mapped('product_uom_qty')), 1.0)

    # M111-19 D
    def test_cut_closing_tolerance(self):
        production = self._production([(self.board, 7.2)])
        self._validate_dispatch(production)
        wizard, line = self._closing(production)
        line.pieces_area_m2 = line.delivered_area_m2 * 1.008
        self.assertFalse(line.balance_ok)
        self.company.construction_cut_closing_tolerance = 1.0
        wizard, line = self._closing(production)
        line.pieces_area_m2 = line.delivered_area_m2 * 1.008
        self.assertTrue(line.balance_ok)

    def test_pieces_not_editable(self):
        self.company.construction_cut_closing_edit_pieces = False
        production = self._production([(self.board, 7.2)])
        wizard, _line = self._closing(production)
        self.assertFalse(wizard.edit_pieces)

    def test_remnant_lot_pattern(self):
        self.company.construction_remnant_lot_pattern = '{orden}-{codigo}-{banda}-{numero}'
        with self.assertRaises(Exception):
            self.company.construction_remnant_lot_pattern = '{obra}-{color}'
        production = self._production([(self.board, 7.2)])
        self._validate_dispatch(production)
        wizard, line = self._closing(production, remnants=[(1830, 1200, 1)])
        line.pieces_area_m2 = 30.0
        wizard.action_confirm()
        r50 = self.board._construction_remnant_variant('r50')
        lot = production.move_finished_ids.filtered(
            lambda m: m.product_id == r50).move_line_ids.lot_id
        self.assertRegex(lot.name, r'^%s-3101508-R50-\d{4}$' % production.name)

    def test_fit_not_required(self):
        self.company.construction_remnant_fit_required = False
        production = self._production([(self.board, 7.2)])
        wizard = self._cover_lot(self._dispatch_qty(production)[1], fit=False)
        self.assertFalse(wizard.fit_required)
        self.assertAlmostEqual(self._board_moves(production).construction_covered_qty, 0.21)

    def test_scope_production_off(self):
        self.company.construction_whole_sheet_production = False
        production = self._production([(self.board, 7.2)])
        self.assertAlmostEqual(self._board_moves(production).product_uom_qty, 7.2)
        self.assertFalse(self._dispatch_qty(production)[1]._construction_whole_controlled())

    def test_scope_purchase_off(self):
        uom = self.uom_sheet
        self.assertEqual(self.board._construction_purchase_qty(3.7, uom, self.company), 4.0)
        self.company.construction_whole_sheet_purchase = False
        self.assertAlmostEqual(self.board._construction_purchase_qty(3.7, uom, self.company), 3.7)
        # El despacho a producción sigue en enteros.
        production = self._production([(self.board, 7.2)])
        self.assertEqual(self._board_moves(production).product_uom_qty, 8.0)

    # M111-18, 2: la compra redondea en planchas y luego convierte.
    def test_purchase_rounds_in_product_uom(self):
        square_meter = self.env.ref('uom.product_uom_square_meter')
        qty = self.board._construction_purchase_qty(3.7, square_meter, self.company)
        self.assertAlmostEqual(qty, 4 * 5.2216, places=3)


# Las pruebas heredadas ya corren en su clase.
for _name in dir(TestRemnantV111):
    if _name.startswith('test_') and callable(getattr(TestRemnantV111, _name)) \
            and _name not in vars(TestPackage111Observations):
        setattr(TestPackage111Observations, _name, None)
for _name in dir(TestWholeSheetV111):
    if _name.startswith('test_') and _name not in vars(TestPackage111Observations):
        setattr(TestPackage111Observations, _name, None)
