# -*- coding: utf-8 -*-
"""Paquete 4 de CREVAL (correcciones de la rutina integral) en el libro de
presupuesto. Datos ficticios.

* CR-27: el «Costo real» se redondea como la línea de la cotización.
* CR-29: «Validar» detecta lo que antes solo detectaba el envío.
* CR-30: un nodo por código de nivel.
* CR-31: el suministro del cliente sale de la hoja.
* CR-35: la etapa actual por su nombre.
* CR-37: términos de la plantilla en el árbol y el Cronograma.
"""
from odoo.tests import tagged

from .test_budget_book_creval import TestBudgetBook


@tagged('post_install', '-at_install')
class TestPackage4Creval(TestBudgetBook):

    def _many_partidas(self, book):
        """22 partidas de metrado y costo no redondos (CR-27)."""
        sheet = book['PRESUPUESTO']
        for index in range(3, 25):
            sheet.append(['01.%02d' % index, 'Arquitectura', 'Muros', 'Muro %s' % index,
                          'BK-R01', 'm2', None, 13.37 + index * 0.731, None])

    def test_cr27_direct_cost_rounded_like_the_quotation(self):
        wizard = self._send(self._edited_book(self._many_partidas))
        self.assertTrue(wizard.can_send, wizard.preview_html)
        wizard.action_import()
        book = wizard._parse()[0]
        lines = self.order.order_line.filtered(
            lambda l: not l.display_type and l.construction_line_role == 'partida')
        self.assertEqual(len(lines), 24)
        self.assertAlmostEqual(sum(lines.mapped('construction_amount_real')),
                               wizard._book_direct_cost(book), places=2)
        for line in lines:
            self.assertAlmostEqual(
                line.construction_amount_real,
                round(line.construction_qty_real * round(line.construction_cost_apu, 4), 2),
                places=2)

    def test_cr27_template_formula_rounds(self):
        from odoo.addons.al_construction_planner_spreadsheet.models.project_project import (
            presupuesto_formula,
        )
        formula = presupuesto_formula('cost_real', 5, digits=(4, 2))
        self.assertIn('ROUND(', formula)
        self.assertIn(',4),2)', formula)

    def test_cr29_contract_mode_needs_its_activity(self):
        def full_contract(book):
            book['APU']['F2'] = 'Contrata a todo costo'
        wizard = self._send(self._edited_book(full_contract))
        self.assertIn('falta la actividad de la contrata', wizard.preview_html)
        self.assertFalse(wizard.can_send)

        def with_contract(book):
            book['APU']['F2'] = 'Contrata a todo costo'
            book['INSUMOS'].append(['BK-SUB', 'Subcontrato de muros (test)', 'Subcontrato', 'm2',
                                    30, self.env.company.currency_id.name])
            book['APU_DETALLE'].append(['BK-R01', 'BK-SUB', None, None, 1, None])
        wizard = self._send(self._edited_book(with_contract))
        self.assertNotIn('falta la actividad de la contrata', wizard.preview_html)

    def test_cr29_broken_formula_is_reported(self):
        def broken(book):
            sheet = book['APU_DETALLE']
            sheet.cell(row=1, column=8, value='Parcial (calc.)')
            sheet.cell(row=2, column=8, value='#REF!')
        wizard = self._send(self._edited_book(broken))
        self.assertIn('La fórmula da error (#REF!)', wizard.preview_html)
        self.assertFalse(wizard.can_send)

    def test_cr29_missing_column_gives_one_error(self):
        def no_unit(book):
            book['INSUMOS'].delete_cols(4)
        wizard = self.env['construction.budget.book.wizard'].create({
            'sale_order_id': self.order.id, 'target': 'budget',
            'file': self._edited_book(no_unit), 'filename': 'libro.xlsx'})
        _book, errors, _warnings = wizard._parse()
        self.assertEqual(len(errors), 1, errors)
        self.assertIn('Unidad', errors[0][3])

    def test_cr30_one_node_per_code(self):
        def levels(book):
            sheet = book['PRESUPUESTO']
            sheet.append(['3', None, None, 'Arquitectura', None, None, None, None, None])
            sheet.append(['3.9001', 'Arquitectura', '3.90 MUROS Y TARRAJEOS', 'Muro 1', 'BK-R01',
                          'm2', None, 10, None])
            sheet.append(['3.9002', 'Arquitectura', '3.90 MUROS Y TARRAJEOS', 'Muro 2', 'BK-R01',
                          'm2', None, 12, None])
            # Sin Sub-especialidad: debe colgar del mismo nodo 3.90.
            sheet.append(['3.9003', None, None, 'Muro 3', 'BK-R01', 'm2', None, 14, None])
        wizard = self._send(self._edited_book(levels), target='plan')
        self.assertTrue(wizard.can_send, wizard.preview_html)
        wizard.action_import()
        nodes = self.env['project.task'].search([
            ('project_id', '=', self.project.id), ('name', '=like', '3.90%'),
            ('construction_level_line_id.sequence', '=', 2)])
        self.assertEqual(len(nodes), 1, nodes.mapped('name'))
        self.assertEqual(nodes.name, '3.90 MUROS Y TARRAJEOS')
        children = self.env['project.task'].search([('parent_id', '=', nodes.id)])
        self.assertEqual(len(children), 3)

    def test_cr31_client_supply_from_the_sheet(self):
        def client(book):
            sheet = book['APU_DETALLE']
            sheet.cell(row=1, column=7, value='Suministro del cliente')
            sheet.cell(row=3, column=7, value='Sí')
        wizard = self._send(self._edited_book(client))
        wizard.action_import()
        recipe = self.env['construction.execution.template'].search([('code', '=', 'BK-R01')])
        brick = recipe.line_ids.filtered(lambda l: l.product_id.default_code == 'BK-LAD')
        self.assertTrue(brick.is_client_supply)
        other = recipe.line_ids - brick
        self.assertFalse(any(other.mapped('is_client_supply')))

    def test_cr35_current_stage_by_name(self):
        selection = dict(self.env['project.task']._fields[
            'construction_current_stage']._description_selection(self.env))
        self.assertEqual(selection.get(self.stage.code), self.stage._label())

    def test_cr37_terms_without_modules(self):
        plan = self.env['construction.resource.plan'].create({'project_id': self.project.id})
        terms = plan.get_tree_terms()
        self.assertFalse(terms['has_modules'])
        self.assertEqual(terms['detail'], 'Partida')
        self.assertNotIn('departamento', terms['empty_hint'])
        self.assertIn('especialidad', terms['empty_hint'])

    def test_cr37_level_number_is_hidden(self):
        template = self.project.construction_level_template_id
        template.line_ids.filtered(lambda l: l.sequence == 3).name = 'Partida (N3)'
        terms = self.env['construction.level.labels.mixin']._construction_level_terms(template)
        self.assertEqual(terms['level_3'], 'Partida')
