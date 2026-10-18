# -*- coding: utf-8 -*-
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestPosPresentationTour(TestPointOfSaleHttpCommon):

    def test_sell_blister_in_pos(self):
        product = self.env['product.template'].create({
            'name': 'Loratadina 10 mg', 'type': 'consu', 'available_in_pos': True,
            'list_price': 0.20, 'taxes_id': [(6, 0, [])],
        })
        self.env['pharmacy.presentation'].create({
            'product_tmpl_id': product.id, 'name': 'Blíster', 'factor': 7, 'price': 1.00})
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('al_pharmacy_pos_presentation')

        order = self.env['pos.order'].search(
            [('session_id', '=', self.main_pos_config.current_session_id.id)], limit=1)
        blister_line = order.lines.filtered('pharmacy_presentation_id')
        self.assertEqual(blister_line.qty, 7)
        self.assertAlmostEqual(blister_line.price_unit * 7, 1.0, places=9)
        self.assertEqual(order.amount_total, 1.20)
