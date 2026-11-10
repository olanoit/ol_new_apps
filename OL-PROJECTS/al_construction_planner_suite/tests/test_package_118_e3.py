# -*- coding: utf-8 -*-
"""Paquete 1.18, entrega 3: «código · nombre» en la importación (M118-08) y el
rótulo del ETO (M118-09). Datos ficticios."""
import base64
from io import BytesIO

from odoo.tests import tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestPackage118Labels(PlannerCommon):

    def _book(self, sheets):
        from openpyxl import Workbook
        book = Workbook()
        book.remove(book.active)
        for name, rows in sheets.items():
            sheet = book.create_sheet(name)
            for row in rows:
                sheet.append(row)
        output = BytesIO()
        book.save(output)
        return base64.b64encode(output.getvalue())

    def test_import_accepts_code_and_name(self):
        wizard = self.env['construction.master.import.wizard'].create({
            'project_id': self.project.id, 'filename': 'maestro.xlsx',
            'file': self._book({
                'MODULOS': [['Tipología', 'Código del módulo', 'Rótulo en el ETO', 'Tipo',
                             'Actividad de armado'],
                            ['T1', 'M1', 'MB-1', 'Bajo', 'ACT1 · Armado de prueba']],
                'BOM': [['Tipología', 'Módulo', 'Código del producto', 'Cantidad'],
                        ['T1', 'M1 · Módulo bajo', 'P1', 2]],
            })})
        sheets, errors = wizard._read_workbook()
        self.assertFalse(errors)
        self.assertEqual(sheets['MODULOS'][0]['activity'], 'ACT1')
        self.assertEqual(sheets['MODULOS'][0]['eto_label'], 'MB-1')
        self.assertEqual(sheets['BOM'][0]['module'], 'M1')

    def test_eto_label_goes_to_the_module_task(self):
        modules = self.env['construction.typology.module'].search(
            [('typology_id.project_id', '=', self.project.id)])
        self.assertTrue(modules)
        modules[0].eto_label = 'MB-1'
        self._generate()
        tasks = self.env['project.task'].search([
            ('project_id', '=', self.project.id), ('construction_level', '=', 'module'),
            ('construction_module_code', '=', modules[0].code)])
        self.assertTrue(tasks)
        self.assertEqual(set(tasks.mapped('construction_eto_label')), {'MB-1'})

    def test_repeated_eto_label_warns(self):
        wizard = self.env['construction.master.import.wizard'].create({
            'project_id': self.project.id, 'filename': 'maestro.xlsx',
            'file': self._book({
                'MODULOS': [['Tipología', 'Código del módulo', 'Rótulo en el ETO', 'Tipo'],
                            ['T1', 'M1', 'MB-1', 'Bajo'], ['T1', 'M2', 'MB-1', 'Bajo']],
            })})
        data = wizard._analyze()
        self.assertIn('T1 · MB-1', data['warnings'].get('eto_label_repeated', []))
