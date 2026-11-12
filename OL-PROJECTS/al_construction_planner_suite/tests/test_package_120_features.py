# -*- coding: utf-8 -*-
"""Paquete 1.20, M120-07: seis funciones más del perfil de vertical.

* Apagar una función oculta sus menús (con su rol, el usuario los sigue
  viendo al volver a encenderla, sin reinstalar nada).
* La tabla de «Aplicar a la compañía» dice qué se oculta, con la ruta del
  menú y los registros que quedan detrás.
* Un usuario «Planificador» sin «Administrador» no aplica perfiles y ve el
  menú según las funciones.
* Ajustes manda a «Funciones de otras verticales» lo que el perfil de la
  compañía no usa y otro perfil sí."""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import TransactionCase, new_test_user

P = 'al_construction_planner.'
FEATURE_MENUS = {
    'milestones': ['al_construction_planner_sale.menu_planner_unit_milestones',
                   'al_construction_planner_sale.menu_planner_deliveries',
                   'al_construction_planner_sale.menu_planner_milestone_templates'],
    'valuation': ['al_construction_planner_sale.menu_planner_valuation_prepare',
                  'al_construction_planner_sale.menu_planner_valuations',
                  'al_construction_planner_sale.menu_planner_valuation_targets'],
    'deductions': ['al_construction_planner_subcontract.menu_planner_deductions',
                   'al_construction_planner_subcontract.menu_planner_interventions',
                   'al_construction_planner_subcontract.menu_planner_guarantee_funds',
                   'al_construction_planner_subcontract.menu_planner_deduction_types',
                   'al_construction_planner_subcontract.menu_planner_contract_requirements'],
    'daily_report': ['al_construction_portal.menu_construction_daily_reports',
                     'al_construction_portal.menu_construction_portal_tareo'],
    'recipes': [P + 'menu_planner_recipes'],
    'installation_board': ['al_construction_attendance.menu_planner_installation_board'],
}


@tagged('post_install', '-at_install')
class TestProfileFeatures(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = new_test_user(
            cls.env, login='m120_manager',
            groups='base.group_user,base.group_system,analytic.group_analytic_accounting,' + P + 'group_planner_manager')
        cls.planner = new_test_user(
            cls.env, login='m120_planner', groups='base.group_user,' + P + 'group_planner_plan_planner')

    def _set(self, **features):
        self.env['res.config.settings'].create(
            {'group_construction_%s' % name: value for name, value in features.items()}).execute()

    def _visible(self, user, xmlids):
        menus = self.env['ir.ui.menu'].with_user(user).load_menus(debug=False)
        ids = {self.env.ref(xmlid, raise_if_not_found=False).id for xmlid in xmlids
               if self.env.ref(xmlid, raise_if_not_found=False)}
        return ids & set(menus)

    def test_each_feature_hides_and_restores_its_menus(self):
        for feature, xmlids in FEATURE_MENUS.items():
            present = [x for x in xmlids if self.env.ref(x, raise_if_not_found=False)]
            if not present:
                continue
            with self.subTest(feature=feature):
                self._set(**{feature: False})
                self.assertFalse(self._visible(self.manager, present), feature)
                # Volver a encenderla restituye sus menús, sin reinstalar nada.
                self._set(**{feature: True})
                self.assertTrue(self._visible(self.manager, present), feature)

    def test_hidden_menu_does_not_widen_roles(self):
        """Una función activa no abre el menú a quien no tiene su rol: los
        tipos de deductivo son del administrador."""
        xmlid = 'al_construction_planner_subcontract.menu_planner_deduction_types'
        if not self.env.ref(xmlid, raise_if_not_found=False):
            self.skipTest('Sin el puente de contratas')
        self._set(deductions=True)
        self.assertFalse(self._visible(self.planner, [xmlid]))
        self.assertTrue(self._visible(self.manager, [xmlid]))

    def test_apply_table_names_menus_and_records(self):
        profile = self.env.ref(P + 'profile_construction').copy({'code': 'm120_test'})
        profile.write({'feature_recipes': False, 'feature_installation_board': False})
        self._set(recipes=True, installation_board=True)
        self.env['construction.execution.template'].create({'name': 'Receta M120 (test)', 'code': 'M120-TEST'})
        rows = {row[0]: row for row in profile._get_apply_changes()}
        recipes = rows['Recetas por partida']
        self.assertEqual(recipes[1:3], ('Activo', 'Apagado'))
        self.assertIn('Se ocultan: Configuración › Recetas', recipes[3])
        self.assertIn('siguen en la base', recipes[3])
        self.assertIn('Control semanal de instalación', rows)
        # Al aplicar, el menú de Recetas se oculta; los registros siguen.
        profile.with_user(self.manager).with_context(
            construction_profile_no_install=True).action_apply()
        self.assertFalse(self._visible(self.manager, [P + 'menu_planner_recipes']))
        self.assertTrue(self.env['construction.execution.template'].search_count(
            [('name', '=', 'Receta M120 (test)')]))

    def test_planner_without_admin(self):
        profile = self.env.ref(P + 'profile_furniture')
        with self.assertRaises(UserError):
            profile.with_user(self.planner).action_open_apply_wizard()
        self._set(recipes=False)
        self.assertFalse(self._visible(self.planner, [P + 'menu_planner_recipes']))

    def test_other_vertical_features_in_settings(self):
        company = self.env.company
        company.construction_profile_id = self.env.ref(P + 'profile_construction')
        settings = self.env['res.config.settings'].create({})
        others = settings.construction_other_features.split()
        self.assertIn('group_construction_measurement', others)
        self.assertIn('group_construction_installation_board', others)
        self.assertNotIn('group_construction_valuation', others)
        if 'module_al_construction_planner_furniture' in settings._fields:
            self.assertIn('module_al_construction_planner_furniture', others)
        # Sin perfil, nada va al bloque plegado.
        company.construction_profile_id = False
        self.assertFalse(self.env['res.config.settings'].create({}).construction_other_features)
        # La vista de Ajustes carga con los dos bloques.
        arch = self.env['res.config.settings'].get_views([(False, 'form')])['views']['form']['arch']
        self.assertIn('Funciones de otras verticales', arch)

    def test_standard_profiles(self):
        furniture = self.env.ref(P + 'profile_furniture')
        construction = self.env.ref(P + 'profile_construction')
        self.assertTrue(furniture.feature_milestones and furniture.feature_installation_board)
        self.assertFalse(furniture.feature_valuation or furniture.feature_deductions
                         or furniture.feature_daily_report or furniture.feature_recipes)
        self.assertFalse(construction.feature_milestones or construction.feature_installation_board)
        self.assertTrue(construction.feature_valuation and construction.feature_deductions
                        and construction.feature_daily_report and construction.feature_recipes)


@tagged('post_install', '-at_install')
class TestProfileFeaturesTour(HttpCase):
    """Prueba de pantalla de M120-07: abrir el perfil, apagar «Valorización por
    avance», aplicar, recargar y abrir Ingresos."""

    def setUp(self):
        super().setUp()
        self.env.ref('base.user_admin').write({
            'company_ids': [Command.link(self.env.company.id)],
            'company_id': self.env.company.id,
            'group_ids': [Command.link(self.env.ref(P + 'group_planner_manager').id)]})

    def test_profile_features_tour(self):
        self.start_tour('/odoo', 'al_construction_profile_features', login='admin')
        self.assertFalse(self.env.ref(P + 'profile_construction').feature_valuation)
