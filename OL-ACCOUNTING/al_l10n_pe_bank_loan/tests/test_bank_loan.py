# -*- coding: utf-8 -*-
from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.addons.al_account_base.tests.common import use_pe_company

from ..tools.schedule import build_schedule, due_dates, irr_annual


class TestLoanSchedule(TransactionCase):
    """El cálculo, sin base de datos."""

    def test_french_fixed_installment(self):
        dates = due_dates(date(2026, 2, 15), 12, 1)
        lines = build_schedule(100000.0, 12.0, 360, date(2026, 1, 15), dates)
        installments = {round(l['principal'] + l['interest'], 2) for l in lines[:-1]}
        self.assertEqual(len(installments), 1, 'cuota fija aunque los meses tengan distintos días')
        self.assertAlmostEqual(sum(l['principal'] for l in lines), 100000.0, places=2)
        self.assertEqual(lines[-1]['balance_end'], 0.0)
        # Interés del primer mes: 100 000 × (1,12^(31/360) − 1)
        self.assertAlmostEqual(lines[0]['interest'], round(100000 * (1.12 ** (31 / 360) - 1), 2), places=2)

    def test_german_and_bullet(self):
        dates = due_dates(date(2026, 2, 1), 4, 3)
        german = build_schedule(40000.0, 10.0, 360, date(2025, 11, 1), dates, method='german')
        self.assertEqual([l['principal'] for l in german], [10000.0] * 4)
        bullet = build_schedule(40000.0, 10.0, 360, date(2025, 11, 1), dates, method='bullet')
        self.assertEqual([l['principal'] for l in bullet], [0.0, 0.0, 0.0, 40000.0])
        self.assertTrue(all(l['interest'] > 0 for l in bullet))

    def test_grace_partial_and_total(self):
        dates = due_dates(date(2026, 2, 1), 6, 1)
        partial = build_schedule(10000.0, 12.0, 360, date(2026, 1, 1), dates, grace_count=2, grace_type='partial')
        self.assertEqual([l['principal'] for l in partial[:2]], [0.0, 0.0])
        self.assertTrue(partial[0]['interest'] > 0, 'en la gracia parcial se pagan intereses')
        total = build_schedule(10000.0, 12.0, 360, date(2026, 1, 1), dates, grace_count=2, grace_type='total')
        self.assertEqual(total[0]['interest'], 0.0)
        self.assertGreater(total[1]['balance_end'], 10000.0, 'intereses capitalizados')
        self.assertAlmostEqual(sum(l['principal'] for l in total),
                               10000.0 + sum(l.get('capitalized', 0.0) for l in total), places=2)

    def test_tcea_equals_tea_without_costs(self):
        dates = due_dates(date(2026, 2, 15), 12, 1)
        lines = build_schedule(100000.0, 12.0, 360, date(2026, 1, 15), dates)
        flows = [(0, 100000.0)] + [((l['date_due'] - date(2026, 1, 15)).days, -(l['principal'] + l['interest']))
                                   for l in lines]
        self.assertAlmostEqual(irr_annual(flows), 0.12, places=4)


@tagged('post_install', '-at_install')
class TestBankLoan(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        Account = cls.env['account.account']
        cls.outstanding_in = Account.create({'name': 'Cobros pendientes (préstamos)', 'code': '104193',
                                             'account_type': 'asset_current', 'reconcile': True})
        cls.outstanding_out = Account.create({'name': 'Pagos pendientes (préstamos)', 'code': '104194',
                                              'account_type': 'asset_current', 'reconcile': True})
        cls.bank_journal = cls.env['account.journal'].create({
            'name': 'Banco préstamos test', 'code': 'BPTS', 'type': 'bank', 'company_id': cls.company.id})
        cls.bank_journal.inbound_payment_method_line_ids.payment_account_id = cls.outstanding_in
        cls.bank_journal.outbound_payment_method_line_ids.payment_account_id = cls.outstanding_out
        cls.misc_journal = cls.env['account.journal'].create({
            'name': 'Préstamos test', 'code': 'PTS', 'type': 'general', 'company_id': cls.company.id})
        cls.bank = cls.env['res.partner'].create({'name': 'BANCO PRÉSTAMOS SA', 'vat': '20100047218',
                                                  'is_company': True})

    def _loan(self, **vals):
        loan = self.env['l10n_pe.bank.loan'].create(dict({
            'partner_id': self.bank.id, 'journal_id': self.bank_journal.id, 'misc_journal_id': self.misc_journal.id,
            'amount': 120000.0, 'rate': 12.0, 'installment_count': 12, 'date_disbursement': date(2026, 1, 15),
        }, **vals))
        loan.action_compute_schedule()
        return loan

    def _balance(self, loan, account):
        lines = loan.move_ids.filtered(lambda m: m.state == 'posted').line_ids.filtered(
            lambda l: l.account_id == account)
        return self.company.currency_id.round(sum(lines.mapped('balance')))

    def _today(self, day):
        return patch('odoo.fields.Date.context_today', return_value=day)

    def _assert_balanced(self, loan):
        for move in loan.move_ids:
            self.assertFalse(self.company.currency_id.round(sum(move.line_ids.mapped('balance'))))

    def test_default_accounts_and_schedule(self):
        loan = self._loan()
        self.assertTrue(loan.name.startswith('PRE/'))
        self.assertTrue(loan.principal_account_id.code.startswith('4511'))
        self.assertTrue(loan.interest_payable_account_id.code.startswith('45511'))
        self.assertTrue(loan.interest_expense_account_id.code.startswith('67311'))
        self.assertEqual(len(loan.line_ids), 12)
        self.assertEqual(loan.date_first_due, date(2026, 2, 15))
        self.assertAlmostEqual(sum(loan.line_ids.mapped('principal')), 120000.0, places=2)
        self.assertAlmostEqual(loan.tcea, 12.0, places=1)

    def test_pagare_accounts(self):
        loan = self._loan(loan_type='promissory', method='bullet', installment_count=1)
        self.assertTrue(loan.principal_account_id.code.startswith('4544'))
        self.assertEqual(loan.line_ids.principal, 120000.0)

    def test_disbursement_with_fee(self):
        loan = self._loan(disbursement_fee=500.0)
        loan.action_confirm()
        self.assertEqual(loan.state, 'running')
        self.assertEqual(self._balance(loan, loan.principal_account_id), -120000.0)
        self.assertEqual(self._balance(loan, self.outstanding_in), 119500.0, 'el banco descuenta los gastos')
        self.assertEqual(self._balance(loan, loan.fee_account_id), 500.0)
        self.assertGreater(loan.tcea, 12.0, 'los gastos encarecen el préstamo')
        self.assertEqual(loan.principal_balance, 120000.0)

    def test_monthly_accrual_and_payment(self):
        loan = self._loan()
        loan.action_confirm()
        first = loan.line_ids.sorted('date_due')[0]
        loan._l10n_pe_accrue(date(2026, 1, 31))
        loan._l10n_pe_accrue(date(2026, 1, 31))  # idempotente
        expected = round(first.interest * 16 / 31, 2)
        self.assertAlmostEqual(first.interest_accrued, expected, places=2)
        self.assertAlmostEqual(self._balance(loan, loan.interest_payable_account_id), -expected, places=2)
        loan._l10n_pe_pay_line(first, date(2026, 2, 15))
        self.assertEqual(first.state, 'paid')
        self.assertEqual(self._balance(loan, loan.interest_payable_account_id), 0.0, 'lo devengado se cancela')
        self.assertAlmostEqual(self._balance(loan, loan.interest_expense_account_id), first.interest, places=2)
        self.assertAlmostEqual(self._balance(loan, self.outstanding_out), -first.amount_total, places=2)
        self.assertAlmostEqual(loan.principal_balance, 120000.0 - first.principal, places=2)
        self._assert_balanced(loan)

    def test_installments_in_order(self):
        loan = self._loan()
        loan.action_confirm()
        second = loan.line_ids.sorted('date_due')[1]
        with self.assertRaises(UserError):
            loan._l10n_pe_pay_line(second, date(2026, 3, 15))

    def test_pay_all_closes_loan(self):
        loan = self._loan(installment_count=3)
        loan.action_confirm()
        for line in loan.line_ids.sorted('date_due'):
            loan._l10n_pe_pay_line(line, line.date_due)
        self.assertEqual(loan.state, 'paid')
        self.assertEqual(self._balance(loan, loan.principal_account_id), 0.0)
        self.assertEqual(loan.principal_balance, 0.0)

    def test_bank_charged_other_interest(self):
        loan = self._loan()
        loan.action_confirm()
        first = loan.line_ids.sorted('date_due')[0]
        loan._l10n_pe_pay_line(first, date(2026, 2, 15), interest=first.interest + 10.0)
        self.assertAlmostEqual(self._balance(loan, loan.interest_expense_account_id), first.interest + 10.0, 2)

    def test_insurance_and_fee(self):
        loan = self._loan(insurance_rate=0.05, fee_amount=10.0)
        first = loan.line_ids.sorted('date_due')[0]
        self.assertAlmostEqual(first.insurance, 60.0, places=2, msg='0,05 % mensual de 120 000')
        self.assertEqual(first.fee, 10.0)
        loan.action_confirm()
        loan._l10n_pe_pay_line(first, first.date_due)
        self.assertEqual(self._balance(loan, loan.insurance_account_id), 60.0)

    def test_prepay_reduces_installment(self):
        loan = self._loan()
        loan.action_confirm()
        first = loan.line_ids.sorted('date_due')[0]
        loan._l10n_pe_pay_line(first, first.date_due)
        old_installment = loan.line_ids.filtered(lambda l: l.state == 'pending').sorted('date_due')[0].amount_total
        balance = loan.principal_balance
        loan._l10n_pe_prepay(date(2026, 3, 1), 30000.0, mode='installment')
        pending = loan.line_ids.filtered(lambda l: l.state == 'pending').sorted('date_due')
        self.assertEqual(len(pending), 11)
        self.assertEqual(pending[0].date_start, date(2026, 3, 1))
        self.assertAlmostEqual(pending[0].balance_start, balance - 30000.0, places=2)
        self.assertLess(pending[1].amount_total, old_installment)
        self.assertAlmostEqual(sum(pending.mapped('principal')), balance - 30000.0, places=2)
        self._assert_balanced(loan)

    def test_prepay_reduces_term(self):
        loan = self._loan()
        loan.action_confirm()
        loan._l10n_pe_prepay(date(2026, 2, 1), 60000.0, mode='term')
        pending = loan.line_ids.filtered(lambda l: l.state == 'pending')
        self.assertLess(len(pending), 12)
        self.assertAlmostEqual(sum(pending.mapped('principal')), 60000.0, places=2)

    def test_full_prepay_closes(self):
        loan = self._loan()
        loan.action_confirm()
        loan._l10n_pe_prepay(date(2026, 2, 1), 120000.0)
        self.assertEqual(loan.state, 'paid')
        self.assertEqual(self._balance(loan, loan.principal_account_id), 0.0)
        self.assertEqual(self._balance(loan, loan.interest_payable_account_id), 0.0)

    def test_total_grace_capitalizes_with_cron(self):
        loan = self._loan(grace_type='total', grace_count=2, installment_count=8)
        loan.action_confirm()
        with self._today(date(2026, 3, 20)):
            self.env['l10n_pe.bank.loan']._cron_l10n_pe_bank_loans()
        grace = loan.line_ids.sorted('date_due')[:2]
        self.assertEqual(grace.mapped('state'), ['paid', 'paid'])
        capitalized = sum(grace.mapped('capitalized'))
        self.assertAlmostEqual(self._balance(loan, loan.principal_account_id), -(120000.0 + capitalized), 2)
        self.assertAlmostEqual(loan.principal_balance, 120000.0 + capitalized, places=2)
        self.assertEqual(self._balance(loan, self.outstanding_out), 0.0, 'la gracia total no mueve dinero')

    def test_current_portion(self):
        loan = self._loan(installment_count=24)
        loan.action_confirm()
        with self._today(date(2026, 1, 15)):
            loan.invalidate_recordset(['current_portion', 'non_current_portion'])
            self.assertAlmostEqual(loan.current_portion + loan.non_current_portion, 120000.0, places=2)
            self.assertAlmostEqual(loan.current_portion,
                                   sum(loan.line_ids.sorted('date_due')[:12].mapped('principal')), places=2)

    def test_credit_line_usage_and_limit(self):
        line = self.env['l10n_pe.treasury.credit.line'].create({
            'name': 'Línea préstamos', 'partner_id': self.bank.id, 'line_type': 'loan', 'amount_limit': 150000.0})
        loan = self._loan(credit_line_id=line.id)
        loan.action_confirm()
        self.assertEqual(line.amount_used, 120000.0)
        self.assertEqual(line.amount_available, 30000.0)
        other = self._loan(credit_line_id=line.id, amount=50000.0)
        with self.assertRaises(UserError):
            other.action_confirm()

    def test_cash_forecast_includes_installments(self):
        loan = self._loan(installment_count=3)
        loan.action_confirm()
        forecast = self.env['l10n_pe.cash.forecast'].create({'date_from': date(2026, 1, 16), 'period_count': 8,
                                                              'period_type': 'month'})
        loan_lines = forecast.line_ids.filtered(lambda l: l.category == 'loan')
        self.assertEqual(len(loan_lines), 3)
        self.assertAlmostEqual(sum(loan_lines.mapped('amount')), -sum(loan.line_ids.mapped('amount_total')), 2)

    def test_notice_before_due(self):
        loan = self._loan()
        loan.action_confirm()
        with self._today(date(2026, 2, 5)):
            self.env['l10n_pe.bank.loan']._cron_l10n_pe_bank_loans()
        self.assertTrue(loan.activity_ids)
        self.assertTrue(loan.line_ids.sorted('date_due')[0].notice_sent)

    def test_cancel_reverses(self):
        loan = self._loan()
        loan.action_confirm()
        loan.action_cancel()
        self.assertEqual(loan.state, 'cancel')
        self.assertEqual(self._balance(loan, loan.principal_account_id), 0.0)

    def test_grace_validation(self):
        with self.assertRaises(ValidationError):
            self._loan(grace_type='partial', grace_count=12)

    def test_foreign_currency_loan(self):
        usd = self.env.ref('base.USD')
        usd.active = True
        self.env['res.currency.rate'].search([('currency_id', '=', usd.id),
                                              ('company_id', 'in', (False, self.company.root_id.id)),
                                              ('name', '>=', date(2026, 1, 1))]).unlink()
        self.env['res.currency.rate'].create({'currency_id': usd.id, 'company_id': self.company.root_id.id,
                                              'name': date(2026, 1, 1), 'inverse_company_rate': 3.70})
        loan = self._loan(currency_id=usd.id, amount=10000.0)
        loan.action_confirm()
        self.assertAlmostEqual(self._balance(loan, loan.principal_account_id), -37000.0, places=2)
        lines = loan.move_ids.line_ids.filtered(lambda l: l.account_id == loan.principal_account_id)
        self.assertEqual(lines.currency_id, usd)
