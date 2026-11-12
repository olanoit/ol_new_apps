# -*- coding: utf-8 -*-
"""Paquete 1.20, M120-03 y M120-04: nombres de nivel y etapas del perfil.

* «Etapa actual por partida» (o por el nivel con etapas de la plantilla) en el
  menú, la acción y las vistas del informe.
* Las columnas de nivel que la plantilla no tiene se ocultan; las que tiene
  llevan su nombre. «Registrar avance» dice «Nivel» y muestra la tipología solo
  con el puente de mobiliario.
* El Cronograma ofrece las etapas del perfil de la obra; una archivada que la
  obra ya tiene registrada va con «(archivada)». Los filtros por etapa de
  Etapas del cronograma son del puente de mobiliario."""
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .common import PlannerCommon

P = 'al_construction_planner.'


@tagged('post_install', '-at_install')
class TestLevelNames120(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.works = cls.env.ref(P + 'level_template_works')
        cls.planner = new_test_user(
            cls.env, login='m120_levels_planner',
            groups='base.group_user,' + P + 'group_planner_plan_planner,' + P + 'group_planner_user')

    def test_space_stage_title(self):
        Labels = self.env['construction.level.labels.mixin']
        self.env.company.construction_level_template_id = self.works
        self.assertEqual(Labels._construction_space_stage_title(), 'Etapa actual por partida')
        menu = self.env.ref(P + 'menu_planner_space_stage_report')
        menus = self.env['ir.ui.menu'].with_user(self.planner).load_menus(debug=False)
        if menu.id in menus:
            self.assertEqual(menus[menu.id]['name'], 'Etapa actual por partida')
        action = self.env.ref(P + 'action_construction_space_stage_report')._get_action_dict()
        self.assertEqual(action['name'], 'Etapa actual por partida')
        pivot = self.env['project.task'].get_views(
            [(self.env.ref(P + 'project_task_view_pivot_construction_space_stage').id, 'pivot')])
        self.assertIn('Etapa actual por partida', pivot['views']['pivot']['arch'])
        furniture = self.env.ref(P + 'level_template_building', raise_if_not_found=False)
        if furniture:
            self.env.company.construction_level_template_id = furniture
            self.assertEqual(Labels._construction_space_stage_title(), 'Etapa actual por ambiente')

    def test_plan_line_columns_follow_template(self):
        Line = self.env['construction.resource.plan.line']
        view = self.env.ref(P + 'construction_resource_plan_line_view_list')
        self.env.company.construction_level_template_id = self.works
        arch = Line.with_user(self.planner).get_views([(view.id, 'list')])['views']['list']['arch']
        self.assertIn('name="apartment_task_id" optional="show" column_invisible="1"', arch)
        # La lista incrustada en el plan recibe las funciones de la plantilla de
        # su obra.
        self.project.construction_level_template_id = self.works
        self.assertNotIn('apartment', self.plan.construction_level_functions.split())
        self.assertIn('space', self.plan.construction_level_functions.split())

    def test_progress_wizard_columns(self):
        Wizard = self.env['construction.plan.progress.wizard']
        arch = Wizard.get_views([(False, 'form')])['views']['form']['arch']
        self.assertIn("'apartment' not in (parent.construction_level_functions", arch)
        self.assertEqual(
            self.env['construction.plan.progress.wizard.line'].fields_get(['task_id'])['task_id']['string'],
            'Nivel')
        furniture = self.env['ir.module.module'].search(
            [('name', '=', 'al_construction_planner_furniture'), ('state', '=', 'installed')])
        typology_hidden = 'name="typology_id" optional="show" column_invisible="1"' in arch
        self.assertEqual(typology_hidden, not furniture)


@tagged('post_install', '-at_install')
class TestScheduleStages120(PlannerCommon):

    def test_offered_stages_follow_profile(self):
        profile = self.env.ref(P + 'profile_construction')
        profile.stage_ids.filtered(lambda s: not s.active).active = True
        self.project.construction_profile_id = profile
        Gantt = self.env['al.gantt.data']
        offered = Gantt._construction_offered_space_states(self.plan, False)
        codes = {state['code'] for state in offered}
        profile_codes = set(profile.stage_ids._leaf_stages().mapped('code'))
        self.assertTrue(codes)
        self.assertTrue(codes <= profile_codes)
        self.assertNotIn('installation', codes)
        # Una etapa fuera del perfil que la obra ya tiene registrada se ve
        # como archivada.
        self.env['construction.space.stage'].create({
            'space_task_id': self.space_501.id, 'stage': 'installation',
            'date_start': date(2026, 1, 5), 'date_end': date(2026, 1, 9)})
        offered = Gantt._construction_offered_space_states(self.plan, False)
        installation = next(s for s in offered if s['code'] == 'installation')
        self.assertTrue(installation['label'].endswith('(archivada)'))

    def test_stage_filters_are_furniture_bridge(self):
        core = self.env.ref(P + 'construction_space_stage_view_search')
        self.assertNotIn('name="installation"', core.arch_db)
        bridge = self.env.ref(
            'al_construction_planner_furniture.construction_space_stage_view_search_furniture',
            raise_if_not_found=False)
        if bridge:
            self.assertIn('name="installation"', bridge.arch_db)
