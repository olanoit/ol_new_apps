# -*- coding: utf-8 -*-
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestTermDeposit(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.bank_journal = cls.env['account.journal'].create({
            'name': 'Banco depósitos test', 'code': 'BDTS', 'type': 'bank', 'company_id': cls.company.id})
        cls.misc_journal = cls.env['account.journal'].create({
            'name': 'Depósitos test', 'code': 'DTS', 'type': 'general', 'company_id': cls.company.id})
        cls.bank = cls.env['res.partner'].create({'name': 'BANCO DEPÓSITOS SA', 'vat': '20100047218'})
        cls.landlord = cls.env['res.partner'].create({'name': 'ARRENDADOR ALMACÉN SAC', 'vat': '20100070970'})
        Config = cls.env['l10n_pe.term.deposit.account.config']
        for deposit_type in ('term', 'guarantee_fund', 'guarantee_given'):
            cls.assertTrue(cls, Config._l10n_pe_get(cls.company, deposit_type, cls.company.currency_id))

    def _deposit(self, **vals):
        return self.env['l10n_pe.term.deposit'].create(dict({
            'partner_id': self.bank.id, 'journal_id': self.bank_journal.id,
            'misc_journal_id': self.misc_journal.id, 'amount': 100000.0, 'rate': 6.0,
            'day_basis': '360', 'date_start': date(2026, 1, 1), 'term_days': 180,
        }, **vals))

    def _balance(self, deposit, account):
        lines = deposit.move_ids.filtered(lambda m: m.state == 'posted').line_ids.filtered(
            lambda l: l.account_id == account)
        return self.company.currency_id.round(sum(lines.mapped('balance')))

    def _assert_balanced(self, deposit):
        for move in deposit.move_ids:
            self.assertFalse(self.company.currency_id.round(sum(move.line_ids.mapped('balance'))))

    def _today(self, day):
        return patch('odoo.fields.Date.context_today', return_value=day)

    # ------------------------------------------------------------------
    def test_open_moves_cash_to_deposit(self):
        deposit = self._deposit()
        self.assertTrue(deposit.name.startswith('DEP/'))
        self.assertEqual(deposit.date_end, date(2026, 6, 30))
        self.assertTrue(deposit.deposit_account_id.code.startswith('1062'), 'PCGE 1062 depósitos a plazo')
        deposit.action_open()
        self.assertEqual(deposit.state, 'open')
        self.assertEqual(self._balance(deposit, deposit.deposit_account_id), 100000.0)
        self.assertEqual(self._balance(deposit, self.bank_journal.default_account_id), -100000.0)

    def test_expected_interest_uses_tea_and_day_basis(self):
        deposit = self._deposit()
        # 100 000 × (1,06^(180/360) − 1) = 2 956,30
        self.assertAlmostEqual(deposit.expected_interest, 2956.30, places=2)
        deposit.day_basis = '365'
        self.assertAlmostEqual(deposit.expected_interest,
                               round(100000 * (1.06 ** (180 / 365) - 1), 2), places=2)

    def test_monthly_accrual_adds_up_and_is_idempotent(self):
        deposit = self._deposit()
        deposit.action_open()
        for month_end in (date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)):
            deposit._l10n_pe_accrue(month_end)
            deposit._l10n_pe_accrue(month_end)  # dos veces: no duplica
        expected = deposit._l10n_pe_interest_until(date(2026, 3, 31))
        self.assertAlmostEqual(deposit.interest_accrued, expected, places=2)
        self.assertEqual(len(deposit.move_ids), 4, 'apertura + 3 devengos')
        self.assertEqual(self._balance(deposit, deposit.interest_account_id), expected)
        self.assertEqual(self._balance(deposit, deposit.income_account_id), -expected)
        # Más allá del vencimiento no se devenga más que el interés del plazo.
        deposit._l10n_pe_accrue(date(2026, 12, 31))
        self.assertAlmostEqual(deposit.interest_accrued, deposit.expected_interest, places=2)

    def test_cron_accrues_month_end_and_expires(self):
        deposit = self._deposit()
        deposit.action_open()
        with self._today(date(2026, 3, 10)):
            self.env['l10n_pe.term.deposit']._cron_l10n_pe_term_deposits()
            self.env['l10n_pe.term.deposit']._cron_l10n_pe_term_deposits()
        self.assertAlmostEqual(deposit.interest_accrued, deposit._l10n_pe_interest_until(date(2026, 2, 28)), 2)
        self.assertEqual(deposit.state, 'open')
        with self._today(date(2026, 6, 25)):
            self.env['l10n_pe.term.deposit']._cron_l10n_pe_term_deposits()
        self.assertTrue(deposit.notice_sent, 'aviso dentro de los 7 días previos')
        self.assertTrue(deposit.activity_ids)
        with self._today(date(2026, 7, 2)):
            self.env['l10n_pe.term.deposit']._cron_l10n_pe_term_deposits()
        self.assertEqual(deposit.state, 'expired')
        self.assertAlmostEqual(deposit.interest_accrued, deposit.expected_interest, places=2)

    def test_close_at_maturity(self):
        deposit = self._deposit()
        deposit.action_open()
        deposit._l10n_pe_accrue(date(2026, 3, 31))
        deposit._l10n_pe_close(date(2026, 6, 30))
        self.assertEqual(deposit.state, 'closed')
        self.assertEqual(self._balance(deposit, deposit.deposit_account_id), 0.0)
        self.assertEqual(self._balance(deposit, deposit.interest_account_id), 0.0)
        self.assertAlmostEqual(self._balance(deposit, self.bank_journal.default_account_id),
                               deposit.expected_interest, places=2, msg='vuelve el capital más los intereses')
        self._assert_balanced(deposit)

    def test_early_close_with_lower_interest_adjusts_income(self):
        deposit = self._deposit()
        deposit.action_open()
        deposit._l10n_pe_accrue(date(2026, 3, 31))
        accrued = deposit.interest_accrued
        deposit._l10n_pe_close(date(2026, 3, 31), interest_received=100.0)
        self.assertEqual(self._balance(deposit, deposit.income_account_id), -100.0,
                         'el ingreso queda en lo cobrado')
        self.assertGreater(accrued, 100.0)
        self._assert_balanced(deposit)

    def test_renew_with_capitalization(self):
        deposit = self._deposit(capitalize_interest=True)
        deposit.action_open()
        new = deposit._l10n_pe_renew(date(2026, 6, 30))
        self.assertEqual(deposit.state, 'renewed')
        self.assertEqual(new.state, 'open')
        self.assertEqual(new.renewed_from_id, deposit)
        self.assertAlmostEqual(new.amount, 100000.0 + deposit.expected_interest, places=2)
        self.assertEqual(new.date_end, date(2026, 6, 30) + timedelta(days=180))
        self.assertEqual(self._balance(deposit | new, deposit.interest_account_id), 0.0)
        self.assertAlmostEqual(self._balance(deposit | new, deposit.deposit_account_id), new.amount, places=2)
        self._assert_balanced(deposit)

    def test_renew_without_capitalization_pays_interest(self):
        deposit = self._deposit()
        deposit.action_open()
        new = deposit._l10n_pe_renew(date(2026, 6, 30), term_days=90, rate=5.5)
        self.assertEqual(new.amount, 100000.0)
        self.assertEqual(new.rate, 5.5)
        self.assertAlmostEqual(self._balance(deposit, self.bank_journal.default_account_id),
                               -100000.0 + deposit.expected_interest, places=2)

    def test_auto_renew_by_cron(self):
        deposit = self._deposit(auto_renew=True)
        deposit.action_open()
        with self._today(date(2026, 7, 1)):
            self.env['l10n_pe.term.deposit']._cron_l10n_pe_term_deposits()
        self.assertEqual(deposit.state, 'renewed')
        self.assertEqual(deposit.renewal_id.state, 'open')

    def test_guarantee_partial_release(self):
        guarantee = self._deposit(deposit_type='guarantee_given', partner_id=self.landlord.id,
                                  amount=6000.0, rate=0.0, term_days=0, date_end=False)
        self.assertTrue(guarantee.deposit_account_id.code.startswith('1643'), 'garantía de alquiler')
        guarantee.action_open()
        with self.assertRaises(UserError):
            guarantee._l10n_pe_renew(date(2026, 3, 1))
        guarantee._l10n_pe_release(date(2026, 3, 1), 2000.0)
        self.assertEqual(guarantee.remaining_amount, 4000.0)
        self.assertEqual(guarantee.state, 'open')
        with self.assertRaises(UserError, msg='no se libera más del saldo'):
            guarantee._l10n_pe_release(date(2026, 3, 2), 5000.0)
        guarantee._l10n_pe_release(date(2026, 4, 1), 4000.0)
        self.assertEqual(guarantee.state, 'closed')
        self.assertEqual(self._balance(guarantee, guarantee.deposit_account_id), 0.0)
        self._assert_balanced(guarantee)

    def test_rules(self):
        with self.assertRaises(ValidationError, msg='un depósito a plazo necesita vencimiento'):
            self._deposit(term_days=0, date_end=False)
        deposit = self._deposit()
        deposit.action_open()
        with self.assertRaises(UserError, msg='solo se eliminan borradores'):
            deposit.unlink()

    def test_wizard_close(self):
        deposit = self._deposit(date_start=fields.Date.context_today(self.env.user) - timedelta(days=200))
        deposit.action_open()
        wizard = Form(self.env['l10n_pe.term.deposit.wizard'].with_context(
            default_deposit_id=deposit.id, default_operation='close'))
        self.assertEqual(wizard.date, deposit.date_end, 'propone el vencimiento')
        self.assertAlmostEqual(wizard.interest_received, deposit.expected_interest, places=2)
        wizard.save().action_apply()
        self.assertEqual(deposit.state, 'closed')

    def test_multicompany(self):
        other = self.env['res.company'].create({'name': 'Otra compañía depósitos'})
        deposit = self._deposit()
        self.assertEqual(deposit.company_id, self.company)
        user = self.env['res.users'].create({
            'name': 'Contable otra compañía', 'login': 'contable_otra_dep',
            'company_id': other.id, 'company_ids': [(6, 0, other.ids)],
            'group_ids': [(6, 0, self.env.ref('account.group_account_user').ids)]})
        self.assertNotIn(deposit, self.env['l10n_pe.term.deposit'].with_user(user).search([]),
                         'regla de registro por compañía')
        with self.assertRaises(UserError, msg='el banco debe ser de la misma compañía'):
            self._deposit(company_id=other.id)
