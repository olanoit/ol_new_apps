# -*- coding: utf-8 -*-
"""Orden de fabricación del mueble (paquete 1.9): accesorios de armado
(M19-02) y presupuestado, requerido y consumido (M19-05).

Cocina tipo 01 en los dos departamentos del piso 05: la bisagra es el
accesorio de Armado del plan (10 por cocina)."""
from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, new_test_user, tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestProductionOrder(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.construction_approval_engine = 'approvals'
        Route = cls.env['construction.approval.route']
        Route.search([('company_id', '=', cls.company.id)]).active = False
        cls.head = new_test_user(
            cls.env, 'jefe_prod_acc_test', name='Jefe de producción (test)',
            groups='al_construction_planner_approvals_mrp.group_planner_production_head')
        cls.technical = new_test_user(
            cls.env, 'ot_acc_test', name='Oficina técnica (test)',
            groups='al_construction_planner_approvals.group_planner_technical_office')
        cls.manager = new_test_user(
            cls.env, 'jp_acc_test', name='Jefe de proyectos (test)',
            groups='al_construction_planner.group_planner_planner')
        cls.operator = new_test_user(
            cls.env, 'operario_acc_test', name='Operario (test)', groups='mrp.group_mrp_user')
        cls.project.user_id = cls.manager
        Route.create({
            'name': 'Accesorios: oficina técnica (test)', 'company_id': cls.company.id,
            'document_type': 'accessories', 'change_type': 'all',
            'approver_ids': [Command.create({'user_id': cls.technical.id})]})
        cls.other_hinge = cls.env['product.product'].create({
            'name': 'Bisagra cierre lento (test)', 'standard_price': 15.0, 'is_storable': True})

    def setUp(self):
        super().setUp()
        self._generate_and_approve()

    def _production(self):
        wizard = self.env['construction.plan.production.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_project=True).create({})
        wizard.action_create()
        return self.env['mrp.production'].search([('construction_plan_id', '=', self.plan.id)])

    def _hinges(self, production):
        return sum(production.move_raw_ids.filtered(
            lambda m: m.product_id == self.p_hinge).mapped('product_uom_qty'))

    def _request(self, production, user=None):
        action = production.with_user(user or self.head).action_construction_request_accessories()
        return self.env['construction.accessory.request'].browse(action['res_id'])

    def test_accessories_without_changes_go_to_the_order(self):
        production = self._production()
        production.action_confirm()
        before = self._hinges(production)
        request = self._request(production)
        self.assertEqual(sum(request.line_ids.mapped('qty_balance')), 20)
        self.assertEqual(request.line_ids.planned_product_id, self.p_hinge)
        self.assertFalse(request.has_changes)
        request.with_user(self.head).action_submit()
        self.assertEqual(request.state, 'done')
        self.assertEqual(self._hinges(production), before + 20)
        self.assertFalse(request.construction_approval_ids)
        # Lo pedido ya no se vuelve a proponer.
        again = self._request(production)
        self.assertFalse(again.line_ids)

    def test_changed_accessory_goes_to_technical_office(self):
        production = self._production()
        production.action_confirm()
        request = self._request(production)
        request.line_ids[:1].product_id = self.other_hinge
        self.assertTrue(request.has_changes)
        self.assertEqual(request.line_ids[:1].change_type, 'material')
        with self.assertRaises(UserError):
            request.with_user(self.head).action_submit()
        request.note = 'Cliente pidió cierre lento (test)'
        request.with_user(self.head).action_submit()
        self.assertEqual(request.state, 'to_approve')
        approval = request.construction_approval_id
        self.assertEqual(approval.approver_ids.user_id, self.technical)
        self.assertEqual(approval.product_line_ids.product_id, self.other_hinge)
        self.assertIn(self.manager.partner_id, request.message_partner_ids)
        request.with_user(self.technical).action_construction_approve()
        self.assertEqual(request.state, 'done')
        self.assertIn(self.other_hinge, production.move_raw_ids.product_id)

    def test_quantity_over_balance_is_a_change(self):
        production = self._production()
        request = self._request(production)
        line = request.line_ids[:1]
        line.qty = line.qty_balance + 2
        self.assertEqual(line.change_type, 'quantity')
        self.assertAlmostEqual(line.amount_diff, 20.0)

    def test_who_requests(self):
        production = self._production()
        with self.assertRaises(AccessError):
            production.with_user(self.operator).action_construction_request_accessories()
        production.construction_accessories_user_id = self.operator
        request = self._request(production, user=self.operator)
        self.assertTrue(request.line_ids)

    def test_confirm_without_accessories_warns(self):
        production = self._production()
        production.action_confirm()
        message = production.message_ids.filtered(
            lambda m: 'sin pedir los accesorios' in (m.body or ''))
        self.assertTrue(message)
        self.assertIn(self.manager.partner_id, message.partner_ids)

    def test_budget_required_consumed(self):
        production = self._production()
        production.action_confirm()
        with Form(production) as form:
            form.qty_producing = production.product_qty
        for move in production.move_raw_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        production.button_mark_done()
        self.assertEqual(production.state, 'done')
        hinge = production.construction_versus_ids.filtered(
            lambda r: r.product_id == self.p_hinge)
        self.assertEqual(hinge.qty_consumed, 20)
        rows = production.construction_analysis_ids
        self.assertEqual(set(rows.space_task_id.ids), {self.space_501.id, self.space_502.id})
        self.assertEqual(rows.floor_task_id, self.floor)
        hinge_rows = rows.filtered(lambda r: r.product_id == self.p_hinge)
        self.assertAlmostEqual(sum(hinge_rows.mapped('qty_budget')), hinge.qty_budget)
        self.assertAlmostEqual(sum(hinge_rows.mapped('qty_required')), hinge.qty_required)
        self.assertAlmostEqual(sum(hinge_rows.mapped('qty_consumed')), 20)
        self.assertAlmostEqual(sum(rows.mapped('amount_budget')),
                               sum(production.construction_versus_ids.mapped('amount_budget')))
        self.assertEqual(set(hinge_rows.mapped('stage')), {'assembly'})
