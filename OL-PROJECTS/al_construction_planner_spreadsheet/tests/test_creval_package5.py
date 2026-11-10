# -*- coding: utf-8 -*-
"""CREVAL, paquete 5, entrega 1: hoja de presupuesto de venta y hoja de
planificación de obra (CR-38), «Pasar a la cotización» y contrato de obra en
borrador al confirmar (CR-44), grupo «Presupuestador» y entradas (CR-47).
Datos ficticios."""
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from odoo.addons.al_construction_planner_suite.tests.test_budget_book_creval import (
    TestBudgetBook,
)


@tagged('post_install', '-at_install')
class TestCrevalPackage5(TestBudgetBook):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.budgeter = new_test_user(
            cls.env, 'presupuesto_p5',
            groups='al_construction_planner_spreadsheet.group_construction_budgeter',
            name='Presupuestador (test)')

    def test_budgeter_opens_the_sale_sheet(self):
        order = self.order.with_user(self.budgeter)
        order.action_construction_open_budget_sheet()
        document = self.env['documents.document'].search(
            [('construction_sale_order_id', '=', self.order.id),
             ('construction_budget_role', '=', 'sale')])
        self.assertEqual(len(document), 1)
        self.assertTrue(document.name.startswith('Presupuesto de venta · %s' % self.order.name))
        # Pulsar dos veces abre la misma.
        order.action_construction_open_budget_sheet()
        self.assertEqual(self.env['documents.document'].search_count(
            [('construction_sale_order_id', '=', self.order.id),
             ('construction_budget_role', '=', 'sale')]), 1)
        metadata = document.with_user(self.budgeter)._get_spreadsheet_metadata()
        self.assertEqual(metadata['construction_budget_role'], 'sale')
        # La hoja de venta no envía el plan.
        with self.assertRaises(UserError):
            document.action_construction_send_to_planner({}, 'plan')

    def test_plan_sheet_is_another_document(self):
        self.order.action_construction_open_budget_sheet()
        self.project.construction_sale_order_id = self.order
        self.project.action_construction_open_plan_sheet()
        plan = self.env['documents.document'].search(
            [('construction_project_id', '=', self.project.id),
             ('construction_budget_role', '=', 'plan')])
        self.assertEqual(len(plan), 1)
        self.assertTrue(plan.name.startswith('Planificación de obra'))
        with self.assertRaises(UserError):
            plan.action_construction_send_to_planner({}, 'budget')

    def test_budgeter_passes_the_budget(self):
        wizard = self.env['construction.budget.book.wizard'].with_user(self.budgeter).create({
            'sale_order_id': self.order.id, 'target': 'budget', 'file': self._book(),
            'filename': 'libro.xlsx'})
        wizard.action_import()
        lines = self.order.order_line.filtered(
            lambda l: not l.display_type and l.construction_line_role == 'partida')
        self.assertEqual(len(lines), 2)
        self.assertEqual(self.order.state, 'draft')
        self.assertFalse(self.env['construction.resource.plan'].search(
            [('project_id', '=', self.project.id)]))

    def test_confirm_creates_a_draft_contract(self):
        self._send(self._book()).action_import()
        self.order.action_confirm()
        contracts = self.env['construction.contract'].search([('project_id', '=', self.project.id)])
        self.assertEqual(len(contracts), 1)
        self.assertEqual(contracts.state, 'draft')
        self.assertEqual(contracts.sale_order_id, self.order)

    # ------------------------------------------------------------------
    # Entrega 2: CR-39, CR-40 y CR-41
    # ------------------------------------------------------------------
    def _sheets(self):
        data = self.env['project.project']._construction_budget_spreadsheet_data(
            self.order, self.project)
        return data, {sheet['name']: sheet for sheet in data['sheets']}

    def test_start_first_and_hidden_lists(self):
        data, sheets = self._sheets()
        self.assertEqual(data['sheets'][0]['name'], 'INICIO')
        names = [sheet['name'] for sheet in data['sheets']]
        self.assertLess(names.index('OBRA'), names.index('PRESUPUESTO'))
        self.assertLess(names.index('PRESUPUESTO'), names.index('APU'))
        for name in ('LISTAS', 'REFERENCIAS', '_CLAVES'):
            self.assertFalse(sheets[name].get('isVisible', True), name)
        start = sheets['INICIO']['cells']
        self.assertEqual(start['A9'], '1 · OBRA')
        self.assertIn('◀ Siguiente', start['E10'])
        self.assertIn('SUM(PRESUPUESTO!', start['B19'])

    def test_obra_gets_the_company_parameters(self):
        self.env.company.write({'construction_budget_overhead_pct': 8.0,
                                'construction_budget_profit_pct': 7.0,
                                'construction_budget_margin_pct': 10.0})
        _data, sheets = self._sheets()
        obra = sheets['OBRA']['cells']
        values = {obra['A%s' % row]: obra.get('B%s' % row) for row in range(1, 14)
                  if obra.get('A%s' % row)}
        self.assertEqual(values['Gastos generales %'], '8.0')
        self.assertEqual(values['Utilidad %'], '7.0')
        self.assertEqual(values['Margen por defecto %'], '10.0')
        self.assertTrue(values['Obra'])
        self.assertTrue(values['Fecha'])

    def test_budget_rows_have_state_and_titles(self):
        _data, sheets = self._sheets()
        presupuesto = sheets['PRESUPUESTO']
        from odoo.addons.al_construction_planner_spreadsheet.models.project_project import (
            PRESUPUESTO_KEYS, _col,
        )
        state = _col(len(PRESUPUESTO_KEYS))
        self.assertEqual(presupuesto['cells']['%s1' % state], 'Estado')
        self.assertIn('Falta APU o costo', presupuesto['cells']['%s2' % state])
        self.assertIn('PRESUPUESTO_title', [cf['id'] for cf in presupuesto['conditionalFormats']])
        self.assertEqual(presupuesto['panes']['xSplit'], PRESUPUESTO_KEYS.index('name') + 1)

    def test_default_margin_when_the_row_has_none(self):
        def margin(book):
            book['OBRA'].append(('Margen por defecto %', 10))
        wizard = self._send(self._edited_book(margin))
        wizard.action_import()
        line = self.order.order_line.filtered(lambda l: l.construction_budget_item == '01.02')
        self.assertAlmostEqual(line.construction_margin_pct, 10.0)

    # ------------------------------------------------------------------
    # Entrega 3: CR-42, CR-43 y el pie de CR-44
    # ------------------------------------------------------------------
    def test_apu_and_insumos_have_state(self):
        _data, sheets = self._sheets()
        apu = sheets['APU']['cells']
        insumos = sheets['INSUMOS']['cells']
        headers = lambda cells: [value for ref, value in cells.items()  # noqa: E731
                                 if ref.endswith('1') and not ref[-2].isdigit()]
        for header in ('Usado en (calc.)', 'Estado (calc.)', 'Código propuesto (calc.)'):
            self.assertIn(header, headers(apu))
        for header in ('Usado en (calc.)', 'Estado (calc.)'):
            self.assertIn(header, headers(insumos))
        state = next(value for ref, value in insumos.items()
                     if ref[-1] == '2' and not ref[-2].isdigit() and 'Producto nuevo sin precio'
                     in str(value))
        self.assertIn('Precio de más de 90 días', state)
        self.assertIn('Total del APU (calc.)', headers(sheets['APU_DETALLE']['cells']))

    def test_footer_sheet(self):
        data, sheets = self._sheets()
        footer = sheets['PIE DE PRESUPUESTO']['cells']
        self.assertEqual(footer['A11'], 'Total')
        self.assertEqual(footer['B9'], '=B7+B8')
        self.assertIn('SUM(PRESUPUESTO!', footer['B3'])
        names = [sheet['name'] for sheet in data['sheets']]
        self.assertEqual(names.index('PIE DE PRESUPUESTO'), names.index('INSUMOS') + 1)

    def test_apu_without_code_gets_the_next_one(self):
        def new_apu(book):
            book['APU'].append([None, 'Salida de termostato (test)', 'und', 10, 8,
                                'Personal propio', 'book_test_stage'])
        wizard = self.env['construction.budget.book.wizard'].create({
            'sale_order_id': self.order.id, 'target': 'budget',
            'file': self._edited_book(new_apu), 'filename': 'libro.xlsx'})
        book, _errors, _warnings = wizard._parse()
        self.assertIn('R01', book['apus'])
        self.assertEqual(book['apus']['R01']['name'], 'Salida de termostato (test)')

    # ------------------------------------------------------------------
    # Entrega 4: CR-45 y CR-46
    # ------------------------------------------------------------------
    def test_plan_uses_the_site_quantity(self):
        def site(book):
            sheet = book['PLAN']
            sheet.cell(row=1, column=7, value='Metrado de obra')
            sheet.cell(row=2, column=7, value=55)
        wizard = self._send(self._edited_book(site), target='plan')
        wizard.action_import()
        line = self.order.order_line.filtered(lambda l: l.construction_budget_item == '01.02')
        self.assertAlmostEqual(line.construction_qty_real, 50.0)
        plan = self.env['construction.resource.plan'].search([('project_id', '=', self.project.id)])
        self.assertIn(55.0, plan.line_ids.task_id.mapped('construction_qty'))

    def test_plan_and_control_tabs(self):
        self._send(self._book()).action_import()
        _data, sheets = self._sheets()
        plan = sheets['PLAN']['cells']
        headers = [plan.get('%s1' % chr(65 + i)) for i in range(14)]
        for header in ('Metrado vendido (calc.)', 'Metrado de obra', 'Estado (calc.)'):
            self.assertIn(header, headers)
        self.assertEqual(plan['A2'], '01.01')
        control = sheets['CONTROL']['cells']
        self.assertEqual(control['G2'], 'Estado')
        self.assertIn('Supera el umbral', control['G3'])
        self.assertEqual(control['J2'], '0.05')
