# -*- coding: utf-8 -*-
"""Vale de despacho para pegar en el bulto (paquete 1.11, M111-07)."""
import ast

from odoo.tests import tagged

from .test_process import TestProcess

PICKING_REPORT = 'al_construction_material_request.action_report_construction_dispatch_slip'
REQUEST_REPORT = 'al_construction_material_request.action_report_construction_request_dispatch_slip'


@tagged('post_install', '-at_install')
class TestDispatchSlip(TestProcess):

    def _render(self, report, records):
        html, _ = self.env['ir.actions.report']._render_qweb_html(report, records.ids)
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


# Las pruebas heredadas ya corren en su clase.
for _name in dir(TestProcess):
    if _name.startswith('test_') and callable(getattr(TestProcess, _name)) \
            and _name not in vars(TestDispatchSlip):
        setattr(TestDispatchSlip, _name, None)
