# -*- coding: utf-8 -*-
"""Funciones activables en Ajustes (v1.7, M17-06)."""
from odoo.tests import TransactionCase, new_test_user, tagged

BRIDGES = ('mrp', 'subcontract', 'purchase', 'crew', 'budget', 'sale', 'furniture')


@tagged('post_install', '-at_install')
class TestFeatures(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, 'funciones_planificador', name='Planificador (test)',
                                 groups='al_construction_planner.group_planner_manager')

    def _visible(self, xmlid):
        menu = self.env.ref(xmlid)
        visible = self.env['ir.ui.menu'].with_user(self.user)._visible_menu_ids()
        return menu.id in visible

    def test_switches_install_their_bridge(self):
        settings = self.env['res.config.settings']
        for bridge in BRIDGES:
            field = 'module_al_construction_planner_%s' % bridge
            self.assertIn(field, settings._fields, field)
            self.assertTrue(self.env['ir.module.module'].search_count(
                [('name', '=', 'al_construction_planner_%s' % bridge)]))

    def test_core_features_hide_their_menus(self):
        self.assertTrue(self._visible('al_construction_planner.menu_planner_progress'))
        self.assertTrue(self._visible('al_construction_planner.menu_planner_control'))
        settings = self.env['res.config.settings'].create({})
        self.assertTrue(settings.group_construction_control)
        self.assertTrue(settings.group_construction_progress)
        settings.group_construction_progress = False
        settings.set_values()
        self.env.registry.clear_cache()
        self.assertFalse(self.user.has_group(
            'al_construction_planner.group_planner_feature_progress'))
        self.assertFalse(self._visible('al_construction_planner.menu_planner_progress'))
        self.assertTrue(self._visible('al_construction_planner.menu_planner_control'))
        plan = self.env['construction.resource.plan'].create({
            'project_id': self.env['project.project'].create({
                'name': 'Obra sin avance (test)', 'is_construction_site': True}).id})
        actions = plan.with_user(self.user).get_tree_actions()
        self.assertNotIn('al_construction_planner.action_plan_progress_wizard',
                         [action['xmlid'] for action in actions])
