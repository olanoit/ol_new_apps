# -*- coding: utf-8 -*-
"""Paquete 1.16, etapa 4, bloque 4b: cargar la obra desde la hoja.

* M113-06: grupo › categoría › producto; _LISTAS con una fila por grupo y por
  categoría (los FILTER no crecen con las filas); raíz de materiales en
  Ajustes; unidad y costo del maestro a la vista; marcas rojo y ámbar.
* M113-05: las filas de la hoja en la ficha (0 = automático) y la ampliación
  de una hoja abierta con las mismas fórmulas y listas.
* M113-04: «Importar Excel a la hoja»: revisión, producto «nombre · unidad ·
  código», códigos nuevos a PRODUCTOS NUEVOS, columnas y pestañas extra,
  versión antes de escribir y mensaje en la obra; en el navegador, la hoja
  escribe el archivo y amplía sus filas.
"""
import base64
import json
from io import BytesIO

from odoo.tests import HttpCase, tagged

from odoo.addons.al_construction_planner_furniture.wizards.master_import_layout import SHEETS

from ..models.project_project import LISTS_SHEET, category_parts
from .test_worksheet_v18 import TestWorksheetV18


def _book(sheets):
    """Libro .xlsx (base64) con ``{pestaña: filas}``."""
    from openpyxl import Workbook
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        worksheet = workbook.create_sheet(name)
        for row in rows:
            worksheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return base64.b64encode(output.getvalue())


def _headers(name):
    return [header for _k, header, _r, _h in SHEETS[name][1]]


def _row(sheet, **values):
    return [values.get(key) for key, _h, _r, _x in SHEETS[sheet][1]]


@tagged('post_install', '-at_install')
class TestPackage116Stage4bSheet(TestWorksheetV18):

    def _document(self):
        self.site.action_construction_open_spreadsheet()
        return self.env['documents.document'].search(
            [('construction_project_id', '=', self.site.id),
             ('construction_source_id', '=', False)])

    def test_category_parts(self):
        self.assertEqual(category_parts('01 MATERIA PRIMA / ACCESORIOS / OTROS'),
                         ('ACCESORIOS', 'ACCESORIOS / OTROS', 'OTROS'))
        self.assertEqual(category_parts('TABLEROS / MELAMINA'),
                         ('MELAMINA', 'MELAMINA', 'MELAMINA'))
        self.assertEqual(category_parts('Varios'), ('Varios', 'Varios', 'Varios'))

    def test_material_lists(self):
        Category = self.env['product.category']
        root = Category.create({'name': 'MP TEST4B'})
        group = Category.create({'name': 'ACCESORIOS', 'parent_id': root.id})
        others = Category.create({'name': 'OTROS', 'parent_id': group.id})
        self.env['product.product'].create({'name': 'Tarugo 8 mm (test 4b)',
                                            'default_code': 'T4B-TAR', 'type': 'consu',
                                            'categ_id': others.id})
        (self.site.company_id or self.env.company).construction_sheet_material_categ_id = root
        groups, shorts = self.site._construction_material_categories()
        self.assertEqual(set(groups), {'ACCESORIOS'})
        self.assertEqual(set(shorts), {'ACCESORIOS / OTROS'})
        data = self.site._construction_spreadsheet_data(rows=400)
        sheets = {sheet['name']: sheet for sheet in data['sheets']}
        bom = sheets['BOM']['cells']
        headers = [bom.get('%s1' % chr(65 + i)) for i in range(20)]
        self.assertLess(headers.index('Grupo de categoría'), headers.index('Categoría'))
        self.assertIn('Unidad del producto (calc.)', headers)
        self.assertIn('Costo unitario (calc.)', headers)
        lists = sheets[LISTS_SHEET]['cells']
        filters = [cell for cell in lists.values() if 'FILTER(' in cell]
        layout = self.site._construction_sheet_layout()
        # Grupos, categorías y el bloque de módulos por tipología (M117-02).
        self.assertEqual(len(filters), layout['finish_base'])
        self.assertLess(len(filters), 600, 'no crecen con las filas')
        # Con la raíz, REFERENCIAS marca solo lo que cuelga de ella.
        self.assertIn('MP TEST4B / ', sheets['REFERENCIAS']['cells']['S3'])
        # Cada fila tiene su lista de categorías y de productos.
        rules = sheets['BOM']['dataValidationRules']
        self.assertEqual(len([r for r in rules if '_categ_' in r['id']]), 400)
        self.assertEqual(len([r for r in rules if '_prod_' in r['id']]), 400)
        self.assertTrue(all('zone' not in rule for rule in rules))
        marks = sheets['BOM']['conditionalFormats']
        self.assertEqual({cf['rule']['style']['fillColor'] for cf in marks},
                         {'#F6E1E4', '#FCE5CD', '#F4F2EF'})

    def test_rows_and_extension(self):
        self.assertEqual(self.site.construction_spreadsheet_rows, 0, 'automático')
        self.site.construction_spreadsheet_rows = 20
        document = self._document()
        self.assertEqual(document.construction_sheet_rows, 20)
        self.assertEqual(document._get_spreadsheet_metadata()['construction_sheet_rows'], 20)
        extension = document.construction_sheet_extension(30)
        self.assertEqual(extension['rows'], 30)
        self.assertEqual(document.construction_sheet_rows, 30)
        bom = extension['sheets']['BOM']
        rows = {int(''.join(c for c in ref if c.isdigit())) for ref in bom['cells']}
        self.assertEqual(min(rows), 22)
        self.assertEqual(max(rows), 31)
        layout = self.site._construction_sheet_layout()
        helper = self.site._construction_helper_row(layout, 'BOM', 'prod', 22)
        self.assertIn('A%s' % helper, extension['sheets'][LISTS_SHEET]['cells'])
        self.assertTrue(all(rule['zone']['top'] >= 21 for rule in bom['rules']))
        self.assertEqual(set(extension['pivots'].values()), {30})
        self.assertFalse(document.construction_sheet_extension(25), 'ya tiene esas filas')

    def _import_file(self):
        bom_headers = _headers('BOM') + ['Fuente']
        bom = [bom_headers,
               _row('BOM', typology='COCINA 04', module='MB01', product_code='T18H-MEL',
                    qty=0.5, stage='Producción') + ['OT 12'],
               _row('BOM', typology='COCINA 04', module='MB01', product_code='T4B-NUEVO',
                    product_name='Tirador aluminio 128 (test 4b)', qty=2,
                    stage='1.2 Armado') + ['OT 13']]
        return _book({
            'LEEME': [['No se copia']],
            'TIPOLOGIAS': [_headers('TIPOLOGIAS'),
                           _row('TIPOLOGIAS', code='COCINA 04', name='Cocina 04',
                                family='Cocina')],
            'BOM': bom,
            'FUENTES': [['Origen', 'Filas'], ['Proyección OT', 2]],
        })

    def test_import_wizard(self):
        document = self._document()
        wizard = self.env['construction.spreadsheet.import.wizard'].create({
            'document_id': document.id, 'file': self._import_file(),
            'filename': 'carga 4b.xlsx'})
        self.assertIn('Columnas reconocidas', wizard.review_html)
        self.assertIn('FUENTES', wizard.review_html)
        self.assertEqual(wizard.action_review()['res_id'], wizard.id)
        result = wizard.action_import()
        self.assertEqual(result['type'], 'ir.actions.act_window_close')
        payload = result['infos']['construction_sheet_import']
        bom = payload['sheets']['BOM']
        rows = [dict(zip(bom['keys'], row)) for row in bom['rows']]
        unit = self.white.uom_id.name
        self.assertEqual(rows[0]['product_name'],
                         'Tablero melamínico blanco (test v18h) · %s · T18H-MEL' % unit)
        self.assertEqual(rows[0]['categ'], 'TEST18 TABLEROS')
        self.assertEqual(rows[1]['product_name'], 'T4B-NUEVO')
        self.assertEqual(bom['extra_headers'], ['Fuente'])
        self.assertEqual(bom['extra_rows'][1], ['OT 13'])
        new = payload['sheets']['PRODUCTOS NUEVOS']
        self.assertEqual([dict(zip(new['keys'], row)) for row in new['rows']],
                         [{'code': 'T4B-NUEVO', 'name': 'Tirador aluminio 128 (test 4b)'}])
        self.assertEqual(payload['added_products'], 1)
        self.assertEqual(list(payload['other']), ['FUENTES'])
        # Versión guardada antes de escribir.
        self.assertEqual(self.env['documents.document'].search_count(
            [('construction_source_id', '=', document.id)]), 1)
        document.construction_sheet_import_done('carga 4b.xlsx', 3, 0, 2)
        self.assertIn('carga 4b.xlsx', self.site.message_ids[0].body)


@tagged('post_install', '-at_install')
class TestPackage116Stage4bTour(HttpCase):
    """M113-04/05 en el navegador: el asistente escribe el archivo en la hoja
    y la amplía (de 10 a 15 filas de datos) con sus fórmulas y listas."""

    def test_import_excel_to_sheet(self):
        site = self.env['project.project'].create({
            'name': 'Obra importar Excel (test)', 'is_construction_site': True,
            'construction_spreadsheet_rows': 10})
        site.action_construction_open_spreadsheet()
        document = self.env['documents.document'].search(
            [('construction_project_id', '=', site.id)])
        rows = [_row('ARBOL', floor='Piso %02d' % (n // 4 + 2), apartment='Dpto %s' % n,
                     space='Cocina') for n in range(15)]
        typology = _row('TIPOLOGIAS', code='COCINA 04', name='Cocina 04', family='Cocina')
        self.env['ir.attachment'].create({
            'name': 'al_sheet_import_tour.xlsx',
            'datas': _book({
                'ARBOL': [_headers('ARBOL')] + rows,
                'TIPOLOGIAS': [_headers('TIPOLOGIAS'), typology],
                # Paquete 1.17, M117-03: el libro viene de otra hoja de trabajo.
                'INICIO': [['OBRA DE OTRA HOJA']],
                '_LISTAS': [['LISTA DE OTRA HOJA']],
                'FUENTES': [['Origen'], ['Proyección OT']],
            }),
        })
        self.start_tour('/odoo', 'al_construction_furniture_sheet_import', login='admin')
        # 15 filas y una de resumen por cada uno de los 4 pisos, más el 10 %.
        self.assertEqual(document.construction_sheet_rows, 21)
        commands = [command for revision in self.env['spreadsheet.revision'].search(
            [('res_model', '=', 'documents.document'), ('res_id', '=', document.id)])
            for command in json.loads(revision.commands).get('commands', [])]
        types = {command['type'] for command in commands}
        self.assertIn('ADD_DATA_VALIDATION_RULE', types)
        self.assertIn('Dpto 14', json.dumps(commands, ensure_ascii=False),
                      sorted(types))
        self.assertIn('Excel importado a la hoja', ''.join(site.message_ids.mapped('body')))
        # Restaurar deja la hoja vinculada a su obra y guarda antes la de hoy.
        self.assertEqual(document.construction_project_id, site)
        self.assertEqual(self.env['documents.document'].search_count(
            [('construction_source_id', '=', document.id)]), 2)
