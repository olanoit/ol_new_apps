# -*- coding: utf-8 -*-
"""Menús y términos por vertical (v1.8, M18-01).

El perfil Construcción por partidas apaga el metrado: no aparece ningún menú
de metrados y los niveles se llaman como en su plantilla (partida,
actividad). Con el perfil Mobiliario vuelven Metrados y Generar metrados.
Aplicar un perfil desde la interfaz avisa qué menús y funciones cambian."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user

REF = 'al_construction_planner.'
MEASUREMENT_MENUS = ('menu_planner_measurements', 'menu_planner_measurement_lines',
                     'menu_planner_measurement_generate')


@tagged('post_install', '-at_install')
class TestVerticalTerms(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.construction = cls.env.ref(REF + 'profile_construction')
        cls.furniture = cls.env.ref(REF + 'profile_furniture')
        cls.user = new_test_user(
            cls.env, login='planner_vertical_user',
            groups='base.group_user,al_construction_planner.group_planner_planner')

    def _apply(self, profile):
        profile.with_context(construction_profile_no_install=True).action_apply()

    def _menus(self):
        self.env.transaction.invalidate_ormcache()
        return self.env['ir.ui.menu'].with_user(self.user)._visible_menu_ids()

    def test_construction_hides_measurement(self):
        self.assertFalse(self.construction.feature_measurement)
        self.assertTrue(self.construction.feature_progress)
        self._apply(self.construction)
        internal = self.env.ref('base.group_user')
        self.assertNotIn(self.env.ref(REF + 'group_planner_feature_measurement'),
                         internal.implied_ids)
        self.assertFalse(self.user.has_group(REF + 'group_planner_feature_measurement'))
        menus = self._menus()
        for xmlid in MEASUREMENT_MENUS:
            self.assertNotIn(self.env.ref(REF + xmlid).id, menus, xmlid)
        self.assertIn(self.env.ref(REF + 'menu_planner_progress_register').id, menus)
        self._apply(self.furniture)
        menus = self._menus()
        for xmlid in MEASUREMENT_MENUS:
            self.assertIn(self.env.ref(REF + xmlid).id, menus, xmlid)

    def test_apply_wizard_lists_changes(self):
        self._apply(self.furniture)
        self.env['project.project'].create({'name': 'Obra existente (test)',
                                            'is_construction_site': True})
        action = self.construction.action_open_apply_wizard()
        wizard = self.env[action['res_model']].browse(action['res_id'])
        self.assertTrue(wizard.site_count)
        rows = self.construction._get_apply_changes()
        metrado = next(row for row in rows if row[0] == 'Metrado')
        self.assertEqual(metrado[1:3], ('Activo', 'Apagado'))
        self.assertIn('Metrados', metrado[3])
        self.assertIn('Metrado', str(wizard.changes_html))
        wizard.with_context(construction_profile_no_install=True).action_confirm()
        self.assertEqual(self.env.company.construction_profile_id, self.construction)

    def test_level_names_follow_the_template(self):
        self._apply(self.construction)
        fields = self.env['construction.resource.plan.line'].fields_get(
            ['space_task_id', 'module_task_id', 'level_1_id', 'level_3_id'], ['string'])
        self.assertEqual(fields['space_task_id']['string'], 'Partida')
        self.assertEqual(fields['module_task_id']['string'], 'Actividad')
        self.assertEqual(fields['level_1_id']['string'], 'Disciplina')
        self.assertEqual(fields['level_3_id']['string'], 'Partida')
        task_fields = self.env['project.task'].fields_get(['construction_space_task_id'], ['string'])
        self.assertEqual(task_fields['construction_space_task_id']['string'], 'Partida')
        site = self.env['project.project'].create({'name': 'Obra por partidas (test)',
                                                   'is_construction_site': True})
        plan = self.env['construction.resource.plan'].create({'project_id': site.id})
        terms = plan.get_tree_terms()
        self.assertEqual(terms['details'], 'Actividades')
        self.assertEqual(terms['spaces'], 'Partidas')
        self.assertFalse(terms['show_ml'])
        self.assertFalse(terms['show_typology'])
        label = self.env['construction.task.progress'].fields_get(['space_task_id'], ['string'])
        self.assertEqual(label['space_task_id']['string'], 'Partida')
