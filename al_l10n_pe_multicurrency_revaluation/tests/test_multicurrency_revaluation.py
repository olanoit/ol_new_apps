# -*- coding: utf-8 -*-
"""Pruebas del T.C. compra/venta por cuenta en ganancias/pérdidas no realizadas.

Escenario: USD a 3,700 venta y 3,720 compra el 01/01/2024; los saldos se
registran a 3,700 (100 USD = S/ 370,00), así que revaluar a venta no ajusta y
revaluar a compra ajusta S/ 2,00.
"""
from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

DATE = '2024-01-01'


@tagged('post_install', '-at_install')
class TestMulticurrencyRevaluation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Compañía propia: el informe lee todos los apuntes de la compañía y
        # los datos reales de la base alterarían los totales.
        cls.report = cls.env.ref('account_reports.multicurrency_revaluation_report')
        cls.usd = cls.env.ref('base.USD')
        cls.usd.active = True
        cls.pen = cls.env.ref('base.PEN')
        cls.pen.active = True
        peru = cls.env.ref('base.pe')
        cls.company = cls.env['res.company'].create({
            'name': 'Revaluación PE Test S.A.C.',
            'currency_id': cls.pen.id,
            'country_id': peru.id,
            'account_fiscal_country_id': peru.id,
        })
        cls.env.user.company_ids = [Command.link(cls.company.id)]
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id]))

        cls.journal = cls.env['account.journal'].create({
            'name': 'Varios', 'code': 'VRT', 'type': 'general',
            'company_id': cls.company.id,
        })
        Account = cls.env['account.account'].with_company(cls.company)
        cls.expense = Account.create({
            'name': 'Gasto', 'code': '659001', 'account_type': 'expense',
            'company_ids': [Command.set(cls.company.ids)],
        })
        cls.income = Account.create({
            'name': 'Ingreso', 'code': '759001', 'account_type': 'income',
            'company_ids': [Command.set(cls.company.ids)],
        })
        cls.payable = Account.create({
            'name': 'Por pagar ME', 'code': '421201', 'account_type': 'liability_payable',
            'reconcile': True, 'company_ids': [Command.set(cls.company.ids)],
        })
        cls.receivable = Account.create({
            'name': 'Por cobrar ME', 'code': '121201', 'account_type': 'asset_receivable',
            'reconcile': True, 'company_ids': [Command.set(cls.company.ids)],
        })
        cls.env['res.currency.rate'].create({
            'name': DATE,
            'currency_id': cls.usd.id,
            'company_id': cls.company.id,
            'rate_sale': 3.700,
            'rate_purchase': 3.720,
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Socio ME'})

    # ------------------------------------------------------------------
    # Ayudantes
    # ------------------------------------------------------------------
    @classmethod
    def _post_entry(cls, account, amount_currency, balance):
        """Saldo en USD en ``account`` contra una cuenta de resultado en soles."""
        counterpart = cls.expense if balance > 0 else cls.income
        move = cls.env['account.move'].with_company(cls.company).create({
            'move_type': 'entry',
            'date': DATE,
            'journal_id': cls.journal.id,
            'line_ids': [
                Command.create({
                    'name': 'ME', 'partner_id': cls.partner.id,
                    'account_id': account.id, 'currency_id': cls.usd.id,
                    'amount_currency': amount_currency, 'balance': balance,
                }),
                Command.create({
                    'name': 'Contrapartida', 'account_id': counterpart.id,
                    'currency_id': cls.usd.id,
                    'amount_currency': -amount_currency, 'balance': -balance,
                }),
            ],
        })
        move.action_post()
        return move

    def _options(self, company=None):
        report = self.report.with_company(company or self.company)
        return report.get_options({
            'selected_variant_id': self.report.id,
            'date': {'date_from': DATE, 'date_to': DATE, 'mode': 'range', 'filter': 'custom'},
            'unfold_all': True,
        })

    def _lines(self, options):
        return self.report.with_company(self.company)._get_lines(options)

    def _account_line(self, lines, account):
        for line in lines:
            if self.report._get_res_id_from_line_id(line['id'], 'account.account') == account.id:
                return line
        return None

    def _currency_line(self, lines):
        for line in lines:
            if self.report._get_model_info_from_id(line['id']) == ('res.currency', self.usd.id):
                return line
        return None

    @staticmethod
    def _value(line, options, label):
        for column, column_data in zip(line['columns'], options['columns']):
            if column_data['expression_label'] == label:
                return column['no_format']
        raise AssertionError('Sin columna %s' % label)

    # ------------------------------------------------------------------
    # Campo en la cuenta
    # ------------------------------------------------------------------
    def test_field_visible_receivable_payable(self):
        self.assertTrue(self.payable.l10n_pe_revaluation_rate_visible)
        self.assertTrue(self.receivable.l10n_pe_revaluation_rate_visible)

    def test_field_hidden_income_expense(self):
        """El informe nunca revalúa resultados, aunque tengan moneda."""
        account = self.env['account.account'].with_company(self.company).create({
            'name': 'Gasto USD', 'code': '659002', 'account_type': 'expense',
            'currency_id': self.usd.id, 'company_ids': [Command.set(self.company.ids)],
        })
        self.assertFalse(account.l10n_pe_revaluation_rate_visible)
        self.assertFalse(self.expense.l10n_pe_revaluation_rate_visible)

    def test_field_visible_foreign_bank(self):
        account = self.env['account.account'].with_company(self.company).create({
            'name': 'Banco USD', 'code': '104201', 'account_type': 'asset_cash',
            'currency_id': self.usd.id, 'company_ids': [Command.set(self.company.ids)],
        })
        self.assertTrue(account.l10n_pe_revaluation_rate_visible)

    def test_field_hidden_outside_peru(self):
        chile = self.env.ref('base.cl')
        company = self.env['res.company'].create({
            'name': 'CL Test', 'currency_id': self.env.ref('base.CLP').id,
            'country_id': chile.id, 'account_fiscal_country_id': chile.id,
        })
        account = self.env['account.account'].with_company(company).create({
            'name': 'CL por pagar', 'code': '421009', 'account_type': 'liability_payable',
            'reconcile': True, 'company_ids': [Command.set(company.ids)],
        })
        self.assertFalse(account.l10n_pe_revaluation_rate_visible)

    # ------------------------------------------------------------------
    # Tasas
    # ------------------------------------------------------------------
    def test_rates_by_type(self):
        self.assertEqual(self.usd._l10n_pe_revaluation_rates(self.company, DATE, 'sale'),
                         {self.usd.id: 3.7})
        self.assertEqual(self.usd._l10n_pe_revaluation_rates(self.company, DATE, 'purchase'),
                         {self.usd.id: 3.72})
        self.assertEqual(self.usd._l10n_pe_revaluation_rates(self.company, '2023-12-31', 'sale'), {})

    # ------------------------------------------------------------------
    # Informe
    # ------------------------------------------------------------------
    def test_generic_rate_without_type(self):
        self._post_entry(self.payable, -100.0, -370.0)
        options = self._options()
        line = self._account_line(self._lines(options), self.payable)
        self.assertAlmostEqual(self._value(line, options, 'adjustment'), 0.0, places=2)
        self.assertEqual(self._value(line, options, 'rate_used'), 'S/ 3.700')

    def test_purchase_rate_changes_adjustment(self):
        self.payable.l10n_pe_revaluation_rate_type = 'purchase'
        self._post_entry(self.payable, -100.0, -370.0)
        options = self._options()
        line = self._account_line(self._lines(options), self.payable)
        self.assertAlmostEqual(self._value(line, options, 'balance_current'), -372.0, places=2)
        self.assertAlmostEqual(self._value(line, options, 'adjustment'), -2.0, places=2)
        self.assertEqual(self._value(line, options, 'rate_used'), 'S/ 3.720')

    def test_sale_rate(self):
        self.receivable.l10n_pe_revaluation_rate_type = 'sale'
        self._post_entry(self.receivable, 100.0, 370.0)
        options = self._options()
        line = self._account_line(self._lines(options), self.receivable)
        self.assertAlmostEqual(self._value(line, options, 'adjustment'), 0.0, places=2)
        self.assertEqual(self._value(line, options, 'rate_used'), 'S/ 3.700')

    def test_currency_total_mixes_rates(self):
        """El total de la moneda suma los ajustes y deja el T.C. en blanco."""
        self.payable.l10n_pe_revaluation_rate_type = 'purchase'
        self.receivable.l10n_pe_revaluation_rate_type = 'sale'
        self._post_entry(self.payable, -100.0, -370.0)
        self._post_entry(self.receivable, 250.0, 925.0)
        options = self._options()
        lines = self._lines(options)
        total = self._currency_line(lines)
        self.assertEqual(self._value(total, options, 'rate_used'), '')
        self.assertAlmostEqual(self._value(total, options, 'balance_currency'), 150.0, places=2)
        self.assertAlmostEqual(self._value(total, options, 'balance_operation'), 555.0, places=2)
        self.assertAlmostEqual(self._value(total, options, 'adjustment'), -2.0, places=2)
        self.assertEqual(total['name'], 'USD (1 USD = S/ 3.700)')
        self.assertEqual(self._value(self._account_line(lines, self.payable), options, 'rate_used'), 'S/ 3.720')
        self.assertEqual(self._value(self._account_line(lines, self.receivable), options, 'rate_used'), 'S/ 3.700')

    def test_same_type_keeps_rate_in_total(self):
        self.payable.l10n_pe_revaluation_rate_type = 'purchase'
        self.receivable.l10n_pe_revaluation_rate_type = 'purchase'
        self._post_entry(self.payable, -100.0, -370.0)
        self._post_entry(self.receivable, 100.0, 370.0)
        options = self._options()
        total = self._currency_line(self._lines(options))
        self.assertEqual(self._value(total, options, 'rate_used'), 'S/ 3.720')
        self.assertAlmostEqual(self._value(total, options, 'adjustment'), 0.0, places=2)

    def test_non_peru_company_untouched(self):
        chile = self.env.ref('base.cl')
        self.env.ref('base.CLP').active = True
        company = self.env['res.company'].create({
            'name': 'CL Test 2', 'currency_id': self.env.ref('base.CLP').id,
            'country_id': chile.id, 'account_fiscal_country_id': chile.id,
        })
        self.env.user.company_ids = [Command.link(company.id)]
        options = self._options(company)
        self.assertEqual(options['l10n_pe_revaluation_groups'], [])
        self.assertNotIn('rate_used', [c['expression_label'] for c in options['columns']])

    # ------------------------------------------------------------------
    # Asiento de ajuste
    # ------------------------------------------------------------------
    def test_wizard_uses_account_rate(self):
        self.payable.l10n_pe_revaluation_rate_type = 'purchase'
        self._post_entry(self.payable, -100.0, -370.0)
        options = self._options()
        wizard = self.env['account.multicurrency.revaluation.wizard'].with_company(self.company).with_context(
            multicurrency_revaluation_report_options=options,
        ).new({
            'journal_id': self.journal.id,
            'expense_provision_account_id': self.expense.id,
            'income_provision_account_id': self.income.id,
        })
        lines = [command[2] for command in wizard._get_move_vals()['line_ids']]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]['account_id'], self.payable.id)
        self.assertEqual(lines[0]['name'], 'Provisión de USD (T.C. S/ 3.720)')
        self.assertAlmostEqual(lines[0]['credit'], 2.0, places=2)
        self.assertEqual(lines[1]['account_id'], self.expense.id)
        self.assertAlmostEqual(lines[1]['debit'], 2.0, places=2)
