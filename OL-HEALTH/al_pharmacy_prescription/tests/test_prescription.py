# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPrescription(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Ingredient = cls.env['pharmacy.ingredient']
        cls.azithro = Ingredient._get_or_create('Azitromicina')
        tablet = cls.env.ref('al_pharmacy_base.dosage_form_tablet')

        def product(name, product_type):
            return cls.env['product.product'].create({
                'name': name, 'is_storable': True, 'pharmacy_ok': True,
                'pharmacy_sale_condition': 'prescription', 'pharmacy_product_type': product_type,
                'pharmacy_dosage_form_id': tablet.id,
                'pharmacy_ingredient_line_ids': [(0, 0, {
                    'ingredient_id': cls.azithro.id, 'strength': 500, 'strength_unit': 'mg'})],
            })
        cls.brand = product('Zitromax 500 mg', 'innovator')
        cls.generic = product('Azitromicina 500 mg tableta', 'generic_dci')
        cls.prescriber = cls.env['res.partner'].create({
            'name': 'Dr. Jorge Salazar', 'pharmacy_is_prescriber': True,
            'pharmacy_profession': 'physician', 'pharmacy_prescriber_license': '045678'})
        cls.patient = cls.env['res.partner'].create({'name': 'Carmen Rojas'})

    def _prescription(self, **vals):
        return self.env['pharmacy.prescription'].create({
            'prescriber_id': self.prescriber.id, 'patient_id': self.patient.id,
            'line_ids': [(0, 0, {'product_id': self.brand.id, 'quantity': 6,
                                 'posology': '1 tableta al día'})],
            **vals,
        })

    def test_validate_requires_data(self):
        prescription = self.env['pharmacy.prescription'].create({
            'line_ids': [(0, 0, {'product_id': self.brand.id, 'quantity': 3})]})
        with self.assertRaises(ValidationError):
            prescription.action_validate()
        prescription.write({'prescriber_id': self.prescriber.id, 'patient_id': self.patient.id})
        prescription.action_validate()
        self.assertEqual(prescription.state, 'valid')

    def test_partial_and_full_dispensation_with_alternative(self):
        prescription = self._prescription()
        prescription.action_validate()
        first = prescription._dispense(self.generic, 3, source='TPV/0001')
        self.assertTrue(first.is_alternative)
        self.assertEqual(prescription.state, 'partial')
        prescription._dispense(self.brand, 3)
        self.assertEqual(prescription.state, 'dispensed')
        with self.assertRaises(UserError):
            prescription._dispense(self.brand, 1)

    def test_cannot_exceed_prescribed_quantity(self):
        prescription = self._prescription()
        prescription.action_validate()
        with self.assertRaises(UserError):
            prescription._dispense(self.brand, 7)

    def test_dci_line_accepts_any_product_with_the_ingredient(self):
        prescription = self.env['pharmacy.prescription'].create({
            'prescriber_id': self.prescriber.id, 'patient_id': self.patient.id,
            'line_ids': [(0, 0, {'ingredient_id': self.azithro.id, 'quantity': 3})]})
        prescription.action_validate()
        dispensation = prescription._dispense(self.generic, 3)
        self.assertFalse(dispensation.is_alternative)

    def test_expired_prescription(self):
        prescription = self._prescription(
            date=fields.Date.today() - timedelta(days=40), validity_days=30)
        prescription.action_validate()
        with self.assertRaises(UserError):
            prescription._dispense(self.brand, 1)
        self.env['pharmacy.prescription']._cron_expire_prescriptions()
        self.assertEqual(prescription.state, 'expired')

    def test_disabled_prescriber_is_rejected(self):
        self.prescriber.pharmacy_prescriber_status = 'disabled'
        with self.assertRaises(ValidationError):
            self._prescription().action_validate()

    def test_allergy_warning(self):
        self.patient.pharmacy_allergy_ids = [(4, self.azithro.id)]
        self.assertEqual(self._prescription()._allergy_warnings(), self.azithro)

    def test_dispensation_cannot_be_deleted(self):
        prescription = self._prescription()
        prescription.action_validate()
        dispensation = prescription._dispense(self.brand, 1)
        with self.assertRaises(UserError):
            dispensation.unlink()

    def test_reports_render(self):
        prescription = self._prescription()
        prescription.action_validate()
        dispensation = prescription._dispense(self.brand, 1)
        Report = self.env['ir.actions.report']
        html, _ = Report._render_qweb_html(
            'al_pharmacy_prescription.report_prescription_book', prescription.ids)
        self.assertIn(b'Libro de recetas', html)
        html, _ = Report._render_qweb_html(
            'al_pharmacy_prescription.report_dispensation_label', dispensation.ids)
        self.assertIn(b'Zitromax', html)
