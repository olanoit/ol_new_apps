# -*- coding: utf-8 -*-
"""Aprobaciones en la aplicación Aprobaciones (paquete 1.9, M19-03 y M19-07).

El requerimiento sin cambios frente al plan va directo al almacén; un
material fuera del plan va a Oficina Técnica y más cantidad que el saldo, a
Oficina Técnica o a la jefatura (basta uno). Los tramos van en escalera y el
resultado vuelve al documento."""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from .common import PlannerCommon
from .test_request_scope import TestRequestScope


class ApprovalRoutesMixin:

    @classmethod
    def _setup_routes(cls):
        cls.company.construction_approval_engine = 'approvals'
        Route = cls.env['construction.approval.route']
        Route.search([('company_id', '=', cls.company.id)]).active = False
        cls.technical = new_test_user(
            cls.env, 'ot_test', name='Oficina técnica (test)',
            groups='al_construction_planner_approvals.group_planner_technical_office')
        cls.head = new_test_user(
            cls.env, 'jefatura_test', name='Jefatura de proyectos (test)',
            groups='al_construction_planner.group_planner_project_head')
        cls.boss = new_test_user(
            cls.env, 'gerencia_test', name='Gerencia (test)',
            groups='al_construction_planner.group_planner_project_head')

    @classmethod
    def _route(cls, name, document_type, change_type='all', threshold=0.0, basis='percent',
               users=(), groups=(), rule='any'):
        return cls.env['construction.approval.route'].create({
            'name': name, 'company_id': cls.company.id, 'document_type': document_type,
            'change_type': change_type, 'threshold': threshold, 'basis': basis,
            'approval_rule': rule,
            'approver_ids': [Command.create({'user_id': user.id}) for user in users]
            + [Command.create({'group_id': group.id}) for group in groups]})


@tagged('post_install', '-at_install')
class TestApprovalsRequest(ApprovalRoutesMixin, TestRequestScope):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_routes()
        cls.route_material = cls._route(
            'Material: oficina técnica (test)', 'material_request', 'material',
            users=cls.technical)
        cls.route_qty = cls._route(
            'Cantidad: oficina técnica o jefatura (test)', 'material_request', 'quantity',
            users=cls.technical | cls.head)
        cls.p_silicone = cls.env['product.product'].create({
            'name': 'Silicona transparente (test)', 'standard_price': 12.0})

    def _fetched(self, space=None):
        request = self._new_request()
        self._scope(request, spaces=space or self.space_501, stages=self.stage_assembly)
        request.action_construction_fetch_plan()
        return request

    def _hinge(self, request):
        return request.line_ids.filtered(lambda l: l.product_id == self.p_hinge)

    def _submit(self, request):
        request.with_user(self.requester).action_request_approval()
        return request

    def _out_of_plan(self):
        request = self._fetched()
        request.write({'line_ids': [Command.create({
            'product_id': self.p_silicone.id, 'product_qty': 3,
            'task_id': self.space_501.id, 'construction_stage': 'assembly'})]})
        return self._submit(request)

    def test_without_changes_goes_to_warehouse(self):
        request = self._submit(self._fetched())
        self.assertEqual(request.state, 'approved')
        self.assertEqual(request.construction_approval_engine, 'approvals')
        self.assertFalse(request.construction_approval_ids)
        self.assertFalse(request.review_ids)

    def test_material_out_of_plan_goes_to_technical_office(self):
        request = self._out_of_plan()
        self.assertEqual(request.state, 'to_approve')
        self.assertFalse(request.review_ids)
        approval = request.construction_approval_id
        self.assertEqual(approval.construction_res_model, 'construction.material.request')
        self.assertEqual(approval.construction_res_id, request.id)
        self.assertEqual(approval.request_status, 'pending')
        self.assertEqual(approval.approver_ids.user_id, self.technical)
        silicone = approval.product_line_ids.filtered(lambda l: l.product_id == self.p_silicone)
        self.assertEqual(silicone.construction_change_type, 'material')
        self.assertEqual(silicone.quantity, 3)
        self.assertEqual(silicone.construction_amount_diff, 36.0)
        self.assertEqual(len(approval.product_line_ids), 1, 'solo los cambios')
        # La jefatura no está en la ruta del cambio de material.
        with self.assertRaises(UserError):
            request.with_user(self.head).action_construction_approve()
        as_technical = request.with_user(self.technical)
        self.assertTrue(as_technical.construction_approval_can_review)
        as_technical.action_construction_approve()
        self.assertEqual(approval.request_status, 'approved')
        self.assertEqual(request.state, 'approved')

    def test_quantity_change_any_of_two(self):
        request = self._fetched()
        self._hinge(request).product_qty += 2
        self._submit(request)
        approval = request.construction_approval_id
        self.assertEqual(request.state, 'to_approve')
        self.assertEqual(approval.approver_ids.user_id, self.technical | self.head)
        hinge = approval.product_line_ids
        self.assertEqual(hinge.construction_change_type, 'quantity')
        self.assertEqual(hinge.construction_qty_diff, 2)
        request.with_user(self.head).action_construction_approve()
        self.assertEqual(request.state, 'approved')
        self.assertEqual(request.construction_exceed_state, 'approved')
        technical = approval.approver_ids.filtered(lambda a: a.user_id == self.technical)
        self.assertEqual(technical.status, 'cancel')
        self.assertFalse(approval.activity_ids)

    def test_ladder_by_percentage(self):
        self._route('Cantidad sobre 50 %: gerencia (test)', 'material_request', 'quantity',
                    threshold=50.0, users=self.boss)
        small = self._fetched()
        self._hinge(small).product_qty += 1
        self._submit(small)
        self.assertEqual(small.construction_approval_id.construction_step_count, 1)
        big = self._fetched(self.space_502)
        self._hinge(big).product_qty *= 3
        self._submit(big)
        approval = big.construction_approval_id
        self.assertEqual(approval.construction_step_count, 2)
        self.assertEqual(approval.construction_current_step, 1)
        boss = approval.approver_ids.filtered(lambda a: a.user_id == self.boss)
        self.assertEqual(boss.status, 'waiting')
        self.assertFalse(big.with_user(self.boss).construction_approval_can_review)
        with self.assertRaises(UserError):
            approval.with_user(self.boss).action_approve()
        big.with_user(self.technical).action_construction_approve()
        self.assertEqual(big.state, 'to_approve')
        self.assertEqual(approval.construction_current_step, 2)
        self.assertEqual(boss.status, 'pending')
        self.assertIn('Gerencia', big.construction_approval_todo)
        big.with_user(self.boss).action_construction_approve()
        self.assertEqual(big.state, 'approved')

    def test_refuse_returns_to_draft_with_reason(self):
        request = self._out_of_plan()
        action = request.with_user(self.technical).action_construction_refuse()
        wizard = self.env[action['res_model']].with_user(self.technical).with_context(
            action['context']).create({'reason': 'Usar la silicona del stock de obra'})
        wizard.action_refuse()
        self.assertEqual(request.construction_approval_ids.request_status, 'refused')
        self.assertEqual(request.state, 'draft')
        self.assertIn('Usar la silicona del stock de obra',
                      ' '.join(request.message_ids.mapped('body')))
        # Se corrige y se vuelve a enviar: otra solicitud.
        request.line_ids.filtered(lambda l: l.product_id == self.p_silicone).unlink()
        self._submit(request)
        self.assertEqual(request.state, 'approved')
        self.assertEqual(len(request.construction_approval_ids), 1)

    def test_rule_all_with_group(self):
        self.route_material.write({
            'approval_rule': 'all',
            'approver_ids': [Command.create({'group_id': self.env['res.groups'].create({
                'name': 'Comité de obra (test)',
                'user_ids': [Command.set((self.head | self.boss).ids)]}).id})]})
        request = self._out_of_plan()
        approval = request.construction_approval_id
        self.assertEqual(approval.approver_ids.user_id, self.technical | self.head | self.boss)
        request.with_user(self.technical).action_construction_approve()
        self.assertEqual(request.state, 'to_approve', 'falta alguien del comité')
        request.with_user(self.boss).action_construction_approve()
        self.assertEqual(request.state, 'approved')
        head = approval.approver_ids.filtered(lambda a: a.user_id == self.head)
        self.assertEqual(head.status, 'cancel')

    def test_draft_cancels_open_request(self):
        request = self._out_of_plan()
        approval = request.construction_approval_id
        request.with_user(self.requester).action_draft()
        self.assertEqual(request.state, 'draft')
        self.assertEqual(approval.request_status, 'cancel')
        self.assertFalse(approval.activity_ids)

    def test_same_user_in_two_steps(self):
        """Odoo no repite un usuario en una solicitud: quien está en dos
        tramos aprueba una vez y cuenta en los dos."""
        self._route('Cantidad sobre 50 %: jefatura (test)', 'material_request', 'quantity',
                    threshold=50.0, users=self.head)
        request = self._fetched()
        self._hinge(request).product_qty *= 3
        self._submit(request)
        approval = request.construction_approval_id
        self.assertEqual(approval.construction_step_count, 2)
        self.assertEqual(len(approval.approver_ids.filtered(lambda a: a.user_id == self.head)), 1)
        self.assertEqual(approval.with_user(self.head).user_status, 'pending')
        request.with_user(self.head).action_construction_approve()
        self.assertEqual(request.state, 'approved')

    def test_missing_route_stops_the_request(self):
        self.route_material.active = False
        request = self._fetched()
        request.write({'line_ids': [Command.create({
            'product_id': self.p_silicone.id, 'product_qty': 1, 'task_id': self.space_501.id,
            'construction_stage': 'assembly'})]})
        with self.assertRaises(UserError):
            self._submit(request)

    def test_tier_engine_keeps_reviews(self):
        """Con la validación por niveles, el requerimiento sigue como antes."""
        self.company.construction_approval_engine = 'tier'
        self.plan.write({'exceed_policy': 'approval', 'exceed_policy_material': 'approval'})
        request = self._fetched()
        self._hinge(request).product_qty += 2
        request.construction_exceed_reason = 'Cambio de bisagras (test)'
        request.with_user(self.requester).with_context(
            construction_exceed_checked=True).action_request_approval()
        self.assertEqual(request.construction_approval_engine, 'tier')
        self.assertTrue(request.review_ids)
        self.assertFalse(request.construction_approval_ids)


@tagged('post_install', '-at_install')
class TestApprovalsPlan(ApprovalRoutesMixin, PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_routes()
        cls._route('Plan: jefatura (test)', 'plan', basis='amount', users=cls.head)
        cls._route('Plan sobre un millón: gerencia (test)', 'plan', basis='amount',
                   threshold=1000000.0, users=cls.boss)

    def test_plan_approved_in_approvals(self):
        self._generate()
        lines = self.plan.line_ids
        lines.filtered(lambda l: not l.stage).stage = 'production'
        for line in lines.filtered(lambda l: not l.price_unit_planned):
            line.price_unit_planned = 10.0
        self.plan.action_request_approval()
        self.assertEqual(self.plan.state, 'to_approve')
        approval = self.plan.construction_approval_id
        self.assertEqual(approval.construction_step_count, 1, 'por debajo del millón')
        self.assertEqual(approval.approver_ids.user_id, self.head)
        self.assertEqual(self.plan.construction_approval_count, 1)
        self.plan.with_user(self.head).action_construction_approve()
        self.assertEqual(self.plan.state, 'approved')
        self.assertTrue(self.plan.date_approved)


# Las pruebas heredadas ya corren en sus clases.
for _base in (TestRequestScope, PlannerCommon):
    for _name in dir(_base):
        if _name.startswith('test_') and callable(getattr(_base, _name)):
            for _cls in (TestApprovalsRequest, TestApprovalsPlan):
                if _name not in _cls.__dict__ and hasattr(_cls, _name):
                    setattr(_cls, _name, None)
