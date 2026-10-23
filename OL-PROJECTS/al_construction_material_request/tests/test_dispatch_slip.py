# -*- coding: utf-8 -*-
"""Vale de despacho para pegar en el bulto (paquete 1.11, M111-07)."""
import ast

from odoo.tests import new_test_user, tagged

from .test_process import TestProcess

PICKING_REPORT = 'al_construction_material_request.action_report_construction_dispatch_slip'
REQUEST_REPORT = 'al_construction_material_request.action_report_construction_request_dispatch_slip'
MOVE_REPORT = 'al_construction_material_request.action_report_construction_dispatch_slip_move'
TO_DISPATCH = 'al_construction_material_request.action_construction_moves_to_dispatch'


@tagged('post_install', '-at_install')
class TestDispatchSlip(TestProcess):

    def _render(self, report, records):
        # Se imprime con el usuario de los registros (el de la sesión).
        html, _ = self.env['ir.actions.report'].with_env(records.env)._render_qweb_html(
            report, records.ids)
        return html.decode()

    def _rows(self, request, picking=None):
        return {row['line'].product_id: row
                for row in request._get_dispatch_slip(picking)['rows']}

    def _processed(self):
        # Cemento con stock (sale ahora); fierro sin stock (va a compra).
        self._set_stock(self.cement, self.stock, 150)
        request = self._approved_request(lines=[(self.cement, 100), (self.steel, 50)])
        self._process(request)
        return request

    def test_slip_from_first_bundle(self):
        request = self._processed()
        dispatch = self._dispatch_picking(request)
        rows = self._rows(request, dispatch)
        cement, steel = rows[self.cement], rows[self.steel]
        self.assertEqual((cement['before'], cement['in_bundle'], cement['pending']), (0, 100, 0))
        self.assertEqual(cement['situation'], 'Va completo en este bulto')
        self.assertEqual((steel['before'], steel['in_bundle'], steel['pending']), (0, 0, 50))
        self.assertEqual(steel['situation'],
                         'En compra · %s' % request.purchase_request_ids.name)
        html = self._render(PICKING_REPORT, dispatch)
        self.assertIn('Vale de despacho', html)
        self.assertIn('Bulto %s' % dispatch.name, html)
        self.assertIn('En este bulto', html)
        self.assertIn('En este bulto: 1 de 2 materiales. Pendientes: 1 (en compra).', html)
        self.assertIn('Los pendientes se enviarán en otro despacho', html)
        # Sin montos ni stock interno.
        self.assertNotIn('Valor estimado', html)
        self.assertNotIn('Disponible', html)

    def test_slip_after_purchase(self):
        request = self._processed()
        self._validate(self._dispatch_picking(request))
        order = self._buy(request.purchase_request_ids)
        steel = self._rows(request)[self.steel]
        self.assertIn('OC %s' % order.name, steel['situation'])
        self.assertIn('llega', steel['situation'])
        self._validate(order.picking_ids)
        pending = self._pending_picking(request)
        self.assertEqual(pending.state, 'assigned')
        rows = self._rows(request, pending)
        cement, steel = rows[self.cement], rows[self.steel]
        self.assertEqual((cement['before'], cement['in_bundle']), (100, 0))
        self.assertEqual(cement['situation'], 'Completo')
        self.assertEqual((steel['in_bundle'], steel['pending']), (50, 0))
        # Ya validado, el bulto sigue mostrando lo suyo y no lo cuenta dos veces.
        self._validate(pending)
        rows = self._rows(request, pending)
        self.assertEqual((rows[self.steel]['before'], rows[self.steel]['in_bundle']), (0, 50))

    def test_slip_from_request_and_binding(self):
        request = self._processed()
        html = self._render(REQUEST_REPORT, request)
        self.assertIn('Vale de despacho', html)
        self.assertNotIn('En este bulto', html)
        self.assertIn('Pendientes: 2 (1 en compra, 1 por despachar).', html)
        rows = self._rows(request)
        self.assertEqual(rows[self.cement]['situation'],
                         'Por despachar · %s' % self._dispatch_picking(request).name)
        # La opción de imprimir solo sale en transferencias con requerimiento.
        report = self.env.ref(PICKING_REPORT)
        self.assertEqual(report.domain, "[('construction_request_id', '!=', False)]")
        other = self.env['stock.picking'].create({
            'picking_type_id': self.warehouse.int_type_id.id,
            'location_id': self.stock.id, 'location_dest_id': self.stock.id})
        self.assertFalse(other.filtered_domain(ast.literal_eval(report.domain)))
        # El vale actual no cambia.
        self.assertIn('Valor estimado', self._render(
            'al_construction_material_request.action_report_construction_request', request))


    # --- M111-11: «Despachado por» -------------------------------------
    def test_slip_dispatched_by(self):
        request = self._processed()
        dispatch = self._dispatch_picking(request)
        storekeeper = new_test_user(
            self.env, 'rqo_almacenero',
            groups='al_construction_material_request.group_construction_logistics',
            name='Almacenero (test)')
        # Sin validar: quien imprime, no quien creó la transferencia.
        self.assertEqual(dispatch.with_user(storekeeper)._get_dispatch_slip_user(), storekeeper)
        self.assertIn('Almacenero (test)', self._render(
            PICKING_REPORT, dispatch.with_user(storekeeper)))
        dispatch.move_ids.picked = True
        dispatch.with_user(storekeeper).button_validate()
        self.assertEqual(dispatch.construction_validated_by_id, storekeeper)
        # Ya validada: quien la validó, imprima quien imprima.
        self.assertEqual(dispatch._get_dispatch_slip_user(), storekeeper)
        self.assertIn('Almacenero (test)', self._render(PICKING_REPORT, dispatch))

    # --- M111-08: «Productos por despachar» -----------------------------
    def _to_dispatch_moves(self, user, request):
        action = self.env['ir.actions.act_window'].with_user(user)._for_xml_id(TO_DISPATCH)
        domain = ast.literal_eval(action['domain'])
        return self.env['stock.move'].with_user(user).search(
            domain + [('construction_request_id', '=', request.id)])

    def test_products_to_dispatch(self):
        request = self._processed()
        dispatch = self._dispatch_picking(request)
        pending = self._pending_picking(request)
        # Solo Inventario: Usuario, sin acceso a los requerimientos de obra.
        storekeeper = new_test_user(
            self.env, 'rqo_solo_inventario', groups='stock.group_stock_user')
        menu = self.env.ref('al_construction_material_request.menu_construction_moves_to_dispatch')
        self.assertIn(menu.id, self.env['ir.ui.menu'].with_user(storekeeper)._visible_menu_ids())
        moves = self._to_dispatch_moves(storekeeper, request)
        self.assertEqual(moves.picking_id, dispatch | pending)
        self.assertEqual(moves.construction_request_id, request)
        self.assertEqual(moves.construction_project_id, self.site_a)
        groups = self.env['stock.move'].with_user(storekeeper).web_read_group(
            [('id', 'in', moves.ids)], ['construction_request_id', 'picking_id'],
            aggregates=['product_uom_qty:sum'])['groups']
        self.assertEqual(groups[0]['construction_request_id'], (request.id, request.name))
        # Validar el despacho lo saca de la lista.
        self._validate(dispatch)
        self.assertEqual(self._to_dispatch_moves(storekeeper, request).picking_id, pending)
        # Imprimir desde las filas marcadas: un vale por transferencia.
        html = self._render(MOVE_REPORT, moves.with_env(self.env))
        self.assertEqual(html.count('Bulto '), 2)
        report = self.env.ref(MOVE_REPORT)
        self.assertEqual(report.binding_model_id.model, 'stock.move')


# Las pruebas heredadas ya corren en su clase.
for _name in dir(TestProcess):
    if _name.startswith('test_') and callable(getattr(TestProcess, _name)) \
            and _name not in vars(TestDispatchSlip):
        setattr(TestDispatchSlip, _name, None)
