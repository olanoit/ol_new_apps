# -*- coding: utf-8 -*-
"""Paquete 1.17, entrega 2.

- M117-01 y M117-23: diseño de la hoja de planificación.
- M117-02: orden de BOM y PIEZAS, módulo según la tipología y etapa por defecto.
- M117-07: «Traer de Odoo» sin residuos de redondeo.
- M117-09: obras sin plan en Inicio.
"""
import json

from odoo import Command
from odoo.tests import tagged

from ..models import sheet_design as design
from .test_worksheet_v18 import TestWorksheetV18


@tagged('post_install', '-at_install')
class TestPackage117Delivery2(TestWorksheetV18):

    def _data(self, rows=10):
        return self.site._construction_spreadsheet_data(rows)

    def _sheet(self, data, name):
        return next(sheet for sheet in data['sheets'] if sheet['name'] == name)

    def _document(self):
        self.site.action_construction_open_spreadsheet()
        return self.env['documents.document'].search(
            [('construction_project_id', '=', self.site.id),
             ('construction_source_id', '=', False)])

    def test_bom_and_pieces_order(self):
        data = self._data()
        bom = self._sheet(data, 'BOM')['cells']
        self.assertEqual([bom['%s1' % letter] for letter in 'ABCDEFGHIJ'], [
            'Tipología', 'Módulo', 'Grupo de categoría', 'Categoría', 'Producto', 'Cantidad',
            'Etapa de consumo', 'Unidad', 'Costo unitario', 'Código del producto'])
        self.assertEqual(bom['O1'], 'Etapa usada (calc.)')
        # El código calculado lee «Producto» en su nueva columna.
        self.assertIn('E2', bom['J2'])
        pieces = self._sheet(data, 'PIEZAS')['cells']
        self.assertEqual([pieces['%s1' % letter] for letter in 'ABCDE'], [
            'Tipología', 'Módulo', 'Grupo de categoría', 'Categoría', 'Producto'])
        keys = self._sheet(data, '_CLAVES')['cells']
        self.assertIn('product_code', keys.values())

    def test_data_and_formula_fill_every_row(self):
        data = self._data()
        self.assertEqual(data['styles'][str(self._style(data, 'data'))]['fillColor'],
                         design.CELL_DATA_COLOR)
        bom = self._sheet(data, 'BOM')
        self.assertEqual(bom['styles']['A2:A11'], self._style(data, 'data'))
        self.assertEqual(bom['styles']['J2:J11'], self._style(data, 'calc'))
        self.assertEqual(data['styles'][str(bom['styles']['A1'])]['fillColor'],
                         design.HEADER_DATA_COLOR)
        self.assertEqual(data['styles'][str(bom['styles']['J1'])]['fillColor'],
                         design.HEADER_CALC_COLOR)
        for name, freeze in (('BOM', 5), ('PIEZAS', 5), ('MODULOS', 3), ('ARBOL', 4),
                             ('TIPOLOGIAS', 2)):
            self.assertEqual(self._sheet(data, name)['panes']['xSplit'], freeze, name)
        self.assertEqual(bom['cols']['4']['size'], 395)
        self.assertEqual(bom['rows']['0']['size'], design.HEADER_HEIGHT)

    @staticmethod
    def _style(data, kind):
        target = design.CELL_CALC if kind == 'calc' else design.CELL_DATA
        return next(int(key) for key, style in data['styles'].items() if style == target)

    def test_native_tables(self):
        data = self._data()
        self.assertIn(design.TABLE_STYLE_ID, data['customTableStyles'])
        bom = self._sheet(data, 'BOM')['tables'][0]
        self.assertEqual(bom['range'], 'A1:O11')
        self.assertTrue(bom['config']['hasFilters'])
        self.assertFalse(bom['config']['bandedRows'])
        self.assertFalse(self._sheet(data, 'ARBOL')['tables'][0]['config']['hasFilters'])
        self.assertEqual(self._sheet(data, 'OBRA')['tables'], [])

    def test_tab_order_and_color(self):
        data = self._data()
        names = [sheet['name'] for sheet in data['sheets']]
        self.assertEqual(names[:6], ['INICIO', 'LEEME', 'OBRA', 'PARAMETROS', 'ACABADOS DE OBRA',
                                     'TIPOLOGIAS'])
        self.assertLess(names.index('MATERIALES OBRA'), names.index('FICHA'))
        self.assertEqual(self._sheet(data, 'BOM')['color'], design.TAB_PLANNING_DATA)
        self.assertEqual(self._sheet(data, 'FICHA')['color'], design.TAB_ANALYSIS)
        # El libro se puede abrir: JSON válido con todo lo anterior.
        self.assertTrue(json.dumps(data))

    def test_module_list_follows_the_typology(self):
        layout = self.site._construction_sheet_layout()
        parts = self.site._construction_row_parts(layout, 2, 5)
        rule = next(rule for rule in parts['BOM']['rules'] if rule['id'] == 'BOM_mod_3')
        helper = self.site._construction_helper_row(layout, 'BOM', 'mod', 3)
        self.assertEqual(rule['ranges'], ['B3'])
        self.assertIn('$A$%s' % helper, rule['criterion']['values'][0])
        formula = parts['_LISTAS']['cells']['A%s' % helper]
        self.assertIn('BOM!A3', formula)
        self.assertEqual(self.site._construction_helper_row(layout, 'BOM', 'mod', 4) - helper, 6)

    def test_extension_carries_format_and_marks(self):
        document = self._document()
        current = document.construction_sheet_rows
        extension = document.construction_sheet_extension(current + 10)
        bom = extension['sheets']['BOM']
        self.assertEqual(bom['table_bottom'], current + 10)
        first = bom['formatting'][0]
        self.assertEqual(first['zone']['bottom'], current + 10)
        self.assertEqual(first['style'], design.CELL_DATA)
        self.assertTrue(any('unknown' in cf['id'] for cf in bom['conditional']))

    def test_old_sheet_asks_for_the_upgrade_before_growing(self):
        document = self._document()
        document.construction_sheet_layout = 0
        rows = document.construction_sheet_rows
        self.assertEqual(document.construction_sheet_extension(rows + 10),
                         {'needs_upgrade': True})
        self.assertEqual(document.construction_sheet_rows, rows)

    def test_upgrade_moves_the_columns_by_key(self):
        document = self._document()
        document.construction_sheet_layout = 0
        old = [['Tipología', 'Código del producto', 'Producto', 'Cantidad', 'Unidad',
                'Etapa de consumo', 'Costo unitario', 'Módulo', 'Grupo de categoría',
                'Categoría'],
               ['C01', 'X1', 'Tablero · Unidad · X1', 2, '', '', '', 'MB01', 'PRINCIPAL',
                'PRINCIPAL / TABLEROS']]
        document.construction_sheet_upgrade({'master': {'BOM': {
            'rows': old, 'keys': {'typology': 0, 'product_code': 1, 'product_name': 2, 'qty': 3,
                                  'uom': 4, 'stage': 5, 'cost': 6, 'module': 7,
                                  'categ_group': 8, 'categ': 9},
            'formula_cols': [1]}}, 'other': {}})
        self.assertEqual(document.construction_sheet_layout, design_layout())
        data = json.loads(document.with_context(bin_size=False).spreadsheet_data)
        cells = self._sheet(data, 'BOM')['cells']
        self.assertEqual((cells['A2'], cells['B2'], cells['C2'], cells['E2'], cells['F2']),
                         ('C01', 'MB01', 'PRINCIPAL', 'Tablero · Unidad · X1', '2'))

    def test_default_stage_of_the_category(self):
        parent = self.env['product.category'].create({'name': 'Materiales 1.17 (test)'})
        child = self.env['product.category'].create(
            {'name': 'Bisagras (test)', 'parent_id': parent.id})
        stage = self.env['construction.stage'].search([], limit=1)
        product = self.env['product.product'].create(
            {'name': 'Bisagra 1.17 (test)', 'categ_id': child.id})
        self.assertFalse(product.construction_default_stage_label)
        parent.construction_default_stage_id = stage
        product.invalidate_recordset()
        self.assertEqual(product.construction_default_stage_label, stage._label())
        self.assertEqual(child._construction_default_stage(), stage)

    def test_home_lists_works_without_plan(self):
        home = self.env['construction.planner.home']
        project = self.env['project.project'].create(
            {'name': 'Obra por planificar (test 1.17)', 'is_construction_site': True})
        row = next(item for item in home.get_home_data()['unplanned']
                   if item['project_id'] == project.id)
        self.assertEqual(row['sheet_state'], 'Sin hoja')
        self.assertEqual(row['actions'], [{'label': 'Crear hoja',
                                           'method': 'action_construction_open_spreadsheet'}])
        project.action_construction_open_spreadsheet()
        project.invalidate_recordset()
        row = next(item for item in home.get_home_data()['unplanned']
                   if item['project_id'] == project.id)
        self.assertEqual(row['actions'][0]['label'], 'Abrir hoja')
        self.assertEqual(row['sheet_state'], 'Borrador')
        self.env['construction.resource.plan'].create({'project_id': project.id})
        self.assertNotIn(project.id, [item['project_id']
                                      for item in home.get_home_data()['unplanned']])

    def test_odoo_rows_without_rounding_residue(self):
        """Una tipología con recetas por módulo no escribe la diferencia de la
        receta de la tipología como una línea sin módulo."""
        document = self._document()
        typology = self.env['construction.typology'].create(
            {'project_id': self.site.id, 'code': 'C117', 'name': 'Cocina 1.17'})
        module = self.env['construction.typology.module'].create(
            {'typology_id': typology.id, 'code': 'MB117', 'module_type': 'low'})
        product = self.env['product.product'].create({'name': 'Canto 1.17 (test)',
                                                      'default_code': 'C117M'})
        self.env['construction.typology.module.material'].create({
            'module_id': module.id, 'product_id': product.id, 'qty': 1.004,
            'uom_id': product.uom_id.id})
        typology.bom_id = self.env['mrp.bom'].sudo().create({
            'product_tmpl_id': self.env['product.template'].create(
                {'name': 'Cocina 1.17 (test)'}).id,
            'bom_line_ids': [Command.create({'product_id': product.id, 'product_qty': 1.01})]})
        bom = document.construction_furniture_odoo_rows()['sheets']['BOM']
        rows = [dict(zip(bom['keys'], row)) for row in bom['rows']
                if dict(zip(bom['keys'], row))['typology'] == 'C117']
        self.assertEqual([row['module'] for row in rows], ['MB117'])


def design_layout():
    from odoo.addons.al_construction_planner_spreadsheet.models.project_project import (
        FURNITURE_LAYOUT,
    )
    return FURNITURE_LAYOUT
