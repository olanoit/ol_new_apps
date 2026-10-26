# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import TODAY, USD_RATE, TreasuryCommon


@tagged('post_install', '-at_install')
class TestTreasuryPosition(TreasuryCommon):

    def _position(self, journals=None, day=TODAY):
        return self.env['l10n_pe.treasury.position'].create({
            'date': day, 'journal_ids': [(6, 0, (journals or self.bank_pen).ids)]})

    def test_book_balance_transit_and_available(self):
        self._post_entry(self.bank_pen.default_account_id, 10000.0)
        self.bank_pen.write({'l10n_pe_treasury_min_balance': 500.0, 'l10n_pe_treasury_overdraft': 2000.0})
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': self.vendor.id,
            'journal_id': self.bank_pen.id, 'amount': 1500.0, 'date': date(2026, 3, 10)})
        payment.action_post()
        line = self._position().line_ids
        self.assertEqual(line.balance, 10000.0)
        self.assertEqual(line.payments_transit, -1500.0, 'pago confirmado sin conciliar')
        self.assertEqual(line.projected, 8500.0)
        self.assertEqual(line.available, 8500.0 - 500.0 + 2000.0)
        self.assertEqual(line.available_company, line.available)

    def test_restricted_account_not_available(self):
        self._post_entry(self.bank_pen2.default_account_id, 3000.0)
        self.bank_pen2.l10n_pe_forecast_exclude = True
        position = self._position(self.bank_pen | self.bank_pen2)
        restricted = position.line_ids.filtered(lambda l: l.journal_id == self.bank_pen2)
        self.assertEqual(restricted.balance, 3000.0)
        self.assertEqual(restricted.available, 0.0)
        self.assertEqual(position.total_restricted, 3000.0)

    def test_foreign_journal_in_soles(self):
        self._post_entry(self.bank_usd.default_account_id, 1000.0 * USD_RATE, currency=self.usd,
                         amount_currency=1000.0)
        line = self._position(self.bank_usd).line_ids
        self.assertEqual(line.currency_id, self.usd)
        self.assertEqual(line.balance, 1000.0)
        self.assertAlmostEqual(line.balance_company, 3700.0, places=2)

    def test_future_entries_excluded(self):
        self._post_entry(self.bank_pen.default_account_id, 800.0, day=date(2026, 4, 1))
        self.assertEqual(self._position().line_ids.balance, 0.0)

    def test_cron_creates_one_position_per_day(self):
        Position = self.env['l10n_pe.treasury.position']
        Position._cron_l10n_pe_daily_position()
        Position._cron_l10n_pe_daily_position()
        today = Position.search([('company_id', '=', self.company.id), ('journal_ids', '=', False),
                                 ('date', '=', date.today())])
        self.assertEqual(len(today), 1)
        self.assertIn(self.bank_pen, today.line_ids.journal_id)


@tagged('post_install', '-at_install')
class TestTreasuryTransfer(TreasuryCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transfer_account = cls.company.transfer_account_id

    def _transfer(self, **vals):
        return self.env['l10n_pe.treasury.transfer'].create(dict({
            'journal_from_id': self.bank_pen.id, 'journal_to_id': self.bank_pen2.id,
            'amount': 5000.0, 'date': TODAY}, **vals))

    def _transfer_balance(self, transfer):
        return self.company.currency_id.round(sum(transfer._l10n_pe_transfer_lines().mapped('balance')))

    def test_same_currency_transfer(self):
        transfer = self._transfer()
        self.assertFalse(transfer.is_exchange)
        self.assertEqual(transfer.amount_to, 5000.0)
        transfer.action_confirm()
        self.assertEqual(transfer.state, 'done')
        self.assertEqual(transfer.payment_from_id.payment_type, 'outbound')
        self.assertEqual(transfer.payment_to_id.journal_id, self.bank_pen2)
        self.assertEqual(transfer.payment_from_id.destination_account_id, self.transfer_account)
        self.assertEqual(self._transfer_balance(transfer), 0.0)
        self.assertTrue(all(transfer._l10n_pe_transfer_lines().mapped('reconciled')))
        self.assertFalse(transfer.payment_from_id.l10n_pe_itf_move_id, 'cuentas propias: sin ITF')

    def test_buy_dollars_at_agreed_rate(self):
        transfer = self._transfer(journal_to_id=self.bank_usd.id, amount=3750.0, agreed_rate=3.75)
        self.assertEqual(transfer.exchange_type, 'buy')
        self.assertEqual(transfer.amount_to, 1000.0)
        transfer.action_confirm()
        self.assertAlmostEqual(abs(transfer.payment_to_id.amount_company_currency_signed), 3750.0, places=2)
        self.assertEqual(self._transfer_balance(transfer), 0.0)
        self.assertFalse(transfer.exchange_move_id)

    def test_buy_dollars_at_official_rate_books_loss(self):
        transfer = self._transfer(journal_to_id=self.bank_usd.id, amount=3750.0, agreed_rate=3.75,
                                  valuation='official')
        transfer.action_confirm()
        # 1 000 US$ a 3,70 = 3 700: se pagaron 50 soles más → pérdida (676).
        self.assertTrue(transfer.exchange_move_id)
        self.assertAlmostEqual(transfer.exchange_difference, -50.0, places=2)
        loss = transfer.exchange_move_id.line_ids.filtered(
            lambda l: l.account_id == self.company.expense_currency_exchange_account_id)
        self.assertAlmostEqual(loss.balance, 50.0, places=2)
        self.assertEqual(self._transfer_balance(transfer), 0.0)
        self.assertTrue(all(transfer._l10n_pe_transfer_lines().mapped('reconciled')))

    def test_sell_dollars_at_official_rate_books_gain(self):
        transfer = self._transfer(journal_from_id=self.bank_usd.id, journal_to_id=self.bank_pen.id,
                                  amount=1000.0, agreed_rate=3.76, valuation='official')
        self.assertEqual(transfer.exchange_type, 'sell')
        self.assertEqual(transfer.amount_to, 3760.0)
        transfer.action_confirm()
        # Salen 1 000 US$ (3 700 contables) y entran 3 760: ganancia de 60 (776).
        self.assertAlmostEqual(transfer.exchange_difference, 60.0, places=2)
        self.assertEqual(self._transfer_balance(transfer), 0.0)

    def test_changing_received_amount_recomputes_rate(self):
        transfer = self._transfer(journal_to_id=self.bank_usd.id, amount=3750.0, agreed_rate=3.75)
        transfer.amount_to = 1010.0
        transfer._onchange_amount_to()
        self.assertAlmostEqual(transfer.agreed_rate, round(3750.0 / 1010.0, 4), places=4)

    def test_exchange_requires_rate(self):
        transfer = self._transfer(journal_to_id=self.bank_usd.id, amount_to=100.0)
        with self.assertRaises(UserError):
            transfer.action_confirm()

    def test_itf_when_marked(self):
        self.bank_pen.l10n_pe_itf_applies = True
        transfer = self._transfer(itf_from=True)
        transfer.action_confirm()
        self.assertTrue(transfer.payment_from_id.l10n_pe_itf_move_id)
        self.assertAlmostEqual(transfer.payment_from_id.l10n_pe_itf_amount, 0.25, places=2)

    def test_approval_threshold_and_segregation(self):
        self.company.l10n_pe_treasury_transfer_approval_amount = 1000.0
        transfer = self._transfer().with_user(self.preparer)
        transfer.action_confirm()
        self.assertEqual(transfer.state, 'to_approve')
        self.assertFalse(transfer.payment_from_id)
        with self.assertRaises(UserError):
            transfer.action_approve()
        transfer.with_user(self.approver).action_approve()
        self.assertEqual(transfer.state, 'done')
        self.assertEqual(transfer.approved_by_id, self.approver)

    def test_cancel_reverts(self):
        transfer = self._transfer(journal_to_id=self.bank_usd.id, amount=3750.0, agreed_rate=3.75,
                                  valuation='official')
        transfer.action_confirm()
        transfer.action_cancel()
        self.assertEqual(transfer.state, 'cancel')
        self.assertEqual(transfer.payment_from_id.state, 'canceled')
        reversal = transfer.exchange_move_id.reversal_move_ids
        self.assertTrue(reversal, 'la diferencia de cambio se extorna')
        posted = (transfer.exchange_move_id | reversal).line_ids.filtered(
            lambda l: l.parent_state == 'posted' and l.account_id == self.transfer_account)
        self.assertEqual(sum(posted.mapped('balance')), 0.0)

    def test_same_journal_rejected(self):
        with self.assertRaises(ValidationError):
            self._transfer(journal_to_id=self.bank_pen.id)


@tagged('post_install', '-at_install')
class TestTreasuryPaymentPlan(TreasuryCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bill1 = cls._bill(cls.vendor, 1000.0, date(2026, 3, 10))
        cls.bill2 = cls._bill(cls.vendor, 400.0, date(2026, 3, 20))
        cls.bill3 = cls._bill(cls.vendor2, 700.0, date(2026, 3, 12))
        cls.bill_later = cls._bill(cls.vendor2, 900.0, date(2026, 5, 30))

    def _plan(self, user=None):
        plan = self.env['l10n_pe.treasury.payment.plan'].with_user(user or self.preparer).create({
            'journal_id': self.bank_pen.id, 'date': TODAY})
        return plan

    def _propose(self, plan, **vals):
        wizard = self.env['l10n_pe.treasury.payment.plan.propose'].with_user(plan.env.user).create(
            dict({'plan_id': plan.id, 'date_due': date(2026, 3, 31)}, **vals))
        wizard.action_propose()

    def test_propose_by_due_date(self):
        plan = self._plan()
        self._propose(plan)
        self.assertEqual(plan.line_ids.move_id, self.bill1 | self.bill2 | self.bill3)
        self.assertEqual(plan.amount_total, 2100.0)
        self.assertEqual(plan.partner_count, 2)
        overdue = plan.line_ids.filtered(lambda l: l.move_id == self.bill1)
        self.assertEqual(overdue.days_overdue, 6)

    def test_propose_filters_partner_and_excludes_planned(self):
        plan = self._plan()
        self._propose(plan, partner_ids=[(6, 0, self.vendor2.ids)])
        self.assertEqual(plan.line_ids.move_id, self.bill3)
        other = self._plan()
        self._propose(other)
        self.assertNotIn(self.bill3, other.line_ids.move_id, 'ya está en otra programación abierta')

    def test_duplicate_line_rejected(self):
        plan = self._plan()
        self._propose(plan)
        other = self._plan()
        with self.assertRaises(ValidationError):
            other.line_ids = [(0, 0, {'move_line_id': self._payable_line(self.bill1).id})]

    def test_single_approval_then_pay(self):
        plan = self._plan()
        self._propose(plan)
        plan.action_submit()
        self.assertEqual(plan.state, 'to_approve')
        self.assertEqual(plan.approval_level, 'single')
        with self.assertRaises(UserError):
            plan.action_approve()  # quien prepara no aprueba
        plan.with_user(self.approver).action_approve()
        self.assertEqual(plan.state, 'approved')
        # El programado aprobado aparece en la posición.
        position = self.env['l10n_pe.treasury.position'].create({
            'date': TODAY, 'journal_ids': [(6, 0, self.bank_pen.ids)]})
        self.assertEqual(position.line_ids.scheduled, 2100.0)
        plan.sudo().action_pay()
        self.assertEqual(plan.state, 'paid')
        self.assertEqual(len(plan.payment_ids), 2, 'un pago por proveedor')
        self.assertTrue(all(plan.line_ids.mapped('payment_id')))
        for bill in self.bill1 | self.bill2 | self.bill3:
            self.assertIn(bill.payment_state, ('paid', 'in_payment'))
        self.assertEqual(plan.payment_ids.l10n_pe_treasury_plan_id, plan)

    def test_partial_payment(self):
        plan = self._plan()
        plan.line_ids = [(0, 0, {'move_line_id': self._payable_line(self.bill1).id, 'amount': 300.0})]
        self.assertFalse(plan.line_ids.is_full)
        plan.action_submit()
        plan.with_user(self.approver).action_approve()
        plan.sudo().action_pay()
        self.assertEqual(self.bill1.payment_state, 'partial')
        self.assertAlmostEqual(self.bill1.amount_residual, 700.0)

    def test_amount_above_residual_rejected(self):
        plan = self._plan()
        plan.line_ids = [(0, 0, {'move_line_id': self._payable_line(self.bill2).id, 'amount': 450.0})]
        with self.assertRaises(UserError):
            plan.action_submit()

    def test_double_approval(self):
        self.company.write({'l10n_pe_treasury_plan_approval_amount': 500.0,
                            'l10n_pe_treasury_plan_double_amount': 2000.0})
        plan = self._plan()
        self._propose(plan)
        self.assertEqual(plan.approval_level, 'double')
        plan.action_submit()
        plan.with_user(self.approver).action_approve()
        self.assertEqual(plan.state, 'to_approve', 'falta la segunda firma')
        with self.assertRaises(UserError):
            plan.with_user(self.approver).action_approve()  # no es administrador
        plan.with_user(self.manager).action_approve()
        self.assertEqual(plan.state, 'approved')
        self.assertEqual(plan.second_approver_id, self.manager)

    def test_below_threshold_needs_no_approval(self):
        self.company.l10n_pe_treasury_plan_approval_amount = 5000.0
        plan = self._plan()
        self._propose(plan)
        plan.action_submit()
        self.assertEqual(plan.state, 'approved')

    def test_over_available_warning(self):
        self._post_entry(self.bank_pen.default_account_id, 1000.0)
        plan = self._plan()
        self._propose(plan)
        self.assertEqual(plan.journal_available, 1000.0)
        self.assertTrue(plan.over_available)

    def test_usd_bill_needs_usd_bank(self):
        bill_usd = self._bill(self.vendor, 100.0, date(2026, 3, 10), currency=self.usd)
        plan = self._plan()
        with self.assertRaises(ValidationError):
            plan.line_ids = [(0, 0, {'move_line_id': self._payable_line(bill_usd).id})]
        plan_usd = self.env['l10n_pe.treasury.payment.plan'].create({'journal_id': self.bank_usd.id, 'date': TODAY})
        self._propose(plan_usd)
        self.assertEqual(plan_usd.line_ids.move_id, bill_usd)
        self.assertEqual(plan_usd.amount_total, 100.0)

    def test_reject_resets_approvals(self):
        plan = self._plan()
        self._propose(plan)
        plan.action_submit()
        plan.with_user(self.approver).action_approve()
        plan.with_user(self.approver).action_reject()
        self.assertEqual(plan.state, 'draft')
        self.assertFalse(plan.first_approver_id)


@tagged('post_install', '-at_install')
class TestTreasuryControls(TreasuryCommon):

    def _cash_payment(self, amount, currency=None, method=None):
        return self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': self.vendor.id,
            'journal_id': self.cash.id, 'amount': amount, 'date': TODAY,
            'currency_id': (currency or self.pen).id,
            'pe_payment_method_id': method.id if method else False})

    def test_bancarization_warns_from_2000(self):
        self.assertFalse(self._cash_payment(1999.0).l10n_pe_bancarization_warning)
        payment = self._cash_payment(2000.0)
        self.assertTrue(payment.l10n_pe_bancarization_warning)
        payment.action_post()
        self.assertTrue(any('medios de pago' in (m.body or '') for m in payment.message_ids))

    def test_bancarization_usd_and_block(self):
        self.company.l10n_pe_bancarization_mode = 'block'
        self.assertFalse(self._cash_payment(499.0, currency=self.usd).l10n_pe_bancarization_warning)
        with self.assertRaises(UserError):
            self._cash_payment(500.0, currency=self.usd).action_post()

    def test_bancarization_respects_payment_method(self):
        transfer_method = self.env.ref('al_account_payments.pe_catalog_payment_003')
        self.assertFalse(self._cash_payment(5000.0, method=transfer_method).l10n_pe_bancarization_warning)
        bank_payment = self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': self.vendor.id,
            'journal_id': self.bank_pen.id, 'amount': 5000.0, 'date': TODAY})
        self.assertFalse(bank_payment.l10n_pe_bancarization_warning)

    def test_credit_line_usage_and_notice(self):
        bank = self.env['res.partner'].create({'name': 'BANCO DE PRUEBA SA', 'is_company': True})
        line = self.env['l10n_pe.treasury.credit.line'].create({
            'name': 'Línea global', 'partner_id': bank.id, 'amount_limit': 100000.0,
            'date_end': date.today()})
        self.assertEqual(line.amount_used, 0.0)
        self.assertEqual(line.amount_available, 100000.0)
        self.env['l10n_pe.treasury.credit.line']._cron_l10n_pe_credit_line_notice()
        self.assertTrue(line.notice_sent)
        self.assertTrue(line.activity_ids)

    def test_credit_line_only_manager_writes(self):
        bank = self.env['res.partner'].create({'name': 'BANCO DOS SA', 'is_company': True})
        with self.assertRaises(AccessError):
            self.env['l10n_pe.treasury.credit.line'].with_user(self.preparer).create({
                'name': 'Línea', 'partner_id': bank.id, 'amount_limit': 1.0})
        line = self.env['l10n_pe.treasury.credit.line'].with_user(self.manager).create({
            'name': 'Línea', 'partner_id': bank.id, 'amount_limit': 1.0})
        self.assertTrue(line)

    def test_preparer_cannot_approve_without_group(self):
        plan = self.env['l10n_pe.treasury.payment.plan'].create({'journal_id': self.bank_pen.id, 'date': TODAY})
        plan.line_ids = [(0, 0, {'move_line_id': self._payable_line(
            self._bill(self.vendor, 50.0, TODAY)).id})]
        plan.action_submit()
        with self.assertRaises(UserError):
            plan.with_user(self.preparer).action_approve()
