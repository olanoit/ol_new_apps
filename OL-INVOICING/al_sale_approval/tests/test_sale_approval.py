# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestSaleApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.approver = new_test_user(cls.env, 'aprobador_venta', name='Gerencia (test)',
                                     groups='approvals.group_approval_user')
        cls.category = cls.env['approval.category'].create({
            'name': 'Aprobación de orden de venta (test)', 'has_reference': 'required',
            'approver_ids': [(0, 0, {'user_id': cls.approver.id, 'required': True})]})
        cls.env.company.sale_approval_category_id = cls.category
        cls.partner = cls.env['res.partner'].create({'name': 'Cliente (test)'})
        cls.guarded = cls.env['product.product'].create({
            'name': 'Muebles de melamina (test)', 'type': 'service',
            'sale_approval_required': True})
        cls.free = cls.env['product.product'].create({'name': 'Flete (test)', 'type': 'service'})
        cls.salesman = new_test_user(cls.env, 'vendedor_ap', name='Vendedor (test)',
                                     groups='sales_team.group_sale_salesman')

    def _order(self, product, **vals):
        return self.env['sale.order'].create(dict({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {'product_id': product.id, 'price_unit': 100.0})]}, **vals))

    def test_free_product_confirms(self):
        order = self._order(self.free)
        self.assertEqual(order.sale_approval_state, 'not_required')
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_request_and_approve(self):
        order = self._order(self.guarded, user_id=self.salesman.id).with_user(self.salesman)
        self.assertEqual(order.sale_approval_state, 'to_request')
        with self.assertRaises(UserError):
            order.action_confirm()
        action = order.action_request_sale_approval()
        request = self.env['approval.request'].browse(action['res_id'])
        self.assertEqual((request.sale_order_id, request.reference), (order, order.name))
        request.action_confirm()
        order.invalidate_recordset(['sale_approval_state'])
        self.assertEqual(order.sale_approval_state, 'pending')
        with self.assertRaises(UserError):
            order.action_confirm()
        request.with_user(self.approver).action_approve()
        order.invalidate_recordset(['sale_approval_state', 'sale_approval_request_count'])
        self.assertEqual(order.sale_approval_state, 'approved')
        self.assertEqual(order.sale_approval_request_count, 1)
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_legacy_request_by_reference(self):
        """Las solicitudes previas al módulo valen por la referencia."""
        order = self._order(self.guarded)
        request = self.env['approval.request'].create({
            'name': 'Aprobación (anterior)', 'category_id': self.category.id,
            'reference': order.name, 'request_owner_id': self.env.user.id})
        request.action_confirm()
        request.with_user(self.approver).action_approve()
        order.invalidate_recordset(['sale_approval_state'])
        self.assertEqual(order.sale_approval_state, 'approved')
        order.action_confirm()

    def test_historical_load_exempt(self):
        order = self._order(self.guarded, sale_approval_exempt=True)
        self.assertEqual(order.sale_approval_state, 'not_required')
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_refused(self):
        order = self._order(self.guarded)
        request = self.env['approval.request'].browse(order.action_request_sale_approval()['res_id'])
        request.action_confirm()
        request.with_user(self.approver).action_refuse()
        order.invalidate_recordset(['sale_approval_state'])
        self.assertEqual(order.sale_approval_state, 'refused')
