# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged('post_install', '-at_install')
class TestCmpVerification(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doctor = cls.env['res.partner'].create({
            'name': 'Dr. Jorge Salazar', 'pharmacy_is_prescriber': True,
            'pharmacy_profession': 'physician', 'pharmacy_prescriber_license': '045678'})

    def test_open_portal(self):
        action = self.doctor.action_pharmacy_open_cmp()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertIn('conoceatumedico.cmp.org.pe', action['url'])

    def test_open_portal_needs_license(self):
        self.doctor.pharmacy_prescriber_license = False
        with self.assertRaises(UserError):
            self.doctor.action_pharmacy_open_cmp()

    def test_pharmacist_records_verification(self):
        self.doctor.action_pharmacy_cmp_enabled()
        self.assertEqual(self.doctor.pharmacy_prescriber_status, 'enabled')
        self.assertEqual(self.doctor.pharmacy_prescriber_checked_by_id, self.env.user)
        self.assertTrue(self.doctor.pharmacy_prescriber_checked)

    def test_technician_cannot_verify(self):
        technician = new_test_user(self.env, login='tecnico_cmp',
                                   groups='al_pharmacy_base.group_pharmacy_technician')
        with self.assertRaises(UserError):
            self.doctor.with_user(technician).action_pharmacy_cmp_enabled()

    def test_disabled_doctor_blocks_prescription(self):
        self.doctor.action_pharmacy_cmp_disabled()
        product = self.env['product.product'].create({'name': 'Losartán 50 mg tableta',
                                                      'pharmacy_ok': True})
        prescription = self.env['pharmacy.prescription'].create({
            'prescriber_id': self.doctor.id,
            'patient_id': self.env['res.partner'].create({'name': 'Julia Ramos'}).id,
            'line_ids': [(0, 0, {'product_id': product.id, 'quantity': 30})]})
        with self.assertRaises(ValidationError):
            prescription.action_validate()
