# -*- coding: utf-8 -*-
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestPosPresentationTour(TestPointOfSaleHttpCommon):

    def test_sell_blister_in_pos(self):
        product = self.env['product.template'].create({
            'name': 'Loratadina 10 mg', 'type': 'consu', 'available_in_pos': True,
            'list_price': 0.20, 'taxes_id': [(6, 0, [])],
        })
        self.env['pharmacy.presentation'].create({
            'product_tmpl_id': product.id, 'name': 'Blíster', 'factor': 7, 'price': 1.00})
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('al_pharmacy_pos_presentation')

        order = self.env['pos.order'].search(
            [('session_id', '=', self.main_pos_config.current_session_id.id)], limit=1)
        blister_line = order.lines.filtered('pharmacy_presentation_id')
        self.assertEqual(blister_line.qty, 7)
        self.assertAlmostEqual(blister_line.price_unit * 7, 1.0, places=9)
        self.assertEqual(order.amount_total, 1.20)

    def test_presentation_with_pricelist(self):
        product = self.env['product.template'].create({
            'name': 'Loratadina 10 mg', 'type': 'consu', 'available_in_pos': True,
            'list_price': 0.20, 'taxes_id': [(6, 0, [])],
        })
        self.env['pharmacy.presentation'].create({
            'product_tmpl_id': product.id, 'name': 'Blíster', 'factor': 7, 'price': 1.00})
        agreement = self.env['product.pricelist'].create({
            'name': 'Convenio 10%', 'currency_id': self.main_pos_config.currency_id.id,
            'item_ids': [(0, 0, {'compute_price': 'percentage', 'applied_on': '3_global',
                                 'percent_price': 10})],
        })
        self.main_pos_config.write({'available_pricelist_ids': [(4, agreement.id)]})
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('al_pharmacy_pos_presentation_pricelist')

        order = self.env['pos.order'].search(
            [('session_id', '=', self.main_pos_config.current_session_id.id)], limit=1)
        self.assertEqual(order.pricelist_id, agreement)
        self.assertEqual(len(order.lines), 2)
        for line in order.lines:
            self.assertEqual(line.pharmacy_presentation_id.factor, 7)
            self.assertAlmostEqual(line.price_unit * 7, 0.90, places=9)
        self.assertAlmostEqual(order.amount_total, 1.80)

    def test_dispense_generic_with_prescription(self):
        ingredient = self.env['pharmacy.ingredient']._get_or_create('Ciprofloxacino')
        tablet = self.env.ref('al_pharmacy_base.dosage_form_tablet')
        common = {
            'type': 'consu', 'available_in_pos': True, 'taxes_id': [(6, 0, [])],
            'pharmacy_ok': True, 'pharmacy_sale_condition': 'prescription',
            'pharmacy_dosage_form_id': tablet.id,
            'pharmacy_ingredient_line_ids': [(0, 0, {'ingredient_id': ingredient.id,
                                                     'strength': 500, 'strength_unit': 'mg'})],
        }
        self.env['product.template'].create({
            **common, 'name': 'Cipro Marca 500 mg', 'list_price': 6.0,
            'pharmacy_product_type': 'innovator'})
        generic = self.env['product.template'].create({
            **common, 'name': 'Ciprofloxacino 500 mg tableta', 'list_price': 2.0,
            'pharmacy_product_type': 'generic_dci'})
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('al_pharmacy_pos_dispensation')

        order = self.env['pos.order'].search(
            [('session_id', '=', self.main_pos_config.current_session_id.id)], limit=1)
        self.assertEqual(order.lines.product_id.product_tmpl_id, generic)
        prescription = order.sudo().pharmacy_prescription_id
        self.assertEqual(prescription.prescription_number, '000321')
        self.assertEqual(prescription.prescriber_id.pharmacy_prescriber_license, '067890')
        self.assertEqual(prescription.patient_id.name, 'Rosa Mendoza')
        self.assertEqual(prescription.state, 'dispensed')
        # El cajero de la prueba no es químico farmacéutico: queda el aviso.
        self.assertTrue(order.pharmacy_no_pharmacist_alert)
