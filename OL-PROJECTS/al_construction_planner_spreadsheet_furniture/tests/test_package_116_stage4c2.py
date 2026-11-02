# -*- coding: utf-8 -*-
"""Paquete 1.16, etapa 4, bloque 4c (segunda parte): el panel Planificación.

* M113-08: ayuda de columnas para el panel, enlaces a Odoo y una versión
  guardada antes de cada acción.
* M113-06, punto 7: MATERIALES OBRA, primero en la lista de su categoría.
* Hojas ya creadas: «Actualizar a la plantilla vigente» las rehace con
  INICIO, FICHA, PROGRAMA y CONTROL y sus datos.

El recorrido usa el panel en el navegador: agrupa ARBOL por piso, copia el
piso 2 a los pisos 3 y 4, numera los ambientes repetidos, asigna una
tipología, crea una variante y reemplaza un material.
"""
import json

from odoo.tests import HttpCase, tagged

from odoo.addons.al_construction_planner_furniture.wizards.master_import_layout import SHEETS

from ..models.project_project import WORK_MATERIALS_SHEET
from .test_package_116_stage4c import _book, _rows
from .test_worksheet_v18 import TestWorksheetV18


@tagged('post_install', '-at_install')
class TestPackage116Stage4c2Sheet(TestWorksheetV18):

    def _document(self):
        self.site.action_construction_open_spreadsheet()
        return self.env['documents.document'].search(
            [('construction_project_id', '=', self.site.id),
             ('construction_source_id', '=', False)])

    def test_work_materials_first_in_lists(self):
        data = self.site._construction_spreadsheet_data(rows=12)
        sheets = {sheet['name']: sheet for sheet in data['sheets']}
        materials = sheets[WORK_MATERIALS_SHEET]
        self.assertEqual(materials['cells']['A1'], 'Material')
        self.assertIn('XLOOKUP(C2,REFERENCIAS!$K$3', materials['cells']['B2'])
        self.assertEqual(materials['dataValidationRules'][0]['criterion']['type'],
                         'isValueInRange')
        lists = sheets['_LISTAS']['cells']
        layout = self.site._construction_sheet_layout()
        first_short = layout['n_groups'] + 1
        formula = lists['B%s' % first_short]
        self.assertIn("UNIQUE(VSTACK(IFERROR(FILTER('MATERIALES OBRA'!$A$2:$A$31", formula)
        self.assertEqual(formula.count('('), formula.count(')'))
        # Las listas por grupo no cambian.
        self.assertNotIn('MATERIALES OBRA', lists['B1'])

    def test_short_sheets_capacity(self):
        """Rendimiento: TIPOLOGIAS y ACTIVIDADES no llevan fórmulas en todas
        las filas de una hoja grande; BOM sí."""
        data = self.site._construction_spreadsheet_data(rows=2500)
        layout = self.site._construction_sheet_layout()
        sheets = {sheet['name']: sheet['cells'] for sheet in data['sheets']}

        def calc(name, row):
            letter = next(iter(layout['sheets'][name]['calc_letters'].values()))
            return '%s%s' % (letter, row) in sheets[name]

        self.assertTrue(calc('TIPOLOGIAS', 501))
        self.assertFalse(calc('TIPOLOGIAS', 502))
        self.assertTrue(calc('ACTIVIDADES', 2001))
        self.assertFalse(calc('ACTIVIDADES', 2002))
        self.assertTrue(calc('BOM', 2501))
        # La ampliación tampoco las pasa del tope.
        parts = self.site._construction_row_parts(layout, 2502, 3001)
        self.assertFalse(parts['TIPOLOGIAS']['cells'])
        self.assertTrue(parts['BOM']['cells'])

    def test_panel_metadata_version_and_links(self):
        document = self._document()
        metadata = document._get_spreadsheet_metadata()
        help_by_sheet = metadata['construction_column_help']
        self.assertEqual(help_by_sheet['ARBOL']['floor'][0], 'Piso')
        self.assertTrue(help_by_sheet['ARBOL']['floor'][2], 'obligatoria')
        self.assertIn('Cocina', help_by_sheet['TIPOLOGIAS']['family'][3])
        self.assertIn('calculada', help_by_sheet['ARBOL']['Piso (calc.)'][1])
        version = document.construction_version
        self.assertEqual(document.construction_version_before('Antes de copiar el piso 2'),
                         version)
        self.assertEqual(document.construction_version, version + 1)
        copy = self.env['documents.document'].search(
            [('construction_source_id', '=', document.id)])
        self.assertEqual(copy.construction_version, version)
        action = document.construction_open_link('project')
        self.assertEqual((action['res_model'], action['res_id']),
                         ('project.project', self.site.id))

    def test_upgrade_an_existing_sheet(self):
        """Una hoja anterior (sin INICIO, con el código del producto como dato
        y una columna propia) pasa a la plantilla vigente con sus datos."""
        document = self._document()
        old_bom = [['Tipología', 'Código del producto', 'Cantidad', 'Mi nota'],
                   ['COCINA 04', 'T18H-MEL', 2, 'revisar canto']]
        old_tree = [['Piso', 'Departamento', 'Ambiente', 'Tipología', 'Piso (calc.)'],
                    ['Piso 2', '201', 'Cocina', 'COCINA 04', 'Piso 2'],
                    ['Piso 2', '201', 'Closet', '', 'Piso 2']]
        payload = {
            'master': {
                'BOM': {'rows': old_bom, 'keys': {}, 'formula_cols': []},
                'ARBOL': {'rows': old_tree, 'keys': {'floor': 0, 'apartment': 1, 'space': 2},
                          'formula_cols': [4]},
            },
            'other': {
                'FUENTES': {'cells': {'A1': 'Piso', 'B1': 'Muebles', 'A2': 'Piso 2', 'B2': '2'}},
                'INICIO': {'cells': {'A1': 'vieja'}},
            },
        }
        version = document.construction_version
        action = document.construction_sheet_upgrade(payload)
        self.assertEqual(action['params']['spreadsheet_id'], document.id)
        self.assertEqual(document.construction_version, version + 1, 'versión guardada antes')
        data = json.loads(document.spreadsheet_data)
        sheets = {sheet['name']: sheet for sheet in data['sheets']}
        for name in ('INICIO', 'FICHA', 'PROGRAMA', 'CONTROL', WORK_MATERIALS_SHEET, 'FUENTES'):
            self.assertIn(name, sheets)
        self.assertNotEqual(sheets['INICIO']['cells'].get('A1'), 'vieja')
        layout = self.site._construction_sheet_layout()
        bom = layout['sheets']['BOM']['letters']
        cells = sheets['BOM']['cells']
        self.assertEqual(cells['%s2' % bom['typology']], 'COCINA 04')
        # El código pasa a «Producto»; la columna de código sigue siendo fórmula.
        self.assertEqual(cells['%s2' % bom['product_name']], 'T18H-MEL')
        self.assertTrue(cells['%s2' % bom['product_code']].startswith('=IF('))
        self.assertEqual(cells['%s2' % bom['qty']], '2')
        extra = '%s1' % self._letter(len(layout['sheets']['BOM']['headers']))
        self.assertEqual(cells[extra], 'Mi nota')
        tree = layout['sheets']['ARBOL']['letters']
        cells = sheets['ARBOL']['cells']
        self.assertEqual(cells['%s3' % tree['space']], 'Closet')
        self.assertEqual(cells['%s2' % tree['typology']], 'COCINA 04')
        self.assertEqual(sheets['FUENTES']['cells']['B2'], '2')
        self.assertFalse(self.env['spreadsheet.revision'].search_count(
            [('res_model', '=', 'documents.document'), ('res_id', '=', document.id)]))
        self.assertGreaterEqual(document.construction_sheet_rows, 10)

    @staticmethod
    def _letter(index):
        letters = ''
        index += 1
        while index:
            index, rest = divmod(index - 1, 26)
            letters = chr(65 + rest) + letters
        return letters


@tagged('post_install', '-at_install')
class TestPackage116Stage4c2Tour(HttpCase):
    """M113-08 en el navegador: panel, acciones y clic derecho."""

    def test_planning_panel(self):
        category = self.env['product.category'].create({'name': 'T4C2 TABLEROS'})
        Product = self.env['product.product']
        Product.create({'name': 'Tablero blanco 4c2 (test)', 'default_code': 'T4C2-BLA',
                        'type': 'consu', 'categ_id': category.id, 'standard_price': 100.0})
        Product.create({'name': 'Tablero roble 4c2 (test)', 'default_code': 'T4C2-ROB',
                        'type': 'consu', 'categ_id': category.id, 'standard_price': 150.0})
        site = self.env['project.project'].create({
            'name': 'Obra panel de planificación (test)', 'is_construction_site': True,
            'construction_spreadsheet_rows': 20})
        sheets = {
            'TIPOLOGIAS': _rows('TIPOLOGIAS', [
                {'code': 'C01', 'name': 'Cocina 01', 'family': 'Cocina'},
                {'code': 'CL01', 'name': 'Closet 01', 'family': 'Closet'}]),
            'MODULOS': _rows('MODULOS', [
                {'typology': 'C01', 'code': 'MB01', 'type': 'Bajo', 'width': 600,
                 'ml_group': 'Mueble bajo', 'name': 'MOD BAJO 600'}]),
            'BOM': _rows('BOM', [{'typology': 'C01', 'module': 'MB01',
                                  'product_code': 'T4C2-BLA', 'qty': 2,
                                  'stage': 'Producción'}]),
            'ARBOL': _rows('ARBOL', [
                {'floor': 'Piso 2', 'apartment': '201', 'space': 'Cocina', 'typology': 'C01'},
                {'floor': 'Piso 2', 'apartment': '201', 'space': 'Closet'},
                {'floor': 'Piso 2', 'apartment': '201', 'space': 'Closet'},
                {'floor': 'Piso 2', 'apartment': '202', 'space': 'Cocina', 'typology': 'C01'}]),
        }
        self.assertEqual(list(sheets['ARBOL'][0][:4]),
                         [h for _k, h, _r, _x in SHEETS['ARBOL'][1]][:4])
        site.action_construction_open_spreadsheet()
        document = self.env['documents.document'].search(
            [('construction_project_id', '=', site.id)])
        self.env['ir.attachment'].create({'name': 'al_sheet_panel_tour.xlsx',
                                          'raw': _book(sheets)})
        version = document.construction_version
        self.start_tour('/odoo', 'al_construction_furniture_panel', login='admin')
        # Una versión por acción: copiar, numerar, asignar, variante, material.
        self.assertGreaterEqual(document.construction_version, version + 5)
        commands = json.dumps([json.loads(revision.commands) for revision in self.env[
            'spreadsheet.revision'].search([('res_model', '=', 'documents.document'),
                                            ('res_id', '=', document.id)])])
        self.assertIn('C01A', commands)
        self.assertIn('T4C2-ROB', commands)
