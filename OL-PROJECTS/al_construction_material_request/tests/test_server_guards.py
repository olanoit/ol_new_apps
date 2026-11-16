# -*- coding: utf-8 -*-
"""Controles del servidor (auditoría del 16-nov-2026): lo aprobado no cambia
por una llamada directa. La vista ya lo impide; aquí se prueba que el servidor
también, porque el Solicitante tiene permiso de escritura sobre sus líneas."""
from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from .common import ConstructionRequestCommon


@tagged('post_install', '-at_install')
class TestServerGuards(ConstructionRequestCommon):

    def _approved(self):
        request = self._new_request(user=self.requester)
        request.action_request_approval()
        request.with_user(self.approver).validate_tier()
        self.assertEqual(request.state, 'approved')
        return request

    def test_lines_locked_after_draft(self):
        request = self._approved()
        line = request.line_ids
        for context in ({}, {'skip_validation_check': True}):
            as_requester = line.with_user(self.requester).with_context(**context)
            with self.assertRaises(UserError):
                as_requester.write({'product_qty': 1000})
            with self.assertRaises(UserError):
                as_requester.write({'cancelled': True})
            with self.assertRaises(UserError):
                as_requester.create({'request_id': request.id, 'product_id': self.steel.id,
                                     'product_qty': 5})
            with self.assertRaises(UserError):
                request.with_user(self.requester).with_context(**context).write({
                    'line_ids': [Command.create({'product_id': self.steel.id,
                                                 'product_qty': 5})]})
            with self.assertRaises(UserError):
                as_requester.unlink()
        self.assertEqual(line.product_qty, 100)
        self.assertEqual(len(request.line_ids), 1)

    def test_lines_locked_under_approval(self):
        request = self._new_request(user=self.requester)
        request.action_request_approval()
        self.assertEqual(request.state, 'to_approve')
        with self.assertRaises(UserError):
            request.line_ids.with_user(self.requester).write({'product_qty': 1000})
        # De vuelta a borrador, el solicitante corrige y vuelve a enviar.
        request.action_draft()
        request.line_ids.with_user(self.requester).write({'product_qty': 120})
        self.assertEqual(request.line_ids.product_qty, 120)

    def test_draft_lines_free_and_flow_still_works(self):
        request = self._new_request(user=self.requester)
        request.line_ids.write({'product_qty': 80})
        request.write({'line_ids': [Command.create({'product_id': self.steel.id,
                                                    'product_qty': 5})]})
        request.line_ids.filtered(lambda l: l.product_id == self.steel).unlink()
        request.action_request_approval()
        request.with_user(self.approver).validate_tier()
        # Logística ajusta el origen de la línea y procesa: el reparto
        # escribe las cantidades de la línea.
        self._set_stock(self.cement, self.loc_cement, 50)
        as_logistics = request.with_user(self.logistics)
        as_logistics.line_ids.write({'location_src_id': self.loc_cement.id})
        as_logistics.action_process()
        self.assertEqual(request.state, 'in_progress')
        self.assertEqual(request.line_ids.qty_to_dispatch, 50)
        self.assertEqual(request.line_ids.qty_to_purchase, 30)

    def test_state_only_through_the_flow(self):
        request = self._new_request(user=self.requester)
        for state in ('in_progress', 'done'):
            with self.assertRaises(UserError):
                request.write({'state': state})
        self.assertEqual(request.state, 'draft')
        approved = self._approved()
        for state in ('draft', 'in_progress', 'done', 'cancel', 'rejected'):
            with self.assertRaises(UserError):
                approved.with_user(self.requester).write({'state': state})
        self.assertEqual(approved.state, 'approved')

    def test_cancel_is_for_logistics_once_sent(self):
        approved = self._approved()
        with self.assertRaises(UserError):
            approved.with_user(self.requester).action_cancel()
        self.assertEqual(approved.state, 'approved')
        approved.with_user(self.logistics).action_cancel()
        self.assertEqual(approved.state, 'cancel')
        # El solicitante sí descarta su borrador.
        draft = self._new_request(user=self.requester)
        draft.action_cancel()
        self.assertEqual(draft.state, 'cancel')
        # Y no toca lo de otra obra.
        foreign = self._new_request(project=self.site_b, user=self.other_requester)
        with self.assertRaises(AccessError):
            foreign.with_user(self.requester).action_cancel()

    def test_close_with_received_by_requester(self):
        """«Cerrar con lo recibido» sigue siendo del solicitante: el paso a
        «Hecho» lo decide el sistema."""
        request = self._approved()
        self._set_stock(self.cement, self.loc_cement, 100)
        request.with_user(self.logistics).action_process()
        # (el requerimiento es del solicitante: la transferencia se toma con el
        # entorno del test)
        picking = self.env['stock.picking'].browse(request.picking_ids.ids)
        picking.move_ids.quantity = 60
        picking.move_ids.picked = True
        picking.with_user(self.logistics).with_context(
            skip_backorder=True, picking_ids_not_to_backorder=picking.ids).button_validate()
        self.assertEqual(request.line_ids.qty_received_on_site, 60)
        # El almacenero de obra: solicitante con permisos de inventario.
        storekeeper = new_test_user(
            self.env, 'rqo_almacenero_obra', name='Almacenero de obra (test)',
            groups='al_construction_material_request.group_construction_requester,'
                   'stock.group_stock_user')
        self.site_a.message_subscribe(partner_ids=storekeeper.partner_id.ids)
        request.line_ids.with_user(storekeeper)._construction_close_with_received()
        self.assertEqual(request.state, 'done')
        self.assertTrue(request.line_ids.closed_with_received)
        # La marca de cierre no se escribe a mano.
        other = self._approved()
        with self.assertRaises(UserError):
            other.line_ids.with_user(self.requester).write({'closed_with_received': True})
