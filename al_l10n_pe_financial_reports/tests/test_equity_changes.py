# -*- coding: utf-8 -*-
"""3.19 Estado de Cambios en el Patrimonio Neto.

Escenario (soles):

* 2025, sin asiento de cierre: aporte de capital 10.000 y utilidad 3.000.
* 2026: aumento de capital 2.000, utilidad 1.000 (ingresos 1.500, gastos
  500), revaluación 400 (57), reserva 300 (59 → 58), dividendos 200 (59 → 44)
  y los asientos de cierre del 31/12 (resultados → 89 → 59) en un diario de
  naturaleza «Cierre».

Informe 2026: saldo inicial 13.000; movimientos 1.000 + 400 + 2.000 + 300
− 500 = 3.200; saldo final 16.200, igual al patrimonio del Balance.
"""
from odoo import Command
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

REPORT = 'al_l10n_pe_financial_reports.pe_statement_changes_equity'


@tagged('post_install', '-at_install')
class TestEquityChanges(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.report = cls.env.ref(REPORT)
        cls.journal = cls.company_data['default_journal_misc']
        Journal = cls.env['account.journal'].with_company(cls.company)
        cls.closing_journal = Journal.create({
            'name': 'Cierre', 'code': 'CIER', 'type': 'general',
            'l10n_pe_journal_kind': 'closing'})
        cls.opening_journal = Journal.create({
            'name': 'Apertura', 'code': 'APER', 'type': 'general',
            'l10n_pe_journal_kind': 'opening'})
        cls.bank = cls._account('104', 'asset_cash')
        cls.fixed = cls._account('33', 'asset_fixed')
        cls.dividends_payable = cls._account('44', 'liability_payable', reconcile=True)
        cls.capital = cls._account('50', 'equity')
        cls.revaluation = cls._account('57', 'equity')
        cls.reserves = cls._account('58', 'equity')
        cls.retained = cls._account('59', 'equity')
        cls.result_account = cls._account('89', 'equity')
        cls.income = cls._account('70', 'income')
        cls.expense = cls._account('63', 'expense')

    @classmethod
    def _account(cls, prefix, account_type, reconcile=False):
        Account = cls.env['account.account'].with_company(cls.company)
        account = Account.search([
            ('company_ids', 'in', cls.company.id),
            ('code', '=like', prefix + '%'),
            ('account_type', '=', account_type),
        ], limit=1)
        return account or Account.create({
            'code': prefix + '9999', 'name': 'Test %s' % prefix,
            'account_type': account_type, 'reconcile': reconcile,
            'company_ids': [Command.set(cls.company.ids)]})

    @classmethod
    def _entry(cls, date, lines, journal=None):
        """``lines``: [(cuenta, importe)], positivo al debe."""
        move = cls.env['account.move'].with_company(cls.company).create({
            'move_type': 'entry',
            'date': date,
            'journal_id': (journal or cls.journal).id,
            'line_ids': [Command.create({
                'name': 'Test', 'account_id': account.id,
                'debit': max(amount, 0.0), 'credit': max(-amount, 0.0),
            }) for account, amount in lines],
        })
        move.action_post()
        return move

    def _year_scenario(self):
        e = self._entry
        e('2025-03-01', [(self.bank, 10000), (self.capital, -10000)])
        e('2025-06-30', [(self.bank, 3000), (self.income, -3000)])
        e('2026-02-01', [(self.bank, 2000), (self.capital, -2000)])
        e('2026-05-31', [(self.bank, 1500), (self.income, -1500)])
        e('2026-06-30', [(self.expense, 500), (self.bank, -500)])
        e('2026-07-01', [(self.fixed, 400), (self.revaluation, -400)])
        e('2026-08-01', [(self.retained, 300), (self.reserves, -300)])
        e('2026-09-01', [(self.retained, 200), (self.dividends_payable, -200)])
        e('2026-12-31', [(self.income, 1500), (self.expense, -500),
                         (self.result_account, -1000)], self.closing_journal)
        e('2026-12-31', [(self.result_account, 1000), (self.retained, -1000)],
          self.closing_journal)

    # ------------------------------------------------------------------
    # Ayudantes del informe
    # ------------------------------------------------------------------
    def _options(self, report, date_from='2026-01-01', date_to='2026-12-31'):
        return report.with_company(self.company).get_options({
            'selected_variant_id': report.id,
            'date': {'date_from': date_from, 'date_to': date_to,
                     'mode': 'range', 'filter': 'custom'},
            'unfold_all': True,
        })

    def _values(self, report, options):
        """``{código de línea: {etiqueta de columna: valor}}``."""
        lines = report.with_company(self.company)._get_lines(options)
        codes = {line.id: line.code for line in report.line_ids}
        result = {}
        for line in lines:
            line_id = report._get_res_id_from_line_id(line['id'], 'account.report.line')
            if line_id in codes and not report._get_res_id_from_line_id(line['id'], 'account.account'):
                result[codes[line_id]] = {
                    column['expression_label']: column.get('no_format')
                    for column in line['columns']}
        return result

    def _equity(self, **dates):
        options = self._options(self.report, **dates)
        return self._values(self.report, options)

    def _balance_sheet_equity(self, date_to):
        balance_sheet = self.env.ref('account_reports.balance_sheet')
        options = self._options(balance_sheet, date_to, date_to)
        return self._values(balance_sheet, options)['EQ']['balance']

    # ------------------------------------------------------------------
    # Pruebas
    # ------------------------------------------------------------------
    def test_report_definition(self):
        self.assertEqual(self.report.country_id.code, 'PE')
        self.assertEqual(self.report.column_ids.mapped('expression_label'),
                         ['movement_note', 'opening', 'movement', 'closing'])
        self.assertIn(self.report, self.env['account.report'].search(
            [('country_id.code', '=', 'PE')]))

    def test_year_with_closing_entries(self):
        self._year_scenario()
        values = self._equity()
        self.assertAlmostEqual(values['SCEP_OPENING']['opening'], 13000)
        self.assertAlmostEqual(values['SCEP_REEXPRESSED']['opening'], 13000)
        self.assertAlmostEqual(values['SCEP_NET_INCOME']['movement'], 1000,
                               msg='los asientos de cierre no anulan el resultado')
        self.assertAlmostEqual(values['SCEP_OCI']['movement'], 400)
        self.assertAlmostEqual(values['SCEP_TOTAL_INTEGRAL']['movement'], 1400)
        self.assertAlmostEqual(values['SCEP_CAPITAL_ISSUE']['movement'], 2000)
        self.assertAlmostEqual(values['SCEP_INVESTMENT_SHARES']['movement'], 0)
        self.assertAlmostEqual(values['SCEP_RESERVES']['movement'], 300)
        self.assertAlmostEqual(values['SCEP_RETAINED']['movement'], -500,
                               msg='reserva y dividendos, sin el traslado del cierre')
        self.assertAlmostEqual(values['SCEP_OTHER']['movement'], 0,
                               msg='la 89 solo se mueve en el cierre')
        self.assertAlmostEqual(values['SCEP_TOTAL_CHANGES']['movement'], 3200)
        self.assertAlmostEqual(values['SCEP_CLOSING']['opening'], 13000)
        self.assertAlmostEqual(values['SCEP_CLOSING']['movement'], 3200)
        self.assertAlmostEqual(values['SCEP_CLOSING']['closing'], 16200)

    def test_closing_matches_the_balance_sheet(self):
        self._year_scenario()
        for date_from, date_to in (('2026-01-01', '2026-12-31'),
                                   ('2026-01-01', '2026-06-30'),
                                   ('2025-01-01', '2025-12-31')):
            with self.subTest(periodo=date_to):
                closing = self._equity(date_from=date_from, date_to=date_to)['SCEP_CLOSING']['closing']
                self.assertAlmostEqual(closing, self._balance_sheet_equity(date_to))

    def test_same_result_without_closing_entries(self):
        """Sin cierre el resultado sigue en las cuentas de resultados: el
        informe da lo mismo."""
        e = self._entry
        e('2026-02-01', [(self.bank, 2000), (self.capital, -2000)])
        e('2026-05-31', [(self.bank, 1500), (self.income, -1500)])
        values = self._equity()
        self.assertAlmostEqual(values['SCEP_NET_INCOME']['movement'], 1500)
        self.assertAlmostEqual(values['SCEP_CLOSING']['closing'], 3500)
        self.assertAlmostEqual(values['SCEP_CLOSING']['closing'],
                               self._balance_sheet_equity('2026-12-31'))

    def test_opening_entries_are_the_initial_balance(self):
        """Saldos iniciales cargados al empezar con Odoo."""
        self._entry('2026-01-01', [(self.bank, 5000), (self.capital, -5000)],
                    self.opening_journal)
        self._entry('2026-03-01', [(self.bank, 700), (self.capital, -700)])
        values = self._equity()
        self.assertAlmostEqual(values['SCEP_OPENING']['opening'], 5000)
        self.assertAlmostEqual(values['SCEP_CAPITAL_ISSUE']['movement'], 700)
        self.assertAlmostEqual(values['SCEP_CLOSING']['closing'], 5700)

    def test_other_equity_accounts_keep_the_total(self):
        other = self._account('53', 'equity')
        self._entry('2026-04-01', [(self.bank, 250), (other, -250)])
        values = self._equity()
        self.assertAlmostEqual(values['SCEP_OTHER']['movement'], 250)
        self.assertAlmostEqual(values['SCEP_CLOSING']['closing'], 250)

    def test_editable_lines_add_to_the_total(self):
        self._entry('2026-02-01', [(self.bank, 2000), (self.capital, -2000)])
        Value = self.env['account.report.external.value']
        for xmlid, amount in (('pe_scep_expr_policy_movement', -100),
                              ('pe_scep_expr_owner_contrib_movement', 50)):
            Value.create({
                'name': 'Ajuste de prueba', 'date': '2026-12-31', 'value': amount,
                'company_id': self.company.id,
                'target_report_expression_id': self.env.ref(
                    'al_l10n_pe_financial_reports.%s' % xmlid).id,
            })
        Value.create({
            'name': 'Nota', 'date': '2026-12-31', 'text_value': 'Nota 12',
            'company_id': self.company.id,
            'target_report_expression_id': self.env.ref(
                'al_l10n_pe_financial_reports.pe_scep_expr_policy_note').id,
        })
        values = self._equity()
        self.assertAlmostEqual(values['SCEP_REEXPRESSED']['opening'], -100)
        self.assertEqual(values['SCEP_POLICY']['movement_note'], 'Nota 12')
        self.assertAlmostEqual(values['SCEP_OWNER_CONTRIB']['movement'], 50)
        self.assertAlmostEqual(values['SCEP_CLOSING']['closing'], 1950)

    def test_menus(self):
        root = self.env.ref('al_l10n_pe_financial_reports.menu_pe_financial_statements')
        self.assertEqual(root.parent_id, self.env.ref('al_account_base.al_l10n_pe_root'))
        self.assertEqual(root.child_id.mapped('name'), [
            'Balance', 'Estado de resultados',
            '3.19 Estado de Cambios en el Patrimonio Neto'])
