# -*- coding: utf-8 -*-
"""Tests unitarios del motor de extracción (funciones puras)."""
from odoo.tests import TransactionCase, tagged

from ..services import engine


@tagged('post_install', '-at_install')
class TestEngine(TransactionCase):

    def test_get_path_simple(self):
        self.assertEqual(engine.get_path({'a': 1}, 'a'), 1)
        self.assertIsNone(engine.get_path({'a': 1}, 'b'))

    def test_get_path_nested(self):
        data = {'data': {'direccion': 'AV X'}}
        self.assertEqual(engine.get_path(data, 'data.direccion'), 'AV X')
        self.assertIsNone(engine.get_path(data, 'data.zzz'))

    def test_get_path_list_index(self):
        data = {'ubigeo': ['15', '01', '150131']}
        self.assertEqual(engine.get_path(data, 'ubigeo.2'), '150131')
        self.assertIsNone(engine.get_path(data, 'ubigeo.9'))

    def test_render_source_plain(self):
        self.assertEqual(engine.render_source({'x': 'v'}, 'x'), 'v')

    def test_render_source_template(self):
        data = {'nombres': 'JUAN', 'ap': 'PEREZ'}
        self.assertEqual(
            engine.render_source(data, '{nombres} {ap}'), 'JUAN PEREZ')
        # Marcador ausente → vacío, sin romper.
        self.assertEqual(engine.render_source(data, '{nombres} {zzz}'), 'JUAN ')

    def test_transforms(self):
        self.assertEqual(engine.apply_transform('aBc', 'upper'), 'ABC')
        self.assertEqual(engine.apply_transform('aBc', 'lower'), 'abc')
        self.assertEqual(engine.apply_transform('juan perez', 'title'), 'Juan Perez')
        self.assertEqual(engine.apply_transform('  x  ', 'strip'), 'x')
        self.assertEqual(engine.apply_transform('x', 'none'), 'x')
        self.assertIsNone(engine.apply_transform(None, 'upper'))

    def test_truthy(self):
        self.assertTrue(engine.truthy(True))
        self.assertTrue(engine.truthy(1))
        self.assertTrue(engine.truthy('true'))
        self.assertFalse(engine.truthy('false'))
        self.assertFalse(engine.truthy(''))
        self.assertFalse(engine.truthy(0))
