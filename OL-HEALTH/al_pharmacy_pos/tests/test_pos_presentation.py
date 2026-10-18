# -*- coding: utf-8 -*-
from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestPosPresentation(TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        cls.product = cls.create_product('Paracetamol 500 mg DEMO', cls.categ_basic, 0.20)
        cls.blister = cls.env['pharmacy.presentation'].create({
            'product_tmpl_id': cls.product.product_tmpl_id.id,
            'name': 'Blíster', 'factor': 7, 'price': 1.00,
        })
        cls.customer = cls.env['res.partner'].create({'name': 'Cliente DEMO'})

    def _order(self, qty, presentation=None, price_unit=None):
        price_unit = price_unit if price_unit is not None else (
            presentation.price / presentation.factor if presentation else 0.20)
        total = self.env.company.currency_id.round(qty * price_unit)
        return self.env['pos.order'].create({
            'session_id': self.pos_session.id,
            'partner_id': self.customer.id,
            'lines': [(0, 0, {
                'product_id': self.product.id,
                'qty': qty,
                'price_unit': price_unit,
                'price_subtotal': total,
                'price_subtotal_incl': total,
                'pharmacy_presentation_id': presentation.id if presentation else False,
            })],
            'amount_tax': 0, 'amount_total': total, 'amount_paid': 0, 'amount_return': 0,
        })

    def test_line_keeps_exact_unit_price(self):
        self.open_new_session()
        order = self._order(7, self.blister)
        self.assertAlmostEqual(order.lines.price_unit * 7, 1.0, places=9)
        self.assertEqual(order.amount_total, 1.0)

    def test_invoice_line_in_presentation_unit(self):
        """1 blíster de 7 a S/ 1,00 se factura como 1 x 1,00, no 7 x 0,14."""
        self.open_new_session()
        order = self._order(14, self.blister)
        invoice = order._create_invoice(order._prepare_invoice_vals())
        line = invoice.invoice_line_ids.filtered('product_id')
        self.assertEqual(line.quantity, 2)
        self.assertEqual(line.product_uom_id, self.blister.uom_id)
        self.assertEqual(line.price_unit, 1.0)
        self.assertEqual(invoice.amount_untaxed, 2.0)

    def test_loose_quantity_stays_in_units(self):
        """3 tabletas sueltas de una línea de blíster: no es un número entero
        de blísteres, la factura queda en unidades."""
        self.open_new_session()
        order = self._order(3, self.blister)
        invoice = order._create_invoice(order._prepare_invoice_vals())
        line = invoice.invoice_line_ids.filtered('product_id')
        self.assertEqual(line.quantity, 3)
        self.assertEqual(line.product_uom_id, self.product.uom_id)

    def test_presentations_are_loaded_in_pos(self):
        self.open_new_session()
        self.assertIn('pharmacy.presentation',
                      self.env['pos.session']._load_pos_data_models(self.config))
        data = self.env['product.template'].load_product_from_pos(
            self.config.id, [('id', '=', self.product.product_tmpl_id.id)])
        self.assertEqual([p['id'] for p in data['pharmacy.presentation']], [self.blister.id])
