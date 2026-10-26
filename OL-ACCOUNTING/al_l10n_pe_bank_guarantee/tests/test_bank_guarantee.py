# -*- coding: utf-8 -*-
from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.addons.al_account_base.tests.common import use_pe_company


@tagged('post_install', '-at_install')
class TestBankGuarantee(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        cls.outstanding_out = cls.env['account.account'].create({
            'name': 'Pagos pendientes (fianzas)', 'code': '104195', 'account_type': 'asset_current',
            'reconcile': True})
        cls.outstanding_in = cls.env['account.account'].create({
            'name': 'Cobros pendientes (fianzas)', 'code': '104196', 'account_type': 'asset_current',
            'reconcile': True})
        cls.journal = cls.env['account.journal'].create({
            'name': 'Banco fianzas test', 'code': 'BFTS', 'type': 'bank', 'company_id': cls.company.id})
        cls.journal.outbound_payment_method_line_ids.payment_account_id = cls.outstanding_out
        cls.journal.inbound_payment_method_line_ids.payment_account_id = cls.outstanding_in
        cls.bank = cls.env['res.partner'].create({'name': 'BANCO FIANZAS SA', 'is_company': True})
        cls.entity = cls.env['res.partner'].create({'name': 'MUNICIPALIDAD DE PRUEBA', 'is_company': True})
        cls.supplier = cls.env['res.partner'].create({'name': 'CONTRATISTA SAC', 'is_company': True})
        cls.commission_account = cls.env.ref('account.%s_chart6391' % cls.company.id)

    def _guarantee(self, **vals):
        return self.env['l10n_pe.bank.guarantee'].create(dict({
            'number': 'CF-0001', 'bank_id': self.bank.id, 'partner_id': self.entity.id, 'amount': 50000.0,
            'date_issue': date(2026, 1, 10), 'date_end': date(2026, 7, 10), 'journal_id': self.journal.id,
            'commission_rate': 0.5, 'commission_min': 100.0,
        }, **vals))

    def _balance(self, guarantee, account):
        return self.company.currency_id.round(sum(guarantee.move_ids.filtered(
            lambda m: m.state == 'posted').line_ids.filtered(lambda l: l.account_id == account).mapped('balance')))

    def _today(self, day):
        return patch('odoo.fields.Date.context_today', return_value=day)

    def test_commission_per_quarter_with_minimum(self):
        guarantee = self._guarantee()
        # 181 días = 3 trimestres (o fracción): 50 000 × 0,5 % × 3 = 750
        self.assertEqual(guarantee.commission_amount, 750.0)
        small = self._guarantee(amount=5000.0, date_end=date(2026, 2, 10))
        self.assertEqual(small.commission_amount, 100.0, 'comisión mínima')

    def test_activate_charges_commission(self):
        guarantee = self._guarantee()
        guarantee.action_activate()
        self.assertEqual(guarantee.state, 'active')
        self.assertEqual(self._balance(guarantee, self.commission_account), 750.0)
        self.assertEqual(self._balance(guarantee, self.outstanding_out), -750.0)

    def test_number_required(self):
        with self.assertRaises(UserError):
            self._guarantee(number=False).action_activate()

    def test_received_has_no_commission_and_claim_deadline(self):
        guarantee = self._guarantee(direction='received', partner_id=self.supplier.id, journal_id=False)
        self.assertEqual(guarantee.commission_amount, 0.0)
        self.assertEqual(guarantee.claim_deadline, date(2026, 7, 25))
        guarantee.action_activate()
        self.assertFalse(guarantee.move_ids)
        with self._today(date(2026, 7, 1)):
            self.env['l10n_pe.bank.guarantee']._cron_l10n_pe_bank_guarantees()
        activity = guarantee.activity_ids
        self.assertTrue(activity)
        self.assertEqual(activity.date_deadline, date(2026, 7, 25), 'vence con el plazo del art. 1898')

    def test_cron_expires(self):
        guarantee = self._guarantee()
        guarantee.action_activate()
        with self._today(date(2026, 7, 11)):
            self.env['l10n_pe.bank.guarantee']._cron_l10n_pe_bank_guarantees()
        self.assertEqual(guarantee.state, 'expired')

    def test_memo_accounts_issue_and_release(self):
        self.company.root_id.l10n_pe_guarantee_memo = True
        debit, credit = self.company._l10n_pe_guarantee_memo_accounts('issued')
        self.assertEqual(debit.code[:4], '0113')
        guarantee = self._guarantee()
        guarantee.action_activate()
        self.assertEqual(self._balance(guarantee, debit), 50000.0)
        self.assertEqual(self._balance(guarantee, credit), -50000.0)
        guarantee.action_release()
        self.assertEqual(guarantee.state, 'released')
        self.assertEqual(self._balance(guarantee, debit), 0.0)

    def test_renewal(self):
        guarantee = self._guarantee()
        guarantee.action_activate()
        new = guarantee._l10n_pe_renew(date(2027, 1, 10))
        self.assertEqual(guarantee.state, 'renewed')
        self.assertEqual(new.state, 'active')
        self.assertEqual(new.renewed_from_id, guarantee)
        self.assertEqual(new.number, guarantee.number)
        self.assertEqual(new.date_issue, date(2026, 7, 10))
        self.assertEqual(self._balance(new, self.commission_account), new.commission_amount)

    def test_execute_issued(self):
        expense = self.env['account.account'].create({'name': 'Penalidades (prueba)', 'code': '659901',
                                                      'account_type': 'expense'})
        guarantee = self._guarantee()
        guarantee.action_activate()
        guarantee._l10n_pe_execute(date(2026, 5, 1), 20000.0, self.journal, expense)
        self.assertEqual(guarantee.state, 'executed')
        self.assertEqual(self._balance(guarantee, expense), 20000.0)

    def test_execute_received_collects(self):
        income = self.env.ref('account.%s_chart7599' % self.company.id)
        guarantee = self._guarantee(direction='received', partner_id=self.supplier.id)
        guarantee.action_activate()
        guarantee._l10n_pe_execute(date(2026, 5, 1), 50000.0, self.journal, income)
        self.assertEqual(self._balance(guarantee, self.outstanding_in), 50000.0)
        with self.assertRaises(UserError):
            guarantee._l10n_pe_execute(date(2026, 5, 2), 1.0, self.journal, income)

    def test_credit_line_usage(self):
        line = self.env['l10n_pe.treasury.credit.line'].create({
            'name': 'Línea de fianzas', 'partner_id': self.bank.id, 'line_type': 'guarantee',
            'amount_limit': 80000.0})
        guarantee = self._guarantee(credit_line_id=line.id)
        guarantee.action_activate()
        self.assertEqual(line.amount_used, 50000.0)
        other = self._guarantee(credit_line_id=line.id, number='CF-0002', amount=40000.0)
        with self.assertRaises(UserError):
            other.action_activate()
        guarantee.action_release()
        line.invalidate_recordset()
        self.assertEqual(line.amount_used, 0.0)

    def test_dates_validation(self):
        with self.assertRaises(ValidationError):
            self._guarantee(date_end=date(2026, 1, 1))
