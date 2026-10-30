# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.al_account_base.tests.common import use_pe_company


@tagged('post_install', '-at_install')
class TestPeCheck(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        cls.company._l10n_pe_check_setup()
        ChartTemplate = cls.env['account.chart.template'].with_company(cls.company)
        cls.portfolio = ChartTemplate.ref('l10n_pe_third_party_check')
        cls.rejected = ChartTemplate.ref('l10n_pe_rejected_check')
        Journal = cls.env['account.journal']
        cls.bank = Journal.search([*Journal._check_company_domain(cls.company), ('type', '=', 'bank')], limit=1)
        Partner = cls.env['res.partner']
        cls.customer = Partner.create({'name': 'Cliente RUC (test)', 'vat': '20100070970', 'is_company': True,
                                       'country_id': cls.env.ref('base.pe').id})
        cls.person = Partner.create({'name': 'Cliente DNI (test)', 'additional_identifiers': {'PE_DNI': '41234567'},
                                     'country_id': cls.env.ref('base.pe').id})
        cls.supplier = Partner.create({'name': 'Proveedor (test)', 'vat': '20131312955', 'is_company': True,
                                       'country_id': cls.env.ref('base.pe').id})

    def _receive(self, partner, number, amount, payment_date, date_received=None):
        line = self.portfolio.inbound_payment_method_line_ids.filtered(
            lambda l: l.code == 'new_third_party_checks')
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound', 'partner_type': 'customer', 'partner_id': partner.id,
            'journal_id': self.portfolio.id, 'payment_method_line_id': line.id,
            'date': date_received or payment_date,
            'l10n_latam_new_check_ids': [Command.create({
                'name': number, 'payment_date': payment_date,
                'amount': amount})],
        })
        payment.action_post()
        return payment

    def _transfer(self, checks, journal, when):
        return self.env['l10n_latam.payment.mass.transfer'].with_context(
            active_model='l10n_latam.check', active_ids=checks.ids).create({
                'to_journal_id': journal.id, 'payment_date': when})

    def test_setup_creates_journals_and_accounts(self):
        self.assertEqual(self.portfolio.default_account_id.code, '1033001')
        self.assertEqual(self.rejected.default_account_id.code, '1689001')
        codes = set(self.portfolio.inbound_payment_method_line_ids.mapped('code'))
        self.assertTrue({'new_third_party_checks', 'in_third_party_checks'} <= codes)
        own = self.bank.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'own_checks')
        self.assertTrue(own, 'cheques propios en el banco')
        self.assertEqual(own.payment_account_id.code, '1049001')
        journals = self.env['account.journal'].search_count([('company_id', '=', self.company.id)])
        self.company._l10n_pe_check_setup()
        self.assertEqual(self.env['account.journal'].search_count([('company_id', '=', self.company.id)]),
                         journals, 'idempotente')

    def test_received_check_goes_to_portfolio(self):
        payment = self._receive(self.customer, '00012345', 1180.0, date(2026, 10, 5))
        check = payment.l10n_latam_new_check_ids
        self.assertEqual(check.current_journal_id, self.portfolio)
        self.assertEqual(check.issuer_vat, '20100070970')
        portfolio_line = payment.move_id.line_ids.filtered(lambda l: l.account_id.code == '1033001')
        self.assertEqual(portfolio_line.debit, 1180.0)
        self.assertEqual(check.l10n_pe_presentation_deadline, date(2026, 11, 4), '30 días')

    def test_issuer_with_dni_is_accepted(self):
        payment = self._receive(self.person, '00700001', 300.0, date(2026, 10, 5))
        self.assertEqual(payment.l10n_latam_new_check_ids.issuer_vat, '41234567')

    def test_issuer_with_wrong_ruc_is_rejected(self):
        payment = self._receive(self.customer, '00012346', 100.0, date(2026, 10, 5))
        with self.assertRaises(ValidationError):
            payment.l10n_latam_new_check_ids.issuer_vat = '20100070971'
        with self.assertRaises(ValidationError):
            payment.l10n_latam_new_check_ids.issuer_vat = '1234'

    def test_deposit_warnings(self):
        today = date(2026, 10, 12)
        expired = self._receive(self.customer, '00012347', 500.0, today - timedelta(days=40)).l10n_latam_new_check_ids
        deferred = self._receive(self.person, '00700002', 200.0, today + timedelta(days=10),
                                 date_received=today).l10n_latam_new_check_ids
        current = self._receive(self.customer, '00012348', 700.0, today - timedelta(days=3)).l10n_latam_new_check_ids
        warning = self._transfer(expired | deferred | current, self.bank, today).l10n_pe_warning
        self.assertIn(expired.name, warning)
        self.assertIn('venció', warning)
        self.assertIn(deferred.name, warning)
        self.assertIn('diferido', warning)
        self.assertNotIn(current.name, warning)
        self.assertFalse(self._transfer(current, self.bank, today).l10n_pe_warning)
        self.assertFalse(self._transfer(expired, self.rejected, today).l10n_pe_warning,
                         'solo al depositar en un banco')

    def test_deposit_moves_check_to_bank(self):
        check = self._receive(self.customer, '00012349', 900.0, date(2026, 10, 5)).l10n_latam_new_check_ids
        self._transfer(check, self.bank, date(2026, 10, 6))._create_payments()
        self.assertEqual(check.current_journal_id, self.bank)
        self.assertEqual(len(check.operation_ids), 2)

    def test_own_check(self):
        line = self.bank.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'own_checks')[:1]
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': self.supplier.id,
            'journal_id': self.bank.id, 'payment_method_line_id': line.id, 'date': date(2026, 10, 12),
            'l10n_latam_new_check_ids': [Command.create({
                'name': '00001021', 'payment_date': date(2026, 10, 20), 'amount': 2360.0})],
        })
        payment.action_post()
        check = payment.l10n_latam_new_check_ids
        self.assertEqual(check.issue_state, 'handed')
        self.assertEqual(check.outstanding_line_id.account_id.code, '1049001')

    def test_new_company_gets_checks_from_template(self):
        company = self.env['res.company'].create({
            'name': 'Compañía nueva (test cheques)', 'country_id': self.env.ref('base.pe').id})
        self.env['account.chart.template'].try_loading('pe', company=company, install_demo=False)
        ChartTemplate = self.env['account.chart.template'].with_company(company)
        journal = ChartTemplate.ref('l10n_pe_third_party_check')
        self.assertEqual(journal.default_account_id.code, '1033001')
        self.assertTrue(ChartTemplate.ref('l10n_pe_check_issued').reconcile)
        # El código de la cuenta depende de la compañía: se lee en la nueva.
        bank = self.env['account.journal'].with_company(company).search(
            [('company_id', '=', company.id), ('type', '=', 'bank')], limit=1)
        own = bank.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'own_checks')
        self.assertEqual(own.payment_account_id.code, '1049001')

    def test_method_lines_in_spanish(self):
        names = set((self.portfolio.inbound_payment_method_line_ids
                     | self.portfolio.outbound_payment_method_line_ids).mapped('name'))
        self.assertTrue({'Nuevos cheques de terceros', 'Cheques de terceros existentes',
                         'Devolver cheques de terceros'} <= names, names)
        own = self.bank.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'own_checks')
        self.assertEqual(own.mapped('name'), ['Cheques propios'])
