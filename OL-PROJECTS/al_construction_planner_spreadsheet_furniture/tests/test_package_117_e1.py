# -*- coding: utf-8 -*-
"""Paquete 1.17, entrega 1.

- M117-03: la importación no escribe en las pestañas de la plantilla; versiones
  con su acción de origen para «Restaurar versión».
- M117-04: las listas fijas rechazan el valor inválido.
- M117-06: CONTROL se compara al abrir la hoja después de un envío (recorrido).
"""
from odoo import fields
from odoo.tests import HttpCase, tagged

from ..models.project_project import FIXED_LISTS
from .test_package_116_stage4b import _book, _headers, _row
from .test_worksheet_v18 import TestWorksheetV18


@tagged('post_install', '-at_install')
class TestPackage117Delivery1(TestWorksheetV18):

    def _document(self):
        self.site.action_construction_open_spreadsheet()
        return self.env['documents.document'].search(
            [('construction_project_id', '=', self.site.id),
             ('construction_source_id', '=', False)])

    def _wizard(self, document, sheets, **values):
        return self.env['construction.spreadsheet.import.wizard'].create({
            'document_id': document.id, 'file': _book(sheets), 'filename': 'otra hoja.xlsx',
            **values})

    def _book_from_other_sheet(self):
        return {
            'INICIO': [['Obra de otra hoja']],
            'LEEME': [['No se copia']],
            'RESUMEN': [['Tabla']],
            'REFERENCIAS': [['Lista']],
            '_LISTAS': [['Lista']],
            'FICHA': [['Ficha']],
            'PROGRAMA': [['Programa']],
            'CONTROL': [['Control']],
            'ERRORES': [['Errores']],
            '_CLAVES': [['Hoja', 'Clave', 'Columna']],
            'VENDIDO': [['Tipología']],
            'EDIFICIO': [['Piso desde']],
            'RESUMEN VENTA': [['Subtotal']],
            'FUENTES': [['Origen'], ['Proyección OT']],
            'MATERIALES OBRA': [['Material', 'Categoría (calc.)', 'Código (calc.)'],
                                ['Tablero · Unidad · T1', 'TABLEROS', 'T1']],
            'BOM': [_headers('BOM') + ['Fuente', 'Costo de la línea (calc.)'],
                    _row('BOM', typology='COCINA 04', product_code='T18H-MEL', qty=1)
                    + ['OT 12', 15]],
        }

    def test_import_leaves_template_sheets_alone(self):
        wizard = self._wizard(self._document(), self._book_from_other_sheet())
        for text in ('Importa por clave', 'Ignorada: es de la plantilla',
                     'Ignorada: es de la hoja de venta', 'Se copia'):
            self.assertIn(text, wizard.review_html)
        payload = wizard.action_import()['infos']['construction_sheet_import']
        self.assertEqual(list(payload['other']), ['FUENTES'])
        self.assertCountEqual(payload['ignored'], [
            'INICIO', 'RESUMEN', 'REFERENCIAS', '_LISTAS', 'FICHA', 'PROGRAMA', 'CONTROL',
            'ERRORES', '_CLAVES', 'VENDIDO', 'EDIFICIO', 'RESUMEN VENTA'])
        self.assertNotIn('LEEME', payload['ignored'])
        # La calculada de otra hoja no es una columna extra; la propia, sí.
        self.assertEqual(payload['sheets']['BOM']['extra_headers'], ['Fuente'])

    def test_work_materials_import_only_the_material(self):
        payload = self._wizard(self._document(), self._book_from_other_sheet()).action_import()[
            'infos']['construction_sheet_import']
        materials = payload['sheets']['MATERIALES OBRA']
        self.assertEqual(materials['keys'], ['material'])
        self.assertEqual(materials['rows'], [['Tablero · Unidad · T1']])
        self.assertEqual(materials['extra_headers'], [])

    def test_keep_extra_off_copies_nothing_and_still_ignores(self):
        wizard = self._wizard(self._document(), self._book_from_other_sheet(), keep_extra=False)
        self.assertIn('No se copia', wizard.review_html)
        payload = wizard.action_import()['infos']['construction_sheet_import']
        self.assertEqual(payload['other'], {})
        self.assertIn('INICIO', payload['ignored'])

    def test_fixed_lists_reject_invalid_values(self):
        layout = self.site._construction_sheet_layout()
        parts = self.site._construction_row_parts(layout, 2, 30)
        for (sheet, _key), values in FIXED_LISTS.items():
            rules = [rule for rule in parts[sheet]['rules']
                     if rule['criterion'].get('values') == values]
            self.assertTrue(rules, sheet)
            self.assertTrue(all(rule['isBlocking'] for rule in rules), sheet)
        # Una lista de rango no rechaza: admite escribir un producto nuevo.
        self.assertFalse(any(rule['isBlocking'] for rule in parts['BOM']['rules']
                             if rule['criterion']['type'] == 'isValueInRange'))

    def test_versions_keep_the_action_that_made_them(self):
        document = self._document()
        version = document.construction_version_before('Antes de importar otra hoja.xlsx')
        document.construction_version_before('Antes de copiar el piso 2')
        versions = document.construction_versions()
        self.assertEqual([item['reason'] for item in versions],
                         ['Antes de copiar el piso 2', 'Antes de importar otra hoja.xlsx'])
        self.assertEqual(versions[1]['version'], version)
        self.assertTrue(versions[0]['date'])


@tagged('post_install', '-at_install')
class TestPackage117Delivery1Tour(HttpCase):

    def test_control_after_send(self):
        site = self.env['project.project'].create({
            'name': 'Obra enviada (test 1.17)', 'is_construction_site': True,
            'construction_spreadsheet_rows': 10})
        site.action_construction_open_spreadsheet()
        document = self.env['documents.document'].search(
            [('construction_project_id', '=', site.id)])
        document.write({'construction_sheet_state': 'sent',
                        'construction_send_date': fields.Datetime.now(),
                        'construction_control_date': False})
        self.assertTrue(document._get_spreadsheet_metadata()['construction_control_pending'])
        self.start_tour('/odoo', 'al_construction_furniture_control_pending', login='admin')
        self.assertTrue(document.construction_control_date)
