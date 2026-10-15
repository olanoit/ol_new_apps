# -*- coding: utf-8 -*-
"""Con el planificador instalado, la aplicación «Gantt» no se muestra: sus
accesos están en Planificación de obra ▸ Cronograma y Configuración."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged('post_install', '-at_install')
class TestMenus(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(
            cls.env, login='planner_menus_user',
            groups='base.group_user,al_construction_planner.group_planner_manager,'
                   'al_project_gantt_base.group_gantt_manager')

    def _menus(self):
        return self.env['ir.ui.menu'].with_user(self.user).load_menus(debug=False)

    def test_gantt_app_is_hidden(self):
        gantt_root = self.env.ref('al_project_gantt_backend.menu_gantt_root')
        self.assertIn(gantt_root.id, self.env['ir.ui.menu']._load_menus_blacklist())
        menus = self._menus()
        self.assertNotIn(gantt_root.id, menus['root']['children'])
        self.assertNotIn(gantt_root.id, menus)

    def test_gantt_entries_in_planner(self):
        menus = self._menus()
        planner_root = self.env.ref('al_construction_planner.menu_planner_root')
        self.assertIn(planner_root.id, menus['root']['children'])
        for xmlid in ('al_construction_planner.menu_planner_schedule',
                      'al_construction_planner.menu_planner_gantt',
                      'al_construction_planner.menu_planner_gantt_colors'):
            self.assertIn(self.env.ref(xmlid).id, menus, xmlid)
        gantt = self.env.ref('al_construction_planner.menu_planner_gantt')
        self.assertEqual(gantt.action, self.env.ref('al_project_gantt_backend.action_gantt_backend'))
