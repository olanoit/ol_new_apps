# -*- coding: utf-8 -*-
"""Paquete 1.11, versión 3: planchas enteras y retazo en el despacho del
requerimiento (M111-22), reposición a planta (M111-23) y detalles de la
verificación del 24-oct (almacén de la línea y unidad en el idioma del
requerimiento). Las acciones las hacen usuarios sin administración:
Solicitante, Logística y Fabricación: usuario."""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from odoo.addons.al_construction_material_request.tests.test_process import TestProcess


@tagged('post_install', '-at_install')
class TestPackage111V3Request(TestProcess):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.write({'construction_whole_sheet': True,
                           'construction_whole_sheet_tolerance': 0.0})
        cls.warehouse.manufacture_steps = 'pbm'
        square_meter = cls.env.ref('uom.product_uom_square_meter')
        uom_sheet = cls.env['uom.uom'].create({
            'name': 'Plancha 2.14×2.44 m (test v3)', 'relative_factor': 5.2216,
            'relative_uom_id': square_meter.id, 'construction_whole_sheet': True})
        category = cls.env['product.category'].create({
            'name': 'Tableros (test v3)', 'property_cost_method': 'average'})
        cls.board = cls.env['product.product'].create({
            'name': 'Melamina blanco fantasía 18 mm (test v3)', 'is_storable': True,
            'uom_id': uom_sheet.id, 'standard_price': 150.0, 'default_code': '3101508',
            'categ_id': category.id})
        cls.board.product_tmpl_id.action_construction_create_remnant()
        cls.pool = cls.env['stock.location'].create({
            'name': 'Retazos General (test v3)', 'usage': 'internal',
            'location_id': cls.warehouse.lot_stock_id.id, 'construction_remnant_pool': True})
        cls.r25 = cls.board._construction_remnant_variant('r25')
        cls.lot = cls.env['stock.lot'].create({
            'name': 'ZZ-3101508-R25-1200x900', 'product_id': cls.r25.id,
            'company_id': cls.company.id,
            'construction_length_mm': 1200, 'construction_width_mm': 900})
        cls.env['stock.quant']._update_available_quantity(cls.r25, cls.pool, 1, lot_id=cls.lot)
        cls.stock_user = new_test_user(
            cls.env, 'm11122_almacen',
            groups='stock.group_stock_user,al_construction_material_request.group_construction_logistics',
            name='Almacenero (test v3)')

    def _line(self, request, product):
        return request.line_ids.filtered(lambda l: l.product_id == product)

    def _board_move(self, request):
        return self._dispatch_picking(request).move_ids.filtered(
            lambda m: m.product_id == self.board)

    # M111-22: necesidad y redondeo en los movimientos de la línea indivisible.
    def test_need_on_dispatch_and_pending(self):
        self._set_stock(self.board, self.stock, 10.6)
        request = self._approved_request(lines=[(self.board, 13.3)])
        self._process(request)
        dispatch = self._board_move(request)
        pending = self._pending_picking(request).move_ids
        self.assertEqual(dispatch.product_uom_qty, 10.0)
        self.assertAlmostEqual(dispatch.construction_need_qty, 10.0)
        self.assertAlmostEqual(pending.construction_need_qty, 3.3)
        self.assertAlmostEqual(pending.construction_rounding_qty, 0.7)

    def test_other_products_have_no_need(self):
        self._set_stock(self.cement, self.stock, 200)
        request = self._approved_request()
        self._process(request)
        self.assertFalse(self._dispatch_picking(request).move_ids.construction_need_qty)

    # M111-22: «Cubrir con retazo» en el despacho; la línea cuenta la fracción.
    def _cover(self, request):
        move = self._board_move(request).with_user(self.stock_user)
        self.assertTrue(move.construction_can_cover)
        self.assertIn(self.lot.name, move.construction_remnant_hint)
        wizard = self.env['construction.remnant.cover.wizard'].with_user(
            self.stock_user).with_context(default_move_id=move.id).create({})
        self.assertAlmostEqual(wizard.need_qty, 7.2)
        self.assertAlmostEqual(wizard.fraction_to_cover, 0.2)
        wizard.line_ids.selected = True
        wizard.fit_confirmed = True
        wizard.action_assign()
        return move.with_env(self.env)

    def test_cover_request_dispatch_with_remnant(self):
        self._set_stock(self.board, self.stock, 20)
        request = self._approved_request(lines=[(self.board, 7.2)])
        self._process(request)
        move = self._board_move(request)
        self.assertEqual(move.product_uom_qty, 8.0)
        self.assertAlmostEqual(move.construction_need_qty, 7.2)
        self._cover(request)
        self.assertEqual(move.product_uom_qty, 7.0)
        picking = move.picking_id
        remnant = picking.move_ids.filtered(lambda m: m.product_id == self.r25)
        self.assertEqual(remnant.move_line_ids.lot_id, self.lot)
        line = self._line(request, self.board)
        self.assertAlmostEqual(line.qty_rounding, 0.01, places=2)
        picking.with_user(self.stock_user).move_ids.picked = True
        picking.with_user(self.stock_user).button_validate()
        self.assertEqual(picking.state, 'done')
        # 7 planchas + 0.207 del retazo cubren las 7.2 pedidas.
        self.assertAlmostEqual(line.qty_received_on_site, 7.21, places=2)
        self.assertEqual(line.line_state, 'done')

    def test_remove_remnant_request(self):
        self._set_stock(self.board, self.stock, 20)
        request = self._approved_request(lines=[(self.board, 7.2)])
        self._process(request)
        move = self._cover(request)
        remnant = move.picking_id.move_ids.filtered(lambda m: m.product_id == self.r25)
        remnant.with_user(self.stock_user).action_construction_remove_remnant()
        self.assertEqual(remnant.state, 'cancel')
        self.assertEqual(move.product_uom_qty, 8.0)
        self.assertAlmostEqual(self._line(request, self.board).qty_rounding, 0.8)

    # M111-22: el destino decide el tipo del despacho.
    def test_preproduction_uses_pick_components(self):
        preproduction = self.env['stock.location'].create({
            'name': 'Preproducción (test v3)', 'usage': 'internal',
            'location_id': self.warehouse.view_location_id.id,
            'construction_preproduction': True})
        self._set_stock(self.cement, self.stock, 200)
        request = self._approved_request(lines=[(self.cement, 10), (self.steel, 5)])
        self._line(request, self.cement).location_dest_id = preproduction
        self._set_stock(self.steel, self.stock, 50)
        self._process(request)
        to_plant = request.picking_ids.filtered(lambda p: p.location_dest_id == preproduction)
        to_site = request.picking_ids - to_plant
        self.assertEqual(to_plant.picking_type_id, self.warehouse.pbm_type_id)
        self.assertEqual(to_site.picking_type_id,
                         self.warehouse.construction_dispatch_type_id
                         or self.company.construction_dispatch_type_id)
        # Lo valida el almacén, como el despacho a obra.
        self.assertIn(self.warehouse.pbm_type_id, request._get_dispatch_picking_types())

    # Verificación del 24-oct: almacén en la línea y unidad en el idioma.
    def test_line_shows_warehouse(self):
        request = self._new_request(lines=[(self.cement, 3)], user=self.requester)
        line = request.line_ids
        self.assertEqual(line.warehouse_src_id, self.stock.warehouse_id)
        other = self.env['stock.warehouse'].create({
            'name': 'Puente Piedra (test v3)', 'code': 'ZZPP', 'company_id': self.company.id})
        line.with_user(self.logistics).warehouse_src_id = other
        self.assertEqual(line.location_src_id, other.lot_stock_id)

    def test_dispatch_note_in_request_language(self):
        self.env['res.lang']._activate_lang('es_419')
        self.requester.lang = 'es_419'
        unit = self.cement.uom_id
        self._set_stock(self.cement, self.stock, 200)
        request = self._approved_request()
        self._process(request)
        self._validate(self._dispatch_picking(request).with_context(lang='en_US'))
        note = request.message_ids.filtered(lambda m: 'Salió de' in (m.body or ''))[:1]
        self.assertIn(unit.with_context(lang='es_419').name, note.body)
        if unit.with_context(lang='es_419').name != unit.with_context(lang='en_US').name:
            self.assertNotIn(' %s' % unit.with_context(lang='en_US').name, note.body)

    # M111-23: reposición a planta sin entrar a Fabricación.
    def _replacement(self, head):
        manufacture = self.warehouse.manu_type_id
        replacement_type = manufacture.copy({
            'name': 'Producción de piezas · reposición (test)', 'sequence_code': 'RP',
            'construction_reason_required': True})
        self.company.write({'construction_replacement_type_id': replacement_type.id,
                            'construction_production_head_id': head.id or False})
        reason = self.env['construction.production.reason'].create({
            'name': 'Falla de fabricación (test)'})
        piece = self.env['product.product'].create({
            'name': 'Puerta de alto C07 (test v3)', 'is_storable': True})
        self.env['mrp.bom'].create({
            'product_tmpl_id': piece.product_tmpl_id.id, 'product_qty': 1.0,
            'bom_line_ids': [Command.create({'product_id': self.cement.id, 'product_qty': 1})]})
        self._set_stock(self.cement, self.warehouse.lot_stock_id, 10)
        replacement = self.env['construction.replacement.request'].with_user(
            self.requester).create({
                'project_id': self.site_a.id, 'product_id': piece.id, 'product_qty': 1,
                'reason_id': reason.id, 'reason_note': 'Se rayó al instalar.'})
        self.assertEqual(replacement.state, 'draft')
        self.assertFalse(self.requester.has_group('mrp.group_mrp_user'))
        replacement.action_submit()
        return replacement, replacement_type, reason

    def test_replacement_without_head(self):
        """Sin jefe de producción, avisa a los responsables de Fabricación,
        nunca a quien pide."""
        manager = new_test_user(self.env, 'm11123_gerente_planta', groups='mrp.group_mrp_manager',
                                name='Gerente de planta (test v3)')
        replacement = self._replacement(self.env['res.users'])[0]
        production = replacement.sudo().production_id
        self.assertIn(manager, production.activity_ids.user_id)
        self.assertNotIn(self.requester, production.activity_ids.user_id)
        self.assertNotEqual(production.user_id, self.requester)

    def test_replacement_to_plant(self):
        head = new_test_user(self.env, 'm11123_planta', groups='mrp.group_mrp_user,stock.group_stock_user',
                             name='Jefe de planta (test v3)')
        replacement, replacement_type, reason = self._replacement(head)
        self.assertEqual(replacement.state, 'requested')
        self.assertTrue(replacement.production_name)
        production = replacement.sudo().production_id
        self.assertEqual(production.state, 'draft')
        self.assertEqual(production.picking_type_id, replacement_type)
        self.assertEqual(production.construction_reason_id, reason)
        self.assertIn(head, production.activity_ids.user_id)
        with self.assertRaises(UserError):
            replacement.action_submit()
        # La planta fabrica.
        production = production.with_user(head).sudo(False)
        production.action_confirm()
        self.assertEqual(replacement.state, 'in_production')
        production.qty_producing = 1
        production.move_raw_ids.picked = True
        production.button_mark_done()
        self.assertEqual(production.state, 'done')
        self.assertEqual(replacement.state, 'produced')
        picking = replacement.sudo().picking_id
        self.assertEqual(picking.location_dest_id, self.site_a.construction_location_id)
        self._validate(picking.with_user(self.logistics).sudo())
        self.assertEqual(replacement.state, 'done')


# Las pruebas heredadas ya corren en su clase.
for _name in dir(TestProcess):
    if _name.startswith('test_') and callable(getattr(TestProcess, _name)) \
            and _name not in vars(TestPackage111V3Request):
        setattr(TestPackage111V3Request, _name, None)
