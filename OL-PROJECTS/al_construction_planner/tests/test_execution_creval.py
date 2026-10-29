# -*- coding: utf-8 -*-
"""Ejecución en la vertical y desde Proyectos (requerimiento CREVAL v1.0,
capítulo 4): los dos ajustes, el menú por momento, el tablero de obra, la
sección Obra del tablero del proyecto y el menú Ejecutar de la tarea."""
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

G = 'al_construction_planner.group_planner_'


@tagged('post_install', '-at_install')
class TestExecutionEntries(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['tier.definition'].search([('model', '=', 'construction.resource.plan')]).active = False
        cls.stage = env['construction.stage'].create({
            'name': 'Acabados (test)', 'code': 'exec_test_stage', 'sequence': 910})
        template = env['construction.level.template'].create({
            'name': 'Especialidad y partida (test ejecución)', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Especialidad', 'role': 'group'}),
                (0, 0, {'sequence': 2, 'name': 'Partida', 'role': 'space'})]})
        lines = template.line_ids.sorted('sequence')
        cls.project = env['project.project'].create({
            'name': 'Obra de la ejecución (test)', 'is_construction_site': True,
            'construction_level_template_id': template.id})
        specialty = env['project.task'].create({
            'name': 'Arquitectura (test)', 'project_id': cls.project.id,
            'construction_level_line_id': lines[0].id})
        cls.task = env['project.task'].create({
            'name': 'Tarrajeo (test)', 'project_id': cls.project.id, 'parent_id': specialty.id,
            'construction_level_line_id': lines[1].id})
        product = env['product.product'].create({'name': 'Mortero (test)'})
        cls.plan = env['construction.resource.plan'].create({'project_id': cls.project.id})
        env['construction.resource.plan.line'].create({
            'plan_id': cls.plan.id, 'task_id': cls.task.id, 'resource_type': 'material',
            'product_id': product.id, 'product_uom_id': product.uom_id.id, 'qty_planned': 4.0,
            'price_unit_planned': 50.0, 'stage': cls.stage.code})
        cls.plan.action_request_approval()
        cls.executor = new_test_user(env, 'ejec_residente', groups=G + 'exec_validator')

    def _feature(self, xmlid, active):
        group = self.env.ref(xmlid)
        internal = self.env.ref('base.group_user')
        internal.implied_ids = [(4 if active else 3, group.id)]
        if not active:
            # Quien ya lo tenía por implicación lo pierde al quitar la
            # implicación (como lo hace el ajuste).
            group.user_ids = [(5, 0, 0)]
        self.env.transaction.invalidate_ormcache()

    def _menu_children(self, menus, xmlid):
        menu_id = self.env.ref(xmlid).id
        return [menus[child]['xmlid'] for child in menus.get(menu_id, {}).get('children', [])]

    def test_settings_default_active(self):
        self.assertTrue(self.executor.has_group(G + 'feature_exec_planner'))
        self.assertTrue(self.executor.has_group(G + 'feature_exec_project'))
        settings = self.env['res.config.settings'].create({})
        self.assertTrue(settings.group_construction_exec_planner)
        self.assertTrue(settings.group_construction_exec_project)

    def test_moment_menus(self):
        Menu = self.env['ir.ui.menu'].with_user(self.env.ref('base.user_admin'))
        menus = Menu.load_menus(False)
        root = self._menu_children(menus, 'al_construction_planner.menu_planner_root')
        self.assertIn('al_construction_planner.menu_planner_planning', root)
        self.assertNotIn('al_construction_planner.menu_planner_supply', root)
        planning = self._menu_children(menus, 'al_construction_planner.menu_planner_planning')
        self.assertEqual(planning[:2], ['al_construction_planner.menu_planner_plans',
                                        'al_construction_planner.menu_planner_lines'])
        execution = self._menu_children(menus, 'al_construction_planner.menu_planner_execution')
        self.assertIn('al_construction_planner.menu_planner_supply', execution)
        # «Obras» abre el tablero de obra.
        sites = menus[self.env.ref('al_construction_planner.menu_planner_sites').id]
        self.assertEqual(sites['action_id'],
                         self.env.ref('al_construction_planner.action_construction_site_board').id)
        # Apagado: el menú de siempre (los XMLID no cambian).
        self._feature(G + 'feature_exec_planner', False)
        menus = Menu.load_menus(False)
        root = self._menu_children(menus, 'al_construction_planner.menu_planner_root')
        self.assertNotIn('al_construction_planner.menu_planner_planning', root)
        self.assertIn('al_construction_planner.menu_planner_supply', root)

    def test_board_and_task_execute(self):
        project = self.project.with_user(self.executor)
        self.assertEqual(project.construction_board_plan_id, self.plan)
        self.assertEqual(project.construction_board_planned, 200.0)
        task = self.task.with_user(self.executor)
        self.assertTrue(task.construction_show_execute)
        action = task.action_construction_execute()
        self.assertEqual(action['res_model'], 'construction.task.execute.wizard')
        wizard = self.env['construction.task.execute.wizard'].with_user(self.executor).create(
            {'task_id': self.task.id})
        self.assertEqual(wizard.plan_id, self.plan)
        launched = wizard.action_register_progress()
        self.assertEqual(launched['context']['default_plan_id'], self.plan.id)
        self.assertEqual(launched['context']['construction_selection_task_ids'], self.task.ids)
        self.assertEqual(
            self.env.ref('al_construction_planner.project_task_view_form_construction_site').model,
            'project.task')

    def test_project_panel_section(self):
        buttons = self.project.with_user(self.executor)._get_construction_stat_buttons()
        obra = [b for b in buttons if b.get('construction_section')]
        self.assertTrue(obra)
        self.assertIn('action_construction_view_current_plan', [b['action'] for b in obra])
        # Un proyecto que no es obra conserva el tablero nativo.
        other = self.env['project.project'].create({'name': 'Proyecto común (test)'})
        self.assertFalse([b for b in other._get_construction_stat_buttons() if b.get('construction_section')])
        # Con «Ejecución desde Proyectos» apagado, el tablero se ve como antes.
        self._feature(G + 'feature_exec_project', False)
        buttons = self.project.with_user(self.executor)._get_construction_stat_buttons()
        self.assertFalse([b for b in buttons if b.get('construction_section')])
        # La tarea de obra de la vertical sigue con su menú Ejecutar.
        self.task.invalidate_recordset()
        self.assertTrue(self.task.with_user(self.executor).construction_show_execute)

    def test_executor_without_plan_axis_has_no_planning_menu(self):
        executor = new_test_user(self.env, 'ejec_sin_plan', groups=G + 'user')
        reporter = new_test_user(self.env, 'ejec_reporta', groups=G + 'progress')
        menus = self.env['ir.ui.menu'].with_user(reporter).load_menus(False)
        self.assertNotIn(self.env.ref('al_construction_planner.menu_planner_planning').id, menus)
        # Ejecuta incluye Plan: consulta.
        self.assertTrue(executor.has_group(G + 'plan_viewer'))

    def test_plan_viewer_opens_the_app(self):
        """Plan: consulta, sin el eje de ejecución, entra a la aplicación."""
        viewer = new_test_user(self.env, 'solo_consulta', groups=G + 'plan_viewer')
        self.assertFalse(viewer.has_group(G + 'progress'))
        menus = self.env['ir.ui.menu'].with_user(viewer).load_menus(False)
        root = self.env.ref('al_construction_planner.menu_planner_root').id
        self.assertIn(root, menus)
        self.assertIn('al_construction_planner.menu_planner_planning',
                      self._menu_children(menus, 'al_construction_planner.menu_planner_root'))
