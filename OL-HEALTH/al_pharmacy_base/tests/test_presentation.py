# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPresentation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.unit = cls.env.ref('uom.product_uom_unit')
        cls.product = cls.env['product.template'].create({
            'name': 'Paracetamol 500 mg DEMO', 'type': 'consu', 'list_price': 0.20,
            'uom_id': cls.unit.id,
        })

    def test_presentation_creates_its_uom(self):
        box = self.env['pharmacy.presentation'].create({
            'product_tmpl_id': self.product.id, 'name': 'Caja', 'factor': 100, 'price': 12.0})
        self.assertEqual(box.display_name, 'Caja x 100')
        self.assertEqual(box.uom_id.relative_uom_id, self.unit)
        self.assertEqual(box.uom_id.relative_factor, 100)
        self.assertIn(box.uom_id, self.product.uom_ids)
        self.assertAlmostEqual(box.unit_price, 0.12)

    def test_uom_is_reused(self):
        other = self.env['product.template'].create({
            'name': 'Ibuprofeno 400 mg DEMO', 'type': 'consu', 'uom_id': self.unit.id})
        first = self.env['pharmacy.presentation'].create({
            'product_tmpl_id': self.product.id, 'name': 'Blíster', 'factor': 10, 'price': 1.5})
        second = self.env['pharmacy.presentation'].create({
            'product_tmpl_id': other.id, 'name': 'Blíster', 'factor': 10, 'price': 2.0})
        self.assertEqual(first.uom_id, second.uom_id)

    def test_unit_price_is_not_rounded(self):
        blister = self.env['pharmacy.presentation'].create({
            'product_tmpl_id': self.product.id, 'name': 'Blíster', 'factor': 7, 'price': 1.0})
        # Campo informativo a 6 decimales: 0,142857, no 0,14 (que sumaría 0,98).
        self.assertAlmostEqual(blister.unit_price, 0.142857, places=6)
        self.assertAlmostEqual(blister.unit_price * 7, 1.0, places=5)

    def test_quantity_in_presentations(self):
        box = self.env['pharmacy.presentation'].create({
            'product_tmpl_id': self.product.id, 'name': 'Caja', 'factor': 100, 'price': 12.0})
        self.assertEqual(box._get_quantity_in_presentations(300), 3)
        self.assertIsNone(box._get_quantity_in_presentations(150))

    def test_presentation_needs_more_than_one_unit(self):
        with self.assertRaises(ValidationError):
            self.env['pharmacy.presentation'].create({
                'product_tmpl_id': self.product.id, 'name': 'Unidad', 'factor': 1, 'price': 0.2})
