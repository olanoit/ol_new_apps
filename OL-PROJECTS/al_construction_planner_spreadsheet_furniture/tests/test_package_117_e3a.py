# -*- coding: utf-8 -*-
"""Paquete 1.17, entrega 3, bloque a. M117-15: parámetros de cálculo."""
import base64
import json
import re

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from ..models.construction_sheet_parameter import (
    PARAMETERS_SHEET, parameter_formula,
)
from .test_package_116_stage4b import _book
from .test_worksheet_v18 import TestWorksheetV18


@tagged('post_install', '-at_install')
class TestPackage117Parameters(TestWorksheetV18):

    def _data(self):
        return self.site._construction_spreadsheet_data(10)

    def _sheet(self, data, name):
        return next(sheet for sheet in data['sheets'] if sheet['name'] == name)

    def _document(self):
        self.site.action_construction_open_spreadsheet()
        return self.env['documents.document'].search(
            [('construction_project_id', '=', self.site.id),
             ('construction_source_id', '=', False)])

    def _parameter(self, key, sheet='planning'):
        return self.env['construction.sheet.parameter'].search([
            ('company_id', '=', self.env.company.id), ('sheet', '=', sheet), ('key', '=', key)])

    def test_planning_template_has_its_parameters(self):
        data = self._data()
        names = [sheet['name'] for sheet in data['sheets']]
        self.assertEqual(names.index(PARAMETERS_SHEET), names.index('OBRA') + 1)
        cells = self._sheet(data, PARAMETERS_SHEET)['cells']
        keys = [cells[ref] for ref in cells if re.fullmatch(r'G\d+', ref) and ref != 'G1']
        # M119-01: más la sección «Rendimientos» de la obra (rend:<código>).
        keys = [key for key in keys if not key.startswith('rend:')]
        self.assertCountEqual(keys, ['piezas_frente', 'dias_semana', 'horas_jornada',
                                     'jornales_semana', 'banda_rendimiento', 'dias_sub_etapa',
                                     'tolerancia_ml', 'tolerancia_ml_venta'])

    def test_no_business_number_in_the_formulas(self):
        data = self._data()
        program = json.dumps(self._sheet(data, 'PROGRAMA')['cells'])
        control = json.dumps(self._sheet(data, 'CONTROL')['cells'])
        for text in ('/5,', '*7-3', 'VALUE(B5),5'):
            self.assertNotIn(text, program)
        self.assertNotIn('0.005', control)
        self.assertIn(parameter_formula('dias_semana').replace('"', '\\"'), program)
        self.assertIn(parameter_formula('tolerancia_ml').replace('"', '\\"'), control)

    def test_percent_goes_as_a_fraction(self):
        cells = self._sheet(self._data(), PARAMETERS_SHEET)['cells']
        row = next(ref[1:] for ref, value in cells.items()
                   if value == 'tolerancia_ml' and ref.startswith('G'))
        self.assertEqual(cells['C%s' % row], '0.005')
        self.assertEqual(cells['F%s' % row], '0.005')

    def test_configuration_validates_the_initial_value(self):
        parameter = self._parameter('dias_semana')
        with self.assertRaises(ValidationError):
            parameter.value_initial = '8'
        with self.assertRaises(ValidationError):
            parameter.value_initial = 'cinco'
        parameter.value_initial = '6'
        self.assertEqual(self._parameter('redondeo_sentido', 'sale').value_type, 'list')
        with self.assertRaises(ValidationError):
            self._parameter('redondeo_sentido', 'sale').value_initial = 'Otro'

    def test_a_new_sheet_takes_the_new_initial_value(self):
        self._parameter('dias_semana').value_initial = '6'
        cells = self._sheet(self._data(), PARAMETERS_SHEET)['cells']
        row = next(ref[1:] for ref, value in cells.items()
                   if value == 'dias_semana' and ref.startswith('G'))
        self.assertEqual(cells['C%s' % row], '6')

    def test_existing_sheet_is_told_about_the_current_value(self):
        document = self._document()
        self._parameter('dias_semana').value_initial = '6'
        current = document._get_spreadsheet_metadata()['construction_parameter_current']
        self.assertEqual(current['dias_semana'], '6')

    def _rows(self, **changes):
        header = ['Grupo', 'Parámetro', 'Valor', 'Unidad', 'Para qué sirve', 'Valor inicial (calc.)',
                  'Clave (calc.)', 'Motivo del cambio', 'Valor usado (calc.)', 'Vigente (calc.)']
        row = dict(key='dias_semana', value=5, initial=5, reason='', current='', **{})
        row.update(changes)
        return [header, ['Programa', 'Días', row['value'], '', '', row['initial'], row['key'],
                         row['reason'], row['value'], row['current']]]

    def _issues(self, rows, used=()):
        return self.env['construction.sheet.parameter']._construction_issues(
            rows, 'planning', self.env.company, used)

    def test_validate_parameters(self):
        self.assertEqual(self._issues(self._rows()), [])
        issues = self._issues(self._rows(value=6))
        self.assertEqual([(issue[2], issue[4]) for issue in issues],
                         [('Motivo del cambio', 'error')])
        self.assertEqual(self._issues(self._rows(value=6, reason='Pedido del cliente')), [])
        issues = self._issues(self._rows(value=9, reason='x'))
        self.assertEqual(issues[0][4], 'error')
        self.assertIn('entre', issues[0][3])
        issues = self._issues(self._rows(current=6))
        self.assertEqual(issues[0][4], 'warning')

    def test_empty_parameter_is_an_error_only_if_used(self):
        rows = self._rows(value='', initial='')
        self.assertEqual(self._issues(rows), [])
        self.assertEqual(self._issues(rows, used=('dias_semana',))[0][4], 'error')

    def test_upgrade_keeps_values_and_adds_new_parameters(self):
        document = self._document()
        document.construction_sheet_upgrade({'master': {}, 'other': {PARAMETERS_SHEET: {'cells': {
            'G1': 'Clave (calc.)', 'G2': 'dias_semana', 'C2': '6', 'F2': '5', 'H2': 'Turno doble',
        }}}})
        data = json.loads(document.with_context(bin_size=False).spreadsheet_data)
        cells = self._sheet(data, PARAMETERS_SHEET)['cells']
        row = next(ref[1:] for ref, value in cells.items()
                   if value == 'dias_semana' and ref.startswith('G'))
        self.assertEqual((cells['C%s' % row], cells['F%s' % row], cells['H%s' % row]),
                         ('6', '5', 'Turno doble'))
        self.assertIn('tolerancia_ml', cells.values(), 'el parámetro nuevo llega')

    def test_import_reads_parameters_by_key(self):
        document = self._document()
        wizard = self.env['construction.spreadsheet.import.wizard'].create({
            'document_id': document.id, 'filename': 'p.xlsx',
            'file': _book({PARAMETERS_SHEET: [
                ['Grupo', 'Parámetro', 'Valor', 'Unidad', 'Para qué', 'Inicial', 'Clave', 'Motivo'],
                ['Programa', 'Días', 6, '', '', 5, 'dias_semana', 'Turno doble']],
                'TIPOLOGIAS': [['Código', 'Nombre'], ['C1', 'Cocina']]})})
        self.assertIn(PARAMETERS_SHEET, wizard.review_html)
        payload = wizard.action_import()['infos']['construction_sheet_import']
        self.assertEqual(payload['parameters'], {'dias_semana': ['6', 'Turno doble']})
        self.assertNotIn(PARAMETERS_SHEET, payload['other'])

    def test_profile_exports_parameters(self):
        profile = self.env['construction.vertical.profile'].search([], limit=1)
        data = profile._export_data()
        self.assertIn('dias_semana', [item['key'] for item in data['sheet_parameters']])
        self.assertTrue(base64)
