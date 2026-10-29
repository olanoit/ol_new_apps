# -*- coding: utf-8 -*-
"""Receta y plan (requerimiento CREVAL v1.0, 6.1, 6.2, 6.3 y 6.5) con la
receta de demostración de la figura 20: mano de obra S/ 6.46 por m²,
herramientas 3 % = S/ 0.19 por m² y costo unitario S/ 43.78 por m²."""
from datetime import date
from io import BytesIO

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import BinaryBytes


@tagged('post_install', '-at_install')
class TestRecipeCalc(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # Cuatro decimales en «Precio del producto», como CREVAL (CR-03).
        env.ref('product.decimal_price').digits = 4
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
        # 3 % × 6.46 = 0.1938: la línea no redondea; la receta, una sola vez.
        self.assertAlmostEqual(tools.amount_unit, 0.1938)
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

    # CR-03: el costo unitario conserva los decimales del precio y la receta
    # redondea una sola vez (el ladrillo a 0.9661 no pasa a 0.97).
    def test_unit_cost_precision(self):
        recipe = self.env['construction.execution.template'].create({
            'code': 'CALC-R02', 'name': 'Muro de ladrillo KK (test)', 'uom_id': self.m2.id,
            'line_ids': [
                Command.create({'resource_type': 'material', 'product_id': self.brick.id,
                                'stage': 'calc_test_stage', 'product_uom_id': self.m2.id,
                                'qty': 54.0, 'price_unit': 0.9661}),
                Command.create({'resource_type': 'material', 'product_id': self.tools.id,
                                'stage': 'calc_test_stage', 'product_uom_id': self.unit.id,
                                'qty': 0.333333, 'price_unit': 0.66}),
            ]})
        brick, other = recipe.line_ids.sorted('id')
        self.assertEqual(brick.price_unit, 0.9661)
        self.assertAlmostEqual(brick.amount_unit, 52.1694)
        # 52.1694 + 0.2200 = 52.3894 → 52.39 (por línea saldría 52.38 + 0.22).
        self.assertEqual(recipe.amount_unit, 52.39)
        project, partida = self._project()
        partida.construction_execution_template_id = recipe
        plan = self.env['construction.resource.plan'].create({'project_id': project.id})
        self.env['construction.plan.recipe.wizard'].create({'plan_id': plan.id}).action_generate()
        line = plan.line_ids.filtered(lambda l: l.product_id == self.brick)
        self.assertEqual(line.price_unit_planned, 0.9661)
        self.assertAlmostEqual(line.amount_planned, round(5400.0 * 0.9661, 2))

    # CR-04: el código del recurso se busca en las actividades y en los
    # productos, y la línea lleva los dos.
    def _recipe_book(self, rows):
        from openpyxl import Workbook
        book = Workbook()
        sheet = book.active
        sheet.title = 'RECETAS'
        sheet.append(['Código de la receta', 'Nombre de la receta', 'Unidad de la receta',
                      'Tipo de recurso', 'Código del recurso', 'Cantidad por unidad', 'Etapa',
                      'Costo unitario', 'Unidad'])
        for row in rows:
            sheet.append(row)
        output = BytesIO()
        book.save(output)
        return BinaryBytes(output.getvalue())

    def test_import_resolves_activity_and_product(self):
        Product = self.env['product.product']
        operator = Product.create({'name': 'Operario (servicio, test)', 'type': 'service',
                                   'default_code': 'MO-OPE-T'})
        drywall = Product.create({'name': 'Tabiquería (servicio, test)', 'type': 'service',
                                  'default_code': 'CTR-DRY-T'})
        Activity = self.env['construction.labor.activity']
        contract = Activity.create({
            'code': 'TC-DRY-T', 'name': 'Tabique drywall (test)', 'stage': 'calc_test_stage',
            'uom_id': self.m2.id, 'product_id': drywall.id})
        overtime = Activity.create({
            'code': 'MO-HEX-T', 'name': 'Recargo por horario extendido (test)',
            'stage': 'calc_test_stage', 'uom_id': self.unit.id, 'default_price': 50.0})
        self.env['construction.uom.alias'].create({'name': 'glb', 'uom_id': self.unit.id})
        project, partida = self._project()
        file = self._recipe_book([
            ('CALC-R09', 'Tabique con recargo (test)', 'm2', 'labor', 'MO-OPE-T', 0.25,
             'calc_test_stage', 23.36, 'h'),
            ('CALC-R09', None, None, 'labor', 'CALC-OP', 0.1, 'calc_test_stage', None, 'h'),
            ('CALC-R09', None, None, 'contract', 'CTR-DRY-T', 1.0, 'calc_test_stage', 12.5,
             'm2'),
            ('CALC-R09', None, None, 'labor', 'MO-HEX-T', 0.01, 'calc_test_stage', None, 'glb'),
            ('CALC-R09', None, None, 'labor', 'NO-EXISTE', 1.0, 'calc_test_stage', None, 'h'),
        ])
        wizard = self.env['construction.recipe.import.wizard'].create({
            'source': 'excel', 'project_id': project.id, 'file': file,
            'filename': 'recetas.xlsx'})
        wizard.action_import()
        self.assertIn('NO-EXISTE no es una actividad ni un producto', wizard.result_html)
        recipe = self.env['construction.execution.template'].search([('code', '=', 'CALC-R09')])
        by_code = {line.activity_id.code: line for line in recipe.line_ids}
        self.assertEqual(set(by_code), {'MO-OPE-T', 'CALC-OP', 'TC-DRY-T', 'MO-HEX-T'})
        # Producto sin actividad: se crea la actividad con ese producto.
        self.assertEqual(by_code['MO-OPE-T'].product_id, operator)
        self.assertEqual(by_code['MO-OPE-T'].activity_id.product_id, operator)
        # El código del producto de una actividad lleva a esa actividad.
        self.assertEqual(by_code['TC-DRY-T'].activity_id, contract)
        self.assertEqual(by_code['TC-DRY-T'].product_id, drywall)
        self.assertEqual(by_code['MO-HEX-T'].activity_id, overtime)
        self.assertEqual(by_code['MO-HEX-T'].product_uom_id, self.unit)
        # Personal propio en una unidad que no es la hora también genera.
        partida.construction_execution_template_id = recipe
        plan = self.env['construction.resource.plan'].create({'project_id': project.id})
        self.env['construction.plan.recipe.wizard'].create({'plan_id': plan.id}).action_generate()
        self.assertEqual(len(plan.line_ids), 4)
        self.assertTrue(plan.line_ids.filtered(lambda l: l.activity_id == overtime))

    def test_plan_names_line_without_activity(self):
        recipe = self.env['construction.execution.template'].create({
            'code': 'CALC-R10', 'name': 'Receta incompleta (test)', 'uom_id': self.m2.id,
            'line_ids': [
                Command.create({'resource_type': 'material', 'product_id': self.brick.id,
                                'stage': 'calc_test_stage', 'product_uom_id': self.m2.id,
                                'qty': 1.0}),
                Command.create({'resource_type': 'labor', 'stage': 'calc_test_stage',
                                'product_uom_id': self.hour.id, 'qty': 0.5,
                                'note': 'OPERARIO'}),
            ]})
        project, partida = self._project()
        partida.construction_execution_template_id = recipe
        plan = self.env['construction.resource.plan'].create({'project_id': project.id})
        wizard = self.env['construction.plan.recipe.wizard'].create({'plan_id': plan.id})
        self.assertIn('CALC-R10, línea 2 (OPERARIO)', wizard.preview_html)
        with self.assertRaisesRegex(UserError, r'CALC-R10, línea 2 \(OPERARIO\)'):
            wizard.action_generate()

    # CR-05: porcentaje del costo directo de un nivel elegido.
    def test_percentage_of_chosen_level(self):
        project, partida = self._project()
        other_group = self.env['project.task'].create({
            'name': 'Arquitectura (test)', 'project_id': project.id,
            'construction_level_line_id':
                partida.parent_id.parent_id.construction_level_line_id.id})
        plan = self.env['construction.resource.plan'].create({'project_id': project.id})
        self.env['construction.plan.recipe.wizard'].create({'plan_id': plan.id}).action_generate()
        structures = partida.parent_id.parent_id
        Line = self.env['construction.resource.plan.line']
        pct = Line.create({
            'plan_id': plan.id, 'task_id': other_group.id, 'resource_type': 'equipment',
            'product_id': self.tools.id, 'product_uom_id': self.unit.id, 'stage': 'calc_test_stage',
            'calc_method': 'pct_group', 'calc_pct': 2.0, 'calc_scope': 'task',
            'calc_task_id': structures.id, 'qty_planned': 0.02, 'price_unit_planned': 0.0})
        direct = sum(plan.line_ids.filtered(
            lambda l: l.calc_method not in ('pct_labor', 'pct_group')).mapped('amount_planned'))
        self.assertAlmostEqual(pct.amount_planned, round(direct * 0.02, 2))
        with self.assertRaises(ValidationError):
            self.recipe.line_ids[:1].write({'calc_method': 'pct_group', 'calc_pct': 2.0,
                                            'calc_scope': 'task'})

    # CR-06: lo que entrega el cliente.
    def test_client_supply(self):
        tv = self.env['product.product'].create({'name': 'Televisor del cliente (test)'})
        recipe = self.env['construction.execution.template'].create({
            'code': 'CALC-R08', 'name': 'Sala de reuniones (test)', 'uom_id': self.unit.id,
            'line_ids': [Command.create({
                'resource_type': 'material', 'product_id': tv.id, 'stage': 'calc_test_stage',
                'product_uom_id': self.unit.id, 'qty': 1.0, 'is_client_supply': True})]})
        project, partida = self._project()
        partida.construction_execution_template_id = recipe
        plan = self.env['construction.resource.plan'].create({'project_id': project.id})
        self.env['construction.plan.recipe.wizard'].create({'plan_id': plan.id}).action_generate()
        line = plan.line_ids
        self.assertTrue(line.is_client_supply)
        self.assertEqual(line.price_unit_planned, 0.0)
        self.assertFalse(plan._get_approval_issues())
        self.assertEqual(plan.unpriced_line_count, 0)
        plan.action_request_approval()
        self.assertEqual(plan.state, 'approved')
        mixin = self.env['construction.plan.reschedule.wizard'].with_context(
            default_plan_id=plan.id, construction_selection_project=True).new({})
        self.assertNotIn(line, mixin._get_selected_lines())
        line.with_context(construction_plan_force=True).qty_client_received = 100.0
        self.assertEqual(line.qty_executed, 100.0)

    # 6.4: modalidad de ejecución por partida.
    def _generate_with_mode(self, mode, activity=None):
        self.recipe.contract_activity_id = activity
        project, partida = self._project()
        partida.construction_execution_mode = mode
        plan = self.env['construction.resource.plan'].create({'project_id': project.id})
        self.env['construction.plan.recipe.wizard'].create({'plan_id': plan.id}).action_generate()
        return plan, partida

    def test_execution_modes(self):
        contract = self.env['construction.labor.activity'].create({
            'code': 'CALC-CTR', 'name': 'Muro por contrata (test)', 'stage': 'calc_test_stage',
            'uom_id': self.m2.id})
        self.assertEqual(self.recipe.execution_mode, 'own')
        own, partida = self._generate_with_mode('own')
        self.assertEqual(set(own.line_ids.mapped('resource_type')), {'labor', 'material', 'equipment'})
        # Solo mano de obra: la mano de obra y las herramientas van a la
        # contrata (6.46 + 3 % = 6.6538 por m²); el ladrillo sigue aparte.
        labor, _partida = self._generate_with_mode('labor_contract', contract)
        line = labor.line_ids.filtered(lambda l: l.resource_type == 'contract')
        self.assertEqual(line.activity_id, contract)
        self.assertAlmostEqual(line.price_unit_planned, 6.6538, places=4)
        self.assertAlmostEqual(line.qty_planned, 100.0)
        self.assertEqual(set(labor.line_ids.mapped('resource_type')), {'contract', 'material'})
        # A todo costo: una sola línea con el costo de la receta y su detalle.
        full, _partida = self._generate_with_mode('full_contract', contract)
        self.assertEqual(len(full.line_ids), 1)
        self.assertAlmostEqual(full.line_ids.price_unit_planned, 43.7838, places=4)
        self.assertIn('CALC-R01', full.line_ids.construction_apu_detail)
        with self.assertRaisesRegex(UserError, 'falta la actividad de la contrata'):
            self._generate_with_mode('full_contract')

    def test_execution_mode_locked_by_approved_plan(self):
        plan, partida = self._generate_with_mode('own')
        plan.action_request_approval()
        self.assertEqual(plan.state, 'approved')
        with self.assertRaisesRegex(UserError, 'nueva versión del plan'):
            partida.construction_execution_mode = 'full_contract'

    # 6.1: equipo propio con tarifa interna y su uso en obra.
    def test_owned_equipment(self):
        mixer = self.env['product.product'].create({
            'name': 'Mezcladora 9 p³ (test)', 'construction_equipment_owned': True,
            'construction_replacement_value': 10000.0, 'construction_life_years': 5.0,
            'construction_hours_year': 2000.0, 'construction_interest_pct': 10.0,
            'construction_maintenance_pct': 10.0, 'construction_fuel_hour': 2.5})
        # (10,000 ÷ 5 + 10,000 × 20 %) ÷ 2,000 + 2.50 = 4.50 por hora.
        self.assertAlmostEqual(mixer.construction_internal_rate, 4.5)
        recipe = self.env['construction.execution.template'].create({
            'code': 'CALC-R03', 'name': 'Concreto con mezcladora (test)', 'uom_id': self.m2.id,
            'line_ids': [Command.create({
                'resource_type': 'equipment', 'product_id': mixer.id, 'stage': 'calc_test_stage',
                'product_uom_id': self.hour.id, 'qty': 0.5})]})
        self.assertAlmostEqual(recipe.amount_unit, 2.25)
        project, partida = self._project()
        partida.construction_execution_template_id = recipe
        plan = self.env['construction.resource.plan'].create({'project_id': project.id})
        self.env['construction.plan.recipe.wizard'].create({'plan_id': plan.id}).action_generate()
        line = plan.line_ids
        self.assertEqual(line.price_unit_planned, 4.5)
        plan.action_request_approval()
        usage = self.env['construction.equipment.usage'].create({
            'plan_line_id': line.id, 'date': date(2026, 11, 3), 'qty': 8.0})
        self.assertEqual(usage.amount, 36.0)
        self.assertEqual(usage.analytic_line_id.account_id, project.account_id)
        self.assertEqual(usage.analytic_line_id.amount, -36.0)
        self.assertEqual(line.qty_executed, 8.0)
        self.assertEqual(line._get_line_execution()[line][1], 36.0)

    # Correcciones del 25-oct (CR-05): la receta no valoriza el % del costo
    # directo de un grupo; el plan sí, sobre el nivel elegido.
    def test_recipe_percentage_of_chosen_level(self):
        project, partida = self._project()
        structures = partida.parent_id.parent_id
        architecture = self.env['project.task'].create({
            'name': '3 ARQUITECTURA (test)', 'project_id': project.id,
            'construction_level_line_id': structures.construction_level_line_id.id})
        supervision = self.env['construction.execution.template'].create({
            'code': 'CALC-R14', 'name': 'Supervisión 2 % (test)', 'uom_id': self.unit.id,
            'line_ids': [Command.create({
                'resource_type': 'equipment', 'product_id': self.tools.id,
                'stage': 'calc_test_stage', 'product_uom_id': self.unit.id,
                'calc_method': 'pct_group', 'calc_pct': 2.0, 'calc_scope': 'task',
                'calc_task_id': structures.id, 'price_unit': 7060.03})]})
        line = supervision.line_ids
        self.assertEqual(line.amount_unit, 0.0)
        self.assertEqual(line.amount_note, 'Se calcula en el plan')
        self.assertIn('2.0 % del costo directo de', supervision.amount_pct_note)
        # De vuelta a «Cantidad por unidad»: el monto se calcula en el momento.
        line.write({'calc_method': 'qty', 'qty': 1.0})
        self.assertAlmostEqual(line.amount_unit, 7060.03)
        line.write({'calc_method': 'pct_group', 'calc_pct': 2.0, 'calc_scope': 'task',
                    'calc_task_id': structures.id})
        # En el plan: el 2 % del costo directo planificado de Estructuras.
        general = self.env['project.task'].create({
            'name': '3.01 Generales (test)', 'project_id': project.id,
            'parent_id': architecture.id, 'construction_level_line_id':
                partida.parent_id.construction_level_line_id.id})
        self.env['project.task'].create({
            'name': '3.01.01 Supervisión (test)', 'project_id': project.id,
            'parent_id': general.id, 'construction_level_line_id':
                partida.construction_level_line_id.id,
            'construction_execution_template_id': supervision.id, 'construction_qty': 1.0})
        plan = self.env['construction.resource.plan'].create({'project_id': project.id})
        self.env['construction.plan.recipe.wizard'].create({'plan_id': plan.id}).action_generate()
        pct = plan.line_ids.filtered(lambda l: l.calc_method == 'pct_group')
        self.assertEqual(pct.calc_task_id, structures)

        def direct():
            return sum(plan.line_ids.filtered(
                lambda l: l.calc_method not in ('pct_labor', 'pct_group')
                and l.task_id.parent_id.parent_id == structures).mapped('amount_planned'))
        self.assertAlmostEqual(pct.amount_planned, round(direct() * 0.02, 2))
        # Cambia una partida de Estructuras: el porcentaje se recalcula.
        brick = plan.line_ids.filtered(lambda l: l.product_id == self.brick)
        brick.qty_planned = 150.0
        self.assertAlmostEqual(pct.amount_planned, round(direct() * 0.02, 2))

    def test_import_percentage_level(self):
        project, partida = self._project()
        from openpyxl import Workbook
        book = Workbook()
        sheet = book.active
        sheet.title = 'RECETAS'
        sheet.append(['Código de la receta', 'Nombre de la receta', 'Tipo de recurso',
                      'Código del recurso', 'Cantidad por unidad', 'Etapa', 'Unidad',
                      'Forma de cálculo', 'Porcentaje', 'Nivel del porcentaje'])
        sheet.append(['CALC-R15', 'Supervisión (test)', 'equipment', '', 0, 'calc_test_stage',
                      'und', '% del costo directo', 2, 'Estructuras'])
        sheet.append(['CALC-R15', None, 'equipment', '', 0, 'calc_test_stage', 'und',
                      '% del costo directo', 1, 'NO-EXISTE'])
        output = BytesIO()
        book.save(output)
        wizard = self.env['construction.recipe.import.wizard'].create({
            'source': 'excel', 'project_id': project.id,
            'file': BinaryBytes(output.getvalue()), 'filename': 'recetas.xlsx'})
        wizard.action_import()
        recipe = self.env['construction.execution.template'].search([('code', '=', 'CALC-R15')])
        first, second = recipe.line_ids.sorted('id')
        self.assertEqual((first.calc_scope, first.calc_task_id),
                         ('task', partida.parent_id.parent_id))
        self.assertFalse(second.calc_task_id)
        self.assertIn('no hay un nivel NO-EXISTE', wizard.result_html)
