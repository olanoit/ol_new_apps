# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestPresentationUnitCode(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env['product.template'].create({
            'name': 'Amoxicilina 500 mg DEMO', 'type': 'consu',
            'uom_id': cls.env.ref('uom.product_uom_unit').id,
        })

    def _presentation(self, name, factor):
        return self.env['pharmacy.presentation'].create({
            'product_tmpl_id': self.product.id, 'name': name, 'factor': factor, 'price': 10.0})

    def test_known_presentation_has_its_sunat_code(self):
        self.assertEqual(self._presentation('Caja', 100).uom_id.l10n_pe_edi_measure_unit_code, 'BX')
        self.assertEqual(self._presentation('Frasco', 2).uom_id.l10n_pe_edi_measure_unit_code, 'BO')

    def test_other_presentation_uses_product_unit_code(self):
        blister = self._presentation('Blíster', 10)
        self.assertEqual(blister.uom_id.l10n_pe_edi_measure_unit_code, 'NIU')
