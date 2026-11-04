# -*- coding: utf-8 -*-
"""Paquete 1.16, etapa 4, bloque 4a: maestro de mobiliario.

* El tipo de hoja sale del perfil: una obra PROF 4 abre el presupuesto.
* M116-09: amarillo el dato, gris la fórmula; el producto se elige como
  «nombre · unidad · código»; las columnas se leen por su clave (_CLAVES).
* M113-01: lo que se perdía en silencio se avisa en el asistente y es error
  en «Validar» (módulo inexistente, tablero inexistente, agrupador sin nivel y
  BOM sin módulo en una tipología con recetas); la fecha de OBRA como número
  de serie de la hoja se lee.
* M113-02: el envío lee solo las pestañas del maestro.
"""
import re
from datetime import date

from odoo.tests import HttpCase, tagged

from odoo.addons.al_construction_planner_furniture.wizards.master_import_layout import SHEETS
from odoo.addons.al_construction_planner_spreadsheet.models.sheet_keys import KEYS_SHEET

from .test_worksheet_v18 import TestWorksheetV18, _rows


@tagged('post_install', '-at_install')
class TestPackage116Stage4Furniture(TestWorksheetV18):

    def _document(self):
        self.site.action_construction_open_spreadsheet()
        return self.env['documents.document'].search(
            [('construction_project_id', '=', self.site.id)])

    def test_sheet_kind_and_template(self):
        furniture = self.env.ref('al_construction_planner.profile_furniture')
        self.assertEqual(furniture.construction_spreadsheet_kind, 'furniture')
        self.assertEqual(self.site._construction_spreadsheet_kind(), 'furniture')
        deep = self.env['construction.vertical.profile'].search(
            [('code', '=', 'construction_prof4')], limit=1)
        works = self.env['project.project'].create({
            'name': 'Obra PROF 4 con los dos puentes (test)', 'is_construction_site': True,
            'construction_profile_id': deep.id})
        self.assertEqual(works._construction_spreadsheet_kind(), 'budget')

        data = self.site._construction_spreadsheet_data()
        sheets = {sheet['name']: sheet for sheet in data['sheets']}
        styles = data['styles']
        bom = sheets['BOM']
        headers = {content: ref for ref, content in bom['cells'].items()
                   if re.fullmatch(r'[A-Z]+1', ref)}
        code_ref = headers['Código del producto']
        self.assertEqual(styles[str(bom['styles'][code_ref])]['fillColor'], '#E6E2DD')
        self.assertEqual(styles[str(bom['styles'][headers['Cantidad']])]['fillColor'],
                         '#FFDC00')
        self.assertNotIn('#E8F0E0', str(styles))
        # El código se lee del final de «nombre · unidad · código».
        self.assertIn('TEXTAFTER', bom['cells'][code_ref[:-1] + '2'])
        self.assertIn('" · "', sheets['REFERENCIAS']['cells']['P3'])
        self.assertTrue(any('$P$3' in cell for cell in sheets['_LISTAS']['cells'].values()))
        keys = sheets[KEYS_SHEET]['cells']
        self.assertIn('=COLUMN(%s!%s)' % ('BOM', code_ref), keys.values())
        self.assertIn("=COLUMN('PRODUCTOS NUEVOS'!A1)", keys.values())
        # M113-02: el envío pide solo las pestañas del maestro.
        names = self._document()._get_spreadsheet_metadata()['construction_send_sheets']
        self.assertEqual(set(names), set(SHEETS) | {KEYS_SHEET, 'PARAMETROS', 'VENDIDO', 'ACABADOS DE OBRA'})

    def _bad_sheets(self):
        sheets = self._sheets()
        bom = sheets['BOM']
        header = bom[0]
        keys = [key for key, _h, _r, _x in SHEETS['BOM'][1]]

        def bom_row(**values):
            return [values.get(key, '') for key in keys]
        # Caso 1: un módulo que no está en MODULOS.
        bom.append(bom_row(typology='COCINA 04', module='MB99', product_code='T18H-TOR',
                           qty=10, stage='1.2 Armado'))
        # Caso 5: sin módulo en una tipología con recetas por módulo.
        bom.append(bom_row(typology='COCINA 04', product_code='T18H-TOR', qty=3,
                           stage='1.2 Armado'))
        self.assertEqual(header[0], 'Tipología')
        pieces = sheets['PIEZAS']
        piece_keys = [key for key, _h, _r, _x in SHEETS['PIEZAS'][1]]
        # Caso 2: un tablero que no existe ni está en PRODUCTOS NUEVOS.
        pieces.append([{'typology': 'COCINA 04', 'module': 'MB01', 'qty': 1, 'length': 500,
                        'width': 300, 'piece_type': 'BASE',
                        'product_code': 'NO-EXISTE-TAB'}.get(key, '') for key in piece_keys])
        # Caso 1 en PIEZAS.
        pieces.append([{'typology': 'COCINA 04', 'module': 'MB98', 'qty': 1,
                        'piece_type': 'BASE'}.get(key, '') for key in piece_keys])
        # Caso 3: la fecha de la hoja llega como número de serie.
        sheets['OBRA'] = _rows('OBRA', [{'key': 'Inicio', 'value': 46335},
                                        {'key': 'Fin', 'value': '31-03-2027'},
                                        {'key': 'Cliente', 'value': self.client.name}])
        # Caso 4: agrupador en una obra sin niveles de agrupador.
        arbol_keys = [key for key, _h, _r, _x in SHEETS['ARBOL'][1]]
        sheets['ARBOL'].append([{'group': 'Torre A', 'floor': 'Piso 04', 'apartment': 'Dpto 404',
                                 'space': 'Cocina', 'typology': 'COCINA 04'}.get(key, '')
                                for key in arbol_keys])
        return sheets

    def test_validate_blocks_what_was_lost(self):
        document = self._document()
        sheets = self._bad_sheets()
        result = document.action_construction_validate(sheets)
        errors = [row for row in result['rows'] if row[4] == 'Error']
        messages = ' | '.join(row[3] for row in errors)
        self.assertIn('MB99', messages)
        self.assertIn('MB98', messages)
        self.assertIn('NO-EXISTE-TAB', messages)
        self.assertIn('recetas por módulo', messages)
        group_depth = len(self.site._construction_level_lines().get('group', []))
        if not group_depth:
            self.assertIn('no tiene Torre o Etapa', messages)
        self.assertTrue(all(row[0] and row[1] for row in errors), errors)
        self.assertFalse([row for row in result['rows'] if row[0] == 'OBRA'])
        bad_date = dict(sheets, OBRA=_rows('OBRA', [{'key': 'Fin', 'value': 'pronto'}]))
        self.assertTrue(any(row[0] == 'OBRA' and row[4] == 'Aviso' for row in
                            document.action_construction_validate(bad_date)['rows']))
        self.assertEqual(result['errors'], len(errors))

        # En el asistente directo siguen siendo avisos y se importa lo válido.
        action = document.action_construction_send_to_planner(sheets)
        wizard = self.env['construction.master.import.wizard'].browse(action['res_id'])
        data = wizard._analyze()
        self.assertFalse(data['errors'], data['errors'])
        for key in ('module_unknown', 'piece_product_unknown', 'bom_without_module'):
            self.assertTrue(data['warnings'].get(key), key)
        self.assertEqual(data['stats']['PIEZAS'][1], 2, 'la pieza de MB98 no se cuenta')
        self.assertIn('MB99', wizard.warning_html)
        wizard.action_import()
        typology = self.env['construction.typology'].search([('project_id', '=', self.site.id)])
        self.assertEqual(sorted(typology.module_line_ids.mapped('code')), ['MA01', 'MB01'])
        mb01 = typology.module_line_ids.filtered(lambda m: m.code == 'MB01')
        screws = mb01.material_ids.filtered(lambda m: m.product_id == self.screw)
        self.assertAlmostEqual(sum(screws.mapped('qty')), 25.0,
                               msg='la fila de MB99 no se suma a otro módulo')
        board_less = mb01.piece_ids.filtered(lambda p: not p.product_id)
        self.assertEqual(len(board_less), 1)
        self.assertEqual(self.site.date_start, date(2026, 11, 9))
        self.assertEqual(self.site.date, date(2027, 3, 31))

    def test_special_kind_with_written_class(self):
        sheets = self._sheets()
        keys = [key for key, _h, _r, _x in SHEETS['MODULOS'][1]]
        sheets['MODULOS'].append([{'typology': 'COCINA 04', 'code': 'MA02', 'type': 'Alto',
                                   'width': 600, 'ml_group': 'Mueble alto',
                                   'name': 'MOD ALTO MICROONDAS 600', 'module_class': 'Especial',
                                   }.get(key, '') for key in keys])
        self._send_sheets(sheets)
        module = self.env['construction.typology.module'].search(
            [('typology_id.project_id', '=', self.site.id), ('code', '=', 'MA02')])
        self.assertEqual(module.module_class, 'special')
        self.assertEqual(module.special_kind, 'microwave')

    def test_renamed_header_is_read_by_key(self):
        sheets = self._sheets()
        bom = [list(row) for row in sheets['BOM']]
        position = bom[0].index('Cantidad')
        bom[0][position] = 'Cantidad por cocina (mía)'
        sheets['BOM'] = bom
        sheets[KEYS_SHEET] = [['Pestaña', 'Clave', 'Columna'], ['BOM', 'qty', position + 1]]
        self._send_sheets(sheets)
        typology = self.env['construction.typology'].search([('project_id', '=', self.site.id)])
        mb01 = typology.module_line_ids.filtered(lambda m: m.code == 'MB01')
        self.assertAlmostEqual(sum(mb01.material_ids.filtered(
            lambda m: m.product_id == self.screw).mapped('qty')), 25.0)

    def _send_sheets(self, sheets):
        document = self._document()
        action = document.action_construction_send_to_planner(sheets)
        wizard = self.env['construction.master.import.wizard'].browse(action['res_id'])
        data = wizard._analyze()
        self.assertFalse(data['errors'], data['errors'])
        wizard.action_import()
        return data


# Las pruebas heredadas ya corren en su clase.
for _name in dir(TestWorksheetV18):
    if _name.startswith('test_') and callable(getattr(TestWorksheetV18, _name)) \
            and _name not in vars(TestPackage116Stage4Furniture):
        setattr(TestPackage116Stage4Furniture, _name, None)


@tagged('post_install', '-at_install')
class TestPackage116Stage4FurnitureTour(HttpCase):
    """M113-03 en el navegador: menú propio del maestro y «Validar»."""

    def test_furniture_sheet_menu(self):
        site = self.env['project.project'].create({'name': 'Obra hoja recorrido (test)',
                                                   'is_construction_site': True})
        site.action_construction_open_spreadsheet()
        self.start_tour('/odoo', 'al_construction_furniture_sheet_menu', login='admin')
