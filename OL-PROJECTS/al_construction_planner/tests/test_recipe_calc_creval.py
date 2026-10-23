# -*- coding: utf-8 -*-
"""Receta y plan (requerimiento CREVAL v1.0, 6.1, 6.2, 6.3 y 6.5) con la
receta de demostración de la figura 20: mano de obra S/ 6.46 por m²,
herramientas 3 % = S/ 0.19 por m² y costo unitario S/ 43.78 por m²."""
from datetime import date

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestRecipeCalc(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['tier.definition'].search([('model', '=', 'construction.resource.plan')]).active = False
        cls.m2 = env.ref('uom.product_uom_square_meter')
        cls.hour = env.ref('uom.product_uom_hour')
        cls.unit = env.ref('uom.product_uom_unit')
        cls.stage = env['construction.stage'].create({
            'name': 'Muros (test)', 'code': 'calc_test_stage', 'sequence': 920})
        cls.mason = env['construction.labor.activity'].create({
            'code': 'CALC-OP', 'name': 'Operario (test)', 'stage': 'calc_test_stage',
            'default_price': 25.0, 'uom_id': cls.hour.id})
        cls.brick = env['product.product'].create({
            'name': 'Ladrillo (test)', 'standard_price': 37.13, 'uom_id': cls.m2.id})
        cls.tools = env['product.product'].create({'name': 'Herramientas manuales (test)'})
        cls.recipe = env['construction.execution.template'].create({
            'code': 'CALC-R01', 'name': 'Muro de ladrillo (test)', 'uom_id': cls.m2.id,
            'line_ids': [
                Command.create({'resource_type': 'labor', 'activity_id': cls.mason.id,
                                'stage': 'calc_test_stage', 'product_uom_id': cls.hour.id,
                                'qty': 0.2584, 'price_unit': 25.0}),
                Command.create({'resource_type': 'material', 'product_id': cls.brick.id,
                                'stage': 'calc_test_stage', 'product_uom_id': cls.m2.id,
                                'qty': 1.0}),
                Command.create({'resource_type': 'equipment', 'product_id': cls.tools.id,
                                'stage': 'calc_test_stage', 'product_uom_id': cls.unit.id,
                                'calc_method': 'pct_labor', 'calc_pct': 3.0}),
            ]})

    def test_percentage_of_labor(self):
        labor, brick, tools = self.recipe.line_ids.sorted('id')
        self.assertAlmostEqual(labor.amount_unit, 6.46)
        self.assertAlmostEqual(tools.qty, 0.03)
        # 3 % × 6.46 = 0.1938, que el monto redondea a 0.19.
        self.assertEqual(tools.amount_unit, 0.19)
        self.assertEqual(self.env.company.currency_id.round(self.recipe.amount_unit), 43.78)
        with self.assertRaises(ValidationError):
            tools.calc_pct = 0.0

    def test_crew_over_productivity(self):
        line = self.env['construction.execution.template.line'].create({
            'template_id': self.recipe.id, 'resource_type': 'labor', 'activity_id': self.mason.id,
            'stage': 'calc_test_stage', 'product_uom_id': self.hour.id, 'calc_method': 'crew',
            'crew_size': 1.0, 'productivity': 19.0, 'price_unit': 25.0})
        # Una persona × 8 horas ÷ 19 m² por día.
        self.assertAlmostEqual(line.qty, 8.0 / 19.0, places=6)

    def _project(self):
        template = self.env['construction.level.template'].create({
            'name': 'Especialidad, sub-especialidad y partida (test)', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Especialidad', 'role': 'group'}),
                (0, 0, {'sequence': 2, 'name': 'Sub-especialidad', 'role': 'group'}),
                (0, 0, {'sequence': 3, 'name': 'Partida', 'role': 'space'})]})
        levels = template.line_ids.sorted('sequence')
        project = self.env['project.project'].create({
            'name': 'Obra de la receta (test)', 'is_construction_site': True,
            'construction_level_template_id': template.id,
            'construction_apu_source': 'excel'})
        Task = self.env['project.task']
        group = Task.create({'name': 'Estructuras (test)', 'project_id': project.id,
                             'construction_level_line_id': levels[0].id})
        sub = Task.create({'name': 'Muros (test)', 'project_id': project.id,
                           'parent_id': group.id, 'construction_level_line_id': levels[1].id})
        partida = Task.create({'name': '04.01.01 Muro KK (test)', 'project_id': project.id,
                               'parent_id': sub.id, 'construction_level_line_id': levels[2].id,
                               'construction_execution_template_id': self.recipe.id,
                               'construction_qty': 100.0})
        return project, partida

    def test_plan_generation_recomputes_percentage(self):
        project, partida = self._project()
        plan = self.env['construction.resource.plan'].create({'project_id': project.id})
        wizard = self.env['construction.plan.recipe.wizard'].create({'plan_id': plan.id})
        wizard.action_generate()
        tools = plan.line_ids.filtered(lambda l: l.calc_method == 'pct_labor')
        labor = plan.line_ids.filtered(lambda l: l.resource_type == 'labor')
        self.assertAlmostEqual(labor.amount_planned, 646.0)
        self.assertAlmostEqual(tools.amount_planned, 19.38)
        # Cambia la mano de obra: el porcentaje se recalcula.
        labor.price_unit_planned = 30.0
        self.assertAlmostEqual(tools.amount_planned, round(0.03 * 0.2584 * 100 * 30.0, 2))
        # Cada línea del plan lleva sus tres niveles.
        self.assertTrue(all(plan.line_ids.mapped('level_1_id')))
        self.assertTrue(all(plan.line_ids.mapped('level_3_id')))
        # Las herramientas por porcentaje no se compran ni se piden.
        plan.action_request_approval()
        mixin = self.env['construction.plan.reschedule.wizard'].with_context(
            default_plan_id=plan.id, construction_selection_project=True).new({})
        self.assertNotIn(tools, mixin._get_selected_lines())

    def test_level_labels_from_project_template(self):
        project, _partida = self._project()
        Line = self.env['construction.resource.plan.line'].with_context(
            construction_project_id=project.id)
        fields_info = Line.fields_get(['level_1_id', 'level_2_id', 'space_task_id'])
        self.assertEqual(fields_info['level_1_id']['string'], 'Especialidad')
        self.assertEqual(fields_info['level_2_id']['string'], 'Sub-especialidad')
        self.assertEqual(fields_info['space_task_id']['string'], 'Partida')
        arch = Line.get_view(view_type='search')['arch']
        self.assertIn('string="Especialidad"', arch)

    def test_uom_alias(self):
        Alias = self.env['construction.uom.alias']
        Alias.create({'name': 'GLB', 'uom_id': self.unit.id})
        self.assertEqual(Alias._find(' glb '), self.unit)
        self.assertFalse(Alias._find('xyz'))

    def test_dollar_line(self):
        usd = self.env.ref('base.USD')
        usd.active = True
        company = self.env.company
        if company.currency_id == usd:
            self.skipTest('La compañía de prueba trabaja en dólares.')
        self.env['res.currency.rate'].create({
            'name': date(2026, 1, 1), 'currency_id': usd.id, 'company_id': company.id,
            'inverse_company_rate': 3.5})
        project, partida = self._project()
        plan = self.env['construction.resource.plan'].create(
            {'project_id': project.id, 'date_start': date(2026, 2, 1)})
        chair = self.env['product.product'].create({'name': 'Silla ergonómica (test)'})
        line = self.env['construction.resource.plan.line'].create({
            'plan_id': plan.id, 'task_id': partida.id, 'resource_type': 'material',
            'product_id': chair.id, 'product_uom_id': self.unit.id, 'qty_planned': 10.0,
            'stage': 'calc_test_stage', 'price_currency_id': usd.id,
            'price_unit_currency': 180.0})
        self.assertTrue(line.is_foreign_currency)
        self.assertAlmostEqual(line.price_unit_planned, 630.0)
        self.assertAlmostEqual(line.amount_planned, 6300.0)
