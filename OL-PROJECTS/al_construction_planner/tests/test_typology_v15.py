# -*- coding: utf-8 -*-
"""v1.5, fase 13: tipologías completas (familia, variantes, otros nombres,
muebles y variantes por unidad)."""
import base64

from odoo.exceptions import ValidationError
from odoo.tests import new_test_user, tagged

from odoo.addons.al_construction_planner.wizards.master_import_layout import build_workbook

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestTypologyV15(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.site = cls.env['project.project'].create({
            'name': 'Obra con muebles (test)', 'is_construction_site': True,
            'construction_level_template_id': cls.env.ref(
                'al_construction_planner.level_template_building').id})
        cls.kitchen_t = cls.typology.copy({'project_id': cls.site.id, 'code': 'VK-01'})
        cls.low = cls.env['construction.typology.furniture'].create({
            'typology_id': cls.kitchen_t.id, 'name': 'Mueble bajo', 'ml_group': 'low', 'ml': 2.4})
        cls.high = cls.env['construction.typology.furniture'].create({
            'typology_id': cls.kitchen_t.id, 'name': 'Mueble alto', 'ml_group': 'high', 'ml': 1.8})
        cls.oven = cls.env['construction.typology.furniture'].create({
            'typology_id': cls.kitchen_t.id, 'name': 'Torre de horno', 'ml_group': 'other'})
        for module in cls.kitchen_t.module_line_ids:
            module.furniture_id = {'low': cls.low, 'high': cls.high}.get(
                module.module_type, cls.oven)
        # Las actividades por ML no listadas en la tipología: se calculan por mueble.
        cls.kitchen_t.activity_line_ids.filtered(lambda l: l.activity_id.ml_based).unlink()
        cls.env['construction.labor.rate'].create([
            {'activity_id': act.id, 'project_id': cls.site.id, 'price': 18.0}
            for act in (cls.act_inst_low, cls.act_inst_high)])
        Task = cls.env['project.task']

        def node(name, level, parent=None, **vals):
            return Task.create(dict(cls.site._construction_level_vals(level), **dict({
                'name': name, 'project_id': cls.site.id,
                'parent_id': parent.id if parent else False}, **vals)))

        cls.floor_s = node('Piso 06', 'floor')
        cls.unit_601 = node('Dpto 601', 'apartment', cls.floor_s)
        cls.unit_602 = node('Dpto 602', 'apartment', cls.floor_s)
        cls.space_601 = node('Cocina', 'space', cls.unit_601,
                             construction_typology_id=cls.kitchen_t.id)
        cls.space_602 = node('Cocina', 'space', cls.unit_602,
                             construction_typology_id=cls.kitchen_t.id)
        cls.site_plan = cls.env['construction.resource.plan'].create({'project_id': cls.site.id})

    def _generate_site(self):
        wizard = self.env['construction.plan.generate.wizard'].create(
            {'plan_id': self.site_plan.id})
        wizard.action_generate()
        return self.site_plan.line_ids

    def test_aliases_and_variant(self):
        Typology = self.env['construction.typology']
        self.kitchen_t.alias_ids = [(0, 0, {'name': 'V-K-01', 'source': 'client_order'}),
                                    (0, 0, {'name': 'COCINA 05', 'source': 'projection'})]
        for name in ('vk01', 'V-K-01', 'Cocina 05', 'VK-01'):
            self.assertEqual(Typology._find_by_name(self.site, name), self.kitchen_t, name)
        variant = self.kitchen_t.copy({'code': 'VK-01A', 'variant_of_id': self.kitchen_t.id})
        self.assertIn(variant, self.kitchen_t.variant_ids)
        with self.assertRaises(ValidationError):
            variant.copy({'code': 'VK-01B', 'variant_of_id': variant.id})

    def test_modules_and_ml_by_furniture(self):
        lines = self._generate_site()
        Task = self.env['project.task']
        furniture = Task.search([('parent_id', '=', self.space_601.id)])
        self.assertEqual(set(furniture.mapped('name')), {'Mueble bajo', 'Mueble alto', 'Torre de horno'})
        bottom = furniture.filtered(lambda f: f.name == 'Mueble bajo')
        self.assertEqual(bottom.construction_furniture_ml, 2.4)
        self.assertEqual(len(Task.search([('parent_id', '=', bottom.id)])), 2, 'tornillo y tarugo 1')
        ml_lines = lines.filtered(lambda l: l.activity_id.ml_based and l.space_task_id == self.space_601)
        self.assertEqual(sorted(ml_lines.mapped('qty_planned')), [1.8, 2.4])
        self.assertEqual(set(ml_lines.mapped('task_id.construction_level')), {'furniture'})
        self.assertEqual(ml_lines.filtered(lambda l: l.task_id == bottom).price_unit_planned, 18.0)
        tree = self.site_plan.get_tree_nodes(str(self.space_601.id))
        self.assertEqual({n['name']: n['ml'] for n in tree}['Mueble bajo'], 2.4)

    def test_unit_overrides(self):
        Override = self.env['construction.unit.override']
        Override.create([
            {'task_id': self.unit_601.id, 'kind': 'color', 'product_id': self.p_white.id,
             'new_product_id': self.p_cognac.id, 'note': 'Rovere (test)'},
            {'task_id': self.space_601.id, 'kind': 'exclude', 'product_id': self.p_hinge.id},
            {'task_id': self.space_601.id, 'kind': 'qty', 'product_id': self.p_screw.id, 'qty': 99},
        ])
        with self.assertRaises(ValidationError):
            Override.create({'task_id': self.unit_602.id, 'kind': 'color',
                             'product_id': self.p_white.id})
        lines = self._generate_site().filtered(lambda l: l.resource_type == 'material')
        mine = lines.filtered(lambda l: l.space_task_id == self.space_601)
        other = lines.filtered(lambda l: l.space_task_id == self.space_602)
        self.assertNotIn(self.p_white, mine.product_id)
        self.assertEqual(len(mine.filtered(lambda l: l.product_id == self.p_cognac)), 2,
                         'la suya y la del color reemplazado')
        self.assertNotIn(self.p_hinge, mine.product_id)
        self.assertEqual(mine.filtered(lambda l: l.product_id == self.p_screw).qty_planned, 99)
        self.assertIn(self.p_white, other.product_id, 'la otra unidad no cambia')
        self.assertIn(self.p_hinge, other.product_id)

    def test_import_aliases_furniture_and_overrides(self):
        manager = new_test_user(self.env, 'plan_admin_typ', name='Admin tipologías (test)',
                                groups='al_construction_planner.group_planner_manager')
        self.p_white.default_code = 'MEL-BL'
        self.p_cognac.default_code = 'MEL-CO'
        site = self.env['project.project'].create({
            'name': 'Obra importada con muebles (test)', 'is_construction_site': True,
            'construction_level_template_id': self.env.ref(
                'al_construction_planner.level_template_building').id})
        rows = {
            'TIPOLOGIAS': [
                {'code': 'C05', 'name': 'Cocina 05', 'family': 'Cocina',
                 'aliases': 'VK-01; V-K-01'},
                {'code': 'C05A', 'name': 'Cocina 05 A', 'family': 'Cocina', 'variant_of': 'VK-01'},
                {'code': 'D1', 'name': 'Ducto tipo 1', 'family': 'Ducto'},
            ],
            'MUEBLES': [{'typology': 'C05', 'name': 'Mueble bajo', 'ml_group': 'Bajo', 'ml': 2.5},
                        {'typology': 'V-K-01', 'name': 'Mueble alto', 'ml_group': 'Alto', 'ml': 2}],
            'MODULOS': [{'typology': 'C05', 'code': 'MB01', 'type': 'Bajo',
                         'activity': self.act_screw.code, 'furniture': 'Mueble bajo'}],
            'ARBOL': [{'floor': 'P1', 'apartment': 'D101', 'space': 'Cocina', 'typology': 'V-K-01'}],
            'VARIANTES': [{'floor': 'P1', 'apartment': 'D101', 'kind': 'Color',
                           'product_code': 'MEL-BL', 'new_product_code': 'MEL-CO',
                           'note': 'Rovere'}],
        }
        wizard = self.env['construction.master.import.wizard'].with_user(manager).create({
            'project_id': site.id, 'file': base64.b64encode(build_workbook(rows)),
            'filename': 'maestro.xlsx'})
        data = wizard._analyze()
        self.assertFalse(data['errors'])
        self.assertFalse(data['warnings'].get('unknown_typology'))
        wizard.action_import()
        Typology = self.env['construction.typology']
        c05 = Typology.search([('project_id', '=', site.id), ('code', '=', 'C05')])
        self.assertEqual(set(c05.alias_ids.mapped('name')), {'VK-01', 'V-K-01'})
        self.assertEqual(Typology.search([('project_id', '=', site.id), ('code', '=', 'C05A')])
                         .variant_of_id, c05)
        self.assertEqual(Typology.search([('project_id', '=', site.id), ('code', '=', 'D1')]).family,
                         'duct')
        self.assertEqual({f.name: f.ml for f in c05.furniture_line_ids},
                         {'Mueble bajo': 2.5, 'Mueble alto': 2.0})
        self.assertEqual(c05.module_line_ids.furniture_id.name, 'Mueble bajo')
        space = self.env['project.task'].search([('project_id', '=', site.id),
                                                 ('construction_level', '=', 'space')])
        self.assertEqual(space.construction_typology_id, c05, 'por su otro nombre')
        override = space.construction_apartment_task_id.construction_override_ids
        self.assertEqual((override.kind, override.product_id, override.new_product_id),
                         ('color', self.p_white, self.p_cognac))
