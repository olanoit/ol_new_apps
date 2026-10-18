# -*- coding: utf-8 -*-
from datetime import date

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestControlled(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1)
        cls.stock = cls.warehouse.lot_stock_id
        cls.clonazepam = cls.env['product.product'].create({
            'name': 'Clonazepam 2 mg tableta', 'is_storable': True, 'pharmacy_ok': True,
            'pharmacy_sanitary_registry': 'EN-03117',
            'pharmacy_control_list': 'IVA', 'pharmacy_sale_condition': 'prescription'})
        cls.morphine = cls.env['product.product'].create({
            'name': 'Morfina 10 mg/mL inyectable', 'is_storable': True, 'pharmacy_ok': True,
            'pharmacy_sanitary_registry': 'EN-02254',
            'pharmacy_control_list': 'IIA', 'pharmacy_sale_condition': 'controlled'})
        cls.prescriber = cls.env['res.partner'].create({
            'name': 'Dra. Elena Vargas', 'pharmacy_is_prescriber': True,
            'pharmacy_prescriber_license': '051234'})
        cls.patient = cls.env['res.partner'].create({
            'name': 'Mario Cárdenas', 'vat': '40112233', 'street': 'Av. Arequipa 1234',
            'phone': '987654321'})

    def _prescription(self, product, prescription_type='common', **vals):
        prescription = self.env['pharmacy.prescription'].create({
            'prescription_type': prescription_type,
            'validity_days': 3 if prescription_type == 'special' else 30,
            'prescriber_id': self.prescriber.id, 'patient_id': self.patient.id,
            'diagnosis': 'Dolor oncológico',
            'line_ids': [(0, 0, {'product_id': product.id, 'quantity': 10,
                                 'posology': '1 ampolla cada 12 horas'})],
            **vals,
        })
        prescription.action_validate()
        return prescription

    def test_control_list_fixes_condition_and_book(self):
        self.assertEqual(self.morphine.pharmacy_control_book, 'narcotic')
        self.assertEqual(self.clonazepam.pharmacy_control_book, 'psychotropic')
        with self.assertRaises(ValidationError):
            self.morphine.pharmacy_sale_condition = 'prescription'

    def test_special_prescription_requires_data_and_three_days(self):
        with self.assertRaises(ValidationError):
            self._prescription(self.morphine, 'special', validity_days=10)
        self.patient.phone = False
        with self.assertRaises(ValidationError):
            self._prescription(self.morphine, 'special')

    def test_special_list_needs_special_prescription_and_purchaser(self):
        common = self._prescription(self.morphine)
        with self.assertRaises(UserError):
            common._dispense(self.morphine, 2, purchaser_name='Mario Cárdenas',
                             purchaser_vat='40112233')
        special = self._prescription(self.morphine, 'special')
        with self.assertRaises(UserError):
            special._dispense(self.morphine, 2)
        special._dispense(self.morphine, 2, purchaser_name='Ana Cárdenas', purchaser_vat='41223344')
        self.assertTrue(special.retained)
        self.assertTrue(special.retention_folio.startswith('F-'))

    def test_retained_list_gets_folio(self):
        prescription = self._prescription(self.clonazepam)
        prescription._dispense(self.clonazepam, 10)
        self.assertTrue(prescription.retained and prescription.retention_folio)

    def _move(self, product, qty, source, dest, origin=False, partner=False):
        picking_type = self.warehouse.out_type_id if dest.usage == 'customer' else self.warehouse.in_type_id
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id, 'location_id': source.id,
            'location_dest_id': dest.id, 'origin': origin, 'partner_id': partner and partner.id,
            'move_ids': [(0, 0, {'product_id': product.id, 'product_uom_qty': qty,
                                 'product_uom': product.uom_id.id, 'location_id': source.id,
                                 'location_dest_id': dest.id})],
        })
        if picking_type.code == 'incoming':
            picking.pharmacy_inspection = 'conform'
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.quantity = qty
        picking.move_ids.picked = True
        picking.with_context(skip_backorder=True).button_validate()
        return picking

    def test_book_and_quarterly_balance(self):
        supplier = self.env.ref('stock.stock_location_suppliers')
        customer = self.env.ref('stock.stock_location_customers')
        self._move(self.clonazepam, 100, supplier, self.stock)
        prescription = self._prescription(self.clonazepam)
        prescription._dispense(self.clonazepam, 10, source='TPV/0042')
        self._move(self.clonazepam, 10, self.stock, customer, origin='TPV/0042', partner=self.patient)
        today = fields.Date.today()
        report = self.env['pharmacy.controlled.report'].create({
            'book': 'psychotropic', 'warehouse_id': self.warehouse.id,
            'year': today.year, 'quarter': str((today.month - 1) // 3 + 1)})
        rows = [r for r in report._get_book_lines() if r['product'] == self.clonazepam]
        self.assertEqual([(r['qty_in'], r['qty_out'], r['balance']) for r in rows],
                         [(100.0, 0.0, 100.0), (0.0, 10.0, 90.0)])
        self.assertEqual(rows[1]['prescription'], prescription.retention_folio)
        balance = [r for r in report._get_balance_lines() if r['product'] == self.clonazepam]
        self.assertEqual((balance[0]['initial'], balance[0]['qty_in'], balance[0]['qty_out'],
                          balance[0]['final']), (0.0, 100.0, 10.0, 90.0))
        self.assertIn(prescription, report._get_period_prescriptions())
        for report_type in ('book', 'balance'):
            report.report_type = report_type
            xmlid = ('al_l10n_pe_pharmacy_controlled.report_controlled_book' if report_type == 'book'
                     else 'al_l10n_pe_pharmacy_controlled.report_controlled_balance')
            html, _ = self.env['ir.actions.report']._render_qweb_html(xmlid, report.ids)
            self.assertIn(b'Clonazepam', html)
            report.action_export_xlsx()
            self.assertTrue(report.file_data)

    def test_quarter_dates(self):
        report = self.env['pharmacy.controlled.report'].create({
            'book': 'narcotic', 'warehouse_id': self.warehouse.id, 'year': 2026, 'quarter': '4'})
        self.assertEqual((report.date_from, report.date_to), (date(2026, 10, 1), date(2026, 12, 31)))
