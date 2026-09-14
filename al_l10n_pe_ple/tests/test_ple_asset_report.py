# -*- coding: utf-8 -*-
"""Libro 7 en pantalla: informe «Registro de Activos Fijos (PLE 7.1)»."""
import base64
import zipfile
from datetime import date
from io import BytesIO

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

RUC_TEST = '20512528458'


@tagged('post_install', '-at_install')
class TestPleAssetReport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        if not (cls.company.vat and len(cls.company.vat) == 11):
            cls.company.vat = RUC_TEST
        Account = cls.env['account.account'].with_company(cls.company)
        fixed = Account.search([('account_type', '=', 'asset_fixed')], limit=2)
        cls.account_asset, cls.account_dep = fixed[0], fixed[-1]
        cls.account_exp = Account.search(
            [('account_type', '=', 'expense')], limit=1)
        cls.journal = cls.env['account.journal'].search(
            [('company_id', '=', cls.company.id),
             ('type', '=', 'general')], limit=1)
        cls.report = cls.env.ref('al_l10n_pe_ple.ple_asset_7_1_report')
        cls.handler = cls.env['l10n_pe.ple.asset.report.handler']

    def _asset(self, name, code, value, acquisition):
        asset = self.env['account.asset'].create({
            'name': name,
            'original_value': value,
            'acquisition_date': acquisition,
            'prorata_date': acquisition,
            'method': 'linear',
            'method_number': 5,
            'method_period': '12',
            'account_asset_id': self.account_asset.id,
            'account_depreciation_id': self.account_dep.id,
            'account_depreciation_expense_id': self.account_exp.id,
            'journal_id': self.journal.id,
            'l10n_pe_ple_code': code,
            'l10n_pe_asset_type': '1',
        })
        asset.write({'state': 'open'})
        return asset

    def _depreciate(self, asset, amount, move_date, move_type=None):
        values = {
            'move_type': 'entry',
            'date': move_date,
            'journal_id': self.journal.id,
            'asset_id': asset.id,
            'line_ids': [
                (0, 0, {'account_id': self.account_exp.id,
                        'debit': amount, 'credit': 0.0}),
                (0, 0, {'account_id': self.account_dep.id,
                        'debit': 0.0, 'credit': amount}),
            ],
        }
        if move_type:
            values['asset_move_type'] = move_type
        move = self.env['account.move'].create(values)
        move.action_post()
        return move

    def _options(self, year=2025):
        return self.report.get_options({
            'date': {'date_to': '%d-12-31' % year, 'filter': 'custom',
                     'mode': 'single'},
        })

    def _values(self, asset, year=2025):
        rows = self.env['l10n_pe.ple.asset.book']._asset_71_values(
            self.company, year)
        return next(values for record, values in rows if record == asset)

    # ------------------------------------------------------------------
    # Opciones
    # ------------------------------------------------------------------
    def test_subheaders_cover_all_columns(self):
        options = self._options()
        spans = sum(h['colspan'] for h in options['custom_columns_subheaders'])
        self.assertEqual(spans, len(options['columns']))

    def test_export_buttons_offered(self):
        names = [b['name'] for b in self._options()['buttons']]
        for label in ('TXT 7.1', 'XLSX 7.1', 'TXT 7.3', 'TXT 7.4'):
            self.assertIn(label, names)

    # ------------------------------------------------------------------
    # Líneas
    # ------------------------------------------------------------------
    def test_lines_grouped_by_account_with_total(self):
        asset = self._asset('Camioneta informe', 'AF-REP-001', 12000.0,
                            date(2025, 3, 1))
        self._depreciate(asset, 2000.0, date(2025, 12, 31))
        options = self._options()
        lines = self.report._get_lines(options)
        labels = [c['expression_label'] for c in options['columns']]

        asset_line = next(l for l in lines if 'AF-REP-001' in l['name'])
        cells = dict(zip(labels, asset_line['columns']))
        self.assertEqual(asset_line['level'], 2)
        self.assertEqual(cells['additions']['no_format'], 12000.0)
        self.assertEqual(cells['dep_year']['no_format'], 2000.0)
        self.assertEqual(cells['historical_value']['no_format'], 12000.0)
        self.assertEqual(cells['dep_historical']['no_format'], 2000.0)

        self.assertEqual(lines[-1]['name'], 'Total')
        account_line = next(
            l for l in lines if l['level'] == 1
            and l['name'].startswith(self.account_asset.code))
        self.assertGreaterEqual(
            dict(zip(labels, account_line['columns']))['additions']['no_format'],
            12000.0)

    def test_disposal_move_is_not_depreciation(self):
        """El asiento de baja no suma al campo 30; el activo sale del
        registro con su depreciación (campos 18 y 31 en negativo)."""
        asset = self._asset('Equipo dado de baja', 'AF-REP-002', 10000.0,
                            date(2024, 1, 1))
        self._depreciate(asset, 2000.0, date(2024, 12, 31))
        self._depreciate(asset, 1000.0, date(2025, 6, 30))
        self._depreciate(asset, 7000.0, date(2025, 7, 1), 'disposal')
        asset.write({'disposal_date': date(2025, 7, 1), 'state': 'close'})

        values = self._values(asset)
        self.assertEqual(values['initial'], 10000.0)
        self.assertEqual(values['retirements'], -10000.0)
        self.assertEqual(values['historical_value'], 0.0)
        self.assertEqual(values['dep_prior'], 2000.0)
        self.assertEqual(values['dep_year'], 1000.0)
        self.assertEqual(values['dep_retirements'], -3000.0)
        self.assertEqual(values['dep_historical'], 0.0)

    # ------------------------------------------------------------------
    # Exportación: pantalla y asistente generan lo mismo
    # ------------------------------------------------------------------
    def test_txt_matches_wizard(self):
        self._asset('Servidor informe', 'AF-REP-003', 5000.0, date(2025, 2, 1))
        options = self._options()
        result = self.handler.l10n_pe_asset_export_0701_txt(options)
        self.assertIn('070100', result['file_name'])

        wizard = self.env['l10n_pe.ple.export.wizard'].create({
            'year': 2025, 'export_71': True, 'generate_xlsx': False})
        wizard.action_export()
        self.assertEqual(result['file_name'], wizard.file_name)
        self.assertEqual(result['file_content'],
                         base64.b64decode(wizard.file_data))

    def test_xlsx_export_is_valid_workbook(self):
        self._asset('Laptop informe', 'AF-REP-004', 3000.0, date(2025, 5, 1))
        result = self.handler.l10n_pe_asset_export_0701_xlsx(self._options())
        self.assertEqual(result['file_type'], 'xlsx')
        with zipfile.ZipFile(BytesIO(result['file_content'])) as workbook:
            shared = workbook.read('xl/sharedStrings.xml').decode('utf-8')
        self.assertIn('AF-REP-004', shared)
