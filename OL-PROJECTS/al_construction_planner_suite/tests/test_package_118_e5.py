# -*- coding: utf-8 -*-
"""Paquete 1.18, entrega 5 (M118-15): ajustes menores. Datos ficticios."""
from odoo.tests import tagged

from .common import PlannerCommon
from .test_package_118_e3 import TestPackage118Labels


@tagged('post_install', '-at_install')
class TestPackage118Minor(PlannerCommon):

    _book = TestPackage118Labels._book

    def test_same_product_in_two_modules_is_not_repeated(self):
        code = self.p_white.default_code or 'TEST-WHITE-5'
        self.p_white.default_code = code
        wizard = self.env['construction.master.import.wizard'].create({
            'project_id': self.project.id, 'filename': 'maestro.xlsx',
            'file': self._book({
                'BOM': [['Tipología', 'Módulo', 'Código del producto', 'Cantidad', 'Etapa'],
                        ['T1', 'M1', code, 1, ''], ['T1', 'M2', code, 1, '']],
            })})
        data = wizard._analyze()
        self.assertFalse(data['warnings'].get('bom_duplicate'))

    def test_complete_operations_only_when_needed(self):
        self.assertFalse(self.project.construction_boms_without_operations)
