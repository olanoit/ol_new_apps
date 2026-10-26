# -*- coding: utf-8 -*-
"""Valorización al cliente por avance de la partida (requerimiento CREVAL
v1.0, CR-01) con gastos generales, utilidad y descuento en proporción
(CR-12). Obra de la ruta del ingreso: 28.10 % de la partida al 28/10."""
from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_income import PRICE, IncomeCommon


@tagged('post_install', '-at_install')
class TestValuationProgress(IncomeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        product = cls.env['product.product'].create({
            'name': 'Conceptos del presupuesto (test)', 'type': 'service',
            'invoice_policy': 'delivery'})
        if 'service_type' in product._fields:
            product.service_type = 'manual'
        cls.order.write({'order_line': [Command.create({
            'product_id': product.id, 'name': name, 'product_uom_qty': 1, 'price_unit': price,
            'tax_ids': [Command.set(cls.tax.ids)]}) for name, price in (
                ('Gastos generales 6 %', 10000.0), ('Utilidad 5 %', 8000.0),
                ('Descuento', -2000.0))]})
        lines = cls.order.order_line
        cls.overhead = lines.filtered(lambda l: l.name.startswith('Gastos'))
        cls.profit = lines.filtered(lambda l: l.name.startswith('Utilidad'))
        cls.discount = lines.filtered(lambda l: l.name.startswith('Descuento'))
        cls.project.construction_valuation_basis = 'progress'

    def test_progress_and_proportional_lines(self):
        # Avance valorizado: contrata, material y servicio al costo del plan.
        self.project.construction_progress_source = 'valued'
        self.assertEqual((self.overhead.construction_line_role, self.profit.construction_line_role,
                          self.discount.construction_line_role),
                         ('overhead', 'profit', 'discount'))
        self.assertEqual(self.project._construction_partida_lines(), self.partida)
        self._progress(4502.23, date(2026, 10, 22))
        self._consume(303, date(2026, 10, 20))
        valuation = self._prepare_valuation(date(2026, 10, 28))
        self.assertFalse(valuation.delivery_ids)
        line = valuation.line_ids.filtered(lambda l: l.sale_line_id == self.partida)
        # 47,984.71 ejecutados ÷ 170,764.10 planificados.
        ratio = 47984.71 / 170764.10
        self.assertAlmostEqual(line.progress_delivered, ratio, places=6)
        self.assertEqual(line.amount_delivered, round(PRICE * ratio, 2))
        overhead = valuation.line_ids.filtered(lambda l: l.sale_line_id == self.overhead)
        discount = valuation.line_ids.filtered(lambda l: l.sale_line_id == self.discount)
        self.assertEqual(overhead.amount_delivered, round(10000.0 * line.amount_delivered / PRICE, 2))
        self.assertLess(discount.amount_delivered, 0.0)
        # El porcentaje escrito en la partida arrastra a los proporcionales.
        line.with_user(self.projects_user).write(
            {'pct_manual': 40.0, 'manual_reason': 'Metrado de la Val 1 del cliente'})
        self.assertEqual(line.amount_delivered, round(PRICE * 0.4, 2))
        self.assertEqual(overhead.amount_delivered, 4000.0)
        self.assertEqual(discount.amount_delivered, -800.0)
        with self.assertRaises(UserError):
            overhead.write({'pct_manual': 50.0, 'manual_reason': 'No va'})
        valuation.with_user(self.projects_user).action_send()
        self._confirm_valuation(valuation)
        self.assertEqual(valuation.state, 'confirmed')
        valuation.with_user(self.finance).action_create_invoice()
        invoice = valuation.invoice_id
        expected = round(PRICE * 0.4, 2) + 4000.0 + 3200.0 - 800.0
        self.assertAlmostEqual(valuation.amount_confirmed, expected, places=2)
        # Sin cuenta del fondo en Ajustes, la factura es lo confirmado, al
        # céntimo (CR-01: ajuste de redondeo si el precio no da exacto).
        self.assertAlmostEqual(invoice.amount_untaxed, expected, places=2)
        names = invoice.invoice_line_ids.mapped('name')
        self.assertTrue(any(name.startswith('Descuento') for name in names))


@tagged('post_install', '-at_install')
class TestValuationProgressQty(TestValuationProgress):
    """Correcciones del 25-oct (CR-01): la partida se reconoce por la línea de
    venta de la tarea aunque todas las partidas compartan producto y no
    tengan receta, el avance es la cantidad validada ÷ la presupuestada y el
    porcentaje escrito sobrevive a «Actualizar»."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Dos partidas con el mismo producto, como la cotización de la obra.
        cls.order.write({'order_line': [Command.create({
            'product_id': cls.partida_product.id, 'name': 'Closets', 'product_uom_qty': 1,
            'price_unit': 50000.0, 'tax_ids': [Command.set(cls.tax.ids)], 'sequence': 1})]})
        cls.partida_2 = cls.order.order_line.filtered(lambda l: l.name == 'Closets')
        cls.space.sale_line_id = cls.partida

    def test_progress_and_proportional_lines(self):
        """La prueba heredada, con dos partidas: ya cubierta arriba."""

    def test_qty_progress_by_task_sale_line(self):
        self.assertEqual(self.project.construction_progress_source, 'qty')
        self.assertEqual(self.project._construction_partida_lines(),
                         self.partida | self.partida_2)
        self._progress(4502.23, date(2026, 10, 22))
        # El material consumido no cuenta en el avance por cantidad.
        self._consume(303, date(2026, 10, 20))
        valuation = self._prepare_valuation(date(2026, 10, 28))
        line = valuation.line_ids.filtered(lambda l: l.sale_line_id == self.partida)
        ratio = 4502.23 / 13000
        self.assertAlmostEqual(line.progress_delivered, ratio, places=6)
        self.assertEqual(line.pct_rule, round(ratio * 100, 2))
        self.assertEqual(line.amount_delivered, round(PRICE * ratio, 2))
        # La partida sin avance entra con 0.
        closets = valuation.line_ids.filtered(lambda l: l.sale_line_id == self.partida_2)
        self.assertFalse(closets.amount_delivered)
        # El % escrito a mano sobrevive a «Actualizar» con su motivo y autor.
        line.with_user(self.projects_user).write(
            {'pct_manual': 40.0, 'manual_reason': 'Metrado acordado con el cliente'})
        self._progress(1000.0, date(2026, 10, 27))
        valuation.with_user(self.projects_user).action_refresh()
        self.assertTrue(line.exists())
        self.assertEqual(line.pct_manual, 40.0)
        self.assertEqual(line.manual_reason, 'Metrado acordado con el cliente')
        self.assertEqual(line.manual_user_id, self.projects_user)
        self.assertEqual(line.amount_delivered, round(PRICE * 0.4, 2))
        self.assertEqual(line.pct_rule, round(5502.23 / 13000 * 100, 2))
        overhead = valuation.line_ids.filtered(lambda l: l.sale_line_id == self.overhead)
        direct = PRICE + 50000.0
        self.assertEqual(overhead.amount_delivered,
                         round(10000.0 * line.amount_delivered / direct, 2))

    def test_overhead_by_section(self):
        """Gastos generales por especialidad: solo el costo directo de las
        partidas de su sección."""
        Line = self.env['sale.order.line']
        Line.create([
            {'order_id': self.order.id, 'display_type': 'line_section', 'name': 'Carpintería',
             'sequence': 0},
            {'order_id': self.order.id, 'display_type': 'line_section', 'name': 'Closets',
             'sequence': 1},
        ])
        self.partida.sequence = 0
        (self.partida_2 | self.overhead).write({'sequence': 2})
        (self.profit | self.discount).write({'sequence': 3})
        self.project.construction_proportional_scope = 'section'
        self._progress(4502.23, date(2026, 10, 22))
        valuation = self._prepare_valuation(date(2026, 10, 28))
        overhead = valuation.line_ids.filtered(lambda l: l.sale_line_id == self.overhead)
        # Los gastos generales van con «Closets», que no tiene avance.
        self.assertFalse(overhead.amount_delivered)
