# -*- coding: utf-8 -*-
"""Aprobaciones del paquete 1.10: lista con los datos para decidir y
aprobación en bloque (M110-07), cifras de la solicitud con saldo negativo y
rechazo después de aprobar (M110-08)."""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PlannerCommon
from .test_approvals_v19 import TestApprovalsRequest
from .test_request_scope import TestRequestScope


@tagged('post_install', '-at_install')
class TestApprovalsV110(TestApprovalsRequest):

    def _quantity_change(self, extra=2, space=None):
        request = self._fetched(space)
        self._hinge(request).product_qty += extra
        return self._submit(request)

    def test_summary_fields(self):
        quantity = self._quantity_change(space=self.space_502).construction_approval_id
        self.assertEqual(quantity.construction_change_summary, 'quantity')
        self.assertEqual(quantity.construction_excess_lines, 1)
        self.assertTrue(quantity.construction_excess_qty_label.startswith('2 '))
        self.assertAlmostEqual(quantity.construction_excess_pct, 20.0)
        material = self._out_of_plan().construction_approval_id
        self.assertEqual(material.construction_change_summary, 'material')
        self.assertAlmostEqual(material.construction_excess_pct, 100.0)
        # Una línea de cada tipo: «Ambos» y el número de materiales.
        material.sudo().product_line_ids = [Command.create({
            'product_id': self.p_hinge.id, 'description': 'Bisagra (test)', 'quantity': 12,
            'product_uom_id': self.p_hinge.uom_id.id, 'construction_change_type': 'quantity',
            'construction_qty_diff': 2, 'construction_diff_pct': 20.0})]
        self.assertEqual(material.construction_change_summary, 'both')
        self.assertEqual(material.construction_excess_lines, 2)
        self.assertEqual(material.construction_excess_qty_label, '2 materiales')
        mine = self.env['approval.request'].with_user(self.technical).search(
            [('approver_ids.user_id', '=', self.technical.id),
             ('approver_ids.status', '=', 'pending')])
        self.assertTrue((quantity | material) <= mine)
        self.assertNotIn(quantity, self.env['approval.request'].with_user(self.boss).search(
            [('approver_ids.user_id', '=', self.boss.id),
             ('approver_ids.status', '=', 'pending')]))

    def test_bulk_approve(self):
        first = self._quantity_change()
        second = self._quantity_change(space=self.space_502)
        approvals = first.construction_approval_id | second.construction_approval_id
        result = approvals.with_user(self.boss).action_construction_bulk_approve()
        self.assertIn('No le toca aprobar', result['params']['message'])
        self.assertEqual(set(approvals.mapped('request_status')), {'pending'})
        approvals.with_user(self.technical).action_construction_bulk_approve()
        self.assertEqual(set(approvals.mapped('request_status')), {'approved'})
        self.assertEqual((first | second).mapped('state'), ['approved', 'approved'])

    def test_bulk_refuse(self):
        first = self._quantity_change()
        second = self._quantity_change(space=self.space_502)
        approvals = first.construction_approval_id | second.construction_approval_id
        wizard = self.env['construction.approval.refuse.wizard'].with_user(
            self.technical).with_context(active_model='approval.request',
                                         active_ids=approvals.ids).create(
            {'reason': 'Use las bisagras del plan (test)'})
        self.assertEqual(wizard.approval_ids, approvals)
        wizard.action_refuse()
        self.assertEqual(set(approvals.mapped('request_status')), {'refused'})
        for request in first | second:
            self.assertEqual(request.state, 'draft')
            self.assertIn('Use las bisagras del plan (test)',
                          ' '.join(request.message_ids.mapped('body')))

    def test_negative_balance_figures(self):
        """4 presupuestados y 24 ya pedidos en la especificación; aquí 10
        presupuestados (la bisagra del ambiente) y 34 ya pedidos."""
        first = self._quantity_change(extra=24)
        first.with_user(self.head).action_construction_approve()
        self.assertEqual(first.state, 'approved')
        request = self._new_request()
        self._scope(request, spaces=self.space_501, stages=self.stage_assembly)
        request.write({'line_ids': [Command.create({
            'product_id': self.p_hinge.id, 'product_qty': 20,
            'task_id': self.space_501.id, 'construction_stage': 'assembly'})]})
        self._submit(request)
        line = request.construction_approval_id.product_line_ids
        self.assertEqual(line.construction_qty_planned, 10)
        self.assertEqual(line.construction_qty_requested_before, 34)
        self.assertEqual(line.construction_qty_budget, -24)
        self.assertEqual(line.quantity, 20)
        self.assertEqual(line.construction_qty_diff, 20, 'nunca más que lo pedido')
        self.assertAlmostEqual(line.construction_diff_pct, 200.0)

    def test_refuse_after_approval_is_blocked(self):
        request = self._quantity_change()
        approval = request.construction_approval_id
        request.with_user(self.head).action_construction_approve()
        self.assertEqual(request.state, 'approved')
        self.assertEqual(approval.approver_ids.filtered(
            lambda a: a.user_id == self.technical).status, 'cancel',
            'el sistema cancela al otro aprobador sin error')
        with self.assertRaises(UserError):
            approval.with_user(self.head).action_refuse()
        with self.assertRaises(UserError):
            approval.approver_ids.filtered(lambda a: a.user_id == self.head).status = 'refused'
        self.assertEqual(request.state, 'approved')
        self.assertEqual(approval.request_status, 'approved')


# Las pruebas heredadas ya corren en sus clases.
for _base in (TestApprovalsRequest, TestRequestScope, PlannerCommon):
    for _name in dir(_base):
        if _name.startswith('test_') and callable(getattr(_base, _name)) \
                and _name not in vars(TestApprovalsV110):
            setattr(TestApprovalsV110, _name, None)
