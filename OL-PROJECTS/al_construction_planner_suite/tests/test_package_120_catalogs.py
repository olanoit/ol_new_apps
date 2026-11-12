# -*- coding: utf-8 -*-
"""Paquete 1.20, M120-05 y M120-06.

* Tipos de recurso del perfil: el plan, la obra y Ajustes saben qué tipos usa
  el perfil; un tipo con monto se ve siempre en el resumen.
* Los campos de mueble de la actividad y de Ajustes los pone el puente de
  mobiliario; el núcleo no los muestra."""
from odoo.tests import tagged

from .common import PlannerCommon

P = 'al_construction_planner.'


@tagged('post_install', '-at_install')
class TestCatalogs120(PlannerCommon):

    def test_resource_types_of_the_profile(self):
        profile = self.env.ref(P + 'profile_construction')
        self.project.construction_profile_id = profile
        codes = self.plan.construction_resource_type_codes
        for code in profile.resource_type_ids.mapped('code'):
            self.assertIn(' %s ' % code, codes)
        production = self.env.ref(P + 'resource_type_production', raise_if_not_found=False)
        if production and production not in profile.resource_type_ids:
            self.assertNotIn(' %s ' % production.code, codes)
            self.assertNotIn(' %s ' % production.code, self.project.construction_resource_type_codes)
        # El resumen muestra un tipo con monto aunque no esté en el perfil.
        arch = self.env['construction.resource.plan'].get_views([(False, 'form')])['views']['form']['arch']
        self.assertIn("not amount_production and ' production ' not in", arch)
        # Sin perfil, todos los tipos: se ve todo como hoy.
        self.project.construction_profile_id = False
        self.env.company.construction_profile_id = False
        every = self.env['construction.resource.type'].with_context(active_test=False).search([])
        for code in every.mapped('code'):
            self.assertIn(' %s ' % code, self.plan.construction_resource_type_codes)

    def test_settings_follow_company_profile(self):
        profile = self.env.ref(P + 'profile_construction')
        self.env.company.construction_profile_id = profile
        settings = self.env['res.config.settings'].create({})
        self.assertEqual(sorted(settings.construction_resource_type_codes.split()),
                         sorted(profile.resource_type_ids.mapped('code')))

    def test_furniture_fields_belong_to_the_bridge(self):
        core = {xmlid: self.env.ref(P + xmlid).arch_db for xmlid in (
            'construction_labor_activity_view_form', 'construction_labor_activity_view_list',
            'construction_labor_activity_view_search')}
        for xmlid, arch in core.items():
            self.assertNotIn('name="module_level"', arch, xmlid)
            self.assertNotIn('name="ml_based"', arch, xmlid)
        self.assertNotIn('name="pass_number"', core['construction_labor_activity_view_form'])
        self.assertNotIn('name="construction_categ_assembly_id"',
                         self.env.ref(P + 'res_config_settings_view_form_construction_planner').arch_db)
        bridge = self.env.ref('al_construction_planner_furniture.construction_labor_activity_view_form_measure',
                              raise_if_not_found=False)
        if bridge:
            arch = self.env['construction.labor.activity'].get_views([(False, 'form')])['views']['form']['arch']
            for name in ('module_level', 'ml_based', 'ml_group', 'pass_number', 'hang_role'):
                self.assertIn('name="%s"' % name, arch)
