# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, fields
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestPosExpiryDiscount(TestPointOfSaleHttpCommon):
    """Precio por vencer en la caja (mejora E11)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Odoo 20: el albarán del TPV busca los lotes como el cajero, que debe
        # ser usuario de Inventario para vender productos con lote (como en
        # los tests de pos_stock).
        cls.pos_user.write({'group_ids': [Command.link(cls.env.ref('stock.group_stock_user').id)]})

    def start_tour(self, url_path, tour_name, step_delay=None, **kwargs):
        # Los pasos de los tours del núcleo usan los textos en inglés; la base
        # de migración está en es_PE y los usuarios de prueba lo heredan.
        if kwargs.get('login'):
            self.env['res.users'].search([('login', '=', kwargs['login'])]).lang = 'en_US'
        return super().start_tour(url_path, tour_name, step_delay=step_delay, **kwargs)

    def _setup_product(self):
        self.env['pharmacy.expiry.discount'].search([]).unlink()
        self.env['pharmacy.expiry.discount'].create([
            {'days': 90, 'discount': 20}, {'days': 30, 'discount': 40}])
        product = self.env['product.product'].create({
            'name': 'Ibuprofeno 400 mg tableta', 'is_storable': True, 'tracking': 'lot',
            'available_in_pos': True, 'list_price': 10.0, 'taxes_id': [(6, 0, [])],
            'pharmacy_ok': True,
        })
        now = fields.Datetime.now()
        location = self.main_pos_config.picking_type_id.default_location_src_id
        self.main_pos_config.picking_type_id.write({'use_existing_lots': True})
        lot = self.env['stock.lot'].create({
            'name': 'IBU2611', 'product_id': product.id,
            'expiration_date': now + timedelta(days=20)})
        expired = self.env['stock.lot'].create({
            'name': 'IBU2501', 'product_id': product.id,
            'expiration_date': now - timedelta(days=2)})
        Quant = self.env['stock.quant']
        Quant._update_available_quantity(product, location, 10, lot_id=lot)
        Quant._update_available_quantity(product, location, 10, lot_id=expired)
        return product, lot

    def test_expired_lot_is_not_offered_and_discount_by_scale(self):
        product, lot = self._setup_product()
        Line = self.env['pos.order.line']
        lots = Line.get_existing_lots(self.env.company.id, self.main_pos_config.id, product.id)
        self.assertEqual([item['name'] for item in lots], ['IBU2611'])
        info = Line.get_pharmacy_lot_expiry(self.main_pos_config.id, product.id, ['IBU2611'])
        self.assertEqual(info['IBU2611']['discount'], 40)

    def test_sell_lot_near_expiry_with_discount(self):
        product, lot = self._setup_product()
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('al_pharmacy_pos_expiry_discount')
        order = self.env['pos.order'].search(
            [('session_id', '=', self.main_pos_config.current_session_id.id)], limit=1)
        line = order.lines.filtered(lambda l: l.product_id == product)
        self.assertEqual(line.discount, 40)
        self.assertIn('Por vencer', line.customer_note)
        self.assertEqual(line.pack_lot_ids.lot_name, 'IBU2611')
