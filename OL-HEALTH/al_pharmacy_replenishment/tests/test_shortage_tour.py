# -*- coding: utf-8 -*-
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestShortageTour(TestPointOfSaleHttpCommon):

    def start_tour(self, url_path, tour_name, step_delay=None, **kwargs):
        # Los pasos de los tours del núcleo usan los textos en inglés; la base
        # de migración está en es_PE y los usuarios de prueba lo heredan.
        if kwargs.get('login'):
            self.env['res.users'].search([('login', '=', kwargs['login'])]).lang = 'en_US'
        return super().start_tour(url_path, tour_name, step_delay=step_delay, **kwargs)

    def test_register_shortage_in_pos(self):
        product = self.env['product.product'].create({
            'name': 'Enalapril 10 mg', 'type': 'consu', 'is_storable': True,
            'available_in_pos': True, 'list_price': 0.30, 'taxes_id': [(6, 0, [])],
        })
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('al_pharmacy_replenishment_shortage')

        session = self.main_pos_config.current_session_id
        shortages = self.env['pharmacy.shortage'].search(
            [('pos_session_id', '=', session.id)], order='id')
        self.assertEqual(len(shortages), 2)
        warehouse = self.main_pos_config.picking_type_id.warehouse_id
        self.assertEqual(shortages.warehouse_id, warehouse)
        self.assertRecordValues(shortages, [
            {'product_id': product.id, 'quantity': 3.0, 'reason': 'no_stock', 'state': 'pending',
             'user_id': self.pos_user.id},
            {'product_id': False, 'quantity': 1.0, 'reason': 'not_carried', 'state': 'pending',
             'user_id': self.pos_user.id},
        ])
        self.assertEqual(shortages[1].description, 'Colirio lubricante 15 ml')
