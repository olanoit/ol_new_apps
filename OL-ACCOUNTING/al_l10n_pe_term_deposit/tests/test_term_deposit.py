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

    # ------------------------------------------------------------------
    # Proceso genérico: ITF, penalidad, garantías, moneda extranjera, reportes
    # ------------------------------------------------------------------
    def _itf_account(self):
        return self.company._l10n_pe_term_deposit_itf_account()

    def test_itf_on_open_and_close(self):
        self.company.l10n_pe_term_deposit_itf = True
        deposit = self._deposit()
        self.assertTrue(deposit.itf_applies, 'toma el valor de Ajustes')
        self.assertEqual(deposit.itf_open_amount, 5.0, '100 000 × 0,005 %')
        deposit.action_open()
        bank = self.bank_journal.default_account_id
        self.assertEqual(self._balance(deposit, bank), -100005.0, 'sale el capital más el ITF')
        self.assertEqual(self._balance(deposit, self._itf_account()), 5.0)
        deposit._l10n_pe_close(date(2026, 6, 30))
        # Vuelven 100 000 de capital (ITF 5,00) y 2 956,30 de intereses, que
        # están exonerados (Informe SUNAT 025-2004-SUNAT/2B0000).
        self.assertEqual(self._balance(deposit, self._itf_account()), 10.0)
        self.assertAlmostEqual(self._balance(deposit, bank), 2956.30 - 10.0, places=2)
        self.assertEqual(deposit.itf_amount, 10.0)
        self._assert_balanced(deposit)

    def test_itf_not_applied_when_deposit_is_exempt_or_renewed(self):
        self.company.l10n_pe_term_deposit_itf = True
        exempt = self._deposit(itf_applies=False)
        exempt.action_open()
        self.assertEqual(self._balance(exempt, self._itf_account()), 0.0, 'no afecto (exonerado)')
        deposit = self._deposit()
        deposit.action_open()
        deposit._l10n_pe_renew(date(2026, 6, 30))
        self.assertEqual(self._balance(deposit, self._itf_account()), 5.0,
                         'solo el ITF de la apertura: la renovación sin dinero nuevo no lleva ITF')

    def test_early_close_with_penalty(self):
        config = self.env['l10n_pe.term.deposit.account.config']._l10n_pe_get(
            self.company, 'term', self.company.currency_id)
        deposit = self._deposit()
        deposit.action_open()
        deposit._l10n_pe_close(date(2026, 3, 31), interest_received=1000.0, penalty=150.0)
        income = self._balance(deposit, deposit.income_account_id)
        self.assertEqual(income, -850.0, 'sin cuenta de penalidad, rebaja el ingreso')
        self.assertAlmostEqual(self._balance(deposit, self.bank_journal.default_account_id), 850.0, places=2)
        self._assert_balanced(deposit)

        penalty_account = self.env['account.account'].search([
            ('company_ids', 'in', self.company.id), ('account_type', '=', 'expense')], limit=1)
        config.penalty_account_id = penalty_account
        other = self._deposit()
        other.action_open()
        other._l10n_pe_close(date(2026, 3, 31), interest_received=1000.0, penalty=150.0)
        self.assertEqual(self._balance(other, other.income_account_id), -1000.0)
        self.assertEqual(self._balance(other, penalty_account), 150.0, 'la penalidad va a su cuenta')
        self._assert_balanced(other)
        with self.assertRaises(UserError, msg='la penalidad no supera capital e intereses'):
            third = self._deposit()
            third.action_open()
            third._l10n_pe_close(date(2026, 3, 31), interest_received=0.0, penalty=200000.0)

    def test_guarantee_details_and_notice_by_validity(self):
        guarantee = self._deposit(
            deposit_type='guarantee_fund', term_days=0, date_end=False, rate=0.0,
            guarantee_purpose='bond', guarantee_beneficiary_id=self.landlord.id,
            guarantee_reference='CF-2026-0081', guarantee_date_end=date(2026, 9, 30))
        guarantee.action_open()
        self.assertEqual(guarantee._l10n_pe_notice_date(), date(2026, 9, 30), 'sin plazo, avisa por la vigencia')
        with self._today(date(2026, 9, 25)):
            self.env['l10n_pe.term.deposit']._cron_l10n_pe_term_deposits()
        self.assertTrue(guarantee.notice_sent)
        self.assertTrue(guarantee.activity_ids, 'actividad para el responsable')
        self.assertEqual(guarantee.state, 'open', 'la garantía sin plazo no vence sola')

    def test_moves_are_linked_and_interest_report(self):
        deposit = self._deposit()
        deposit.action_open()
        deposit._l10n_pe_accrue(date(2026, 1, 31))
        deposit._l10n_pe_accrue(date(2026, 2, 28))
        self.assertTrue(all(move.l10n_pe_term_deposit_id == deposit for move in deposit.move_ids))
        self.assertTrue(self.env.ref('al_l10n_pe_term_deposit.action_term_deposit_interest'))
        lines = self.env['account.move.line'].search(
            [('l10n_pe_term_deposit_interest', '=', True), ('parent_state', '=', 'posted')])
        mine = lines.filtered(lambda l: l.l10n_pe_term_deposit_id == deposit)
        self.assertEqual(len(mine), 2, 'un apunte de ingreso por devengo')
        self.assertAlmostEqual(sum(mine.mapped('credit')), deposit.interest_accrued, places=2)

    def test_foreign_currency_warning(self):
        if 'l10n_pe_exchange_closing' not in self.env['account.account']._fields:
            self.skipTest('Requiere al_l10n_pe_exchange_closure')
        usd = self.env.ref('base.USD')
        usd.active = True
        deposit = self._deposit(currency_id=usd.id)
        accounts = deposit.deposit_account_id | deposit.interest_account_id
        accounts.write({'l10n_pe_exchange_closing': False})
        deposit.invalidate_recordset(['fx_warning'])
        self.assertIn(deposit.deposit_account_id.code, deposit.fx_warning or '')
        accounts.write({'l10n_pe_exchange_closing': 'summary'})
        deposit.invalidate_recordset(['fx_warning'])
        self.assertFalse(deposit.fx_warning)
        self.assertFalse(self._deposit().fx_warning, 'en soles no hay aviso')

    def test_link_existing_moves(self):
        """Migración a la versión 2: asientos previos enlazados y marcados."""
        deposit = self._deposit()
        deposit.action_open()
        deposit._l10n_pe_accrue(date(2026, 1, 31))
        deposit.move_ids.write({'l10n_pe_term_deposit_id': False})
        deposit.move_ids.line_ids.write({'l10n_pe_term_deposit_interest': False})
        deposit._l10n_pe_link_existing_moves()
        self.assertTrue(all(move.l10n_pe_term_deposit_id == deposit for move in deposit.move_ids))
        flagged = deposit.move_ids.line_ids.filtered('l10n_pe_term_deposit_interest')
        self.assertEqual(flagged.account_id, deposit.income_account_id)
