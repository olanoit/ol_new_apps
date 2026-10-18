# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPharmacyMaster(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Ingredient = cls.env['pharmacy.ingredient']
        # Naproxeno no está en los datos de demostración: las equivalencias
        # de la prueba no se mezclan con productos de la base.
        cls.naproxen = Ingredient._get_or_create('Naproxeno sódico')
        cls.paracetamol = Ingredient._get_or_create('Paracetamol')
        cls.caffeine = Ingredient._get_or_create('Cafeína')
        cls.tablet = cls.env.ref('al_pharmacy_base.dosage_form_tablet')
        cls.syrup = cls.env.ref('al_pharmacy_base.dosage_form_syrup')

    def _product(self, name, ingredients, form, price, product_type='generic_brand'):
        return self.env['product.template'].create({
            'name': name, 'type': 'consu', 'pharmacy_ok': True, 'list_price': price,
            'pharmacy_dosage_form_id': form.id, 'pharmacy_product_type': product_type,
            'pharmacy_ingredient_line_ids': [(0, 0, {
                'ingredient_id': ingredient.id, 'strength': strength, 'strength_unit': 'mg'})
                for ingredient, strength in ingredients],
        })

    def test_composition_label(self):
        product = self._product('Panadol Extra', [(self.paracetamol, 500), (self.caffeine, 65)],
                                self.tablet, 9.0)
        self.assertEqual(product.pharmacy_composition, 'Paracetamol 500 mg + Cafeína 65 mg')

    def test_equivalents_same_ingredient_strength_and_form(self):
        brand = self._product('Apronax', [(self.naproxen, 550)], self.tablet, 6.0, 'innovator')
        generic = self._product('Naproxeno 550 mg tableta', [(self.naproxen, 550)],
                                self.tablet, 1.5, 'generic_dci')
        other_strength = self._product('Naproxeno 275 mg', [(self.naproxen, 275)],
                                       self.tablet, 2.0, 'generic_dci')
        other_form = self._product('Naproxeno suspensión', [(self.naproxen, 550)],
                                   self.syrup, 8.0, 'generic_dci')
        self.assertEqual(brand.pharmacy_equivalent_ids, generic)
        self.assertNotIn(other_strength, brand.pharmacy_equivalent_ids)
        self.assertNotIn(other_form, brand.pharmacy_equivalent_ids)

    def test_alternatives_generic_first_then_cheapest(self):
        brand = self._product('Apronax', [(self.naproxen, 550)], self.tablet, 6.0, 'innovator')
        generic_cheap = self._product('Naproxeno Genfar', [(self.naproxen, 550)], self.tablet, 1.2,
                                      'generic_dci')
        generic_dear = self._product('Naproxeno Portugal', [(self.naproxen, 550)], self.tablet, 2.0,
                                     'generic_dci')
        branded_generic = self._product('Naprox', [(self.naproxen, 550)],
                                        self.tablet, 1.0, 'generic_brand')
        self.assertEqual(brand._pharmacy_sorted_alternatives(),
                         generic_cheap + generic_dear + branded_generic)

    def test_ingredient_get_or_create_is_case_insensitive(self):
        self.assertEqual(self.env['pharmacy.ingredient']._get_or_create('  paracetamol '),
                         self.paracetamol)


@tagged('post_install', '-at_install')
class TestPharmacyEstablishment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.env.company.id)], limit=1)
        cls.pharmacist = cls.env['hr.employee'].create({
            'name': 'Rosa Quispe', 'pharmacy_role': 'pharmacist',
            'pharmacy_license_number': '12345'})

    def test_logbook_is_append_only(self):
        entry = self.env['pharmacy.logbook.entry'].create({
            'entry_type': 'incident', 'description': 'Corte de luz de 20 minutos.'})
        self.assertTrue(entry.name.startswith('OC/'))
        with self.assertRaises(UserError):
            entry.description = 'Otra cosa'
        with self.assertRaises(UserError):
            entry.unlink()
        correction = self.env['pharmacy.logbook.entry'].create({
            'entry_type': 'incident', 'description': 'Fueron 30 minutos.',
            'correction_of_id': entry.id})
        self.assertEqual(correction.correction_of_id, entry)

    def test_replacement_shift_writes_logbook(self):
        now = fields.Datetime.now()
        shift = self.env['pharmacy.shift'].create({
            'employee_id': self.pharmacist.id, 'warehouse_id': self.warehouse.id,
            'date_start': now - timedelta(hours=1), 'date_end': now + timedelta(hours=7),
            'role': 'replacement'})
        entry = self.env['pharmacy.logbook.entry'].search(
            [('entry_type', '=', 'absence'), ('warehouse_id', '=', self.warehouse.id)],
            order='id desc', limit=1)
        self.assertIn('Rosa Quispe', entry.description)
        self.assertEqual(self.env['pharmacy.shift']._get_pharmacists_on_duty(self.warehouse),
                         shift.employee_id)

    def test_shift_dates(self):
        now = fields.Datetime.now()
        with self.assertRaises(ValidationError):
            self.env['pharmacy.shift'].create({
                'employee_id': self.pharmacist.id, 'warehouse_id': self.warehouse.id,
                'date_start': now, 'date_end': now - timedelta(hours=1)})

    def test_logbook_report_renders(self):
        entry = self.env['pharmacy.logbook.entry'].create({
            'entry_type': 'other', 'description': 'Inventario anual realizado.'})
        html, _ = self.env['ir.actions.report']._render_qweb_html(
            'al_pharmacy_base.report_pharmacy_logbook', entry.ids)
        self.assertIn(b'Inventario anual realizado', html)
