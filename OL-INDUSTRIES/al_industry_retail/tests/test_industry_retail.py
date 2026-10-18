# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestIndustryRetail(TransactionCase):

    def test_industry_registered(self):
        industry = self.env.ref('al_industry_retail.industry_retail')
        self.assertEqual(industry.ciiu_code, '4711')
        self.assertEqual(industry.module_id.name, 'al_industry_retail')
        self.assertTrue(self.env['l10n_pe.economic.activity'].search_count(
            [('code', '=', industry.ciiu_code)]), 'La clase CIIU debe estar en el catálogo')

    def test_apply_to_new_company(self):
        industry = self.env.ref('al_industry_retail.industry_retail')
        company = self.env['res.company'].create({
            'name': 'Bodega y minimarket Lima', 'country_id': self.env.ref('base.pe').id})
        industry._apply(company)
        main = company.partner_id.l10n_pe_economic_activity_ids.filtered(
            lambda line: line.kind == 'principal')
        self.assertEqual(main.code, '4711')
        self.assertIn(company, industry.company_ids)

    def test_pos_theme_installed(self):
        self.assertEqual(self.env['ir.module.module']._get('al_pos_theme').state, 'installed')

    def test_master_data(self):
        self.assertTrue(self.env.ref('al_industry_retail.product_category_groceries'))
