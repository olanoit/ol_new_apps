# -*- coding: utf-8 -*-
"""Importación del presupuesto con secciones (requerimiento CREVAL v1.0, 6.4):
el costo directo de la cotización importada es igual al del archivo y cada
partida queda con sus tres niveles. Datos ficticios."""
import base64
import io

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestBudgetImport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.unit = env.ref('uom.product_uom_unit')
        cls.meter = env.ref('uom.product_uom_meter')
        env['construction.uom.alias'].create([
            {'name': 'UND', 'uom_id': cls.unit.id}, {'name': 'GLB', 'uom_id': cls.unit.id},
            {'name': 'ML', 'uom_id': cls.meter.id}])
        template = env['construction.level.template'].create({
            'name': 'Especialidad, sub-especialidad y partida (test ppto)', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Especialidad', 'role': 'group'}),
                (0, 0, {'sequence': 2, 'name': 'Sub-especialidad', 'role': 'group'}),
                (0, 0, {'sequence': 3, 'name': 'Partida', 'role': 'space'})]})
        cls.project = env['project.project'].create({
            'name': 'Obra del presupuesto (test)', 'is_construction_site': True,
            'construction_level_template_id': template.id, 'allow_billable': True})
        partner = env['res.partner'].create({'name': 'Cliente del presupuesto (test)'})
        cls.order = env['sale.order'].create({'partner_id': partner.id,
                                              'project_id': cls.project.id})

    def _book(self):
        import openpyxl
        book = openpyxl.Workbook()
        ws = book.active
        ws.append(['PRESUPUESTO DE OBRA (test)'])
        ws.append(['Ítem', 'Descripción', 'Unidad', 'Metrado', 'Precio unitario', 'Parcial'])
        rows = [
            ['01', 'ESTRUCTURAS', None, None, None, None],
            ['01.01', 'Concreto armado', None, None, None, None],
            ['01.01.01', 'Columnas', 'und', 10, 150.0, 1500.0],
            ['01.01.02', 'Vigas', 'ML', 20.5, 80.0, 1640.0],
            [None, 'Encofrado sin número', 'Und', 5, 12.5, 62.5],
            ['02', 'INSTALACIONES', None, None, None, None],
            ['02.01', 'Eléctricas', None, None, None, None],
            ['02.01.01', 'Tomacorrientes', 'UND', 30, 45.0, 1350.0],
            ['02.01.01', 'Tomacorrientes (repetido)', 'GLB', 1, 300.0, 300.0],
        ]
        for row in rows:
            ws.append(row)
        buffer = io.BytesIO()
        book.save(buffer)
        return base64.b64encode(buffer.getvalue())

    def test_import_and_levels(self):
        wizard = self.env['construction.budget.import.wizard'].create({
            'sale_order_id': self.order.id, 'file': self._book(), 'filename': 'ppto.xlsx'})
        wizard.action_preview()
        self.assertEqual(wizard.state, 'preview')
        self.assertAlmostEqual(wizard.amount_file, 4852.5)
        self.assertIn('02.01.01', wizard.preview_html)  # ítem repetido
        self.assertIn('sin número', wizard.preview_html)
        wizard.action_import()
        lines = self.order.order_line
        self.assertEqual(len(lines.filtered(lambda l: l.display_type == 'line_section')), 2)
        self.assertEqual(len(lines.filtered(lambda l: l.display_type == 'line_subsection')), 2)
        products = lines.filtered(lambda l: not l.display_type)
        self.assertEqual(len(products), 5)
        self.assertAlmostEqual(self.order.amount_untaxed, 4852.5)
        self.assertEqual(products.filtered(
            lambda l: l.construction_budget_item == '01.01.02').product_uom_id, self.meter)
        # De la cotización a los niveles de la obra.
        action = self.order.action_construction_create_levels()
        partidas = self.env['project.task'].browse(action['domain'][0][2])
        self.assertEqual(len(partidas), 5)
        columns = partidas.filtered(lambda t: t.name.startswith('01.01.01'))
        self.assertEqual(columns.construction_qty, 10)
        self.assertEqual(columns.parent_id.name, '01.01 Concreto armado')
        self.assertEqual(columns.parent_id.parent_id.name, '01 ESTRUCTURAS')
        self.assertEqual(columns.sale_line_id.order_id, self.order)
