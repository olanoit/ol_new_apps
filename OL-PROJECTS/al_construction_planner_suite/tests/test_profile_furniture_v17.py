# -*- coding: utf-8 -*-
"""Mobiliario (v1.7, M17-05): con el perfil aplicado, la demo del piso 05 da las
cifras del criterio 2 (66 módulos, 41.33 ML y S/ 8,944.44)."""
from odoo.tests import TransactionCase, tagged

from .common import load_demo


@tagged('post_install', '-at_install')
class TestFurnitureProfile(TransactionCase):

    def test_demo_figures_with_the_profile(self):
        profile = self.env.ref('al_construction_planner.profile_furniture')
        profile.with_context(construction_profile_no_install=True).action_apply()
        self.assertFalse(profile._modules_to_install())
        demo = load_demo(self.env, 'TEST PERFIL')
        project = demo['project']
        self.assertEqual(project.construction_level_template_id,
                         self.env.ref('al_construction_planner.level_template_building'))
        self.assertEqual(demo['floor'].construction_level_line_id.name, 'Piso')
        root = demo['plan'].get_tree_nodes('root')[0]
        self.assertEqual(root['modules'], 66)
        self.assertAlmostEqual(root['ml'], 41.33)
        self.assertAlmostEqual(root['total'], 8944.44)
