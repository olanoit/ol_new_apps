# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestPosFractionLabel(TestPoSCommon):
    """Rótulo de la venta fraccionada (DS 020-2024-SA, art. 48)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        cls.product = cls.create_product('Loratadina 10 mg tableta', cls.categ_basic, 0.20)
        cls.product.product_tmpl_id.write({
            'pharmacy_ok': True, 'is_storable': True, 'tracking': 'lot',
            'pharmacy_laboratory_id': cls.env['res.partner'].create({'name': 'Laboratorios Andinos'}).id,
            'pharmacy_route_id': cls.env.ref('al_pharmacy_base.route_oral').id,
        })
        cls.blister = cls.env['pharmacy.presentation'].create({
            'product_tmpl_id': cls.product.product_tmpl_id.id,
            'name': 'Blíster', 'factor': 10, 'price': 2.00,
        })
        cls.lot = cls.env['stock.lot'].create({
            'name': 'LOR2611', 'product_id': cls.product.id,
            'expiration_date': fields.Datetime.now() + timedelta(days=400),
        })

    def _order(self, qty, presentation=None):
        price_unit = presentation.price / presentation.factor if presentation else 0.20
        total = self.env.company.currency_id.round(qty * price_unit)
        return self.env['pos.order'].create({
            'session_id': self.pos_session.id,
            'lines': [(0, 0, {
                'product_id': self.product.id, 'qty': qty, 'price_unit': price_unit,
                'price_subtotal': total, 'price_subtotal_incl': total,
                'pharmacy_presentation_id': presentation.id if presentation else False,
                'pack_lot_ids': [(0, 0, {'lot_name': self.lot.name})],
            })],
            'amount_tax': 0, 'amount_total': total, 'amount_paid': 0, 'amount_return': 0,
        })

    def test_loose_units_get_a_label_with_lot_and_expiry(self):
        self.open_new_session()
        labels = self._order(3)._get_pharmacy_fraction_labels()
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels[0]['lot'], self.lot)
        self.assertEqual(labels[0]['quantity'], 3)

    def test_presentation_sale_has_no_label(self):
        self.open_new_session()
        self.assertFalse(self._order(10, self.blister)._get_pharmacy_fraction_labels())

    def test_label_report_shows_the_six_data(self):
        self.open_new_session()
        order = self._order(3)
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_pharmacy_pos.report_pos_fraction_label', order.ids)[0].decode()
        for text in ('Loratadina 10 mg tableta', 'Laboratorios Andinos', 'LOR2611',
                     self.env.company.name):
            self.assertIn(text, html)
        self.assertIn('Vence:', html)
