# -*- coding: utf-8 -*-
"""Excel de carga de APU y presupuesto (requerimiento CREVAL v1.0, 6.6 y 6.8)
con datos de demostración: un muro de ladrillo con operario por cuadrilla,
herramientas al 5 % de la mano de obra y ladrillo a 0.9661."""
import base64
from io import BytesIO

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestBudgetBook(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env.ref('product.decimal_price').digits = 4
        env['tier.definition'].search([('model', '=', 'construction.resource.plan')]).active = False
        cls.stage = env['construction.stage'].create({
            'name': 'Muros (test libro)', 'code': 'book_test_stage', 'sequence': 930})
        template = env['construction.level.template'].create({
            'name': 'Especialidad, sub-especialidad y partida (test libro)', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Especialidad', 'role': 'group'}),
                (0, 0, {'sequence': 2, 'name': 'Sub-especialidad', 'role': 'group'}),
                (0, 0, {'sequence': 3, 'name': 'Partida', 'role': 'space'})]})
        cls.project = env['project.project'].create({
            'name': 'OBR-03 Oficina de demostración (test libro)', 'is_construction_site': True,
            'construction_level_template_id': template.id, 'allow_billable': True,
            'construction_apu_source': 'excel'})
        if not cls.project.account_id:
            cls.project._create_analytic_account()
        cls.customer = env['res.partner'].create({'name': 'Cliente del libro (test)'})
        cls.order = env['sale.order'].create({'partner_id': cls.customer.id,
                                              'project_id': cls.project.id})

    def _book(self, qty_second=50.0):
        from openpyxl import Workbook
        book = Workbook()
        sheet = book.active
        sheet.title = 'OBRA'
        for row in (('Obra', 'OBR-03'), ('Tipo de contrato', 'Suma alzada'),
                    ('Gastos generales %', 8), ('Utilidad %', 7)):
            sheet.append(row)
        sheet = book.create_sheet('INSUMOS')
        sheet.append(['Código', 'Descripción', 'Tipo de insumo', 'Unidad', 'Precio sin IGV',
                      'Moneda'])
        sheet.append(['BK-LAD', 'Ladrillo KK 18 huecos (test)', 'Material', 'und', 0.9661, 'PEN'])
        sheet.append(['BK-OPE', 'Operario (test)', 'Mano de obra', 'hh', 23.36, 'PEN'])
        sheet.append(['BK-HER', 'Herramientas manuales (test)', 'Herramienta %MO', '%MO', None,
                      'PEN'])
        sheet = book.create_sheet('APU')
        sheet.append(['Código', 'Descripción', 'Unidad', 'Rendimiento por día',
                      'Horas por jornada', 'Modalidad por defecto', 'Etapa'])
        sheet.append(['BK-R01', 'Muro de ladrillo KK (test)', 'm2', 19, 8, 'Personal propio',
                      'book_test_stage'])
        sheet = book.create_sheet('APU_DETALLE')
        sheet.append(['Código del APU', 'Código del insumo', 'Cuadrilla', '% de la mano de obra',
                      'Cantidad por unidad', 'Precio manual'])
        sheet.append(['BK-R01', 'BK-OPE', 1, None, None, None])
        sheet.append(['BK-R01', 'BK-LAD', None, None, 54, None])
        sheet.append(['BK-R01', 'BK-HER', None, 5, None, None])
        sheet = book.create_sheet('PRESUPUESTO')
        sheet.append(['Ítem', 'Especialidad', 'Sub-especialidad', 'Partida', 'Código del APU',
                      'Unidad', 'Modalidad', 'Metrado real', 'Holgura de metrado (%)'])
        sheet.append(['01.01', 'Arquitectura', 'Muros', 'Muro del eje A', 'BK-R01', 'm2', None,
                      100, 10])
        sheet.append(['01.02', 'Arquitectura', 'Muros', 'Muro del eje B', 'BK-R01', 'm2', None,
                      qty_second, None])
        sheet = book.create_sheet('PLAN')
        sheet.append(['Ítem', 'Partida', 'Modalidad final', 'Contratista sugerido', 'Inicio',
                      'Fin'])
        sheet.append(['01.02', 'Muro del eje B', 'Personal propio', None, '2026-11-02',
                      '2026-11-20'])
        sheet = book.create_sheet('LISTAS')
        sheet.append(['Tipo de insumo', None, 'Modalidad', None, 'Escrito como', 'Unidad'])
        sheet.append(['Material', None, 'Personal propio', None, 'hh', 'Hours'])
        sheet.append([None, None, None, None, 'und', 'Units'])
        sheet.append([None, None, None, None, 'm2', 'm²'])
        output = BytesIO()
        book.save(output)
        return base64.b64encode(output.getvalue())

    def _wizard(self, target='budget', **vals):
        return self.env['construction.budget.book.wizard'].create(dict({
            'sale_order_id': self.order.id, 'target': target, 'file': self._book(),
            'filename': 'libro.xlsx'}, **vals))

    def test_budget_and_plan(self):
        wizard = self._wizard('plan')
        wizard.action_preview()
        self.assertIn('3 insumos, 1 APU y 2 partidas', wizard.preview_html)
        wizard.action_import()
        recipe = self.env['construction.execution.template'].search([('code', '=', 'BK-R01')])
        # Mano de obra 1 × 8 ÷ 19 × 23.36 = 9.8358; ladrillo 54 × 0.9661 =
        # 52.1694; herramientas 5 % de la mano de obra = 0.4918.
        unit = 8 / 19 * 23.36 * 1.05 + 54 * 0.9661
        self.assertAlmostEqual(recipe.amount_unit, round(unit, 2))
        lines = self.order.order_line.filtered(
            lambda l: not l.display_type and l.construction_line_role == 'partida')
        self.assertEqual(len(lines), 2)
        first = lines.filtered(lambda l: l.construction_budget_item == '01.01')
        self.assertAlmostEqual(first.construction_qty_real, 100.0)
        self.assertAlmostEqual(first.product_uom_qty, 110.0)
        self.assertAlmostEqual(first.construction_cost_apu, unit, places=4)
        self.assertEqual(self.order.order_line.filtered(
            lambda l: l.display_type == 'line_section').name, 'Arquitectura')
        overhead = self.order.order_line.filtered(lambda l: l.construction_line_role == 'overhead')
        self.assertAlmostEqual(overhead.price_unit, sum(lines.mapped('price_subtotal')) * 0.08,
                               places=2)
        self.assertEqual(self.order.construction_contract_type, 'lump_sum')
        # Plan: niveles con la receta y el metrado real, sin las líneas del pie.
        plan = self.env['construction.resource.plan'].search([('project_id', '=', self.project.id)])
        self.assertEqual(len(plan), 1)
        tasks = plan.line_ids.task_id
        self.assertEqual(len(tasks), 2)
        self.assertEqual(set(tasks.mapped('construction_qty')), {100.0, 50.0})
        second = tasks.filtered(lambda t: t.construction_qty == 50.0)
        self.assertEqual(str(second.date_deadline)[:10], '2026-11-20')
        self.assertEqual(set(plan.line_ids.mapped('resource_type')),
                         {'labor', 'material', 'equipment'})
        # Volver a enviar no duplica.
        count = len(self.order.order_line)
        plan_lines = len(plan.line_ids)
        again = self._wizard('plan')
        again.action_preview()
        again.action_import()
        self.assertEqual(len(self.order.order_line), count)
        self.assertEqual(len(plan.line_ids), plan_lines)
        self.assertEqual(self.env['construction.execution.template'].search_count(
            [('code', '=', 'BK-R01')]), 1)
        self.assertTrue(self.env['construction.uom.alias'].search([('name', '=', 'hh')]))

    def test_errors_block(self):
        wizard = self._wizard()
        content = base64.b64decode(wizard.file)
        from openpyxl import load_workbook
        book = load_workbook(BytesIO(content))
        book['APU_DETALLE'].append(['BK-R01', 'NO-EXISTE', None, None, 1, None])
        book['INSUMOS'].append(['BK-LAD', 'Repetido', 'Material', 'und', 1, 'PEN'])
        output = BytesIO()
        book.save(output)
        wizard.file = base64.b64encode(output.getvalue())
        wizard.action_preview()
        self.assertIn('NO-EXISTE no existe en la hoja INSUMOS', wizard.preview_html)
        self.assertIn('BK-LAD está repetido', wizard.preview_html)
        with self.assertRaises(UserError):
            wizard.action_import()

    def test_template(self):
        from openpyxl import load_workbook
        content = self.env['construction.budget.book.wizard']._template_workbook()
        book = load_workbook(BytesIO(content))
        self.assertEqual(book.sheetnames, ['INSTRUCCIONES', 'OBRA', 'INSUMOS', 'APU',
                                           'APU_DETALLE', 'PRESUPUESTO', 'LISTAS'])
