# -*- coding: utf-8 -*-
"""Perfiles de vertical (v1.7, M17-05)."""
from odoo.tests import TransactionCase, tagged

REF = 'al_construction_planner.'


@tagged('post_install', '-at_install')
class TestProfiles(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.construction = cls.env.ref(REF + 'profile_construction')
        cls.furniture = cls.env.ref(REF + 'profile_furniture')
        cls.company = cls.env.company

    def _apply(self, profile):
        profile.with_context(construction_profile_no_install=True).action_apply()

    def test_construction_profile_without_production(self):
        modules = self.construction.module_ids.mapped('name')
        self.assertIn('al_construction_planner_subcontract', modules)
        self.assertIn('al_construction_planner_sale', modules)
        self.assertNotIn('al_construction_planner_mrp', modules)
        self.assertNotIn('al_construction_planner_furniture', modules)
        self._apply(self.construction)
        self.assertEqual(self.company.construction_profile_id, self.construction)
        self.assertEqual(self.company.construction_week_start_day, '0')
        self.assertEqual(self.company.construction_level_template_id,
                         self.env.ref(REF + 'level_template_works'))
        plans = self.env['account.analytic.plan'].search([]).mapped('name')
        for name in ('Disciplina', 'Subpartida', 'Partida'):
            self.assertIn(name, plans)
        # Volver a aplicar no duplica los planes.
        count = len(plans)
        self._apply(self.construction)
        self.assertEqual(self.env['account.analytic.plan'].search_count([]), count)
        site = self.env['project.project'].create({
            'name': 'Obra de constructora (test)', 'is_construction_site': True})
        self.assertEqual(site.construction_profile_id, self.construction)
        self.assertEqual(site.construction_level_template_id.summary,
                         'Disciplina › Subpartida › Partida › Actividad')
        self.assertEqual(site.construction_purchase_destination, 'project')
        deviations = [row[0] for row in self.construction._get_deviations()]
        self.assertNotIn('Plantilla de niveles', deviations)
        self.company.construction_week_start_day = '3'
        self.assertIn(self.company._fields['construction_week_start_day'].string,
                      [row[0] for row in self.construction._get_deviations()])

    def test_export_import_keeps_the_configuration(self):
        data = self.construction._export_data()
        self.assertEqual(data['level_template']['lines'][2]['stages'],
                         ['works_layout', 'works_execution', 'works_finishing', 'works_test'])
        data.update(code='construction_copy', name='Constructora copiada (test)')
        data['level_template']['name'] = 'Partidas copiadas (test)'
        data['stages'].append({'code': 'test17_pressure', 'name': 'Prueba hidrostática (test)',
                               'sequence': 300, 'kind': 'control',
                               'production_consumption': False, 'previous': 'works_test',
                               'duration_days': 1, 'color': False})
        copy = self.env['construction.vertical.profile']._import_data(data)
        self.assertEqual(copy.level_template_id.summary,
                         'Disciplina › Subpartida › Partida › Actividad')
        self.assertEqual(copy.module_ids, self.construction.module_ids)
        self.assertEqual(copy.parameter_ids.mapped('name'), ['construction_week_start_day'])
        pressure = self.env['construction.stage'].search([('code', '=', 'test17_pressure')])
        self.assertEqual(pressure.previous_stage_id.code, 'works_test')
        self.assertIn(pressure, copy.stage_ids)
        # Importarlo otra vez lo actualiza (por su código), no lo duplica.
        data['name'] = 'Constructora copiada 2 (test)'
        again = self.env['construction.vertical.profile']._import_data(data)
        self.assertEqual(again, copy)
        self.assertEqual(copy.name, 'Constructora copiada 2 (test)')

    def test_legacy_companies_get_the_furniture_profile(self):
        """Migración de Allcenter: la compañía con obras pasa a Mobiliario sin
        que sus obras sin plantilla cambien de árbol; la que no usaba el
        planificador y la que ya tiene perfil no cambian."""
        Company = self.env['res.company']
        legacy, unused, chosen = Company.create([
            {'name': 'Mobiliario antiguo (test)'}, {'name': 'Sin obras (test)'},
            {'name': 'Ya elegida (test)', 'construction_profile_id': self.construction.id}])
        Project = self.env['project.project']
        site = Project.with_company(legacy).create(
            {'name': 'Obra antigua (test)', 'is_construction_site': True, 'company_id': legacy.id})
        other = Project.with_company(chosen).create(
            {'name': 'Obra elegida (test)', 'is_construction_site': True, 'company_id': chosen.id})
        # Sin compañía, con compañías de perfiles distintos: no se toca.
        shared = Project.create({'name': 'Obra sin compañía (test)', 'is_construction_site': True,
                                 'company_id': False, 'construction_profile_id': False})
        self.assertFalse(site.construction_level_template_id)
        companies = self.env['construction.vertical.profile']._assign_legacy_companies()
        self.assertIn(legacy, companies)
        self.assertNotIn(unused, companies)
        self.assertEqual(legacy.construction_profile_id, self.furniture)
        self.assertFalse(unused.construction_profile_id)
        self.assertEqual(chosen.construction_profile_id, self.construction)
        self.assertEqual(site.construction_profile_id, self.furniture)
        self.assertFalse(site.construction_level_template_id)
        self.assertEqual(other.construction_profile_id, self.construction)
        self.assertFalse(shared.construction_profile_id)
        # Una obra nueva de la compañía actualizada sigue con el árbol clásico.
        new_site = Project.with_company(legacy).create(
            {'name': 'Obra nueva (test)', 'is_construction_site': True, 'company_id': legacy.id})
        self.assertEqual(new_site.construction_profile_id, self.furniture)
        self.assertFalse(new_site.construction_level_template_id)
        # Otra pasada no cambia nada.
        self.assertFalse(self.env['construction.vertical.profile']._assign_legacy_companies()
                         & (legacy | unused | chosen))

    def test_legacy_sites_without_company(self):
        """Si todas las compañías quedan en Mobiliario (Allcenter), las obras
        sin compañía también, sin cambiar de árbol."""
        Company = self.env['res.company'].with_context(active_test=False)
        legacy = Company.create({'name': 'Única antigua (test)'})
        Company.search([('id', '!=', legacy.id)]).construction_profile_id = self.furniture
        Project = self.env['project.project']
        Project.with_company(legacy).create(
            {'name': 'Obra antigua (test)', 'is_construction_site': True, 'company_id': legacy.id})
        shared = Project.create({'name': 'Obra sin compañía (test)', 'is_construction_site': True,
                                 'company_id': False, 'construction_profile_id': False})
        self.assertEqual(self.env['construction.vertical.profile']._assign_legacy_companies(),
                         legacy)
        self.assertEqual(shared.construction_profile_id, self.furniture)
        self.assertFalse(shared.construction_level_template_id)
