# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPharmacyStock(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1)
        cls.stock = cls.warehouse.lot_stock_id
        cls.customer_location = cls.env.ref('stock.stock_location_customers')
        cls.supplier_location = cls.env.ref('stock.stock_location_suppliers')
        cls.customer = cls.env['res.partner'].create({'name': 'Lucía Fernández'})
        cls.supplier = cls.env['res.partner'].create({'name': 'Droguería Andina'})
        cls.product = cls.env['product.product'].create({
            'name': 'Cetirizina 10 mg tableta', 'is_storable': True, 'tracking': 'lot',
            'use_expiration_date': True, 'pharmacy_ok': True,
            'pharmacy_sanitary_registry': 'EN-06231',
            'pharmacy_registry_expiry': fields.Date.today() + timedelta(days=700),
        })
        now = fields.Datetime.now()
        cls.lot_good = cls.env['stock.lot'].create({
            'name': 'CTZ2401', 'product_id': cls.product.id,
            'expiration_date': now + timedelta(days=400)})
        cls.lot_quarantine = cls.env['stock.lot'].create({
            'name': 'CTZ2312', 'product_id': cls.product.id,
            'expiration_date': now + timedelta(days=200)})
        for lot in (cls.lot_good, cls.lot_quarantine):
            cls.env['stock.quant']._update_available_quantity(cls.product, cls.stock, 10, lot_id=lot)
        cls.lot_quarantine.action_pharmacy_quarantine()

    def _delivery(self, qty):
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.warehouse.out_type_id.id,
            'partner_id': self.customer.id,
            'location_id': self.stock.id,
            'location_dest_id': self.customer_location.id,
            'move_ids': [(0, 0, {
                'product_id': self.product.id, 'product_uom_qty': qty,
                'uom_id': self.product.uom_id.id,
                'location_id': self.stock.id, 'location_dest_id': self.customer_location.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        return picking

    def _receipt(self, lot_name, expiry=True):
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.warehouse.in_type_id.id,
            'partner_id': self.supplier.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock.id,
            'move_ids': [(0, 0, {
                'product_id': self.product.id, 'product_uom_qty': 5,
                'uom_id': self.product.uom_id.id,
                'location_id': self.supplier_location.id, 'location_dest_id': self.stock.id,
            })],
        })
        picking.action_confirm()
        picking.move_ids.move_line_ids.write({
            'lot_name': lot_name, 'quantity': 5,
            'expiration_date': fields.Datetime.now() + timedelta(days=300) if expiry else False,
        })
        picking.move_ids.picked = True
        return picking

    # Reserva -------------------------------------------------------------
    def test_quarantine_lot_is_not_reserved(self):
        picking = self._delivery(15)
        self.assertEqual(picking.move_ids.move_line_ids.lot_id, self.lot_good)
        self.assertEqual(picking.move_ids.quantity, 10)

    def test_release_needs_pharmacist(self):
        technician = self.env['res.users'].create({
            'name': 'Técnico', 'login': 'tecnico_farmacia',
            'group_ids': [(6, 0, [self.env.ref('al_pharmacy_base.group_pharmacy_technician').id,
                                  self.env.ref('stock.group_stock_user').id])]})
        with self.assertRaises(UserError):
            self.lot_quarantine.with_user(technician).action_pharmacy_release()
        self.lot_quarantine.action_pharmacy_release()
        self.assertEqual(self.lot_quarantine.pharmacy_state, 'available')

    def test_cron_marks_expired_lots(self):
        self.lot_good.expiration_date = fields.Datetime.now() - timedelta(days=1)
        self.env['stock.lot']._cron_pharmacy_expire_lots()
        self.assertEqual(self.lot_good.pharmacy_state, 'expired')

    def test_expiry_soon_filter(self):
        self.env.company.pharmacy_expiry_alert_days = 250
        found = self.env['stock.lot'].search([('pharmacy_expiry_soon', '=', True),
                                              ('product_id', '=', self.product.id)])
        self.assertEqual(found, self.lot_quarantine)

    # Recepción -----------------------------------------------------------
    def test_reception_needs_inspection(self):
        picking = self._receipt('CTZ2502')
        with self.assertRaises(UserError):
            picking.button_validate()
        picking.pharmacy_inspection = 'conform'
        picking.button_validate()
        self.assertEqual(picking.state, 'done')

    def test_reception_rejects_expired_registry(self):
        self.product.pharmacy_registry_expiry = fields.Date.today() - timedelta(days=1)
        picking = self._receipt('CTZ2503')
        picking.pharmacy_inspection = 'conform'
        with self.assertRaises(UserError):
            picking.button_validate()

    def test_nonconform_reception_quarantines_lots(self):
        picking = self._receipt('CTZ2504')
        picking.write({'pharmacy_inspection': 'nonconform',
                       'pharmacy_inspection_note': 'Cajas húmedas.'})
        picking.button_validate()
        lot = picking.move_line_ids.lot_id
        self.assertEqual(lot.pharmacy_state, 'quarantine')

    # Bonificaciones --------------------------------------------------------
    def test_bonus_line_at_zero_price(self):
        order = self.env['purchase.order'].create({
            'partner_id': self.supplier.id,
            'order_line': [(0, 0, {'product_id': self.product.id, 'product_qty': 12,
                                   'price_unit': 10.0, 'pharmacy_bonus_qty': 1})],
        })
        main = order.order_line.filtered(lambda l: not l.pharmacy_bonus_of_id)
        bonus = main.pharmacy_bonus_line_ids
        self.assertEqual((bonus.product_qty, bonus.price_unit), (1, 0.0))
        self.assertEqual(order.amount_untaxed, 120.0)
        main.pharmacy_bonus_qty = 2
        self.assertEqual(bonus.product_qty, 2)
        self.assertEqual(bonus.price_unit, 0.0)
        main.pharmacy_bonus_qty = 0
        self.assertFalse(main.pharmacy_bonus_line_ids)

    # Control ambiental -----------------------------------------------------
    def test_out_of_range_reading_needs_action_and_logs(self):
        point = self.env['pharmacy.environment.point'].create({
            'name': 'Refrigeradora 1', 'warehouse_id': self.warehouse.id, 'point_type': 'cold',
            'temp_min': 2.0, 'temp_max': 8.0, 'humidity_max': 0.0})
        Reading = self.env['pharmacy.environment.reading']
        self.assertFalse(Reading.create({'point_id': point.id, 'temperature': 5.0}).out_of_range)
        with self.assertRaises(ValidationError):
            Reading.create({'point_id': point.id, 'temperature': 11.0})
        Reading.create({'point_id': point.id, 'temperature': 11.0,
                        'corrective_action': 'Se trasladaron las insulinas a la refrigeradora 2.'})
        entry = self.env['pharmacy.logbook.entry'].search([], order='id desc', limit=1)
        self.assertIn('Refrigeradora 1', entry.description)

    def test_reading_reminder_creates_activity(self):
        point = self.env['pharmacy.environment.point'].create({
            'name': 'Sala de ventas', 'warehouse_id': self.warehouse.id})
        self.env['pharmacy.environment.point']._cron_pharmacy_reading_reminder()
        self.assertTrue(point.activity_ids)

    # Alerta sanitaria y baja -------------------------------------------------
    def test_alert_blocks_lot_and_finds_customers(self):
        delivery = self._delivery(3)
        delivery.move_ids.picked = True
        delivery.button_validate()
        alert = self.env['pharmacy.alert'].create({
            'name': 'ALERTA 105-2025',
            'line_ids': [(0, 0, {'product_tmpl_id': self.product.product_tmpl_id.id,
                                 'lot_names': 'CTZ2401'})],
        })
        alert.action_confirm()
        self.assertEqual(self.lot_good.pharmacy_state, 'blocked')
        self.assertIn(self.customer, alert.customer_ids)
        self.assertTrue(alert.quant_ids)
        self.assertFalse(self._delivery(1).move_ids.move_line_ids)

    def test_destruction_scraps_blocked_lot(self):
        destruction = self.env['pharmacy.destruction'].create({
            'warehouse_id': self.warehouse.id,
            'line_ids': [(0, 0, {'product_id': self.product.id, 'lot_id': self.lot_quarantine.id,
                                 'location_id': self.stock.id, 'quantity': 10,
                                 'reason': 'damaged'})],
        })
        destruction.action_validate()
        self.assertEqual(destruction.state, 'done')
        self.assertEqual(destruction.scrap_ids.state, 'done')
        quantity = self.env['stock.quant']._get_available_quantity(
            self.product, self.stock, lot_id=self.lot_quarantine, strict=True)
        self.assertEqual(quantity, 0)

    def test_destruction_report_renders(self):
        destruction = self.env['pharmacy.destruction'].create({
            'warehouse_id': self.warehouse.id, 'method': 'Operador de residuos sólidos',
            'line_ids': [(0, 0, {'product_id': self.product.id, 'lot_id': self.lot_quarantine.id,
                                 'location_id': self.stock.id, 'quantity': 2})],
        })
        html, _ = self.env['ir.actions.report']._render_qweb_html(
            'al_pharmacy_stock.report_pharmacy_destruction', destruction.ids)
        self.assertIn(b'CTZ2312', html)
