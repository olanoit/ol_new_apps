# -*- coding: utf-8 -*-
"""Costo real, holguras y precio en la cotización (requerimiento CREVAL v1.0,
6.5) con el ejemplo de demostración: tabique de drywall con metrado real 90 y
holgura de 20 m² → 110 ofertados; costo del APU 58.04 y holgura de 5.00 →
63.04; costo real 5,223.60, costo ofertado 6,934.40 y reserva 1,710.80."""
from odoo import Command
from odoo.tests import tagged

from .test_income import IncomeCommon


@tagged('post_install', '-at_install')
class TestQuotationLayers(IncomeCommon):

    def test_layers(self):
        product = self.env['product.product'].create({
            'name': 'Tabique drywall (test 6.5)', 'type': 'service'})
        order = self.env['sale.order'].create({
            'partner_id': self.customer.id, 'construction_contract_type': 'unit_price',
            'order_line': [Command.create({
                'product_id': product.id, 'name': 'Tabique drywall',
                'construction_qty_real': 90.0, 'construction_qty_slack': 20.0,
                'construction_cost_apu': 58.04, 'construction_cost_slack': 5.0,
                'construction_margin_pct': 10.0})]})
        line = order.order_line
        self.assertAlmostEqual(line.product_uom_qty, 110.0)
        self.assertAlmostEqual(line.construction_cost_offered, 63.04)
        self.assertAlmostEqual(line.price_unit, 69.344, places=3)
        self.assertAlmostEqual(line.construction_amount_real, 5223.60)
        self.assertAlmostEqual(line.construction_amount_offered, 6934.40)
        self.assertAlmostEqual(order.construction_amount_reserve, 1710.80)
        self.assertIn('holgura de metrado no se cobra', order.construction_layers_warning)
        if 'purchase_price' in line._fields:
            self.assertAlmostEqual(line.purchase_price, 63.04)
