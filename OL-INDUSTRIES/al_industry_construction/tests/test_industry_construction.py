# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestIndustryConstruction(TransactionCase):

    def test_industry_registered(self):
        industry = self.env.ref('al_industry_construction.industry_construction')
        self.assertEqual(industry.ciiu_code, '4100')
        self.assertEqual(industry.module_id.name, 'al_industry_construction')
        self.assertTrue(self.env['l10n_pe.economic.activity'].search_count(
            [('code', '=', industry.ciiu_code)]), 'La clase CIIU debe estar en el catálogo')

    def test_apply_to_new_company(self):
        industry = self.env.ref('al_industry_construction.industry_construction')
        company = self.env['res.company'].create({
            'name': 'Constructora DEMO', 'country_id': self.env.ref('base.pe').id})
        industry._apply(company)
        main = company.partner_id.l10n_pe_economic_activity_ids.filtered(
            lambda line: line.kind == 'principal')
        self.assertEqual(main.code, '4100')
        self.assertIn(company, industry.company_ids)
        self.assertEqual(company.construction_profile_id,
                         self.env.ref('al_construction_planner.profile_construction'))

    def test_master_data(self):
        self.assertTrue(self.env.ref('al_industry_construction.product_category_materials'))

    def test_groups_for_internal_users(self):
        implied = self.env.ref('base.group_user').all_implied_ids
        self.assertIn(self.env.ref('al_construction_planner.group_planner_feature_control'), implied)
        self.assertIn(self.env.ref('al_construction_planner.group_planner_feature_progress'), implied)
        self.assertIn(self.env.ref('stock.group_stock_multi_locations'), implied)
