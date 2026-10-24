# -*- coding: utf-8 -*-
"""Hoja de trabajo de presupuesto y plan (requerimiento CREVAL v1.0, 6.7):
plantilla en Presupuestos › cotización, validación, envío al planificador con
el asistente del libro (6.6), costos vigentes y versiones."""
import base64
import json
from io import BytesIO

from odoo.tests import tagged

from odoo.addons.al_construction_planner_suite.tests.test_budget_book_creval import (
    TestBudgetBook,
)


def _sheets_from_book(content):
    from openpyxl import load_workbook
    book = load_workbook(BytesIO(content), data_only=True)
    return {sheet.title: [['' if value is None else value for value in row]
                          for row in sheet.iter_rows(values_only=True)]
            for sheet in book.worksheets}


@tagged('post_install', '-at_install')
class TestBudgetWorksheet(TestBudgetBook):

    def _document(self):
        self.order.action_construction_open_spreadsheet()
        return self.env['documents.document'].search([
            ('construction_sale_order_id', '=', self.order.id),
            ('construction_source_id', '=', False)])

    def test_template_and_folder(self):
        document = self._document()
        self.assertEqual(len(document), 1)
        self.assertEqual(document.construction_sheet_kind, 'budget')
        self.assertEqual(document.folder_id.name, self.order.name)
        self.assertEqual(document.folder_id.folder_id.name, 'Presupuestos')
        data = json.loads(document.spreadsheet_data)
        names = [sheet['name'] for sheet in data['sheets']]
        self.assertEqual(names, ['INSTRUCCIONES', 'OBRA', 'INSUMOS', 'APU', 'APU_DETALLE',
                                 'PRESUPUESTO', 'PLAN', 'LISTAS', 'REFERENCIAS', 'ERRORES'])
        budget = next(sheet for sheet in data['sheets'] if sheet['name'] == 'PRESUPUESTO')
        self.assertEqual(budget['cells']['A1'], 'Ítem')
        self.assertIn('VLOOKUP', budget['cells']['O2'])
        self.assertEqual(document._get_spreadsheet_metadata()['construction_sheet_kind'],
                         'budget')
        # La obra de la cotización abre la misma hoja.
        self.project.construction_sale_order_id = self.order
        self.project.action_construction_open_spreadsheet()
        self.assertEqual(self.env['documents.document'].search_count([
            ('construction_project_id', '=', self.project.id),
            ('construction_source_id', '=', False)]), 1)

    def test_send_validate_costs_and_versions(self):
        document = self._document()
        sheets = _sheets_from_book(base64.b64decode(self._book()))
        result = document.action_construction_validate(sheets)
        self.assertEqual(result['errors'], [])
        bad = dict(sheets, APU_DETALLE=sheets['APU_DETALLE'] + [['BK-R01', 'NO-EXISTE', '', '',
                                                                 1]])
        errors = document.action_construction_validate(bad)['errors']
        self.assertTrue(any('NO-EXISTE' in error[3] for error in errors))
        action = document.action_construction_send_to_planner(sheets, 'plan')
        wizard = self.env[action['res_model']].browse(action['res_id'])
        self.assertEqual(wizard.state, 'preview')
        self.assertEqual(wizard.spreadsheet_id, document)
        wizard.action_import()
        self.assertEqual(wizard.state, 'done')
        self.assertTrue(self.env['construction.resource.plan'].search(
            [('project_id', '=', self.project.id)]).line_ids)
        # Cada envío guarda una copia numerada.
        copies = self.env['documents.document'].search([('construction_source_id', '=',
                                                         document.id)])
        self.assertEqual(len(copies), 1)
        self.assertIn('v1', copies.name)
        self.assertEqual(document.construction_version, 2)
        document.action_construction_new_version()
        self.assertEqual(document.construction_version, 3)
        costs = document.construction_current_costs(['BK-LAD', 'X'])
        self.assertAlmostEqual(costs['BK-LAD'][0], 0.9661)
        rows = document.construction_odoo_rows()
        self.assertEqual(len(rows['PRESUPUESTO']), 2)
        self.assertEqual(rows['PRESUPUESTO'][0][4], 'BK-R01')


# Las pruebas heredadas ya corren en su clase.
for _name in dir(TestBudgetBook):
    if _name.startswith('test_') and callable(getattr(TestBudgetBook, _name)) \
            and _name not in vars(TestBudgetWorksheet):
        setattr(TestBudgetWorksheet, _name, None)
