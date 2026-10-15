# -*- coding: utf-8 -*-
"""v1.5, fase 20: pestaña «Planificación» de la obra."""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestPlanningTabV15(PlannerCommon):

    def test_margins_and_buttons(self):
        project = self.project
        empty = self.env['project.project'].create({
            'name': 'Obra sin plan (test)', 'is_construction_site': True})
        with self.assertRaises(UserError):
            empty.action_construction_open_tree()
        self._generate_and_approve()
        product = self.env['product.product'].create({'name': 'Cocinas (test)', 'type': 'service'})
        order = self.env['sale.order'].create({
            'partner_id': self.contractor.id,
            'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': 1,
                                           'price_unit': 5000.0, 'tax_ids': [Command.clear()]})]})
        project.construction_sale_order_id = order
        if not project.account_id:
            project._create_analytic_account()
        self.env['account.analytic.line'].create([
            {'name': 'Factura (test)', 'account_id': project.account_id.id, 'amount': 3000.0},
            {'name': 'Consumo (test)', 'account_id': project.account_id.id, 'amount': -1200.0},
        ])
        project.invalidate_recordset()
        cost = sum(self.plan.line_ids.mapped('amount_planned'))
        self.assertEqual(project.construction_current_plan_id, self.plan)
        self.assertEqual(project.construction_income_planned, 5000.0)
        self.assertAlmostEqual(project.construction_cost_planned, cost, 2)
        self.assertAlmostEqual(project.construction_margin_planned, 5000.0 - cost, 2)
        self.assertAlmostEqual(project.construction_margin_planned_pct, (5000.0 - cost) / 5000.0)
        self.assertEqual(project.construction_income_accounting, 3000.0)
        self.assertEqual(project.construction_cost_accounting, 1200.0)
        self.assertEqual(project.construction_margin_accounting, 1800.0)
        self.assertAlmostEqual(project.construction_margin_accounting_pct, 0.6)
        self.assertEqual(project.construction_income_earned, 0.0)
        self.assertEqual(project.action_construction_open_tree()['tag'],
                         'al_construction_planner.plan_tree')
        self.assertEqual(project.action_construction_open_schedule()['context']
                         ['construction_plan_id'], self.plan.id)
