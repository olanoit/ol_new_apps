# -*- coding: utf-8 -*-
"""Paquete 1.21, M121-02: la obra recibe en el portal la recepción encadenada
de una salida a obra; el residente es un usuario portal sin permisos internos."""
from odoo.tests import new_test_user, tagged

from odoo.addons.al_construction_material_request.tests.common import setup_dispatch_transit
from odoo.addons.al_construction_planner_subcontract.tests.test_contract_terms_creval import (
    PHOTO, ContractTermsCommon,
)

PHOTOS = [{'name': 'guia.jpg', 'mimetype': 'image/png', 'data': PHOTO.decode()}]


@tagged('post_install', '-at_install')
class TestPortalReception121(ContractTermsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.resident_user = new_test_user(env, 'portal_residente_121', groups='base.group_portal',
                                          name='Residente (test 1.21)')
        env['construction.portal.member'].create({
            'project_id': cls.project.id, 'user_id': cls.resident_user.id, 'role': 'resident'})
        company = env.company
        company._al_construction_ensure_setup()
        cls.stock = company.construction_src_location_id
        cls.site_location = cls.project.construction_location_id
        cls.transit, _out, _in, _route = setup_dispatch_transit(
            env, cls.stock.warehouse_id, cls.site_location.location_id)
        env['tier.definition'].search([('model', '=', 'construction.material.request')]).active = False
        cls.board = env['product.product'].create({
            'name': 'Rejilla de ventilación (test 1.21)', 'is_storable': True})
        env['stock.quant']._update_available_quantity(cls.board, cls.stock, 10)

    def _processed_request(self, qty):
        request = self.env['construction.material.request'].create({
            'project_id': self.project.id,
            'line_ids': [(0, 0, {'product_id': self.board.id, 'product_qty': qty})]})
        # La aprobación y el control del plan no son de este paquete: sin
        # reglas, se aprueba sola; el material no está en el plan de la obra.
        request.with_context(construction_exceed_checked=True).action_request_approval()
        self.assertEqual(request.state, 'approved')
        request.action_process()
        dispatch = request.picking_ids
        self.assertEqual(dispatch.location_dest_id, self.transit)
        return request, dispatch

    def _service(self):
        return self.env['construction.portal.service'].with_user(self.resident_user)

    def test_portal_lists_only_what_left(self):
        request, dispatch = self._processed_request(2)
        # La salida en «Listo» no está en el portal: aún no salió.
        self.assertFalse(self._service().sync(self.project.id)['deliveries'])
        dispatch.move_ids.picked = True
        dispatch.button_validate()
        receipt = dispatch.move_ids.move_dest_ids.picking_id
        deliveries = self._service().sync(self.project.id)['deliveries']
        self.assertEqual([d['id'] for d in deliveries], receipt.ids)
        self.assertEqual(deliveries[0]['origin'], request.name)
        self.assertEqual(deliveries[0]['kind'], 'dispatch')

    def test_full_chain_and_shortage(self):
        request, dispatch = self._processed_request(2)
        line = request.line_ids
        dispatch.move_ids.picked = True
        dispatch.button_validate()
        receipt = dispatch.move_ids.move_dest_ids.picking_id
        self.assertEqual(line.qty_received_on_site, 0)
        result = self._service().reception({
            'uuid': 'rec-121-1', 'project_id': self.project.id, 'picking_id': receipt.id,
            'photos': PHOTOS, 'lines': [{'move_id': receipt.move_ids.id, 'qty': 1}]})
        self.assertEqual(receipt.state, 'done')
        self.assertTrue(result['backorder'])
        self.assertEqual(line.qty_received_on_site, 1)
        self.assertEqual(request.state, 'in_progress')
        backorder = self.env['stock.picking'].search([('backorder_id', '=', receipt.id)])
        self.assertEqual(backorder.construction_request_id, request)
        self._service().reception({
            'uuid': 'rec-121-2', 'project_id': self.project.id, 'picking_id': backorder.id,
            'photos': PHOTOS, 'lines': [{'move_id': backorder.move_ids.id, 'qty': 1}]})
        self.assertEqual(line.qty_received_on_site, 2)
        self.assertEqual(request.state, 'done')
