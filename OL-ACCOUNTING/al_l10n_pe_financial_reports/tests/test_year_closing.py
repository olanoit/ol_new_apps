# -*- coding: utf-8 -*-
"""Cierre del ejercicio y hoja de trabajo.

Escenario 2025 (soles), plan contable peruano:

* venta de mercaderías 1.000 a crédito (701 contra 12, conciliable);
* costo de ventas 600 (691 contra 20);
* sueldos 200 (621 contra 41) con su destino a la 94 (94 contra 79);
* intereses 50 (67 contra 104);
* impuesto a la renta 30 (881 contra 40).

Resultado: 1.000 − 600 − 200 − 50 − 30 = 120 de utilidad. La cascada:
801 = 400, 821 = 400, 831 = 200, 841 = 200, 851 = 150, 891 = 120 y 5911 = 120.
"""
from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

PNL_TYPES = ('income', 'income_other', 'expense', 'expense_depreciation', 'expense_direct_cost')


@tagged('post_install', '-at_install')
class TestYearClosing(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.misc = cls.company_data['default_journal_misc']
        cls.closing_journal = cls.env['account.journal'].with_company(cls.company).create({
            'name': 'Cierre', 'code': 'CIER', 'type': 'general',
            'l10n_pe_journal_kind': 'closing'})
        cls.receivable = cls.company_data['default_account_receivable']
        cls.sales = cls._account('701', 'income')
        cls.cost = cls._account('691', 'expense_direct_cost')
        cls.inventory = cls._account('20', 'asset_current')
        cls.wages = cls._account('621', 'expense')
        cls.wages_payable = cls._account('41', 'liability_current')
        cls.interest = cls._account('67', 'expense')
        cls.bank = cls._account('104', 'asset_cash')
        cls.income_tax = cls._account('881', 'expense')
        cls.tax_payable = cls._account('40', 'liability_current')
        cls.load = cls._account('791', 'income')
        cls.admin = cls._account('94', 'expense')

        cls._entry([(cls.receivable, 1000, cls.partner_a), (cls.sales, -1000, None)])
        cls._entry([(cls.cost, 600, None), (cls.inventory, -600, None)])
        cls._entry([(cls.wages, 200, None), (cls.wages_payable, -200, None)])
        cls._entry([(cls.admin, 200, None), (cls.load, -200, None)])
        cls._entry([(cls.interest, 50, None), (cls.bank, -50, None)])
        cls._entry([(cls.income_tax, 30, None), (cls.tax_payable, -30, None)])

    @classmethod
    def _account(cls, prefix, account_type):
        Account = cls.env['account.account'].with_company(cls.company)
        account = Account.search([
            ('company_ids', 'in', cls.company.id),
            ('code', '=like', prefix + '%'),
            ('account_type', '=', account_type),
        ], limit=1)
        return account or Account.create({
            'code': prefix + '99', 'name': 'Test %s' % prefix, 'account_type': account_type})

    @classmethod
    def _entry(cls, lines, journal=None, entry_date=date(2025, 6, 30)):
        move = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': entry_date,
            'journal_id': (journal or cls.misc).id,
            'line_ids': [Command.create({
                'account_id': account.id,
                'balance': balance,
                'partner_id': partner and partner.id,
            }) for account, balance, partner in lines],
        })
        move.action_post()
        return move

    def _wizard(self, **vals):
        return self.env['l10n_pe.year.closing.wizard'].with_company(self.company).create({
            'date_to': date(2025, 12, 31),
            'journal_id': self.closing_journal.id,
            **vals,
        })

    def _balance(self, code, date_to=date(2025, 12, 31), date_from=None):
        # El plan peruano rellena los códigos: la 5911 es 5911000.
        domain = [
            ('company_id', '=', self.company.id),
            ('parent_state', '=', 'posted'),
            ('account_id.code', '=like', code + '%'),
            ('date', '<=', date_to),
        ]
        if date_from:
            domain.append(('date', '>=', date_from))
        return sum(self.env['account.move.line'].search(domain).mapped('balance'))

    def _closing_balance(self, move, code):
        return sum(move.line_ids.filtered(lambda line: line.account_id.code.startswith(code)).mapped('balance'))

    # ------------------------------------------------------------------

    def test_result_cascade(self):
        wizard = self._wizard()
        wizard.action_generate()
        moves = wizard.move_ids
        self.assertEqual(set(moves.mapped('state')), {'draft'})
        self.assertEqual(set(moves.mapped('l10n_pe_closing_step')), {'result'})
        # Pasos con saldo: 9/79, 801, 821, 831, 841, 851, 891 y 59.
        self.assertEqual(len(moves), 8)

        by_ref = {move.ref: move for move in moves}
        self.assertAlmostEqual(self._closing_balance(by_ref['Margen comercial'], '801'), -400)
        self.assertAlmostEqual(self._closing_balance(by_ref['Valor agregado'], '821'), -400)
        self.assertAlmostEqual(
            self._closing_balance(by_ref['Excedente bruto (insuficiencia bruta) de explotación'], '831'), -200)
        self.assertAlmostEqual(
            self._closing_balance(by_ref['Resultado antes del impuesto a la renta'], '851'), -150)
        self.assertAlmostEqual(self._closing_balance(by_ref['Resultado del ejercicio'], '891'), -120)

        wizard.action_post()
        self.assertEqual(set(moves.mapped('state')), {'posted'})
        self.assertAlmostEqual(self._balance('5911'), -120)
        # Todas las cuentas de resultados y de las clases 8 y 9 quedan en cero.
        lines = self.env['account.move.line'].search([
            ('company_id', '=', self.company.id),
            ('parent_state', '=', 'posted'),
            ('date', '<=', date(2025, 12, 31)),
        ])
        for account in lines.account_id:
            if account.account_type in PNL_TYPES or account.code[:1] in ('8', '9'):
                self.assertAlmostEqual(
                    sum(lines.filtered(lambda line: line.account_id == account).mapped('balance')), 0.0,
                    msg='La cuenta %s no quedó saldada' % account.code)

    def test_loss_goes_to_892_and_5921(self):
        # Con una pérdida extraordinaria de 500 el resultado es −380.
        self._entry([(self._account('659', 'expense'), 500, None), (self.bank, -500, None)])
        wizard = self._wizard()
        wizard.action_generate()
        wizard.action_post()
        self.assertAlmostEqual(self._balance('5921'), 380)
        self.assertAlmostEqual(self._balance('5911'), 0)

    def test_regenerate_replaces_drafts_and_blocks_posted(self):
        wizard = self._wizard()
        wizard.action_generate()
        first = wizard.move_ids
        other = self._entry([(self.bank, 10, None), (self.wages_payable, -10, None)],
                            journal=self.closing_journal, entry_date=date(2025, 12, 31))
        wizard.action_generate()
        self.assertFalse(first.exists())
        self.assertTrue(other.exists(), 'Solo se borran los asientos que generó el asistente.')
        wizard.action_post()
        with self.assertRaises(UserError):
            wizard.action_generate()

    def test_unmapped_account_is_reported(self):
        self._entry([(self._account('871', 'equity'), 10, None), (self.bank, -10, None)])
        with self.assertRaisesRegex(UserError, '871'):
            self._wizard().action_generate()

    def test_date_must_be_fiscal_year_end(self):
        with self.assertRaises(UserError):
            self._wizard(date_to=date(2025, 6, 30)).action_generate()

    def test_balance_closing_and_reopening(self):
        wizard = self._wizard(include_balance=True)
        wizard.action_generate()
        closing = wizard.move_ids.filtered(lambda move: move.l10n_pe_closing_step == 'balance')
        reopening = wizard.move_ids.filtered(lambda move: move.l10n_pe_closing_step == 'reopening')
        self.assertTrue(closing and reopening)
        self.assertEqual(reopening.date, date(2026, 1, 1))
        wizard.action_post()

        # Al 31/12, con los asientos de cierre, todo el balance queda en cero;
        # el 1/1 vuelven los saldos, con la utilidad en la 59.
        for code, reopened in ((self.receivable.code, 1000), (self.inventory.code, -600),
                               (self.bank.code, -50), ('5911', -120)):
            self.assertAlmostEqual(self._balance(code), 0.0, msg=code)
            self.assertAlmostEqual(self._balance(code, date_to=date(2026, 1, 1)), reopened, msg=code)

        # La reapertura queda conciliada con el cierre: la partida abierta del
        # cliente sigue siendo la venta.
        receivable_lines = (closing | reopening).line_ids.filtered(
            lambda line: line.account_id == self.receivable)
        self.assertTrue(all(receivable_lines.mapped('reconciled')))
        open_items = self.env['account.move.line'].search([
            ('account_id', '=', self.receivable.id),
            ('partner_id', '=', self.partner_a.id),
            ('reconciled', '=', False),
            ('parent_state', '=', 'posted'),
        ])
        self.assertEqual(open_items.move_id.l10n_pe_closing_step, False)
        self.assertAlmostEqual(sum(open_items.mapped('amount_residual')), 1000)

    def test_reports_ignore_closing_entries(self):
        whole_journal = ('journal_id.l10n_pe_journal_kind', '!=', 'closing')
        balance_only = ('move_id.l10n_pe_closing_step', 'not in', ('balance', 'reopening'))
        for xmlid, condition in (
                ('l10n_pe_reports.account_financial_report_bs', balance_only),
                ('l10n_pe_reports.account_financial_report_pnl', whole_journal),
                ('al_l10n_pe_financial_reports.pe_worksheet_format_1', whole_journal)):
            report = self.env.ref(xmlid)
            options = report.get_options({})
            self.assertIn(condition, options['forced_domain'], xmlid)
            self.assertTrue(report.filter_analytic, xmlid)

    def test_balance_sheet_shows_result_in_59(self):
        # Con el cierre publicado (resultado y balance), el Balance al 31/12
        # cuenta el traslado a la 59 pero no el cierre del balance.
        wizard = self._wizard(include_balance=True)
        wizard.action_generate()
        wizard.action_post()
        report = self.env.ref('l10n_pe_reports.account_financial_report_bs')
        options = report.get_options({'date': {'date_to': '2025-12-31', 'filter': 'custom', 'mode': 'single'}})
        domain = report._get_options_domain(options, 'from_beginning')
        lines = self.env['account.move.line'].search(domain)
        retained = lines.filtered(lambda line: line.account_id.code.startswith('5911'))
        self.assertAlmostEqual(sum(retained.mapped('balance')), -120)
        receivable = lines.filtered(lambda line: line.account_id == self.receivable)
        self.assertAlmostEqual(sum(receivable.mapped('balance')), 1000)

    def test_unclosed_prior_profit_goes_to_5911(self):
        # 2024 se quedó sin cerrar con 300 de utilidad: el cierre del balance
        # de 2025 la reconoce en la 5911, no en la 5921.
        self._entry([(self.receivable, 300, self.partner_a), (self.sales, -300, None)],
                    entry_date=date(2024, 6, 30))
        wizard = self._wizard(include_balance=True)
        wizard.action_generate()
        closing = wizard.move_ids.filtered(lambda move: move.l10n_pe_closing_step == 'balance')
        residual = closing.line_ids.filtered(
            lambda line: line.name == 'Resultados de ejercicios anteriores sin cierre')
        self.assertTrue(residual.account_id.code.startswith('5911'))
        self.assertAlmostEqual(residual.balance, 300)
        # La reapertura lo revierte en la 5911: el residual solo cuadra el
        # asiento de cierre; la utilidad de 2024 sigue en sus cuentas.
        reopening = wizard.move_ids.filtered(lambda move: move.l10n_pe_closing_step == 'reopening')
        reversed_residual = reopening.line_ids.filtered(
            lambda line: line.name == 'Resultados de ejercicios anteriores sin cierre')
        self.assertEqual(reversed_residual.account_id, residual.account_id)
        self.assertAlmostEqual(reversed_residual.balance, -300)
        wizard.action_post()
        self.assertAlmostEqual(self._balance('5911', date_to=date(2026, 1, 1)), -120)

    def test_balance_closing_foreign_currency(self):
        # Factura en dólares: 100 USD a 3,00 = 300 soles, cobrada en parte
        # (40 USD a 3,50 = 140 soles). Queda 60 USD con 160 soles: saldo y
        # moneda del mismo signo. Un ajuste de cambio de −200 soles deja el
        # saldo en −40 con 60 USD positivos: hay que partir la línea.
        usd = self.setup_other_currency('USD', rounding=0.01)
        common = {'currency_id': usd.id, 'partner_id': self.partner_a.id}
        move = self.env['account.move'].create({
            'move_type': 'entry', 'date': date(2025, 6, 30), 'journal_id': self.misc.id,
            'line_ids': [
                Command.create({'account_id': self.receivable.id, 'balance': 300, 'amount_currency': 100, **common}),
                Command.create({'account_id': self.sales.id, 'balance': -300, 'amount_currency': -100, 'currency_id': usd.id}),
                Command.create({'account_id': self.receivable.id, 'balance': -140, 'amount_currency': -40, **common}),
                Command.create({'account_id': self.bank.id, 'balance': 140, 'amount_currency': 40, 'currency_id': usd.id}),
                Command.create({'account_id': self.receivable.id, 'balance': -200, 'amount_currency': 0, **common}),
                Command.create({'account_id': self.sales.id, 'balance': 200, 'amount_currency': 0, 'currency_id': usd.id}),
            ],
        })
        move.action_post()
        wizard = self._wizard(include_balance=True)
        wizard.action_generate()
        wizard.action_post()
        usd_lines = self.env['account.move.line'].search([
            ('account_id', '=', self.receivable.id),
            ('currency_id', '=', usd.id),
            ('parent_state', '=', 'posted'),
        ])
        at_close = usd_lines.filtered(lambda line: line.date <= date(2025, 12, 31))
        self.assertAlmostEqual(sum(at_close.mapped('balance')), 0.0)
        self.assertAlmostEqual(sum(at_close.mapped('amount_currency')), 0.0)
        reopened = usd_lines.filtered(lambda line: line.date <= date(2026, 1, 1))
        self.assertAlmostEqual(sum(reopened.mapped('balance')), -40)
        self.assertAlmostEqual(sum(reopened.mapped('amount_currency')), 60)
        # El cierre y la reapertura en dólares quedan conciliados entre sí.
        generated = usd_lines.filtered(lambda line: line.move_id.l10n_pe_closing_step)
        self.assertTrue(generated and all(generated.mapped('reconciled')))

    # ------------------------------------------------------------------
    # Hoja de trabajo
    # ------------------------------------------------------------------

    def _worksheet(self, fmt=1):
        report = self.env.ref('al_l10n_pe_financial_reports.pe_worksheet_format_%d' % fmt)
        options = report.get_options({
            'date': {'date_from': '2025-01-01', 'date_to': '2025-12-31', 'filter': 'custom', 'mode': 'range'},
        })
        values = {}
        for line in report._get_lines(options):
            values[line['name']] = {
                column['expression_label']: column.get('no_format') or 0.0
                for column in line['columns']
            }
        return values

    def _row(self, values, account):
        return next(row for name, row in values.items() if name.startswith(account.code))

    def test_worksheet_columns(self):
        self.company.l10n_pe_ws_function_prefixes = '69,70,71,72,73,74,75,76,77,78,88,9,67'
        values = self._worksheet()
        sales = self._row(values, self.sales)
        self.assertAlmostEqual(sales['sum_credit'], 1000)
        self.assertAlmostEqual(sales['balance_credit'], 1000)
        self.assertAlmostEqual(sales['nature_profit'], 1000)
        self.assertAlmostEqual(sales['function_profit'], 1000)
        cost = self._row(values, self.cost)
        self.assertAlmostEqual(cost['function_loss'], 600)
        self.assertFalse(cost.get('nature_loss'))
        wages = self._row(values, self.wages)
        self.assertAlmostEqual(wages['nature_loss'], 200)
        self.assertFalse(wages.get('function_loss'))
        self.assertAlmostEqual(self._row(values, self.admin)['function_loss'], 200)
        load = self._row(values, self.load)
        self.assertFalse(load.get('nature_profit') or load.get('function_profit'))
        receivable = self._row(values, self.receivable)
        self.assertAlmostEqual(receivable['asset'], 1000)
        self.assertNotIn('init_debit', receivable, 'El formato 1 no lleva saldos iniciales.')

        # El resultado del balance y el de función coinciden: 120 de utilidad.
        result = values['Resultado del ejercicio']
        self.assertAlmostEqual(result['liability'], 120)
        self.assertAlmostEqual(result['function_loss'], 120)
        totals = values['Totales']
        for debit, credit in (('sum_debit', 'sum_credit'), ('balance_debit', 'balance_credit'),
                              ('asset', 'liability'), ('function_loss', 'function_profit'),
                              ('nature_loss', 'nature_profit')):
            self.assertAlmostEqual(totals[debit], totals[credit], msg=debit)

    def test_worksheet_format_2_initial_balances(self):
        # Un movimiento de 2024: el cliente y la venta arrastran saldo, pero
        # la venta de 2024 no es saldo inicial de una cuenta de resultados,
        # sino resultados de ejercicios anteriores.
        self._entry([(self.receivable, 300, self.partner_a), (self.sales, -300, None)],
                    entry_date=date(2024, 6, 30))
        values = self._worksheet(fmt=2)
        receivable = self._row(values, self.receivable)
        self.assertAlmostEqual(receivable['init_debit'], 300)
        self.assertAlmostEqual(receivable['period_debit'], 1000)
        self.assertAlmostEqual(receivable['balance_debit'], 1300)
        sales = self._row(values, self.sales)
        self.assertFalse(sales.get('init_credit'))
        self.assertAlmostEqual(sales['period_credit'], 1000)
        prior = values['Resultados de ejercicios anteriores']
        self.assertAlmostEqual(prior['init_credit'], 300)
        self.assertAlmostEqual(prior['liability'], 300)
        totals = values['Totales']
        self.assertAlmostEqual(totals['asset'], totals['liability'])

    def test_worksheet_excludes_closing_entries(self):
        wizard = self._wizard()
        wizard.action_generate()
        wizard.action_post()
        values = self._worksheet()
        self.assertAlmostEqual(self._row(values, self.sales)['nature_profit'], 1000)
        self.assertFalse(any(name.startswith('5911') for name in values))
