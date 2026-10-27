# -*- coding: utf-8 -*-
"""Paquete 1.12, M112-04: modalidad de ejecución por defecto en la etapa.

«Generar plan» de mobiliario busca la modalidad del nivel con etapas (el
ambiente), luego la de la actividad, luego la de su etapa y, al final,
personal propio. La tipología 01 de PlannerCommon tiene armado por módulo,
colocación de puertas y entarugado (armado) e instalación por ML."""
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestPackage112Mode(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # El catálogo como viene: todas las etapas en personal propio.
        cls.stages = cls.env['construction.stage'].with_context(active_test=False).search([])
        cls.stages.default_execution_mode = 'own'
        Plan = cls.env['account.analytic.plan']
        Account = cls.env['account.analytic.account']
        plan_cost = Plan.create({'name': 'Partida (test 112 modo)'})
        cls.mod_fixed = Account.create({'name': '4 MOD fija', 'plan_id': plan_cost.id})
        cls.mod_variable = Account.create({'name': '5 MOD variable', 'plan_id': plan_cost.id})
        if not cls.project.account_id:
            cls.project._create_analytic_account()
        cls.env['construction.analytic.rule'].create([
            {'resource_type': 'labor', 'cost_account_id': cls.mod_fixed.id},
            {'resource_type': 'contract', 'cost_account_id': cls.mod_variable.id},
        ])

    def _activity_lines(self):
        return self.plan.line_ids.filtered('activity_id')

    def _types(self, activity):
        return set(self._activity_lines().filtered(
            lambda l: l.activity_id == activity).mapped('resource_type'))

    def _accounts(self, line):
        key = next(iter(line.analytic_distribution or {}), '')
        return self.env['account.analytic.account'].browse(int(a) for a in key.split(',') if a)

    def test_default_catalog_is_own_staff(self):
        self.assertEqual(self.env['construction.stage'].create(
            {'name': 'Nueva (test 112)', 'code': 'new112'}).default_execution_mode, 'own')
        self._generate()
        lines = self._activity_lines()
        self.assertTrue(lines)
        self.assertEqual(set(lines.mapped('resource_type')), {'labor'},
                         'ninguna línea de contrata')
        # El precio de hoy: tarifa de la obra o tarifa base.
        install = lines.filtered(lambda l: l.activity_id == self.act_inst_low)[0]
        self.assertEqual(install.price_unit_planned, 18.0)
        screw = lines.filtered(lambda l: l.activity_id == self.act_screw)[0]
        self.assertEqual(screw.price_unit_planned, 6.0)
        self.assertEqual(screw.qty_planned, 1.0)
        self.assertEqual(screw.product_uom_id, self.act_screw.uom_id)
        self.assertIn(self.mod_fixed, self._accounts(screw), 'analítica de personal propio')

    def test_stage_in_contract(self):
        self.stages.filtered(lambda s: s.code == 'assembly').default_execution_mode = \
            'labor_contract'
        self._generate()
        self.assertEqual(self._types(self.act_screw), {'contract'})
        self.assertEqual(self._types(self.act_doors), {'contract'})
        self.assertEqual(self._types(self.act_inst_low), {'labor'})
        contract = self._activity_lines().filtered(lambda l: l.resource_type == 'contract')[0]
        self.assertIn(self.mod_variable, self._accounts(contract))

    def test_priority_activity_then_space(self):
        self.stages.filtered(lambda s: s.code == 'assembly').default_execution_mode = \
            'labor_contract'
        self.act_doors.execution_mode = 'own'
        self.act_inst_low.execution_mode = 'labor_contract'
        self._generate()
        self.assertEqual(self._types(self.act_doors), {'labor'}, 'la actividad manda sobre la etapa')
        self.assertEqual(self._types(self.act_inst_low), {'contract'})
        self.assertEqual(self._types(self.act_screw), {'contract'})
        # El ambiente manda sobre las dos.
        self.space_501.construction_execution_mode = 'own'
        self._generate()
        lines = self._activity_lines()
        self.assertEqual(set(lines.filtered(
            lambda l: l.space_task_id == self.space_501).mapped('resource_type')), {'labor'})
        self.assertIn('contract', lines.filtered(
            lambda l: l.space_task_id == self.space_502).mapped('resource_type'))

    def test_full_contract_warns(self):
        self.act_doors.execution_mode = 'full_contract'
        wizard = self._wizard()
        self.assertIn(self.act_doors.display_name, wizard.warning_html)
        wizard.action_generate()
        self.assertEqual(self._types(self.act_doors), {'contract'})

    def test_space_mode_change_after_approval(self):
        self._generate_and_approve()
        with self.assertRaises(UserError):
            self.space_501.construction_execution_mode = 'labor_contract'
        # En una versión nueva del plan sí se cambia.
        self.env['construction.resource.plan'].create({'project_id': self.project.id})
        self.space_501.construction_execution_mode = 'labor_contract'
        self.assertEqual(self.space_501.construction_execution_mode, 'labor_contract')

    def test_own_lines_for_crew(self):
        self._generate()
        planner = new_test_user(
            self.env, 'm112_planificador', name='Planificador (test 112)',
            groups='al_construction_planner.group_planner_planner')
        lines = self.plan.with_user(planner).line_ids.filtered(
            lambda l: l.resource_type == 'labor')
        self.assertTrue(lines.activity_id)
