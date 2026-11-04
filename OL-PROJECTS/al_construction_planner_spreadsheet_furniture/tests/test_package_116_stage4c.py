# -*- coding: utf-8 -*-
"""Paquete 1.16, etapa 4, bloque 4c (primera parte): planificar en la hoja.

* M113-07: INICIO es la primera pestaña, con la ruta de 8 pasos, los
  indicadores, los gráficos y el resumen por piso con filtros.
* M113-09/10/11: FICHA, PROGRAMA y CONTROL con fórmulas; los conteos del
  planificador por piso y «Traer de Odoo» del maestro.
* M113-11/12: estado de la hoja (importada, validada, enviada vN) con la
  versión guardada en cada envío, y la ficha de la obra que lo muestra.

El recorrido evalúa las fórmulas en el navegador: con la obra importada en el
planificador y el mismo libro en la hoja, INICIO da las cifras, FICHA marca la
controversia de ancho, PROGRAMA escribe Inicio y Fin en OBRA y CONTROL
coincide.
"""
import base64
import json
import re
from io import BytesIO

from odoo.tests import Form, HttpCase, tagged

from odoo.addons.al_construction_planner_furniture.wizards.master_import_layout import SHEETS

from ..models.planning_sheets import PLANNING_SHEETS, START_SHEET
from .test_worksheet_v18 import TestWorksheetV18


def _book(sheets):
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


def _rows(name, records):
    columns = SHEETS[name][1]
    return [[h for _k, h, _r, _x in columns]] + [
        [record.get(key) for key, _h, _r, _x in columns] for record in records]


@tagged('post_install', '-at_install')
class TestPackage116Stage4cSheet(TestWorksheetV18):

    def _document(self):
        self.site.action_construction_open_spreadsheet()
        return self.env['documents.document'].search(
            [('construction_project_id', '=', self.site.id),
             ('construction_source_id', '=', False)])

    def test_planning_sheets_in_template(self):
        data = self.site._construction_spreadsheet_data(rows=20)
        names = [sheet['name'] for sheet in data['sheets']]
        self.assertEqual(names[0], START_SHEET, 'la hoja abre en INICIO')
        for name in PLANNING_SHEETS + ('ERRORES',):
            self.assertIn(name, names)
        sheets = {sheet['name']: sheet for sheet in data['sheets']}
        ids = {sheet['name']: sheet['id'] for sheet in data['sheets']}
        start = sheets[START_SHEET]
        links = [text for text in start['cells'].values() if 'HYPERLINK(' in text]
        for name in ('ARBOL', 'PROGRAMA', 'ERRORES'):
            self.assertIn('o-spreadsheet://%s' % ids[name], ''.join(links))
        self.assertEqual(len([ref for ref in start['cells'] if re.fullmatch(r'B1[2-9]', ref)]), 8)
        self.assertEqual([figure['data']['chartId'] for figure in start['figures']],
                         [figure['id'] for figure in start['figures']])
        self.assertTrue(start['tables'][0]['config']['hasFilters'])
        # Los formatos de número van por id, como los guarda la hoja.
        for sheet in data['sheets']:
            for format_id in sheet.get('formats', {}).values():
                self.assertIn(str(format_id), data['formats'])
        # Columnas calculadas nuevas y sin marcadores sin resolver.
        layout = self.site._construction_sheet_layout()
        self.assertIn('Módulos a armar (calc.)', layout['sheets']['TIPOLOGIAS']['calc_letters'])
        self.assertIn('Piso (calc.)', layout['sheets']['ARBOL']['calc_letters'])
        self.assertIn('Costo en la obra (calc.)', layout['sheets']['BOM']['calc_letters'])
        for sheet in data['sheets']:
            for text in sheet.get('cells', {}).values():
                self.assertNotRegex(str(text), r'\{[cx]:', sheet['name'])
                if str(text).startswith('='):
                    self.assertEqual(text.count('('), text.count(')'), text)
        arbol = layout['sheets']['ARBOL']
        floor_formula = sheets['ARBOL']['cells']['%s2' % arbol['calc_letters']['Piso (calc.)']]
        self.assertIn('&" / "&', floor_formula)
        # La ampliación también lleva las columnas calculadas nuevas.
        parts = self.site._construction_row_parts(layout, 22, 25)
        self.assertIn('%s25' % arbol['calc_letters']['ML (calc.)'], parts['ARBOL']['cells'])

    def test_send_saves_version_and_state(self):
        document = self._document()
        self.assertEqual(document.construction_sheet_state, 'draft')
        result = document.action_construction_validate(self._sheets())
        self.assertFalse(result['errors'], result['rows'])
        self.assertEqual(document.construction_sheet_state, 'validated')
        self.assertIn('Validada', result['state'])
        self._send()
        self.assertEqual(document.construction_sheet_state, 'sent')
        self.assertEqual(document.construction_send_version, 1)
        self.assertTrue(document.construction_send_message_id)
        copy = self.env['documents.document'].search(
            [('construction_source_id', '=', document.id)])
        self.assertEqual(copy.construction_version, 1)
        self.assertIn('Enviada v1', document._construction_state_label())
        metadata = document._get_spreadsheet_metadata()
        self.assertTrue(metadata['construction_control_pending'])
        self.assertIn('Enviada v1', metadata['construction_sheet_state'])
        document.construction_control_done(True)
        self.assertFalse(document._get_spreadsheet_metadata()['construction_control_pending'])
        # M113-12: la ficha de la obra lo muestra.
        self.site.invalidate_recordset()
        self.assertEqual(self.site.construction_sheet_document_id, document)
        self.assertEqual(self.site.construction_sheet_state, 'sent')
        self.assertEqual(self.site.construction_sheet_send_version, 1)
        self.assertEqual(self.site.construction_sheet_control_state, 'match')
        with Form(self.site) as form:
            form.construction_spreadsheet_rows = 40
        action = self.site.action_construction_open_sheet_message()
        self.assertEqual(action['res_id'], document.construction_send_message_id.res_id)

    def test_rept_migration(self):
        """La hoja de Odoo 19 no tiene REPT: las hojas ya creadas pasan a
        TEXTAFTER y TEXTBEFORE en sus datos y en sus revisiones."""
        from odoo.addons.al_construction_planner_spreadsheet.models.sheet_migration import (
            migrate_documents, migrate_revisions, replace_in_cells, replace_rept,
        )
        old = ('=IF(C2="","",IFERROR(TRIM(RIGHT(SUBSTITUTE(C2," · ",REPT(" ",200)),200)),'
               'C2))')
        document = self._document()
        data = json.loads(document.spreadsheet_data)
        bom = next(sheet for sheet in data['sheets'] if sheet['name'] == 'BOM')
        bom['cells']['B2'] = old
        document.with_context(preserve_spreadsheet_revisions=True).spreadsheet_data = \
            json.dumps(data)
        revision = self.env['spreadsheet.revision'].create({
            'res_model': 'documents.document', 'res_id': document.id,
            'revision_uuid': 'test-4c-rept', 'commands': json.dumps({
                'type': 'REMOTE_REVISION', 'commands': [{
                    'type': 'AL_CONSTRUCTION_BATCH', 'commands': [
                        ['UPDATE_CELL', {'sheetId': bom['id'], 'col': 1, 'row': 2,
                                         'content': old.replace('C2', 'C3')}]]}]})})
        migrate_documents(self.env, document,
                          lambda values: replace_in_cells(values, replace_rept))
        migrate_revisions(self.env, document, replace_rept, 'REPT(')
        self.assertNotIn('REPT(', document.spreadsheet_data)
        cells = next(sheet for sheet in json.loads(document.spreadsheet_data)['sheets']
                     if sheet['name'] == 'BOM')['cells']
        self.assertIn('TEXTAFTER(" · "&C2," · ",-1)', cells['B2'])
        self.assertNotIn('REPT(', revision.commands)
        command = json.loads(revision.commands)['commands'][0]['commands'][0][1]
        self.assertIn('TEXTAFTER(" · "&C3," · ",-1)', command['content'])
        # La forma de las hojas anteriores a 1.16 (ancho 100 y «/»).
        self.assertEqual(
            replace_rept('=IFERROR(TRIM(RIGHT(SUBSTITUTE(N5,"/",REPT(" ",100)),100)),N5)'),
            '=IFERROR(TRIM(TEXTAFTER("/"&N5,"/",-1)),N5)')
        # Y la plantilla ya no lo usa.
        template = json.dumps(self.site._construction_spreadsheet_data(rows=12))
        self.assertNotIn('REPT(', template)

    def test_import_done_sets_state(self):
        document = self._document()
        document.construction_sheet_import_done('carga.xlsx', 3, 2, 1)
        self.assertEqual(document.construction_sheet_state, 'imported')
        self.assertEqual(document.construction_import_errors, 2)
        self.assertEqual(document.construction_import_filename, 'carga.xlsx')
        document.construction_sheet_import_done('carga.xlsx', 3, 0, 1)
        self.assertEqual(document.construction_sheet_state, 'validated')

    def test_control_counts(self):
        self._send()
        document = self._document()
        typology = self.env['construction.typology'].search([('project_id', '=', self.site.id)])
        self.assertEqual(document.construction_control_counts(),
                         [['Piso 03', 1, 2, round(typology.ml_total, 2)]])

    def test_furniture_odoo_rows(self):
        self._send()
        document = self._document()
        before = self.env['documents.document'].search_count(
            [('construction_source_id', '=', document.id)])
        payload = document.construction_furniture_odoo_rows()
        # M117-07: la versión se guarda al confirmar la vista previa, no al leer.
        self.assertEqual(self.env['documents.document'].search_count(
            [('construction_source_id', '=', document.id)]), before)
        sheets = payload['sheets']

        def records(name):
            spec = sheets[name]
            return [dict(zip(spec['keys'], row)) for row in spec['rows']]

        self.assertEqual(records('TIPOLOGIAS')[0]['code'], 'COCINA 04')
        self.assertEqual(records('TIPOLOGIAS')[0]['family'], 'Cocina')
        modules = records('MODULOS')
        self.assertEqual([m['code'] for m in modules], ['MB01', 'MA01'])
        self.assertEqual(modules[0]['ml_group'], 'Mueble bajo')
        bom = records('BOM')
        white = next(line for line in bom if line['product_code'] == 'T18H-MEL')
        self.assertEqual(white['module'], 'MB01')
        self.assertTrue(white['product_name'].endswith(' · T18H-MEL'))
        self.assertEqual(white['categ'], 'TEST18 TABLEROS')
        self.assertTrue(white['stage'])
        self.assertEqual(records('PIEZAS')[0]['piece_type'], 'PUERTA')
        tree = records('ARBOL')[0]
        self.assertEqual((tree['floor'], tree['apartment'], tree['space'], tree['typology']),
                         ('Piso 03', 'Dpto 304', 'Cocina', 'COCINA 04'))
        self.assertEqual(records('TARIFAS')[0]['activity'], self.act_screw.code)
        self.assertEqual(payload['mode'], 'replace')


@tagged('post_install', '-at_install')
class TestPackage116Stage4cTour(HttpCase):
    """M113-07 a 11 en el navegador, con las fórmulas evaluadas."""

    def test_planning_in_the_sheet(self):
        category = self.env['product.category'].create({'name': 'T4C TABLEROS'})
        self.env['product.product'].create({
            'name': 'Tablero 4c (test)', 'default_code': 'T4C-MEL', 'type': 'consu',
            'categ_id': category.id, 'standard_price': 100.0})
        site = self.env['project.project'].create({
            'name': 'Obra planificar en la hoja (test)', 'is_construction_site': True,
            'construction_spreadsheet_rows': 20})
        sheets = {
            'OBRA': _rows('OBRA', [{'key': 'Cliente', 'value': 'Cliente 4c (test)'},
                                   {'key': 'Inicio', 'value': '2026-11-09'},
                                   {'key': 'Fin', 'value': '2026-12-31'}]),
            'TIPOLOGIAS': _rows('TIPOLOGIAS', [
                {'code': 'C01', 'name': 'Cocina 01', 'family': 'Cocina'},
                {'code': 'CL01', 'name': 'Closet 01', 'family': 'Closet'}]),
            'MODULOS': _rows('MODULOS', [
                {'typology': 'C01', 'code': 'MB01', 'type': 'Bajo', 'width': 600,
                 'ml_group': 'Mueble bajo', 'name': 'MOD BAJO 600'},
                {'typology': 'C01', 'code': 'MA01', 'type': 'Alto', 'width': 600,
                 'ml_group': 'Mueble alto', 'name': 'MOD ALTO 600'},
                {'typology': 'C01', 'code': 'ZO01', 'type': 'Otro', 'width': 600,
                 'ml_group': 'Sin ML', 'name': 'ZOCALO 600'},
                {'typology': 'CL01', 'code': 'MC01', 'type': 'Otro', 'width': 900,
                 'ml_group': 'Mueble completo', 'name': 'CLOSET 900'}]),
            'BOM': _rows('BOM', [{'typology': 'C01', 'module': 'MB01', 'product_code': 'T4C-MEL',
                                  'qty': 2, 'stage': 'Producción'}]),
            'PIEZAS': _rows('PIEZAS', [
                {'typology': 'C01', 'module': 'MB01', 'qty': 2, 'length': 630, 'width': 500,
                 'piece_type': 'BASE', 'product_code': 'T4C-MEL'},
                {'typology': 'C01', 'module': 'MA01', 'qty': 3, 'length': 600, 'width': 300,
                 'piece_type': 'TAPA', 'product_code': 'T4C-MEL'}]),
            'ARBOL': _rows('ARBOL', [
                {'floor': 'Piso 2', 'apartment': 'Dpto 201', 'space': 'Cocina',
                 'typology': 'C01'},
                {'floor': 'Piso 2', 'apartment': 'Dpto 201', 'space': 'Closet',
                 'typology': 'CL01'},
                {'floor': 'Piso 3', 'apartment': 'Dpto 301', 'space': 'Cocina',
                 'typology': 'C01'}]),
        }
        book = _book(sheets)
        # La obra ya está en el planificador: CONTROL debe coincidir.
        wizard = self.env['construction.master.import.wizard'].create({
            'project_id': site.id, 'file': book, 'filename': 'obra 4c.xlsx',
            'create_missing_products': True})
        data = wizard._analyze()
        self.assertFalse(data['errors'], data['errors'])
        wizard.action_import()
        site.action_construction_open_spreadsheet()
        document = self.env['documents.document'].search(
            [('construction_project_id', '=', site.id)])
        self.env['ir.attachment'].create({'name': 'al_sheet_planning_tour.xlsx', 'datas': book})
        self.start_tour('/odoo', 'al_construction_furniture_planning', login='admin')
        self.assertEqual(document.construction_control_state, 'match')
        self.assertEqual(document.construction_sheet_state, 'validated')
        commands = json.dumps([json.loads(revision.commands) for revision in self.env[
            'spreadsheet.revision'].search([('res_model', '=', 'documents.document'),
                                            ('res_id', '=', document.id)])])
        self.assertIn('2026-11-16', commands)
