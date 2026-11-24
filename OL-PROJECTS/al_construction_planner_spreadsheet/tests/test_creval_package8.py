# -*- coding: utf-8 -*-
"""CREVAL, paquete 8: títulos de la venta en la hoja de planificación de obra
(CR-69) y el 0 de la hoja que se conserva al enviarla (CR-72). Datos
ficticios."""
import json
from io import BytesIO

from odoo import Command
from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.al_construction_planner_suite.tests.test_budget_book_creval import (
    TestBudgetBook,
)


@tagged('post_install', '-at_install')
class TestCrevalPackage8Sheets(TestBudgetBook):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        grp = 'al_construction_planner.group_planner_'
        cls.planner = new_test_user(
            cls.env, 'planificador_p8_hoja', name='Planificador (test paquete 8, hoja)',
            groups=f'{grp}planner,{grp}amounts')

    def _rows(self, order, project=None):
        return self.env['project.project']._construction_budget_rows(
            order, project or self.project, sold=False)['PRESUPUESTO']

    # ------------------------------------------------------------------
    # CR-69
    # ------------------------------------------------------------------
    def test_cr69_plan_sheet_inherits_the_sale_titles(self):
        self._send(self._book()).action_import()
        self.project.construction_sale_order_id = self.order
        rows = self._rows(self.order)
        self.assertEqual([row['item'] for row in rows], ['01', '01.01', '01.02'])
        self.assertEqual(rows[0], {'item': '01', 'name': 'Arquitectura'})
        self.project.with_user(self.planner).action_construction_open_plan_sheet()
        document = self.env['documents.document'].search([
            ('construction_project_id', '=', self.project.id),
            ('construction_budget_role', '=', 'plan')])
        sheets = {sheet['name']: sheet for sheet in
                  json.loads(document.spreadsheet_data)['sheets']}
        cells = sheets['PRESUPUESTO']['cells']
        # El título, en su lugar: antes de sus partidas, sin unidad ni metrado.
        self.assertEqual((cells['A2'], cells['B2']), ('01', 'Arquitectura'))
        self.assertEqual(cells['A3'], '01.01')
        self.assertEqual(cells['A4'], '01.02')
        self.assertNotIn('D2', cells)
        self.assertIn('PRESUPUESTO_title',
                      [rule['id'] for rule in sheets['PRESUPUESTO']['conditionalFormats']])
        start = sheets['INICIO']['cells']
        self.assertEqual(start['A21'], 'Títulos')
        self.assertIn('"Título"', start['B21'])
        self.assertEqual(start['A17'], 'Partidas')
        # PLAN solo lleva partidas.
        plan_items = [sheets['PLAN']['cells'].get('A%s' % row) for row in (2, 3, 4)]
        self.assertEqual(plan_items, ['01.01', '01.02', None])

    def test_cr69_sheet_with_titles_validates_and_sends(self):
        """La hoja con títulos se valida sin errores y el envío los lee como
        títulos (no como partidas sin dato)."""
        self._send(self._book()).action_import()
        self.project.construction_sale_order_id = self.order

        def with_title(book):
            sheet = book['PRESUPUESTO']
            sheet.insert_rows(2)
            sheet.cell(row=2, column=1, value='01')
            sheet.cell(row=2, column=4, value='Arquitectura')
        wizard = self._send(self._edited_book(with_title), target='plan')
        self.assertTrue(wizard.can_send, wizard.preview_html)
        wizard.action_import()
        self.assertEqual(len(self.order.order_line.filtered(
            lambda l: not l.display_type and l.construction_line_role == 'partida')), 2)

    def test_cr69_without_sale_sheet_takes_the_sections(self):
        Line = self.env['sale.order.line']
        order = self.env['sale.order'].create({'partner_id': self.customer.id})
        product = self.env['product.product'].create({
            'name': 'Partida de presupuesto (test paquete 8)', 'type': 'service'})
        sequence = 0
        for display_type, name, item in (
                ('line_section', 'Estructuras', False),
                ('line_subsection', 'Concreto', False),
                (False, 'Zapatas', '02.01.01'),
                (False, 'Columnas', '02.01.02'),
                ('line_subsection', 'Acero', False),
                (False, 'Acero de zapatas', '02.02.01'),
                ('line_section', 'Arquitectura', False),
                (False, 'Pintura', '03.01')):
            sequence += 1
            values = {'order_id': order.id, 'sequence': sequence, 'name': name}
            if display_type:
                values['display_type'] = display_type
            else:
                values.update(product_id=product.id, product_uom_qty=1.0,
                              construction_budget_item=item, name=name,
                              construction_line_role='partida')
            Line.create(values)
        rows = self._rows(order, self.env['project.project'])
        self.assertEqual(
            [(row['item'], row['name']) for row in rows],
            [('02', 'Estructuras'), ('02.01', 'Concreto'), ('02.01.01', 'Zapatas'),
             ('02.01.02', 'Columnas'), ('02.02', 'Acero'), ('02.02.01', 'Acero de zapatas'),
             ('03', 'Arquitectura'), ('03.01', 'Pintura')])

    # ------------------------------------------------------------------
    # CR-72
    # ------------------------------------------------------------------
    def test_cr72_zero_is_kept_in_the_book(self):
        from openpyxl import load_workbook
        content = self.env['documents.document']._construction_book({
            'PRESUPUESTO': [['Ítem', 'Costo', 'Texto', 'Casilla', 'Metrado'],
                            ['01.01', 0, '', False, 0.0]]})
        sheet = load_workbook(BytesIO(content))['PRESUPUESTO']
        values = [cell.value for cell in sheet[2]]
        self.assertEqual(values[0], '01.01')
        self.assertEqual(values[1], 0)
        self.assertIsNotNone(values[1])
        self.assertIsNone(values[2])
        self.assertIsNone(values[3])
        self.assertEqual(values[4], 0)
        self.assertIsNotNone(values[4])


@tagged('post_install', '-at_install')
class TestCrevalPackage8SheetsTour(TestBudgetBook, HttpCase):
    """Recorrido de pantalla de CR-69 con un planificador sin permisos de
    administrador."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        grp = 'al_construction_planner.group_planner_'
        cls.planner = new_test_user(
            cls.env, 'planificador_p8_hoja_tour',
            name='Planificador (test paquete 8, recorrido de la hoja)',
            groups=f'{grp}planner,{grp}amounts,project.group_project_user')
        cls.planner.write({'company_ids': [Command.link(cls.env.company.id)],
                           'company_id': cls.env.company.id})

    def test_cr69_tour_plan_sheet_with_titles(self):
        self._send(self._book()).action_import()
        self.project.construction_sale_order_id = self.order
        self.project.with_user(self.planner).action_construction_open_plan_sheet()
        document = self.env['documents.document'].search([
            ('construction_project_id', '=', self.project.id),
            ('construction_budget_role', '=', 'plan')])
        document.name = 'Planificación de obra (títulos, test paquete 8)'
        self.start_tour('/odoo', 'al_construction_package8_titles',
                        login='planificador_p8_hoja_tour')
