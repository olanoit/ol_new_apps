# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPharmacyExpiry(TransactionCase):
    """Precio por vencer y canje con la droguería (mejora E11)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1)
        cls.stock = cls.warehouse.lot_stock_id
        cls.supplier = cls.env['res.partner'].create({'name': 'Droguería Andina S.A.C.'})
        cls.categ = cls.env['product.category'].create({'name': 'Antigripales'})
        cls.product = cls.env['product.product'].create({
            'name': 'Paracetamol 500 mg tableta', 'is_storable': True, 'tracking': 'lot',
            'use_expiration_date': True, 'pharmacy_ok': True, 'list_price': 1.0,
            'standard_price': 0.4,
            'seller_ids': [(0, 0, {'partner_id': cls.supplier.id, 'price': 0.4})],
        })
        cls.env['pharmacy.expiry.discount'].search([]).unlink()
        cls.env['pharmacy.expiry.discount'].create([
            {'days': 90, 'discount': 20}, {'days': 30, 'discount': 40}])

    def _lot(self, name, days, qty=10, product=None):
        product = product or self.product
        lot = self.env['stock.lot'].create({
            'name': name, 'product_id': product.id,
            'expiration_date': fields.Datetime.now() + timedelta(days=days)})
        if qty:
            self.env['stock.quant']._update_available_quantity(product, self.stock, qty, lot_id=lot)
        return lot

    # Escalas -------------------------------------------------------------
    def test_scale_by_days_to_expiry(self):
        self.assertEqual(self._lot('P20', 20, qty=0).pharmacy_expiry_discount, 40)
        lot = self._lot('P60', 60, qty=0)
        self.assertEqual(lot.pharmacy_expiry_discount, 20)
        self.assertAlmostEqual(lot.pharmacy_suggested_price, 0.8)
        self.assertEqual(self._lot('P200', 200, qty=0).pharmacy_expiry_discount, 0)

    def test_category_scale_has_priority(self):
        self.product.categ_id = self.categ
        self.env['pharmacy.expiry.discount'].create(
            {'days': 60, 'discount': 10, 'categ_id': self.categ.id})
        self.assertEqual(self._lot('P50', 50, qty=0).pharmacy_expiry_discount, 10)
        other = self.env['product.product'].create({'name': 'Gasa estéril', 'is_storable': True,
                                                    'tracking': 'lot', 'list_price': 2.0})
        self.assertEqual(self._lot('G50', 50, qty=0, product=other).pharmacy_expiry_discount, 20)

    def test_expired_lot_has_no_discount(self):
        self.assertEqual(self._lot('PV', -3, qty=0).pharmacy_expiry_discount, 0)

    # Canje ---------------------------------------------------------------
    def _return_with_lots(self):
        near = self._lot('P45', 45)
        expired = self._lot('PVEN', -5, qty=4)
        self.env['stock.lot']._cron_pharmacy_expire_lots()
        self._lot('P400', 400)  # lejos del vencimiento: no entra
        supplier_return = self.env['pharmacy.supplier.return'].create({
            'partner_id': self.supplier.id, 'warehouse_id': self.warehouse.id})
        wizard = self.env['pharmacy.supplier.return.load'].create({
            'return_id': supplier_return.id, 'source': 'seller', 'days': 90})
        wizard.action_load()
        return supplier_return, near, expired

    def test_load_lots_near_expiry_and_expired(self):
        supplier_return, near, expired = self._return_with_lots()
        lines = supplier_return.line_ids
        self.assertEqual(lines.lot_id, near | expired)
        self.assertEqual(lines.filtered(lambda l: l.lot_id == expired).reason, 'expired')
        self.assertEqual(lines.filtered(lambda l: l.lot_id == near).quantity, 10)
        self.assertAlmostEqual(supplier_return.amount_total, 14 * 0.4)
        # Cargar otra vez no duplica.
        self.env['pharmacy.supplier.return.load'].create({
            'return_id': supplier_return.id, 'source': 'seller', 'days': 90}).action_load()
        self.assertEqual(len(supplier_return.line_ids), 2)

    def test_accept_returns_stock_and_refund(self):
        supplier_return, near, expired = self._return_with_lots()
        supplier_return.action_send()
        self.assertEqual(supplier_return.state, 'sent')
        supplier_return.action_accept()
        picking = supplier_return.picking_id
        self.assertEqual(supplier_return.state, 'accepted')
        self.assertEqual(picking.move_line_ids.lot_id, near | expired)
        supplier_return.action_done()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(near.product_qty, 0)
        self.assertEqual(expired.product_qty, 0)
        self.assertEqual(supplier_return.state, 'done')
        supplier_return.action_create_refund()
        refund = supplier_return.refund_id
        self.assertEqual(refund.move_type, 'in_refund')
        self.assertEqual(refund.state, 'draft')
        self.assertEqual(refund.partner_id, self.supplier)
        self.assertAlmostEqual(refund.amount_untaxed, 14 * 0.4)

    def test_cancel_cancels_the_picking(self):
        supplier_return, near, expired = self._return_with_lots()
        supplier_return.action_accept()
        supplier_return.action_cancel()
        self.assertEqual(supplier_return.picking_id.state, 'cancel')
        self.assertEqual(supplier_return.state, 'cancel')

    def test_report_renders(self):
        supplier_return, near, expired = self._return_with_lots()
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_pharmacy_stock.report_pharmacy_supplier_return', supplier_return.ids)[0]
        self.assertIn(b'P45', html)
        self.assertIn(b'Droguer', html)
