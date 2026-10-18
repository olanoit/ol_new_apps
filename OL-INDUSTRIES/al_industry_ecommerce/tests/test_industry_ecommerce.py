# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestIndustryEcommerce(TransactionCase):

    def test_industry_registered(self):
        industry = self.env.ref('al_industry_ecommerce.industry_ecommerce')
        self.assertEqual(industry.ciiu_code, '4791')
        self.assertEqual(industry.module_id.name, 'al_industry_ecommerce')
        self.assertTrue(self.env['l10n_pe.economic.activity'].search_count(
            [('code', '=', industry.ciiu_code)]), 'La clase CIIU debe estar en el catálogo')

    def test_apply_to_new_company(self):
        industry = self.env.ref('al_industry_ecommerce.industry_ecommerce')
        company = self.env['res.company'].create({
            'name': 'Tienda en línea Lima', 'country_id': self.env.ref('base.pe').id})
        industry._apply(company)
        main = company.partner_id.l10n_pe_economic_activity_ids.filtered(
            lambda line: line.kind == 'principal')
        self.assertEqual(main.code, '4791')
        self.assertIn(company, industry.company_ids)

    def test_master_data(self):
        self.assertTrue(self.env.ref('al_industry_ecommerce.product_category_catalog'))
