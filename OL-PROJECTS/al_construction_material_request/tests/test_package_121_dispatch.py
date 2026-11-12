# -*- coding: utf-8 -*-
"""Paquete 1.21: despacho a obra en dos pasos.

* M121-01: con un tipo de despacho cuyo destino es un tránsito, «Procesar» crea
  la salida al tránsito con la obra como ubicación final; sin tránsito, un paso.
* M121-02: la recepción encadenada lleva el requerimiento y la obra, y solo ella
  cuenta como «Recibido en obra».

El almacenero valida con el grupo de Inventario y Logística, sin «Administrador»."""
from odoo.tests import new_test_user, tagged

from .common import ConstructionRequestCommon, setup_dispatch_transit


@tagged('post_install', '-at_install')
class TestDispatchTransit121(ConstructionRequestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.site_location = cls.site_a.construction_location_id
        cls.src_warehouse = cls.stock.warehouse_id
        cls.one_step_type = cls.src_warehouse.construction_dispatch_type_id \
            or cls.company.construction_dispatch_type_id
        cls.transit, cls.out_type, cls.in_type, cls.route = setup_dispatch_transit(
            cls.env, cls.src_warehouse, cls.site_location.location_id)
        cls.client = cls.env['res.partner'].create({'name': 'Cliente de la obra (test)'})
        cls.site_a.partner_id = cls.client
        cls.storekeeper = new_test_user(
            cls.env, 'rqo_almacenero',
            groups='stock.group_stock_user,al_construction_material_request.group_construction_logistics',
            name='Almacenero (test)')

    def _approved_request(self, lines=None):
        request = self._new_request(lines=lines, user=self.requester)
        request.action_request_approval()
        request.with_user(self.approver).validate_tier()
        self.assertEqual(request.state, 'approved')
        return request.with_env(self.env)

    def _process(self, request):
        request.with_user(self.logistics).action_process()
        self.assertEqual(request.state, 'in_progress')

    def _validate(self, picking):
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, 'done')

    def _chain(self, qty=100):
        self._set_stock(self.cement, self.stock, 150)
        request = self._approved_request(lines=[(self.cement, qty)])
        self._process(request)
        return request

    def test_process_dispatches_to_transit(self):
        """M121-01, criterio 1: salida al tránsito con la obra como final."""
        request = self._chain()
        dispatch = request.picking_ids
        self.assertEqual(len(dispatch), 1)
        self.assertEqual(dispatch.picking_type_id, self.out_type)
        self.assertEqual(dispatch.location_dest_id, self.transit)
        self.assertEqual(dispatch.move_ids.location_final_id, self.site_location)
        self.assertEqual(dispatch.construction_request_id, request)
        self.assertEqual(dispatch.project_id, self.site_a)
        self.assertEqual(dispatch.partner_id, self.client)
        self.assertEqual(dispatch.state, 'assigned')
        if 'l10n_pe_edi_reason_for_transfer' in dispatch._fields:
            self.assertEqual(dispatch.l10n_pe_edi_reason_for_transfer, '04')

    def test_full_chain_with_storekeeper(self):
        """M121-01 criterio 2 y M121-02: validar crea la recepción en «Listo»
        con el requerimiento; lo recibido solo cuenta al recibirla."""
        request = self._chain()
        dispatch = request.picking_ids
        line = request.line_ids
        dispatch = dispatch.with_user(self.storekeeper)
        dispatch.move_ids.picked = True
        dispatch.button_validate()
        self.assertEqual(dispatch.state, 'done')
        receipt = dispatch.move_ids.move_dest_ids.picking_id
        self.assertEqual(len(receipt), 1)
        self.assertEqual(receipt.state, 'assigned')
        self.assertEqual(receipt.picking_type_id, self.in_type)
        self.assertEqual(receipt.location_id, self.transit)
        self.assertEqual(receipt.location_dest_id, self.site_location)
        self.assertEqual(receipt.construction_request_id, request)
        self.assertEqual(receipt.project_id, self.site_a)
        self.assertEqual(receipt.origin, request.name)
        self.assertEqual(receipt.move_ids.construction_request_line_id, line)
        # En tránsito: despachado, no recibido.
        self.assertEqual(line.qty_dispatched, 100)
        self.assertEqual(line.qty_received_on_site, 0)
        self.assertEqual(request.state, 'in_progress')
        self.assertIn(receipt, request.picking_ids)
        self.assertEqual(request.construction_transit_count, 1)
        self._validate(receipt)
        self.assertEqual(request.construction_transit_count, 0)
        self.assertEqual(line.qty_received_on_site, 100)
        self.assertEqual(line.qty_dispatched, 100)
        self.assertEqual(request.state, 'done')

    def test_return_before_reception(self):
        """«Devolver» la salida antes de recibirla deja de contarla como
        despachada."""
        request = self._chain()
        dispatch = request.picking_ids
        self._validate(dispatch)
        receipt = dispatch.move_ids.move_dest_ids.picking_id
        receipt.action_cancel()
        wizard = self.env['stock.return.picking'].with_context(
            active_id=dispatch.id, active_model='stock.picking').create({})
        wizard.product_return_moves.quantity = 100
        back = self.env['stock.picking'].browse(wizard.action_create_returns()['res_id'])
        self._validate(back)
        self.assertEqual(request.line_ids.qty_dispatched, 0)
        self.assertEqual(request.line_ids.qty_received_on_site, 0)

    def test_one_step_without_transit(self):
        """M121-01, criterio 3: con el tipo de un paso, como hoy."""
        self.src_warehouse.construction_dispatch_type_id = self.one_step_type
        request = self._chain()
        dispatch = request.picking_ids
        self.assertEqual(dispatch.location_dest_id, self.site_location)
        self.assertFalse(dispatch.move_ids.location_final_id)
        self.assertFalse(dispatch.partner_id)
        dispatch = dispatch.with_user(self.storekeeper)
        dispatch.move_ids.picked = True
        dispatch.button_validate()
        self.assertFalse(dispatch.move_ids.move_dest_ids)
        self.assertEqual(request.line_ids.qty_received_on_site, 100)
        self.assertEqual(request.state, 'done')
