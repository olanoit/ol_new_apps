# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestIndustryPharmacy(TransactionCase):

    def test_industry_registered(self):
        industry = self.env.ref('al_industry_pharmacy.industry_pharmacy')
        self.assertEqual(industry.ciiu_code, '4772')
        self.assertEqual(industry.module_id.name, 'al_industry_pharmacy')
        self.assertTrue(self.env['l10n_pe.economic.activity'].search_count(
            [('code', '=', industry.ciiu_code)]), 'La clase CIIU debe estar en el catálogo')

    def test_apply_to_new_company(self):
        industry = self.env.ref('al_industry_pharmacy.industry_pharmacy')
        company = self.env['res.company'].create({
            'name': 'Farmacia y botica Lima', 'country_id': self.env.ref('base.pe').id})
        industry._apply(company)
        main = company.partner_id.l10n_pe_economic_activity_ids.filtered(
            lambda line: line.kind == 'principal')
        self.assertEqual(main.code, '4772')
        self.assertIn(company, industry.company_ids)

    def test_pos_theme_installed(self):
        self.assertEqual(self.env['ir.module.module']._get('al_pos_theme').state, 'installed')

    def test_master_data(self):
        self.assertTrue(self.env.ref('al_industry_pharmacy.product_category_medicines'))

    def test_groups_for_internal_users(self):
        implied = self.env.ref('base.group_user').all_implied_ids
        self.assertIn(self.env.ref('stock.group_production_lot'), implied)
        self.assertIn(self.env.ref('product_expiry.group_expiry_date_on_delivery_slip'), implied)
        self.assertIn(self.env.ref('stock.group_lot_on_delivery_slip'), implied)

    def test_medicines_leave_by_expiry(self):
        fefo = self.env.ref('product_expiry.removal_fefo')
        for xmlid in ('product_category_medicines', 'product_category_medicines_rx'):
            category = self.env.ref('al_industry_pharmacy.%s' % xmlid)
            self.assertEqual(category.removal_strategy_id, fefo)

    def test_prescription_filter(self):
        product = self.env['product.template'].create({
            'name': 'Clonazepam 2 mg', 'type': 'consu', 'is_storable': True,
            'tracking': 'lot', 'pharmacy_sale_condition': 'controlled'})
        found = self.env['product.template'].search(
            [('pharmacy_sale_condition', 'in', ('prescription', 'controlled'))])
        self.assertIn(product, found)
