# -*- coding: utf-8 -*-
"""v1.5, fase 21: hoja de trabajo de la obra y «Enviar al planificador»."""
import json

from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from odoo.addons.al_construction_planner.tests.common import PlannerCommon
from odoo.addons.al_construction_planner.wizards.master_import_layout import SHEETS


@tagged('post_install', '-at_install')
class TestConstructionSpreadsheet(PlannerCommon):

    def test_template_has_master_sheets_and_odoo_lists(self):
        action = self.project.action_construction_open_spreadsheet()
        document = self.env['documents.document'].search(
            [('construction_project_id', '=', self.project.id)])
        self.assertEqual(len(document), 1)
        self.assertEqual(document.handler, 'spreadsheet')
        self.assertEqual(action['params']['spreadsheet_id'], document.id)
        data = json.loads(document.spreadsheet_data)
        names = [sheet['name'] for sheet in data['sheets']]
        self.assertEqual(names, list(SHEETS) + ['REFERENCIAS'])
        arbol = next(sheet for sheet in data['sheets'] if sheet['name'] == 'ARBOL')
        self.assertEqual(arbol['cells']['A1'], SHEETS['ARBOL'][1][0][1])
        self.assertEqual({lst['model'] for lst in data['lists'].values()},
                         {'construction.labor.activity', 'construction.typology'})
        reference = data['sheets'][-1]
        self.assertEqual(reference['cells']['A3'], '=ODOO.LIST(1,1,"code")')
        # Se abre la misma hoja, no otra.
        self.project.action_construction_open_spreadsheet()
        self.assertEqual(self.env['documents.document'].search_count(
            [('construction_project_id', '=', self.project.id)]), 1)
        self.assertEqual(document._get_spreadsheet_metadata()['construction_project_id'],
                         self.project.id)

    def test_send_to_planner_opens_import_with_row_errors(self):
        manager = new_test_user(self.env, 'plan_hoja_admin', name='Admin hoja (test)',
                                groups='al_construction_planner.group_planner_manager,'
                                       'documents.group_documents_user')
        site = self.env['project.project'].create({
            'name': 'Obra desde la hoja (test)', 'is_construction_site': True})
        site.with_user(manager).action_construction_open_spreadsheet()
        document = self.env['documents.document'].search(
            [('construction_project_id', '=', site.id)])
        headers = {name: [header for _k, header, _r, _h in columns]
                   for name, (_d, columns) in SHEETS.items()}
        typology_headers = headers['TIPOLOGIAS']
        sheets = {
            'TIPOLOGIAS': [typology_headers,
                           ['C01', 'Cocina 01', 'Cocina'] + [''] * (len(typology_headers) - 3)],
            'ARBOL': [headers['ARBOL'][:5], ['', 'P1', 'D101', 'Cocina', 'C01'],
                      ['', 'P1', 'D102', 'Cocina', 'NO-EXISTE']],
            'REFERENCIAS': [['Actividades'], ['Código']],
            'Notas sueltas': [['no se importa']],
        }
        action = document.with_user(manager).action_construction_send_to_planner(sheets)
        self.assertEqual(action['res_model'], 'construction.master.import.wizard')
        wizard = self.env['construction.master.import.wizard'].browse(action['res_id'])
        self.assertEqual(wizard.project_id, site)
        data = wizard._analyze()
        self.assertFalse(data['errors'], data['errors'])
        self.assertIn('NO-EXISTE', str(data['warnings']))
        self.assertIn('D102', str(data['warnings']), 'la advertencia dice la fila')
        wizard.action_import()
        spaces = self.env['project.task'].search([('project_id', '=', site.id),
                                                  ('construction_level', '=', 'space')])
        self.assertEqual(spaces.filtered(lambda t: t.construction_typology_id.code == 'C01')
                         .construction_apartment_task_id.name, 'D101')
        with self.assertRaises(UserError):
            self.env['documents.document'].create({
                'name': 'Suelta', 'handler': 'spreadsheet',
                'mimetype': 'application/o-spreadsheet',
            }).action_construction_send_to_planner(sheets)
