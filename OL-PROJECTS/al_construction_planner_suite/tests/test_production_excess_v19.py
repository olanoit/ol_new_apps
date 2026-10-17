# -*- coding: utf-8 -*-
"""Exceso en la orden de fabricación (paquete 1.9, M19-04).

Cocina tipo 01 en los dos departamentos del piso 05, con el plan a S/ 10 por
unidad de material. El jefe de producción aprueba hasta el 5 % del costo de
la orden; por encima, la orden pide la aprobación a Gerencia por la tabla de
rutas. Con el exceso pendiente la orden no empieza."""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, new_test_user, tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestProductionExcess(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.write({
            'construction_approval_engine': 'approvals',
            'construction_production_margin': 5.0,
            'construction_production_margin_basis': 'order',
            'construction_production_margin_material': False,
        })
        Route = cls.env['construction.approval.route']
        Route.search([('company_id', '=', cls.company.id)]).active = False
        cls.head = new_test_user(
            cls.env, 'jefe_produccion_test', name='Jefe de producción (test)',
            groups='al_construction_planner_approvals_mrp.group_planner_production_head')
        cls.boss = new_test_user(
            cls.env, 'gerencia_of_test', name='Gerencia (test)',
            groups='al_construction_planner.group_planner_project_head,mrp.group_mrp_user')
        Route.create({
            'name': 'OF: gerencia (test)', 'company_id': cls.company.id,
            'document_type': 'production', 'change_type': 'all',
            'approver_ids': [Command.create({'user_id': cls.boss.id})]})

    def setUp(self):
        super().setUp()
        self._generate_and_approve()

    def _production(self):
        wizard = self.env['construction.plan.production.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_project=True).create({})
        wizard.action_create()
        return self.env['mrp.production'].search([('construction_plan_id', '=', self.plan.id)])

    def _move(self, production, product):
        return production.move_raw_ids.filtered(lambda m: m.product_id == product)

    def _start(self, production, user=None):
        with Form(production.with_user(user or self.env.user)) as form:
            form.qty_producing = production.product_qty

    def test_in_budget_starts(self):
        production = self._production()
        production.action_confirm()
        self.assertEqual(production.construction_exceed_state, 'ok')
        self.assertEqual(production.construction_approval_engine, 'approvals')
        hinge = production.construction_versus_ids.filtered(
            lambda r: r.product_id == self.p_hinge)
        self.assertEqual(hinge.qty_budget, 20)
        self.assertEqual(hinge.qty_required, 20)
        self.assertFalse(hinge.change_type)
        self.assertAlmostEqual(hinge.amount_budget, 200.0)
        self._start(production)
        self.assertEqual(production.qty_producing, production.product_qty)

    def test_small_excess_approved_by_production_head(self):
        production = self._production()
        self._move(production, self.p_white).product_uom_qty += 0.5
        production.action_confirm()
        self.assertEqual(production.construction_exceed_state, 'exceeded')
        self.assertAlmostEqual(production.construction_excess_amount, 5.0, places=2)
        self.assertLess(production.construction_excess_pct, 5.0)
        white = production.construction_versus_ids.filtered(
            lambda r: r.product_id == self.p_white)
        self.assertEqual(white.change_type, 'quantity')
        self.assertAlmostEqual(white.qty_diff, 0.5)
        with self.assertRaises(UserError):
            self._start(production)
        as_head = production.with_user(self.head)
        self.assertEqual(as_head.construction_excess_action, 'approve')
        self.assertEqual(production.construction_excess_action, 'request', 'no es jefe')
        action = as_head.action_construction_approve_excess()
        self.env[action['res_model']].with_user(self.head).with_context(
            action['context']).create({'reason': 'Merma del corte (test)'}).action_approve()
        self.assertEqual(production.construction_exceed_state, 'approved')
        self.assertEqual(production.construction_excess_approved_by, self.head)
        logs = self.env['construction.exceed.log'].search([
            ('res_model', '=', 'mrp.production'), ('res_id', '=', production.id)])
        self.assertEqual(logs.product_id, self.p_white)
        self.assertEqual(logs.user_id, self.head)
        self._start(production)

    def test_large_excess_goes_to_approvals(self):
        production = self._production()
        self._move(production, self.p_hinge).product_uom_qty += 10
        production.action_confirm()
        self.assertGreater(production.construction_excess_pct, 5.0)
        as_head = production.with_user(self.head)
        self.assertEqual(as_head.construction_excess_action, 'request')
        as_head.action_construction_request_excess_approval()
        approval = production.construction_approval_id
        self.assertEqual(approval.construction_res_model, 'mrp.production')
        self.assertEqual(approval.approver_ids.user_id, self.boss)
        self.assertEqual(approval.product_line_ids.product_id, self.p_hinge)
        self.assertFalse(as_head.construction_excess_action, 'ya está pedida')
        with self.assertRaises(UserError):
            self._start(production)
        production.with_user(self.boss).action_construction_approve()
        self.assertEqual(production.construction_exceed_state, 'approved')
        self.assertEqual(production.construction_excess_approved_by, self.boss)
        self._start(production)

    def test_refused_excess_stays_pending(self):
        production = self._production()
        self._move(production, self.p_hinge).product_uom_qty += 10
        production.action_confirm()
        production.with_user(self.head).action_construction_request_excess_approval()
        action = production.with_user(self.boss).action_construction_refuse()
        self.env[action['res_model']].with_user(self.boss).with_context(
            action['context']).create({'reason': 'Use las bisagras del plan'}).action_refuse()
        self.assertEqual(production.construction_exceed_state, 'exceeded')
        self.assertIn('Use las bisagras del plan', ' '.join(production.message_ids.mapped('body')))
        # Se corrige el componente y la comparación libera la orden.
        self._move(production, self.p_hinge).product_uom_qty -= 10
        production.action_construction_refresh_versus()
        self.assertEqual(production.construction_exceed_state, 'ok')

    def test_material_change_needs_approvals(self):
        silicone = self.env['product.product'].create({
            'name': 'Silicona (test)', 'standard_price': 3.0, 'is_storable': True})
        production = self._production()
        production.write({'move_raw_ids': [Command.create({
            'product_id': silicone.id, 'product_uom_qty': 1,
            'location_id': production.location_src_id.id,
            'location_dest_id': production.production_location_id.id,
            'raw_material_production_id': production.id})]})
        production.action_confirm()
        self.assertTrue(production.construction_excess_material)
        self.assertEqual(production.with_user(self.head).construction_excess_action, 'request')
        self.company.construction_production_margin_material = True
        production.invalidate_recordset(['construction_excess_action'])
        self.assertEqual(production.with_user(self.head).construction_excess_action, 'approve')

    def test_under_budget_is_recorded_without_approval(self):
        production = self._production()
        self._move(production, self.p_hinge).product_uom_qty -= 4
        production.action_confirm()
        self.assertEqual(production.construction_exceed_state, 'ok')
        hinge = production.construction_versus_ids.filtered(
            lambda r: r.product_id == self.p_hinge)
        self.assertAlmostEqual(hinge.qty_diff, -4)
        self.assertAlmostEqual(hinge.amount_diff, -40.0)
