# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestPosDispensation(TestPoSCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        cls.product = cls.create_product('Amoxicilina 500 mg cápsula', cls.categ_basic, 1.0)
        cls.product.product_tmpl_id.write({
            'pharmacy_ok': True, 'pharmacy_sale_condition': 'prescription',
            'is_storable': True, 'tracking': 'lot'})
        cls.customer = cls.env['res.partner'].create({'name': 'Pedro Huamán', 'additional_identifiers': {'PE_DNI': '44556677'}})

    def _paid_order(self, qty=10, lot_name=False, **vals):
        order = self.env['pos.order'].create({
            'session_id': self.pos_session.id,
            'partner_id': self.customer.id,
            'lines': [(0, 0, {
                'product_id': self.product.id, 'qty': qty, 'price_unit': 1.0,
                'price_subtotal': qty, 'price_subtotal_incl': qty,
                'pack_lot_ids': [(0, 0, {'lot_name': lot_name})] if lot_name else [],
            })],
            'amount_tax': 0, 'amount_total': qty, 'amount_paid': qty, 'amount_return': 0,
            **vals,
        })
        order.state = 'paid'
        order._pharmacy_register_dispensation()
        return order

    def test_prescription_registered_from_pos(self):
        self.open_new_session()
        lot = self.env['stock.lot'].create({'name': 'AMX2601', 'product_id': self.product.id})
        order = self._paid_order(
            lot_name='AMX2601', pharmacy_prescription_number='000123',
            pharmacy_prescriber_name='Dra. Ana Torres', pharmacy_prescriber_license='067890')
        prescription = order.sudo().pharmacy_prescription_id
        self.assertEqual(prescription.state, 'dispensed')
        self.assertEqual(prescription.prescriber_id.pharmacy_prescriber_license, '067890')
        self.assertEqual(prescription.patient_id, self.customer)
        self.assertEqual(prescription.dispensation_ids.lot_id, lot)
        self.assertEqual(prescription.dispensation_ids.source, order.name)

    def test_exception_and_alert_go_to_logbook(self):
        self.open_new_session()
        pharmacist = self.env['res.users'].create({
            'name': 'Q.F. Luis Paredes', 'login': 'qf_luis_paredes',
            'group_ids': [(6, 0, [self.env.ref('al_pharmacy_base.group_pharmacy_pharmacist').id])]})
        order = self._paid_order(pharmacy_exception_user_id=pharmacist.id,
                                 pharmacy_no_pharmacist_alert=True)
        entries = self.env['pharmacy.logbook.entry'].sudo().search(
            [('res_model', '=', 'pos.order'), ('res_id', '=', order.id)])
        self.assertEqual(set(entries.mapped('entry_type')), {'exception', 'alert'})
        self.assertFalse(order.pharmacy_prescription_id)

    def test_missing_data_does_not_block_the_sale(self):
        """Receta sin prescriptor: la venta se guarda y el libro lo anota."""
        self.open_new_session()
        order = self._paid_order(pharmacy_prescription_number='000999')
        self.assertFalse(order.sudo().pharmacy_prescription_id)
        entry = self.env['pharmacy.logbook.entry'].sudo().search(
            [('res_model', '=', 'pos.order'), ('res_id', '=', order.id)])
        self.assertIn('no se pudo registrar', entry.description)

    def test_existing_lots_only_available_and_fefo(self):
        self.open_new_session()
        stock = self.config.picking_type_id.default_location_src_id
        now = fields.Datetime.now()
        Lot = self.env['stock.lot']
        late = Lot.create({'name': 'L-LATE', 'product_id': self.product.id,
                           'expiration_date': now + timedelta(days=300)})
        soon = Lot.create({'name': 'L-SOON', 'product_id': self.product.id,
                           'expiration_date': now + timedelta(days=30)})
        blocked = Lot.create({'name': 'L-BLOCK', 'product_id': self.product.id,
                              'expiration_date': now + timedelta(days=10)})
        for lot in (late, soon, blocked):
            self.env['stock.quant']._update_available_quantity(self.product, stock, 5, lot_id=lot)
        blocked._pharmacy_set_state('blocked', 'Alerta')
        lots = self.env['pos.order.line'].get_existing_lots(
            self.env.company.id, self.config.id, self.product.id)
        self.assertEqual([lot['name'] for lot in lots], ['L-SOON', 'L-LATE'])
