# -*- coding: utf-8 -*-
"""Paquete 1.17, entrega 4. M117-08 (avance) y M117-24 en la hoja."""
from odoo.tests import HttpCase, tagged

from .test_package_116_stage4b import _book, _headers, _row
from .test_worksheet_v18 import TestWorksheetV18


@tagged('post_install', '-at_install')
class TestPackage117TypesInSheet(TestWorksheetV18):

    def _data(self):
        return self.site._construction_spreadsheet_data(10)

    def _sheet(self, data, name):
        return next(sheet for sheet in data['sheets'] if sheet['name'] == name)

    def test_modules_read_the_catalog(self):
        data = self._data()
        modules = self._sheet(data, 'MODULOS')
        cells = modules['cells']
        self.assertEqual(cells['J1'], 'Clase (calc.)')
        self.assertIn('REFERENCIAS!$AC$3', cells['J2'])
        armar = next(ref for ref, value in cells.items() if value == 'A armar (calc.)')
        formula = cells[armar.replace('1', '2')]
        self.assertIn('REFERENCIAS!$AD$3', formula)
        self.assertNotIn('ZOCALO', formula)
        rules = {rule['id']: rule for rule in modules['dataValidationRules']}
        self.assertEqual(rules['MODULOS_type_2']['criterion']['type'], 'isValueInRange')
        self.assertIn('MODULOS_type_2', rules)
        self.assertFalse(any('module_class' in rule_id for rule_id in rules))
        lists = {item['name']: item for item in data['lists'].values()}
        self.assertEqual(lists['Tipos de módulo']['model'], 'construction.furniture.type')

    def test_import_writes_the_catalog_name(self):
        self.env['construction.furniture.type'].create({
            'name': 'Panel de TV', 'code': 'panel_tv', 'level': 'module', 'keywords': 'PANEL'})
        self.site.action_construction_open_spreadsheet()
        document = self.env['documents.document'].search(
            [('construction_project_id', '=', self.site.id),
             ('construction_source_id', '=', False)])
        wizard = self.env['construction.spreadsheet.import.wizard'].create({
            'document_id': document.id, 'filename': 'm.xlsx', 'file': _book({'MODULOS': [
                _headers('MODULOS'),
                _row('MODULOS', typology='C1', code='P1', type='Otro', name='PANEL TV 1200'),
                _row('MODULOS', typology='C1', code='M1', type='Mueble bajo')]})})
        payload = wizard.action_import()['infos']['construction_sheet_import']
        spec = payload['sheets']['MODULOS']
        rows = [dict(zip(spec['keys'], row)) for row in spec['rows']]
        self.assertEqual([row['type'] for row in rows], ['Panel de TV', 'Bajo'])


@tagged('post_install', '-at_install')
class TestPackage117ProgressTour(HttpCase):

    def test_progress_cancel_and_time(self):
        site = self.env['project.project'].create({
            'name': 'Obra carga grande (test)', 'is_construction_site': True,
            'construction_spreadsheet_rows': 10})
        site.action_construction_open_spreadsheet()
        rows = [_row('ARBOL', floor='Piso %02d' % (n // 40), apartment='Dpto %s' % n,
                     space='Cocina') for n in range(1500)]
        self.env['ir.attachment'].create({
            'name': 'al_sheet_progress_tour.xlsx', 'datas': _book({
                'ARBOL': [_headers('ARBOL')] + rows})})
        self.start_tour('/odoo', 'al_construction_sheet_progress', login='admin', timeout=500)
