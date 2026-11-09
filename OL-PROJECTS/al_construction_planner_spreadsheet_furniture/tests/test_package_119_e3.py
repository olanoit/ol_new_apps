# -*- coding: utf-8 -*-
"""Paquete 1.19, entrega 3. M119-01 en la hoja de planificación.

* PARAMETROS lleva «Banda del rendimiento» y una fila de «Rendimientos» por
  actividad de las sub etapas con presupuesto, con el inicial del catálogo o
  el de la obra.
* PROGRAMA lleva un bloque por sub etapa y modalidad; _MO, los días
  equivalentes por fecha y la tabla de actividades.
* El envío escribe la tabla de rendimientos (con motivo) y el presupuesto de
  la obra."""
from datetime import date

from odoo.tests import tagged

from odoo.addons.al_construction_planner.tests.test_package_119_schedule import site_calendar

from ..models.labor_budget_sheet import (
    BLOCK_ROWS, BUDGET_SHEET, BUDGET_TITLE, PRODUCTIVITY_PREFIX, read_labor_payload,
)
from .test_worksheet_v18 import TestWorksheetV18

MONDAY = date(2026, 11, 2)


def serial(day):
    return (day - date(1899, 12, 30)).days


@tagged('post_install', '-at_install')
class TestPackage119Budget(TestWorksheetV18):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.resource_calendar_id.tz = 'America/Lima'
        cls.env.company.construction_site_calendar_id = site_calendar(cls.env, cls.env.company)
        meter = cls.env.ref('uom.product_uom_meter')
        cls.ml = cls.env['construction.labor.activity'].create({
            'code': 'T19-INS', 'name': 'Instalación ML (test 1.19)', 'stage': 'installation',
            'uom_id': meter.id, 'productivity': 4.0, 'default_price': 7.0, 'sequence': 1})
        cls.install = cls.env['construction.stage'].search([('code', '=', 'installation')])

    def _sheets_of(self, data):
        return {sheet['name']: sheet for sheet in data['sheets']}

    def test_template_has_the_budget(self):
        data = self.site._construction_spreadsheet_data(10)
        sheets = self._sheets_of(data)
        parameters = sheets['PARAMETROS']['cells']
        keys = {value: ref[1:] for ref, value in parameters.items()
                if ref.startswith('G') and ref[1:].isdigit()}
        self.assertIn('banda_rendimiento', keys)
        row = keys[PRODUCTIVITY_PREFIX + 'T19-INS']
        self.assertEqual(parameters['F%s' % row], '4')
        self.assertEqual(parameters['A%s' % row], 'Rendimientos')
        mo = sheets[BUDGET_SHEET]
        self.assertFalse(mo['isVisible'])
        self.assertIn('=DATE(', mo['cells']['A2'])
        tab = next(tab['name'] for tab in self.site._construction_matrix_tabs()
                   if self.ml in tab['activities'])
        self.assertIn("'%s'!" % tab, mo['cells']['D2'])
        self.assertIn('"%s"&D2' % PRODUCTIVITY_PREFIX, mo['cells']['G2'])
        program = sheets['PROGRAMA']['cells']
        titles = [value for value in program.values()
                  if isinstance(value, str) and value.startswith(BUDGET_TITLE)]
        self.assertTrue(any(self.install._label() in title for title in titles))
        # Con la obra con su tabla, el inicial es el de la obra.
        self.site._construction_productivity_ensure(self.ml)
        self.site.construction_productivity_ids.write({'productivity': 3.5,
                                                       'reason': 'Accesos (test)'})
        parameters = self._sheets_of(self.site._construction_spreadsheet_data(10))[
            'PARAMETROS']['cells']
        self.assertEqual(parameters['F%s' % row], '3.5')

    def _payload_sheets(self):
        """Valores calculados de lo que el envío lee de la hoja."""
        parameters = [['Grupo', 'Parámetro', 'Valor', 'Unidad', 'Para qué sirve',
                       'Valor inicial (calc.)', 'Clave (calc.)', 'Motivo del cambio',
                       'Valor usado (calc.)', 'Vigente (calc.)'],
                      ['Programa', 'Banda', '', '%', '', 0.1, 'banda_rendimiento', '', 0.1, ''],
                      ['Rendimientos', 'T19-INS', 4.5, '', '', 4, PRODUCTIVITY_PREFIX + 'T19-INS',
                       'Mueble sencillo', 4.5, '']]
        label = self.install._label()
        mo = [['Fecha', 'Días'], ['', '', '', 'T19-INS', label, 400, 4.5, 88.89, 7, 2800,
                                  'own', 0]]
        program = [[''] for _row in range(5)]
        program.append(['%s%s · Personal propio' % (BUDGET_TITLE, label)])
        block = [[''] for _row in range(max(BLOCK_ROWS.values()) + 1)]
        block[BLOCK_ROWS['stage']] = ['Sub etapa', label, 'installation']
        block[BLOCK_ROWS['mode']] = ['Modalidad', 'Personal propio', 'own']
        block[BLOCK_ROWS['start']] = ['Inicio', serial(MONDAY)]
        block[BLOCK_ROWS['end']] = ['Fin', serial(date(2026, 12, 1))]
        block[BLOCK_ROWS['daily_wage']] = ['Jornal', 120]
        program += block[1:]
        return {'PARAMETROS': parameters, BUDGET_SHEET: mo, 'PROGRAMA': program}

    def test_payload_and_apply(self):
        payload = read_labor_payload(self._payload_sheets())
        self.assertAlmostEqual(payload['band'], 10.0)
        self.assertEqual(payload['blocks'][0]['start'], MONDAY)
        self.assertEqual(payload['blocks'][0]['mode'], 'own')
        budgets = self.site._construction_labor_budget_apply(payload)
        self.assertEqual(len(budgets), 1)
        self.assertEqual(budgets.equivalent_days, 24.5)
        self.assertAlmostEqual(budgets.line_ids.productivity, 4.5)
        row = self.site.construction_productivity_ids.filtered(
            lambda r: r.activity_id == self.ml)
        self.assertEqual(row.productivity, 4.5)
        self.assertEqual(row.origin, 'adjusted')
        self.assertEqual(row.reason, 'Mueble sencillo')
        # 400 ÷ 4.5 = 88.89 persona-días ÷ 24.5 = 3.63 → 4 personas al 91 %.
        self.assertEqual(budgets.persons, 4)
        self.assertAlmostEqual(budgets.amount, 4 * 24.5 * 120, places=2)
        # Un segundo envío actualiza el mismo presupuesto.
        again = self.site._construction_labor_budget_apply(payload)
        self.assertEqual(again, budgets)

    def test_send_writes_the_budget(self):
        self.site.action_construction_open_spreadsheet()
        document = self.env['documents.document'].search(
            [('construction_project_id', '=', self.site.id),
             ('construction_source_id', '=', False)])
        self.assertIn(BUDGET_SHEET, document._construction_send_sheet_names())
        sheets = dict(self._sheets(), **self._payload_sheets())
        action = document.action_construction_send_to_planner(sheets)
        wizard = self.env['construction.master.import.wizard'].browse(action['res_id'])
        self.assertTrue(wizard.construction_labor_payload)
        wizard.action_import()
        self.assertEqual(self.site.construction_labor_budget_ids.persons, 4)
        metadata = document._get_spreadsheet_metadata()
        self.assertEqual(metadata['construction_parameter_current'][
            PRODUCTIVITY_PREFIX + 'T19-INS'], '4.5')
        self.assertTrue(metadata['construction_day_factors'])

    def test_generate_plan_and_crew_use_the_budget(self):
        """El personal propio cuesta jornal ÷ rendimiento exigido: con 400 ML,
        4.5 de rendimiento y 24.5 días, 4 personas y 4.08 exigido, S/ 29.40 por
        ML. «Asignar cuadrilla» dice cuántas personas pide el presupuesto."""
        self.ml.execution_mode = 'own'
        self.site.action_construction_open_spreadsheet()
        document = self.env['documents.document'].search(
            [('construction_project_id', '=', self.site.id),
             ('construction_source_id', '=', False)])
        sheets = dict(self._sheets(), **self._payload_sheets())
        sheets['ACTIVIDADES'] = [['Tipología', 'Actividad', 'Cantidad por ambiente'],
                                 ['COCINA 04', 'T19-INS', 400]]
        action = document.action_construction_send_to_planner(sheets)
        self.env['construction.master.import.wizard'].browse(action['res_id']).action_import()
        budget = self.site.construction_labor_budget_ids
        self.assertEqual(budget.persons, 4)
        plan = self.env['construction.resource.plan'].create({'project_id': self.site.id})
        self.env['construction.plan.generate.wizard'].create(
            {'plan_id': plan.id}).action_generate()
        line = plan.line_ids.filtered(lambda l: l.activity_id == self.ml)
        self.assertEqual(line.resource_type, 'labor')
        self.assertAlmostEqual(line.price_unit_planned, 120 / budget.line_ids.required_productivity,
                               places=2)
        self.assertAlmostEqual(line.price_unit_planned, 29.40, places=2)
        self.assertAlmostEqual(line.construction_person_days, 98.0, places=1)
        self.assertIn('Presupuesto de mano de obra', line.price_basis)
        # «Asignar cuadrilla» (si está instalada) propone las personas.
        if 'construction.plan.crew.wizard' in self.env:
            plan.line_ids.filtered(lambda l: not l.price_unit_planned).price_unit_planned = 1.0
            plan.action_request_approval()
            wizard = self.env['construction.plan.crew.wizard'].with_context(
                default_plan_id=plan.id).create({
                    'whole_project': True, 'date_start': MONDAY, 'weeks': 1,
                    'time_mode': 'days'})
            self.assertEqual(wizard.budget_persons, 4)
            self.assertAlmostEqual(wizard.budget_person_days, 22.5, places=2)
            self.assertIn('Presupuesto de mano de obra', wizard.note or '')
