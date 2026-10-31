# -*- coding: utf-8 -*-
"""Balance y Estado de resultados peruanos con asientos de destino (9x / 79).

Escenario (soles):

* 2025: aporte de capital 10.000; ingresos 3.000; gastos 1.200 con su
  destino 94 / 791 por 1.200.
* 2026: ingresos 1.500; gastos 500 con su destino 94 / 791 por 500.

El destino es analítico: no cambia el resultado (2025: 1.800; 2026: 1.000)
ni el balance (activo 13.800 = patrimonio 13.800).
"""
from odoo import Command
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestDestinationReports(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.journal = cls.company_data['default_journal_misc']
        cls.pnl = cls.env.ref('l10n_pe_reports.account_financial_report_pnl')
        cls.bs = cls.env.ref('l10n_pe_reports.account_financial_report_bs')
        cls.bank = cls._account('104', 'asset_cash')
        cls.capital = cls._account('50', 'equity')
        cls.income = cls._account('70', 'income')
        cls.expense = cls._account('63', 'expense')
        cls.destination = cls._account('94', 'expense')
        cls.load = cls._account('791', 'income')

    @classmethod
    def _account(cls, prefix, account_type):
        Account = cls.env['account.account'].with_company(cls.company)
        account = Account.search([
            ('company_ids', 'in', cls.company.id),
            ('code', '=like', prefix + '%'),
            ('account_type', '=', account_type),
        ], limit=1)
        return account or Account.create({
            'code': prefix + '9999', 'name': 'Test %s' % prefix,
            'account_type': account_type,
            'company_ids': [Command.set(cls.company.ids)]})

    def _entry(self, date, lines):
        """``lines``: [(cuenta, importe)], positivo al debe."""
        move = self.env['account.move'].with_company(self.company).create({
            'move_type': 'entry',
            'date': date,
            'journal_id': self.journal.id,
            'line_ids': [Command.create({
                'name': 'Test', 'account_id': account.id,
                'debit': max(amount, 0.0), 'credit': max(-amount, 0.0),
            }) for account, amount in lines],
        })
        move.action_post()

    def _scenario(self):
        e = self._entry
        e('2025-01-15', [(self.bank, 10000), (self.capital, -10000)])
        e('2025-06-30', [(self.bank, 3000), (self.income, -3000)])
        e('2025-07-31', [(self.expense, 1200), (self.bank, -1200)])
        e('2025-07-31', [(self.destination, 1200), (self.load, -1200)])
        e('2026-05-31', [(self.bank, 1500), (self.income, -1500)])
        e('2026-06-30', [(self.expense, 500), (self.bank, -500)])
        e('2026-06-30', [(self.destination, 500), (self.load, -500)])

    def _values(self, report, date_from, date_to):
        """``{código de línea: saldo}``."""
        report = report.with_company(self.company)
        options = report.get_options({
            'selected_variant_id': report.id,
            'date': {'date_from': date_from, 'date_to': date_to,
                     'mode': 'range', 'filter': 'custom'},
        })
        codes = {line.id: line.code for line in report.line_ids}
        result = {}
        for line in report._get_lines(options):
            line_id = report._get_res_id_from_line_id(line.id, 'account.report.line')
            if line_id in codes and not report._get_res_id_from_line_id(line.id, 'account.account'):
                result[codes[line_id]] = line.columns[0].no_format or 0.0
        return result

    def test_load_account_is_not_income(self):
        self._scenario()
        values = self._values(self.pnl, '2026-01-01', '2026-12-31')
        self.assertAlmostEqual(values.get('PE_PNL_A_5', 0.0), 0.0,
                               msg='la 79 no es «Otro ingreso operativo»')
        self.assertAlmostEqual(values['PE_PNL_F'], 1000.0)

    def test_balance_sheet_balances(self):
        self._scenario()
        for date_to, previous, current in (('2025-12-31', 0.0, 1800.0),
                                           ('2026-12-31', 1800.0, 1000.0)):
            with self.subTest(fecha=date_to):
                values = self._values(self.bs, date_to[:4] + '-01-01', date_to)
                self.assertAlmostEqual(values.get('PE_BS_E_U_PY', 0.0), previous,
                                       msg='la 79 no es resultado de años anteriores')
                self.assertAlmostEqual(values['PE_BS_E_U_CY'], current)
                self.assertAlmostEqual(values['PE_BS_A_TOTAL'], values['PE_BS_EL_TOTAL'])
                self.assertAlmostEqual(values['PE_BS_A_TOTAL'], 10000.0 + previous + current)
