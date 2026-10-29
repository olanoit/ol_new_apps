# -*- coding: utf-8 -*-
"""Entregas a rendir y caja chica: entrega, rendición, devolución, reembolso,
reposición, planilla de movilidad y cierre con la cuenta conciliada."""
from datetime import date

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.addons.al_account_base.tests.common import use_pe_company


@tagged('post_install', '-at_install')
class TestCashFund(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        Account = cls.env['account.account']
        cls.advance_account = cls.company._l10n_pe_cash_fund_account('advance')
        if not cls.advance_account:
            cls.advance_account = Account.create({
                'code': '1413099', 'name': 'Entregas a rendir (test)',
                'account_type': 'asset_receivable', 'reconcile': True})
        cls.company.l10n_pe_cash_advance_account_id = cls.advance_account
        cls.mobility_account = Account.search([
            *Account._check_company_domain(cls.company), ('account_type', '=', 'expense')], limit=1)
        cls.company.write({'l10n_pe_mobility_account_id': cls.mobility_account.id,
                           'l10n_pe_rmv_amount': 1130.0, 'l10n_pe_mobility_limit_pct': 4.0})
        cls.bank = cls.env['account.journal'].search([
            *cls.env['account.journal']._check_company_domain(cls.company),
            ('type', '=', 'bank')], limit=1)
        cls.worker = cls.env['res.partner'].create({
            'name': 'Rosa Quispe (test)', 'additional_identifiers': {'PE_DNI': '40506070'}})
        cls.supplier = cls.env['res.partner'].create({'name': 'Grifo Central (test)'})
        cls.expense = cls.env['account.account'].search([
            *Account._check_company_domain(cls.company), ('account_type', '=', 'expense')], limit=1)

    _bill_number = 0

    def _bill(self, amount, currency=None):
        TestCashFund._bill_number += 1
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': self.supplier.id,
            'l10n_latam_document_number': 'F001-%06d' % (900000 + TestCashFund._bill_number),
            'invoice_date': date(2026, 10, 5), 'currency_id': (currency or self.company.currency_id).id,
            'invoice_line_ids': [Command.create({
                'name': 'Combustible', 'quantity': 1, 'price_unit': amount,
                'account_id': self.expense.id, 'tax_ids': [Command.clear()]})],
        })
        bill.action_post()
        return bill

    def _fund(self, amount, fund_type='advance'):
        fund = self.env['l10n_pe.cash.fund'].create({
            'fund_type': fund_type, 'partner_id': self.worker.id, 'purpose': 'Visita a obra',
            'amount': amount, 'journal_id': self.bank.id, 'date': date(2026, 10, 1)})
        fund.action_approve()
        action = fund.action_deliver()
        self.env['account.payment'].browse(action['res_id']).action_post()
        return fund

    def _post_payment(self, action):
        payment = self.env['account.payment'].browse(action['res_id'])
        payment.action_post()
        return payment

    def test_advance_settle_return_close(self):
        fund = self._fund(500.0)
        self.assertTrue(fund.name.startswith('ER/'))
        self.assertEqual((fund.state, fund.amount_delivered, fund.amount_balance), ('open', 500.0, 500.0))
        bill = self._bill(300.0)
        settlement = self.env['l10n_pe.cash.settlement'].create({
            'fund_id': fund.id, 'date': date(2026, 10, 6),
            'document_line_ids': [Command.create({'move_id': bill.id})],
            'mobility_line_ids': [
                Command.create({'date': date(2026, 10, 2), 'reason': 'Visita a obra',
                                'destination': 'Santa Anita - Ate', 'amount': 30.0}),
                Command.create({'date': date(2026, 10, 2), 'reason': 'Retorno',
                                'destination': 'Ate - Santa Anita', 'amount': 25.0}),
            ]})
        self.assertEqual(settlement.document_line_ids.amount, 300.0)
        # Tope diario: 4 % de 1 130 = 45,20; el exceso del día es 9,80.
        self.assertAlmostEqual(settlement.amount_mobility_excess, 9.8)
        settlement.action_post()
        self.assertEqual(bill.payment_state, 'paid')
        self.assertTrue(settlement.mobility_number)
        self.assertEqual(settlement.move_id.state, 'posted')
        self.assertAlmostEqual(fund.amount_balance, 145.0)
        with self.assertRaises(UserError):
            fund.action_close()
        self._post_payment(fund.action_register_return())
        self.assertAlmostEqual(fund.amount_balance, 0.0)
        fund.action_close()
        self.assertEqual(fund.state, 'closed')
        self.assertTrue(all(fund._fund_move_lines().mapped('reconciled')))
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_cash_fund.action_report_mobility_sheet', settlement.ids)[0]
        self.assertIn(b'Planilla de gastos de movilidad', html)

    def test_advance_reimbursement(self):
        fund = self._fund(100.0)
        bill = self._bill(150.0)
        self.env['l10n_pe.cash.settlement'].create({
            'fund_id': fund.id, 'document_line_ids': [Command.create({'move_id': bill.id})],
        }).action_post()
        self.assertAlmostEqual(fund.amount_balance, -50.0)
        payment = self._post_payment(fund.action_register_reimbursement())
        self.assertEqual((payment.payment_type, payment.amount), ('outbound', 50.0))
        fund.action_close()
        self.assertEqual(fund.state, 'closed')

    def test_petty_cash_replenishment(self):
        fund = self._fund(1000.0, 'petty_cash')
        self.assertTrue(fund.name.startswith('CCH/'))
        self.env['l10n_pe.cash.settlement'].create({
            'fund_id': fund.id, 'document_line_ids': [Command.create({'move_id': self._bill(400.0).id})],
        }).action_post()
        payment = self._post_payment(fund.action_replenish())
        self.assertEqual((payment.amount, payment.l10n_pe_cash_fund_kind), (400.0, 'replenishment'))
        self.assertAlmostEqual(fund.amount_balance, 1000.0)

    def test_partial_document_and_cancel(self):
        fund = self._fund(500.0)
        bill = self._bill(300.0)
        settlement = self.env['l10n_pe.cash.settlement'].create({
            'fund_id': fund.id, 'document_line_ids': [Command.create({'move_id': bill.id, 'amount': 120.0})]})
        settlement.action_post()
        self.assertEqual(bill.payment_state, 'partial')
        settlement.action_cancel()
        self.assertEqual(bill.payment_state, 'not_paid')
        self.assertEqual(settlement.move_id.state, 'cancel')
        self.assertAlmostEqual(fund.amount_balance, 500.0)
        number = settlement.name
        settlement.action_draft()
        settlement.action_post()
        self.assertEqual(settlement.name, number, 'Vuelta a confirmar, conserva su número')
        self.assertEqual(bill.payment_state, 'partial')

    def test_document_validations(self):
        fund = self._fund(500.0)
        bill = self._bill(100.0)
        settlement = self.env['l10n_pe.cash.settlement'].create({
            'fund_id': fund.id, 'document_line_ids': [Command.create({'move_id': bill.id, 'amount': 150.0})]})
        with self.assertRaises(ValidationError):
            settlement.action_post()
        usd = self.env.ref('base.USD')
        usd.active = True
        bill_usd = self._bill(80.0, currency=usd)
        settlement.document_line_ids = [Command.clear(), Command.create({'move_id': bill_usd.id})]
        with self.assertRaises(ValidationError):
            settlement.action_post()

    def test_cannot_cancel_fund_with_posted_settlement(self):
        fund = self._fund(200.0)
        self.env['l10n_pe.cash.settlement'].create({
            'fund_id': fund.id, 'mobility_line_ids': [Command.create({
                'date': date(2026, 10, 3), 'reason': 'Banco', 'destination': 'Centro', 'amount': 20.0})],
        }).action_post()
        with self.assertRaises(UserError):
            fund.action_cancel()

    def test_default_accounts_from_chart(self):
        """Sin configurar, el fondo usa la 1413 y la movilidad la 63112 del PCGE."""
        company = self.company
        company.write({'l10n_pe_cash_advance_account_id': False,
                       'l10n_pe_mobility_account_id': False})
        chart = self.env.ref('account.%s_chart63112' % company.id, raise_if_not_found=False)
        if not chart:
            self.skipTest('Plan contable sin la 63112')
        self.assertEqual(company._l10n_pe_mobility_account(), chart)
        self.assertEqual(company._l10n_pe_cash_fund_account('advance'),
                         self.env.ref('account.%s_chart1413' % company.id))
