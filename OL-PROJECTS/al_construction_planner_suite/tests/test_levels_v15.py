# -*- coding: utf-8 -*-
"""v1.5, fase 12: plantilla de niveles, tipos de unidad, mueble, ritmo de
programación y fechas del árbol."""
from datetime import date, datetime, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tools import BinaryBytes

from odoo.addons.al_construction_planner_furniture.wizards.master_import_layout import build_workbook

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestLevelsV15(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.towers = cls.env.ref('al_construction_planner.level_template_towers')
        cls.lines = {line.name: line for line in cls.towers.line_ids}
        cls.site = cls.env['project.project'].create({
            'name': 'Obra con torres (test)', 'is_construction_site': True,
            'construction_level_template_id': cls.towers.id})
        cls.typology_site = cls.typology.copy({'project_id': cls.site.id})
        Task = cls.env['project.task']

        def node(name, level, parent=None, depth=0, **vals):
            return Task.create(dict(cls.site._construction_level_vals(level, depth), **dict({
                'name': name, 'project_id': cls.site.id,
                'parent_id': parent.id if parent else False}, **vals)))

        cls.node = staticmethod(node)
        cls.tower_a = node('Torre A', 'group')
        cls.tower_b = node('Torre B', 'group')
        cls.floor_a1 = node('Piso 01', 'floor', cls.tower_a)
        cls.floor_a2 = node('Piso 02', 'floor', cls.tower_a)
        cls.floor_b1 = node('Piso 01', 'floor', cls.tower_b)
        cls.spaces = Task
        for floor in (cls.floor_a1, cls.floor_a2, cls.floor_b1):
            apartment = node('Dpto %s' % floor.id, 'apartment', floor,
                             construction_unit_type='apartment')
            cls.spaces |= node('Cocina', 'space', apartment,
                               construction_typology_id=cls.typology_site.id)
        cls.site_plan = cls.env['construction.resource.plan'].create({'project_id': cls.site.id})

    def _generate_site(self, **vals):
        wizard = self.env['construction.plan.generate.wizard'].create(
            dict({'plan_id': self.site_plan.id}, **vals))
        wizard.action_generate()
        return wizard

    # ------------------------------------------------------------------
    # Plantilla
    # ------------------------------------------------------------------
    def test_template_levels_and_roles(self):
        self.assertEqual(self.towers.summary,
                         'Torre › Piso › Departamento › Ambiente › Mueble › Módulo')
        self.assertEqual(self.lines['Torre'].level, 'group')
        self.assertEqual(self.lines['Piso'].level, 'floor', 'el último agrupador hace de piso')
        self.assertEqual(self.tower_a.construction_level, 'group')
        self.assertEqual(self.floor_a1.construction_level, 'floor')
        self.assertEqual(self.tower_a.construction_level_name, 'Torre')

    def test_template_rules(self):
        Template = self.env['construction.level.template']
        # Desde la v1.7 (M17-01) la unidad y el módulo son opcionales; el
        # nivel con etapas sigue siendo uno solo.
        with self.assertRaises(ValidationError):
            Template.create({'name': 'Sin nivel con etapas', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Piso', 'role': 'group'}),
                (0, 0, {'sequence': 2, 'name': 'Departamento', 'role': 'unit'}),
                (0, 0, {'sequence': 3, 'name': 'Módulo', 'role': 'module'})]})
        with self.assertRaises(ValidationError):
            Template.create({'name': 'Desordenada', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Departamento', 'role': 'unit'}),
                (0, 0, {'sequence': 2, 'name': 'Torre', 'role': 'group'}),
                (0, 0, {'sequence': 3, 'name': 'Ambiente', 'role': 'space'}),
                (0, 0, {'sequence': 4, 'name': 'Módulo', 'role': 'module'})]})
        parking = Template.create({'name': 'Sótano', 'line_ids': [
            (0, 0, {'sequence': 1, 'name': 'Sótano', 'role': 'group'}),
            (0, 0, {'sequence': 2, 'name': 'Estacionamiento', 'role': 'unit'}),
            (0, 0, {'sequence': 3, 'name': 'Ambiente', 'role': 'space'}),
            (0, 0, {'sequence': 4, 'name': 'Módulo', 'role': 'module'})]})
        self.assertEqual(parking.line_ids.sorted('sequence')[0].level, 'floor')

    def test_parent_follows_the_template(self):
        with self.assertRaises(ValidationError):
            self.node('Piso suelto', 'floor')  # el piso cuelga de una torre
        with self.assertRaises(ValidationError):
            self.node('Torre dentro de torre', 'group', self.tower_a)

    def test_template_locked_with_approved_plan(self):
        self._generate_site()
        self.site_plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        for line in self.site_plan.line_ids.filtered(lambda l: not l.price_unit_planned):
            line.price_unit_planned = 1.0
        self.site_plan.action_request_approval()
        self.assertEqual(self.site_plan.state, 'approved')
        with self.assertRaises(ValidationError):
            self.site.construction_level_template_id = self.env.ref(
                'al_construction_planner.level_template_building')

    # ------------------------------------------------------------------
    # Mueble y árbol
    # ------------------------------------------------------------------
    def test_modules_hang_from_furniture(self):
        self._generate_site()
        space = self.spaces[0]
        furniture = self.env['project.task'].search([('parent_id', '=', space.id)])
        self.assertEqual(set(furniture.mapped('construction_level')), {'furniture'})
        self.assertEqual(set(furniture.mapped('name')),
                         {'Mueble bajo', 'Mueble alto', 'Otros muebles'})
        modules = self.env['project.task'].search([
            ('construction_space_task_id', '=', space.id), ('construction_level', '=', 'module')])
        self.assertEqual(len(modules), 7)
        self.assertTrue(all(m.construction_furniture_task_id for m in modules))
        lines = self.site_plan.line_ids.filtered(lambda l: l.module_task_id in modules)
        self.assertTrue(lines and all(l.furniture_task_id for l in lines))

    def test_tree_with_towers(self):
        self._generate_site()
        roots = self.site_plan.get_tree_nodes('p')
        self.assertEqual([n['name'] for n in roots], ['Torre A', 'Torre B'])
        self.assertEqual(roots[0]['level_name'], 'Torre')
        floors = self.site_plan.get_tree_nodes(str(self.tower_a.id))
        self.assertEqual([n['name'] for n in floors], ['Piso 01', 'Piso 02'])
        self.assertAlmostEqual(roots[0]['total'], sum(n['total'] for n in floors), 2)
        self.assertEqual(roots[0]['modules'], 14)
        self.assertTrue(roots[0]['total'] > 0)
        total = self.site_plan.get_tree_nodes('root')[0]['total']
        self.assertAlmostEqual(total, roots[0]['total'] + roots[1]['total'], 2)
        # Bajo el ambiente, los muebles; bajo el mueble, sus módulos.
        apartment = self.site_plan.get_tree_nodes(str(self.floor_a1.id))[0]
        space = self.site_plan.get_tree_nodes(apartment['key'])[0]
        furniture = self.site_plan.get_tree_nodes(space['key'])
        self.assertEqual({n['level'] for n in furniture}, {'furniture'})
        self.assertEqual(sum(n['modules'] for n in furniture), 7)

    def test_unit_type(self):
        apartment = self.spaces[0].parent_id
        self.assertEqual(apartment.construction_unit_type, 'apartment')

    # ------------------------------------------------------------------
    # Ritmo de programación y fechas
    # ------------------------------------------------------------------
    def test_pace_weeks_per_floor_and_rollup(self):
        monday = date(2026, 11, 2)
        self._generate_site(schedule_mode='weeks_per_floor', schedule_pace=1.5,
                            schedule_date_start=monday, days_production=3, days_assembly=2,
                            days_installation=2, days_finishing=1)
        Stage = self.env['construction.space.stage']
        first = Stage.search([('space_task_id', '=', self.spaces[0].id)], order='sequence')
        self.assertEqual(first[0].date_start, monday)
        self.assertEqual(first[0].date_end, date(2026, 11, 4), '3 días hábiles')
        self.assertEqual(first[1].date_start, date(2026, 11, 5))
        self.assertEqual(first[1].date_end, date(2026, 11, 6))
        self.assertEqual(first[2].date_start, date(2026, 11, 9), 'salta el fin de semana')
        # Segundo piso de la torre A: 1.5 semanas después (11 días → jueves 13).
        second = Stage.search([('space_task_id', '=', self.spaces[1].id)], order='sequence')
        self.assertEqual(second[0].date_start, date(2026, 11, 13))
        # Fechas guardadas en las tareas del árbol.
        start_field, end_field = Stage._task_date_fields()
        space = self.spaces[0]
        self.assertEqual(fields_date(space[start_field]), monday)
        self.assertEqual(fields_date(space[end_field]), first[-1].date_end)
        self.assertEqual(fields_date(self.tower_a[start_field]), monday)
        self.assertEqual(fields_date(self.tower_a[end_field]), second[-1].date_end)

    def test_pace_skips_holidays(self):
        holiday = date(2026, 11, 3)
        self.env['resource.calendar.leaves'].create({
            'name': 'Feriado (test)', 'company_id': self.env.company.id,
            'calendar_id': self.env.company.resource_calendar_id.id,
            'date_from': datetime(2026, 11, 3, 5, 0), 'date_to': datetime(2026, 11, 4, 4, 0)})
        self._generate_site(schedule_mode='floors_per_week', schedule_pace=2,
                            schedule_date_start=date(2026, 11, 2), days_production=3)
        stage = self.env['construction.space.stage'].search(
            [('space_task_id', '=', self.spaces[0].id)], order='sequence', limit=1)
        company = self.env.company
        self.assertTrue(company._construction_is_holiday(holiday))
        self.assertFalse(company._construction_is_site_day(holiday))
        self.assertEqual(stage.date_end, company._construction_add_site_days(date(2026, 11, 2), 3))
        self.assertGreater(stage.date_end, date(2026, 11, 4), 'el feriado no cuenta')

    def test_form_edit_chains_successors_in_working_days(self):
        self._generate_site(schedule_mode='weeks_per_floor', schedule_pace=1,
                            schedule_date_start=date(2026, 11, 2), days_production=2,
                            days_assembly=2)
        stages = self.env['construction.space.stage'].search(
            [('space_task_id', '=', self.spaces[0].id)], order='sequence')
        production, assembly = stages[0], stages[1]
        self.assertEqual(assembly.date_start, date(2026, 11, 4))
        production.date_end = date(2026, 11, 5)  # jueves
        self.assertEqual(assembly.date_start, date(2026, 11, 6), 'el día hábil siguiente')
        self.assertEqual(assembly.date_end, date(2026, 11, 9), 'conserva 2 días hábiles')

    # ------------------------------------------------------------------
    # Importador con agrupadores
    # ------------------------------------------------------------------
    def test_import_with_towers(self):
        manager = new_test_user(self.env, 'plan_admin_levels', name='Admin niveles (test)',
                                groups='al_construction_planner.group_planner_manager')
        site = self.env['project.project'].create({
            'name': 'Obra importada con torres (test)', 'is_construction_site': True,
            'construction_level_template_id': self.towers.id})
        rows = {'ARBOL': [
            {'group': 'Torre A', 'floor': 'Piso 01', 'apartment': '101', 'space': 'Cocina',
             'unit_type': 'Departamento'},
            {'group': 'Torre B', 'floor': 'Piso 01', 'apartment': '101', 'space': 'Cocina'},
            {'group': 'Torre B', 'floor': 'Sótano 1', 'apartment': 'E-01', 'space': 'Depósito',
             'unit_type': 'Estacionamiento'},
        ]}
        wizard = self.env['construction.master.import.wizard'].with_user(manager).create({
            'project_id': site.id, 'file': BinaryBytes(build_workbook(rows)),
            'filename': 'maestro.xlsx'})
        data = wizard._analyze()
        self.assertFalse(data['errors'])
        wizard.action_import()
        Task = self.env['project.task']
        towers = Task.search([('project_id', '=', site.id), ('construction_level', '=', 'group')])
        self.assertEqual(sorted(towers.mapped('name')), ['Torre A', 'Torre B'])
        floors = Task.search([('project_id', '=', site.id), ('name', '=', 'Piso 01')])
        self.assertEqual(len(floors), 2, 'el mismo piso en dos torres')
        parking = Task.search([('project_id', '=', site.id), ('name', '=', 'E-01')])
        self.assertEqual(parking.construction_unit_type, 'parking')
        self.assertEqual(parking.construction_level_line_id, self.lines['Departamento'])
        # Reimportar no duplica.
        wizard2 = self.env['construction.master.import.wizard'].with_user(manager).create({
            'project_id': site.id, 'file': BinaryBytes(build_workbook(rows)),
            'filename': 'maestro.xlsx'})
        wizard2._analyze()
        wizard2.action_import()
        self.assertEqual(Task.search_count([('project_id', '=', site.id),
                                            ('construction_level', '=', 'space')]), 3)


def fields_date(value):
    return value.date() if isinstance(value, datetime) else value
