# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import ConstructionRequestCommon


@tagged('post_install', '-at_install')
class TestProcess(ConstructionRequestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vendor = cls.env['res.partner'].create({'name': 'Proveedor ficticio (test)'})
        plan = cls.env['account.analytic.plan'].create({'name': 'Partida (test)'})
        cls.analytic_partida = cls.env['account.analytic.account'].create({
            'name': '02.01 Concreto (test)', 'plan_id': plan.id})

    # ------------------------------------------------------------------
    def _approved_request(self, lines=None, **line_vals):
        request = self._new_request(lines=lines, user=self.requester)
        if line_vals:
            request.line_ids.write(line_vals)
        request.action_request_approval()
        request.with_user(self.approver).validate_tier()
        self.assertEqual(request.state, 'approved')
        # Validar, comprar y recibir los hace el almacén/compras, no el residente.
        return request.with_env(self.env)

    def _process(self, request):
        request.with_user(self.logistics).action_process()
        self.assertEqual(request.state, 'in_progress')

    def _dispatch_picking(self, request):
        return request.picking_ids.filtered(
            lambda p: p.move_ids.filtered(lambda m: m.procure_method == 'make_to_stock'))

    def _pending_picking(self, request):
        return request.picking_ids.filtered(
            lambda p: p.move_ids.filtered(lambda m: m.procure_method == 'make_to_order'))

    def _validate(self, picking):
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, 'done')

    def _buy(self, purchase_request):
        wizard = self.env['purchase.request.line.make.purchase.order'].with_context(
            active_model='purchase.request', active_ids=purchase_request.ids,
        ).create({'supplier_id': self.vendor.id})
        wizard.make_purchase_order()
        order = purchase_request.line_ids.purchase_lines.order_id
        self.assertEqual(len(order), 1)
        order.button_confirm()
        return order

    # ------------------------------------------------------------------
    def test_enough_stock_only_transfer(self):
        self._set_stock(self.cement, self.stock, 150)
        request = self._approved_request()
        self._process(request)
        picking = request.picking_ids
        self.assertEqual(len(picking), 1)
        self.assertEqual(picking.state, 'assigned')
        self.assertEqual(picking.location_id, self.stock)
        self.assertEqual(picking.location_dest_id, self.site_a.construction_location_id)
        self.assertEqual(picking.picking_type_id, self.company.construction_dispatch_type_id)
        self.assertEqual(picking.project_id, self.site_a)
        self.assertEqual(picking.origin, request.name)
        if 'l10n_pe_edi_reason_for_transfer' in picking._fields:
            # GRE nativa: traslado entre establecimientos de la misma empresa
            self.assertEqual(picking.l10n_pe_edi_reason_for_transfer, '04')
        self.assertEqual(picking.move_ids.product_uom_qty, 100)
        self.assertFalse(request.purchase_request_ids)
        line = request.line_ids
        self.assertEqual((line.qty_available_at_approval, line.qty_to_dispatch,
                          line.qty_to_purchase), (150, 100, 0))
        self.assertEqual(line.line_state, 'dispatched')

        self._validate(picking)
        self.assertEqual(line.qty_dispatched, 100)
        self.assertEqual(line.qty_received_on_site, 100)
        self.assertEqual(line.line_state, 'done')
        self.assertEqual(request.state, 'done')

    def test_scheduled_date_keeps_the_local_day(self):
        self.env.user.tz = 'America/Lima'
        self._set_stock(self.cement, self.stock, 150)
        request = self._approved_request()
        request.date_required = '2026-10-05'
        self._process(request)
        local = fields.Datetime.context_timestamp(
            request.with_context(tz='America/Lima'), request.picking_ids.scheduled_date)
        self.assertEqual(str(local.date()), '2026-10-05')

    def test_no_stock_only_purchase_request(self):
        request = self._approved_request()
        self._process(request)
        self.assertFalse(self._dispatch_picking(request))
        purchase_request = request.purchase_request_ids
        self.assertEqual(len(purchase_request), 1)
        self.assertEqual(purchase_request.state, 'approved')
        self.assertEqual(purchase_request.origin, request.name)
        self.assertEqual(purchase_request.line_ids.product_qty, 100)
        # vía central: movimiento central → obra esperando la compra
        pending = self._pending_picking(request)
        self.assertEqual(pending.move_ids.state, 'waiting')
        self.assertEqual(pending.move_ids.created_purchase_request_line_id,
                         purchase_request.line_ids)
        self.assertEqual(request.line_ids.line_state, 'purchasing')

    def test_partial_stock_splits_100_60(self):
        self._set_stock(self.cement, self.stock, 60)
        distribution = {str(self.analytic_partida.id): 100}
        request = self._approved_request(analytic_distribution=distribution)
        self._process(request)
        picking = self._dispatch_picking(request)
        self.assertEqual(picking.move_ids.product_uom_qty, 60)
        self.assertEqual(picking.move_ids.quantity, 60)
        self.assertEqual(picking.move_ids.construction_analytic_distribution, distribution)
        pr_line = request.purchase_request_ids.line_ids
        self.assertEqual(pr_line.product_qty, 40)
        self.assertEqual(pr_line.analytic_distribution, distribution)
        self.assertEqual(pr_line.construction_request_line_id, request.line_ids)
        self.assertEqual(self._pending_picking(request).move_ids.product_uom_qty, 40)
        # referencia de inventario común, como las OC (stock.reference)
        reference = request.stock_reference_id
        self.assertEqual(reference.name, request.name)
        self.assertEqual(request.picking_ids.reference_ids, reference)
        self.assertEqual(request.picking_ids.move_ids.reference_ids, reference)
        self.assertEqual(picking.move_ids.warehouse_id, self.warehouse)
        self.assertIn('Requerimiento procesado', request.message_ids[0].body)

    def test_stock_in_two_family_sublocations(self):
        self._set_stock(self.cement, self.loc_cement, 40)
        self._set_stock(self.cement, self.loc_steel, 20)
        request = self._approved_request()
        self._process(request)
        picking = self._dispatch_picking(request)
        self.assertEqual(picking.move_ids.quantity, 60)
        self.assertEqual(
            set(picking.move_ids.move_line_ids.location_id.ids),
            {self.loc_cement.id, self.loc_steel.id})
        self.assertEqual(request.purchase_request_ids.line_ids.product_qty, 40)

    def test_line_uom_differs_from_product(self):
        uom_dozen = self.env.ref('uom.product_uom_dozen')
        self._set_stock(self.cement, self.stock, 30)
        request = self._new_request(lines=[(self.cement, 5)], user=self.requester)
        request.line_ids.product_uom_id = uom_dozen
        request.action_request_approval()
        request.with_user(self.approver).validate_tier()
        request = request.with_env(self.env)
        self._process(request)
        line = request.line_ids
        self.assertEqual((line.qty_to_dispatch, line.qty_to_purchase), (2.5, 2.5))
        move = self._dispatch_picking(request).move_ids
        self.assertEqual(move.product_uom, uom_dozen)
        self.assertEqual(move.product_qty, 30)
        pr_line = request.purchase_request_ids.line_ids
        self.assertEqual((pr_line.product_qty, pr_line.product_uom_id), (2.5, uom_dozen))

    def test_product_uom_qty_in_product_unit(self):
        request = self._new_request(lines=[(self.cement, 5)])
        line = request.line_ids
        self.assertEqual(line.product_uom_qty, 5)
        line.product_uom_id = self.env.ref('uom.product_uom_dozen')
        self.assertEqual(line.product_uom_qty, 60)
        self.assertEqual(request.amount_estimated, 60 * 30.0)

    def test_split_with_non_exact_uom(self):
        """Como la regla nativa mts_else_mto: el faltante se calcula en la UdM
        del producto y se convierte a la de la línea con HALF-UP; lo
        despachado es el resto, así la suma siempre da lo pedido."""
        self._set_stock(self.cement, self.stock, 31)
        request = self._new_request(lines=[(self.cement, 5)], user=self.requester)
        request.line_ids.product_uom_id = self.env.ref('uom.product_uom_dozen')
        request.action_request_approval()
        request.with_user(self.approver).validate_tier()
        request = request.with_env(self.env)
        self._process(request)
        line = request.line_ids
        self.assertAlmostEqual(line.qty_to_purchase, 2.42)  # 29 u = 2,4167 dz
        self.assertAlmostEqual(line.qty_to_dispatch + line.qty_to_purchase, 5)
        self.assertAlmostEqual(line.qty_available_at_approval, 2.58)  # 31 u

    def test_return_from_site_reduces_received(self):
        """Como purchase_stock con las devoluciones al proveedor: lo que vuelve
        de la obra al almacén resta de lo recibido y de lo despachado."""
        self._set_stock(self.cement, self.stock, 150)
        request = self._approved_request()
        self._process(request)
        picking = self._dispatch_picking(request)
        self._validate(picking)
        self.assertEqual(request.line_ids.qty_received_on_site, 100)
        wizard = self.env['stock.return.picking'].with_context(
            active_id=picking.id, active_ids=picking.ids, active_model='stock.picking').create({})
        wizard.product_return_moves.quantity = 30
        action = wizard.action_create_returns()
        return_picking = self.env['stock.picking'].browse(action['res_id'])
        self.assertEqual(return_picking.move_ids.construction_request_line_id, request.line_ids)
        self._validate(return_picking)
        line = request.line_ids
        self.assertEqual(line.qty_received_on_site, 70)
        self.assertEqual(line.qty_dispatched, 70)
        self.assertEqual(line.line_state, 'partial')

    def test_two_lines_same_product_share_stock(self):
        self._set_stock(self.cement, self.stock, 60)
        request = self._approved_request(lines=[(self.cement, 50), (self.cement, 50)])
        self._process(request)
        first, second = request.line_ids
        self.assertEqual((first.qty_to_dispatch, first.qty_to_purchase), (50, 0))
        self.assertEqual((second.qty_to_dispatch, second.qty_to_purchase), (10, 40))

    def test_previous_reservation_is_respected(self):
        """Otro documento ya reservó parte del stock: free_qty lo descuenta."""
        self._set_stock(self.cement, self.stock, 60)
        other = self._approved_request(lines=[(self.cement, 25)])
        self._process(other)
        request = self._approved_request()
        self._process(request)
        self.assertEqual(self._dispatch_picking(request).move_ids.quantity, 35)
        self.assertEqual(request.purchase_request_ids.line_ids.product_qty, 65)

    def test_race_condition_shortage_goes_to_purchase(self):
        """La foto de disponibilidad promete más de lo que se logra reservar."""
        self._set_stock(self.cement, self.stock, 60)
        request = self._approved_request()
        Request = type(self.env['construction.material.request'])
        with patch.object(Request, '_get_free_qty_by_product',
                          lambda self, products: {p.id: 100.0 for p in products}):
            self._process(request)
        line = request.line_ids
        self.assertEqual((line.qty_to_dispatch, line.qty_to_purchase), (60, 40))
        move = self._dispatch_picking(request).move_ids
        self.assertEqual((move.product_uom_qty, move.quantity), (60, 60))
        self.assertEqual(request.purchase_request_ids.line_ids.product_qty, 40)
        self.assertIn('reservó stock antes', request.message_ids[0].body)

    def test_race_condition_nothing_reserved(self):
        request = self._approved_request()
        Request = type(self.env['construction.material.request'])
        with patch.object(Request, '_get_free_qty_by_product',
                          lambda self, products: {p.id: 100.0 for p in products}):
            self._process(request)
        self.assertEqual(self._dispatch_picking(request).move_ids.state, 'cancel')
        self.assertEqual(request.purchase_request_ids.line_ids.product_qty, 100)

    def test_cancel_with_partially_done_transfer(self):
        self._set_stock(self.cement, self.stock, 60)
        request = self._approved_request()
        self._process(request)
        picking = self._dispatch_picking(request)
        picking.move_ids.quantity = 30
        picking.move_ids.picked = True
        picking.with_context(cancel_backorder=False)._action_done()
        backorder = picking.backorder_ids
        self.assertEqual(backorder.move_ids.construction_request_line_id, request.line_ids)
        self.assertIn(backorder, request.picking_ids)
        self.assertEqual(request.line_ids.line_state, 'partial')
        pending = self._pending_picking(request)

        request.with_user(self.logistics).action_cancel()
        self.assertEqual(request.state, 'cancel')
        self.assertEqual(backorder.state, 'cancel')
        self.assertEqual(pending.state, 'cancel')
        self.assertTrue(request.purchase_request_ids.line_ids.cancelled)
        self.assertEqual(request.purchase_request_ids.state, 'rejected')
        line = request.line_ids
        self.assertEqual(line.qty_dispatched, 30)
        self.assertTrue(line.cancelled)

    def test_cancel_keeps_purchase_already_ordered(self):
        request = self._approved_request()
        self._process(request)
        order = self._buy(request.purchase_request_ids)
        request.with_user(self.logistics).action_cancel()
        self.assertFalse(request.purchase_request_ids.line_ids.cancelled)
        self.assertIn(order.name, request.message_ids[0].body)

    def test_full_flow_purchase_via_central(self):
        self._set_stock(self.cement, self.stock, 60)
        request = self._approved_request()
        self._process(request)
        self._validate(self._dispatch_picking(request))
        self.assertEqual(request.state, 'in_progress')

        order = self._buy(request.purchase_request_ids)
        # Mensaje de la OC en el requerimiento de compra: HTML real, no escapado
        pr_messages = request.purchase_request_ids.message_ids
        confirmed = pr_messages.filtered(
            lambda m: 'data-oe-model="purchase.order"' in (m.body or ''))
        self.assertTrue(confirmed)
        self.assertNotIn('&lt;', confirmed.body)
        self.assertIn('<strong>', confirmed.body)
        pending_move = self._pending_picking(request).move_ids
        receipt = order.picking_ids
        self.assertEqual(receipt.move_ids.move_dest_ids, pending_move)
        self._validate(receipt)
        # Mensaje de asignación (servicios): mismo fallo de escape en OCA
        body = self.env['purchase.request.allocation']._purchase_request_confirm_done_message_content({
            'product_name': 'Cemento <42.5>', 'product_qty': 40.0, 'product_uom': 'Unidades'})
        self.assertIn('<strong>Cemento &lt;42.5&gt;</strong>', body)
        self.assertIn('40,00', body)
        self.assertEqual(pending_move.state, 'assigned')
        self.assertEqual(pending_move.quantity, 40)
        self._validate(pending_move.picking_id)
        self.assertEqual(request.line_ids.qty_received_on_site, 100)
        self.assertEqual(request.state, 'done')
        self.assertEqual(request.purchase_order_ids, order)

    def test_full_flow_direct_to_site(self):
        request = self._approved_request(supply_mode='direct')
        self._process(request)
        self.assertFalse(request.picking_ids)
        order = self._buy(request.purchase_request_ids)
        self.assertEqual(order.order_line.location_final_id,
                         self.site_a.construction_location_id)
        receipt = order.picking_ids
        self.assertEqual(receipt.move_ids.location_dest_id,
                         self.site_a.construction_location_id)
        self._validate(receipt)
        self.assertEqual(request.line_ids.qty_received_on_site, 100)
        self.assertEqual(request.state, 'done')

    def test_direct_and_central_lines_not_merged_in_po(self):
        direct = self._approved_request(supply_mode='direct')
        central = self._approved_request()
        self._process(direct)
        self._process(central)
        prs = direct.purchase_request_ids | central.purchase_request_ids
        wizard = self.env['purchase.request.line.make.purchase.order'].with_context(
            active_model='purchase.request', active_ids=prs.ids,
        ).create({'supplier_id': self.vendor.id})
        wizard.make_purchase_order()
        self.assertEqual(len(prs.line_ids.purchase_lines), 2)

    def test_only_logistics_processes(self):
        request = self._approved_request()
        with self.assertRaises(AccessError):
            request.with_user(self.requester).action_process()
