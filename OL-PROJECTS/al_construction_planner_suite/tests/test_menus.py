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


P = 'al_construction_planner.'


@tagged('post_install', '-at_install')
class TestMomentMenus120(TransactionCase):
    """Paquete 1.20, M120-01 y M120-02: la barra en ocho menús, Ejecución en
    cuatro secciones, Contratas con su personal y Configuración en siete
    secciones. Con «Ejecución en Planificación de obra» apagado, el menú de
    siempre."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.config.settings'].create({'group_construction_exec_planner': True}).execute()
        cls.manager = new_test_user(
            cls.env, login='m120_menu_manager',
            groups='base.group_user,' + P + 'group_planner_manager,' + P + 'group_planner_revenue,'
                   'al_project_gantt_base.group_gantt_manager')
        cls.executor = new_test_user(
            cls.env, login='m120_menu_executor', groups='base.group_user,' + P + 'group_planner_user')

    def _tree(self, user):
        menus = self.env['ir.ui.menu'].with_user(user).load_menus(debug=False)

        def node(menu_id):
            entry = menus[menu_id]
            return {'name': entry['name'], 'xmlid': entry.get('xmlid'), 'id': menu_id,
                    'children': [node(child) for child in entry.get('children', [])]}
        return node(self.env.ref(P + 'menu_planner_root').id)

    @staticmethod
    def _child(tree, xmlid):
        return next((child for child in tree['children'] if child['xmlid'] == xmlid), None)

    def test_bar_execution_and_contracts(self):
        tree = self._tree(self.manager)
        bar = [child['xmlid'] for child in tree['children']]
        expected = [P + 'menu_planner_works', P + 'menu_planner_planning',
                    P + 'menu_planner_execution', P + 'menu_planner_supply',
                    P + 'menu_planner_contracts', 'al_construction_planner_sale.menu_planner_income',
                    P + 'menu_planner_reports', P + 'menu_planner_config']
        self.assertEqual([x for x in bar if x in expected], expected)
        execution = self._child(tree, P + 'menu_planner_execution')
        sections = [child['xmlid'] for child in execution['children']]
        self.assertEqual(sections, [P + 'menu_planner_progress', P + 'menu_planner_exec_control',
                                    P + 'menu_planner_exec_staff', P + 'menu_planner_changes'])
        # Ninguna opción suelta en Ejecución y ninguna sección vacía.
        self.assertTrue(all(section['children'] for section in execution['children']))
        progress = self._child(execution, P + 'menu_planner_progress')
        names = [child['xmlid'] for child in progress['children']]
        for hidden in ('menu_planner_measurements', 'menu_planner_measurement_lines',
                       'menu_planner_measurement_generate'):
            self.assertNotIn(P + hidden, names)
        # El personal de contratas solo en Contratas.
        contracts = self._child(tree, P + 'menu_planner_contracts')
        staff = self._child(contracts, P + 'menu_planner_contract_staff')
        workers = 'al_construction_attendance.menu_planner_contractor_workers'
        if self.env.ref(workers, raise_if_not_found=False):
            self.assertIn(workers, [child['xmlid'] for child in staff['children']])
            own = self._child(execution, P + 'menu_planner_exec_staff')
            self.assertNotIn(workers, [child['xmlid'] for child in own['children']])
        # «Deductivos de contrata» abre la acción de siempre.
        deductions = self.env.ref('al_construction_planner_subcontract.menu_planner_deductions',
                                  raise_if_not_found=False)
        if deductions:
            entry = self._child(contracts, 'al_construction_planner_subcontract.menu_planner_deductions')
            self.assertEqual(entry['name'], 'Deductivos de contrata')
            menus = self.env['ir.ui.menu'].with_user(self.manager).load_menus(debug=False)
            self.assertEqual(menus[deductions.id]['action_id'], deductions.action.id)

    def test_configuration_sections(self):
        tree = self._tree(self.manager)
        config = self._child(tree, P + 'menu_planner_config')
        order = [child['xmlid'] for child in config['children']]
        expected = [P + 'menu_planner_settings', P + 'menu_planner_config_vertical',
                    P + 'menu_planner_config_recipes', P + 'menu_planner_config_contracts',
                    P + 'menu_planner_config_sheets', P + 'menu_planner_config_analytic',
                    P + 'menu_planner_config_portal', P + 'menu_planner_config_other']
        self.assertEqual([x for x in order if x in expected], [x for x in expected if x in order])
        self.assertNotIn(P + 'menu_planner_config_plan', order)
        self.assertNotIn('al_construction_planner_sale.menu_planner_config_income', order)
        vertical = self._child(config, P + 'menu_planner_config_vertical')
        self.assertEqual([child['xmlid'] for child in vertical['children']][:3],
                         [P + 'menu_planner_profiles', P + 'menu_planner_profile_import',
                          P + 'menu_planner_level_templates'])

    def test_executor_without_admin(self):
        tree = self._tree(self.executor)
        self.assertTrue(self._child(tree, P + 'menu_planner_execution'))
        contracts = self._child(tree, P + 'menu_planner_contracts')
        self.assertTrue(contracts)
        self.assertFalse(self._child(tree, P + 'menu_planner_config'))

    def test_without_moments_menu_is_unchanged(self):
        self.env['res.config.settings'].create({'group_construction_exec_planner': False}).execute()
        tree = self._tree(self.manager)
        execution = self._child(tree, P + 'menu_planner_execution')
        self.assertTrue(self._child(execution, P + 'menu_planner_contracts'))
        self.assertFalse(self._child(tree, P + 'menu_planner_contracts'))
        config = self._child(tree, P + 'menu_planner_config')
        self.assertTrue(self._child(config, P + 'menu_planner_config_plan'))
