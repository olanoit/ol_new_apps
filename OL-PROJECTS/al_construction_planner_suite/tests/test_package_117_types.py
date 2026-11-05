# -*- coding: utf-8 -*-
"""Paquete 1.17, M117-24: catálogo de tipos de mueble y de módulo."""
from odoo import Command
from odoo.tests import tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestPackage117Types(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Type = cls.env['construction.furniture.type']
        project = cls.env['project.project'].create(
            {'name': 'Obra tipos (test)', 'is_construction_site': True})
        cls.typology = cls.env['construction.typology'].create(
            {'project_id': project.id, 'code': 'T117', 'name': 'Cocina 1.17'})

    def _module(self, **values):
        return self.env['construction.typology.module'].create(
            dict({'typology_id': self.typology.id, 'code': 'M'}, **values))

    def test_catalog_has_todays_values(self):
        for code in ('low', 'high', 'drawer', 'hood', 'shelf', 'other', 'microwave', 'cupboard',
                     'oven_tower', 'fridge', 'corner', 'spice', 'bottle', 'plinth'):
            self.assertTrue(self.Type._by_code('module', code), code)
        for code in ('low', 'high', 'tower', 'island', 'block'):
            self.assertTrue(self.Type._by_code('furniture', code), code)
        self.assertTrue(self.Type._by_code('module', 'plinth').not_counted)

    def test_low_with_microwave_keeps_its_group(self):
        """Lo que hace la migración: tipo Bajo y especial Microondas."""
        module = self._module(module_type='low', special_kind='microwave', module_class='special',
                              ml_group='low')
        self.assertEqual(module.type_id.code, 'microwave')
        self.assertEqual(module.ml_group, 'low')

    def test_plain_module_takes_its_old_type(self):
        self.assertEqual(self._module(module_type='high').type_id.code, 'high')

    def test_name_gives_the_special_kind(self):
        module = self._module(name='MOD MICROONDAS 600')
        self.assertEqual(module.module_class, 'special')
        self.assertEqual(module.special_kind, 'microwave')
        self.assertEqual(module.type_id.code, 'microwave')

    def test_new_type_from_the_catalog(self):
        panel = self.Type.create({'name': 'Panel de TV', 'code': 'panel_tv', 'level': 'module',
                                  'keywords': 'PANEL', 'ml_group': 'none', 'module_class': 'special'})
        self.assertEqual(self.Type._resolve('Otro', 'PANEL TV 1200'), panel)
        self.assertIn(('panel_tv', 'Panel de TV'), self.Type._selection('module', special=True))
        module = self._module(code='PANEL TV 1200', type_id=panel.id)
        self.assertEqual((module.special_kind, module.module_class, module.ml_group),
                         ('panel_tv', 'special', 'none'))
        self.assertEqual(module.module_type, 'other')
        self.assertEqual(module.type_id, panel, 'el tipo elegido se conserva')

    def test_resolve_accepts_todays_values(self):
        self.assertEqual(self.Type._resolve('Bajo').code, 'low')
        self.assertEqual(self.Type._resolve('Mueble alto').code, 'high')
        self.assertFalse(self.Type._resolve('Inexistente'))

    def test_inactive_type_keeps_its_modules(self):
        kind = self.Type.create({'name': 'Viejo', 'code': 'old', 'level': 'module'})
        module = self._module(type_id=kind.id)
        kind.active = False
        self.assertEqual(module.type_id, kind)
        self.assertFalse(self.Type._resolve('Viejo'))

    def test_task_shows_the_type(self):
        task = self.env['project.task'].create({
            'name': 'Módulo (test)', 'construction_special_kind': 'plinth'})
        self.assertEqual(task.construction_furniture_type_id.code, 'plinth')
        self.assertTrue(Command)
