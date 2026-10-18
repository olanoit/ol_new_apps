# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged('post_install', '-at_install')
class TestIndustryBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Botica Santa Rosa', 'country_id': cls.env.ref('base.pe').id})
        cls.industry = cls.env['al.industry'].create({
            'name': 'Industria de prueba', 'code': 'test_industry', 'ciiu_code': '4772'})

    def _main_activity(self, company):
        return self.env['l10n_pe.partner.economic.activity'].search(
            [('partner_id', '=', company.partner_id.id), ('kind', '=', 'principal')])

    def test_apply_sets_main_activity(self):
        self.industry._apply(self.company)
        self.assertEqual(self._main_activity(self.company).code, '4772')
        self.assertIn(self.company, self.industry.company_ids)

    def test_apply_keeps_existing_activity(self):
        activity = self.env['l10n_pe.economic.activity'].search([('code', '=', '4711')], limit=1)
        self.env['l10n_pe.partner.economic.activity'].create({
            'partner_id': self.company.partner_id.id, 'kind': 'principal',
            'activity_id': activity.id})
        self.industry._apply(self.company)
        self.industry._apply(self.company)
        self.assertEqual(self._main_activity(self.company).code, '4711')

    def test_apply_only_admin(self):
        user = new_test_user(self.env, login='industry_user', groups='base.group_user')
        with self.assertRaises(UserError):
            self.industry.with_user(user).action_apply_current_company()
