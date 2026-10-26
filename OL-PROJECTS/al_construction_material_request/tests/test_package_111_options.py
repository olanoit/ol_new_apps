# -*- coding: utf-8 -*-
"""Paquete 1.11, opciones y pantalla del requerimiento: vale configurable
(M111-19 B), aprobador del interno sin jefe (M111-19 C y M111-18), solicitante
interno (M111-20 A), origen por ruta (M111-20 C), valor estimado con su grupo
(M111-20 E) e historial (M111-20 F)."""
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .test_dispatch_slip import PICKING_REPORT, REQUEST_REPORT, TestDispatchSlip

INTERNAL = 'al_construction_material_request.group_construction_internal_requester'
LOGISTICS = 'al_construction_material_request.group_construction_logistics'


@tagged('post_install', '-at_install')
class TestPackage111Options(TestDispatchSlip):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        plan = cls.env['account.analytic.plan'].create({'name': 'Área (test 1.11)'})
        cls.company.construction_area_plan_id = plan
        cls.area = cls.env['account.analytic.account'].create({
            'name': 'Administración (test)', 'plan_id': plan.id, 'company_id': cls.company.id})
        cls.paper = cls.env['product.product'].create({
            'name': 'Papel A4 (test 1.11)', 'type': 'consu', 'is_storable': True,
            'standard_price': 12.0})

    def _internal(self, user):
        return self.env['construction.material.request'].with_user(user).create({
            'request_type': 'internal', 'area_id': self.area.id,
            'line_ids': [(0, 0, {'product_id': self.paper.id, 'product_qty': 2})]})

    # M111-19 B
    def test_slip_options(self):
        request = self._processed()
        dispatch = self._dispatch_picking(request)
        self.company.write({
            'construction_slip_dispatch_label': 'Entrega almacén',
            'construction_slip_receive_site_label': 'Recibe residente',
            'construction_slip_unvalidated_signer': 'blank',
            'construction_slip_show_previous': False,
        })
        html = self._render(PICKING_REPORT, dispatch)
        self.assertIn('Entrega almacén', html)
        self.assertIn('Recibe residente', html)
        self.assertNotIn('Despachado antes', html)
        self.assertFalse(dispatch._get_dispatch_slip_user())
        self.company.construction_slip_unvalidated_signer = 'printer'
        self.assertEqual(dispatch._get_dispatch_slip_user(), self.env.user)

    def test_internal_slip_receiver(self):
        self._set_stock(self.paper, self.stock, 10)
        request = self._internal(self.requester)
        request.action_request_approval()
        if request.state == 'to_approve':
            request.with_user(self.logistics).validate_tier()
        request = request.with_env(self.env)
        self._process(request)
        html = self._render(PICKING_REPORT, request.picking_ids)
        self.assertIn('Recibido por (área)', html)
        self.assertNotIn('Recibido por (capataz)', html)

    # M111-19 C y M111-18: el interno de quien no tiene jefe lo aprueba
    # Logística; sin grupo, se aprueba al solicitarlo.
    def test_internal_fallback_approver(self):
        self.company.construction_internal_fallback_group_id = self.env.ref(LOGISTICS)
        rule = self.env['tier.definition'].search([
            ('construction_internal_fallback', '=', True),
            ('company_id', '=', self.company.id)])
        self.assertTrue(rule.active)
        self.assertEqual(rule.reviewer_group_id, self.env.ref(LOGISTICS))
        request = self._internal(self.requester)
        self.assertFalse(request.construction_department_manager_id)
        request.action_request_approval()
        self.assertEqual(request.state, 'to_approve')
        request.with_user(self.logistics).validate_tier()
        self.assertEqual(request.state, 'approved')
        self.company.construction_internal_fallback_group_id = False
        self.assertFalse(rule.active)
        other = self._internal(self.requester)
        other.action_request_approval()
        self.assertEqual(other.state, 'approved')

    # M111-20 A
    def test_internal_requester_only(self):
        user = new_test_user(self.env, 'rqi_solo_interno', groups=INTERNAL,
                             name='Asistente administrativa (test)')
        Request = self.env['construction.material.request'].with_user(user)
        request = self._internal(user)
        self.assertEqual(Request.new({}).request_type, 'internal')
        self.assertFalse(request.user_is_site_requester)
        # No pide para obras: lo frena la regla de acceso.
        with self.assertRaises(AccessError):
            Request.create({'request_type': 'site', 'project_id': self.site_a.id})
        mine = self._internal(self.requester)
        self.assertEqual(Request.search([]), request, 'solo ve sus internos')
        self.assertTrue(mine)
        menu = self.env.ref('al_construction_material_request.menu_construction_internal_requests')
        self.assertIn(menu.id, self.env['ir.ui.menu'].with_user(user)._visible_menu_ids())

    def test_all_users_internal_setting(self):
        user = new_test_user(self.env, 'rqi_cualquiera', groups='base.group_user')
        self.assertTrue(user.has_group(INTERNAL))
        self.env['res.config.settings'].create(
            {'group_construction_internal_request_all': False}).execute()
        user.invalidate_recordset()
        self.assertFalse(user.has_group(INTERNAL))
        root = self.env.ref('al_construction_material_request.menu_construction_root')
        self.assertNotIn(root.id, self.env['ir.ui.menu'].with_user(user)._visible_menu_ids())

    # M111-20 C
    def _north_warehouse(self):
        """Almacén «Planta norte» con su ruta a obras para los fierros."""
        Warehouse = self.env['stock.warehouse']
        other = Warehouse.create({'name': 'Planta norte (test)', 'code': 'PNT',
                                  'company_id': self.company.id})
        other_type = self.env['stock.picking.type'].create({
            'name': 'Despacho a obra norte (test)', 'code': 'internal',
            'sequence_code': 'PNO', 'warehouse_id': other.id, 'company_id': self.company.id})
        other.construction_dispatch_type_id = other_type
        route = self.env['stock.route'].create({
            'name': 'Obras desde la planta norte (test)', 'product_categ_selectable': True,
            'company_id': self.company.id,
            'rule_ids': [(0, 0, {
                'name': 'Planta norte → obras (test)', 'action': 'pull',
                'procure_method': 'make_to_stock',
                'location_src_id': other.lot_stock_id.id,
                'location_dest_id': self.company.construction_sites_location_id.id,
                'picking_type_id': other.int_type_id.id,
                'company_id': self.company.id})]})
        category = self.env['product.category'].create({
            'name': 'Fierros (test)', 'route_ids': [(6, 0, route.ids)]})
        self.steel.categ_id = category
        return other, other_type

    def test_source_by_route(self):
        other, other_type = self._north_warehouse()
        self._set_stock(self.cement, self.stock, 150)
        self._set_stock(self.steel, other.lot_stock_id, 80)
        request = self._approved_request(lines=[(self.cement, 100), (self.steel, 50)])
        steel_line = request.line_ids.filtered(lambda l: l.product_id == self.steel)
        cement_line = request.line_ids - steel_line
        self.assertEqual(steel_line.location_src_id, other.lot_stock_id)
        self.assertEqual(cement_line.location_src_id, self.stock)
        self.assertEqual(steel_line.qty_available_now, 80.0)
        self.assertIn('Planta norte (test) · 1', request.construction_source_summary)
        self._process(request)
        pickings = self._dispatch_picking(request)
        self.assertEqual(len(pickings), 2)
        north = pickings.filtered(lambda p: p.location_id == other.lot_stock_id)
        self.assertEqual(north.picking_type_id, other_type)
        self.assertEqual(north.move_ids.product_id, self.steel)
        self.assertEqual(steel_line.qty_to_dispatch, 50.0)
        self.assertFalse(request.purchase_request_ids)
        self._validate(north)
        self.assertEqual(steel_line.qty_dispatched, 50.0)

    def test_shortage_received_at_line_source(self):
        """El faltante de una línea con otro origen se compra con la recepción
        de ese almacén: lo recibido reserva la salida a obra en espera."""
        other, other_type = self._north_warehouse()
        self._set_stock(self.steel, other.lot_stock_id, 30)
        request = self._approved_request(lines=[(self.cement, 10), (self.steel, 50)])
        steel_line = request.line_ids.filtered(lambda l: l.product_id == self.steel)
        self._process(request)
        self.assertEqual(steel_line.qty_to_purchase, 20.0)
        self.assertEqual(len(request.purchase_request_ids), 2)
        north_request = request.purchase_request_ids.filtered(
            lambda r: r.picking_type_id == other.in_type_id)
        self.assertEqual(north_request.line_ids.product_id, self.steel)
        central_request = request.purchase_request_ids - north_request
        self.assertEqual(central_request.picking_type_id,
                         self.company.construction_pr_picking_type_id)
        pending = request.picking_ids.filtered(
            lambda p: p.location_id == other.lot_stock_id and p.state == 'waiting')
        self.assertEqual(pending.move_ids.product_uom_qty, 20.0)
        body = request.message_ids.filtered(
            lambda m: 'Requerimiento procesado' in (m.body or ''))[:1].body
        self.assertIn(north_request.name, body)
        self.assertIn(central_request.name, body)
        order = self._buy(north_request)
        receipt = order.picking_ids
        self.assertEqual(receipt.location_dest_id, other.lot_stock_id)
        self._validate(receipt)
        self.assertEqual(pending.state, 'assigned')
        self.assertEqual(pending.move_ids.quantity, 20.0)

    def test_source_without_routes_is_default(self):
        request = self._approved_request(lines=[(self.cement, 10)])
        self.assertEqual(request.line_ids.location_src_id, request.location_src_id)

    # M111-20 E
    def test_amounts_need_group(self):
        Request = self.env['construction.material.request']
        arch = Request.with_user(self.requester).get_view(view_type='form')['arch']
        self.assertNotIn('amount_estimated', arch)
        boss = new_test_user(
            self.env, 'rqo_montos',
            groups='al_construction_material_request.group_construction_requester,'
                   'al_construction_material_request.group_construction_amounts')
        self.assertIn('amount_estimated', Request.with_user(boss).get_view(
            view_type='form')['arch'])
        request = self._new_request(user=self.requester)
        html = self._render(REQUEST_REPORT, request.with_user(self.requester))
        self.assertNotIn('Valor estimado', html)

    # M111-20 F
    def test_history_messages(self):
        request = self._processed()
        body = request.message_ids.filtered(
            lambda m: 'Requerimiento procesado' in (m.body or ''))[:1].body
        self.assertIn('Reservado para despacho desde', body)
        self.assertNotIn('disponibles en el almacén central', body)
        dispatch = self._dispatch_picking(request)
        self.assertIn(dispatch.name, body)
        self._validate(dispatch)
        note = request.message_ids[:1].body
        self.assertIn('Salió de', note)
        self.assertIn(dispatch.name, note)
        self.assertIn('1 en compra', note)


# Las pruebas heredadas ya corren en su clase.
for _name in dir(TestDispatchSlip):
    if _name.startswith('test_') and callable(getattr(TestDispatchSlip, _name)) \
            and _name not in vars(TestPackage111Options):
        setattr(TestPackage111Options, _name, None)
