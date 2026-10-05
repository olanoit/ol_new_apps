# -*- coding: utf-8 -*-
"""El motor de datos de los informes SIRE debe funcionar también en pantalla.

El de ``l10n_pe_reports`` falla con ``UndefinedTable`` porque escribe el ``FROM``
a mano e inyecta el ``WHERE`` del ORM. Ver ``docs/tecport/BUG_EE_RCE_SQL.md``.
"""
from datetime import date

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

HANDLERS = (
    ('RCE 8.4', 'l10n_pe.tax.ple.8.1.report.handler'),
    ('RCE 8.5', 'l10n_pe.tax.ple.8.2.report.handler'),
    ('RVIE 14.4', 'l10n_pe.tax.ple.14.1.report.handler'),
)


@tagged('post_install', '-at_install')
class TestPleReportEngine(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.company.vat = '20512528458'

    def _options(self, report):
        return report.get_options({
            'date': {
                'date_from': '2026-03-01',
                'date_to': '2026-03-31',
                'filter': 'custom',
                'mode': 'range',
            },
            'selected_variant_id': report.id,
        })

    def test_reports_render_on_screen(self):
        """Los tres informes del SIRE se abren sin error de SQL."""
        for label, handler_name in HANDLERS:
            report = self.env['account.report'].search(
                [('custom_handler_model_name', '=', handler_name)], limit=1)
            self.assertTrue(report, 'falta el informe %s' % label)
            with self.subTest(report=label):
                # No debe lanzar: antes reventaba con psycopg2 UndefinedTable.
                report._get_lines(self._options(report))

    def test_engine_returns_empty_dict_without_grouping(self):
        """Sin agrupación y sin datos, el motor devuelve el dict de columnas."""
        handler = self.env['l10n_pe.tax.ple.8.1.report.handler']
        report = self.env['account.report'].search(
            [('custom_handler_model_name', '=',
              'l10n_pe.tax.ple.8.1.report.handler')], limit=1)
        result = handler.with_company(self.company)._get_ple_report_data(
            self._options(report), None)
        self.assertIsInstance(result, dict)
        self.assertIn('base_igv', result)

    def test_engine_groups_by_move(self):
        """Con agrupación devuelve pares (id de asiento, columnas)."""
        doc_type = self.env['l10n_latam.document.type'].search(
            [('code', '=', '01'),
             ('country_id', '=', self.env.ref('base.pe').id)], limit=1)
        supplier = self.env['res.partner'].create({
            'name': 'PROVEEDOR MOTOR S.A.C.',
            'vat': '20601034809',
            'country_id': self.env.ref('base.pe').id,
            'l10n_latam_identification_type_id': self.env.ref('l10n_pe.it_RUC').id,
        })
        bill = self.env['account.move'].with_company(self.company).create({
            'move_type': 'in_invoice',
            'partner_id': supplier.id,
            'invoice_date': date(2026, 3, 10),
            'date': date(2026, 3, 10),
            'l10n_latam_document_type_id': doc_type.id,
            'l10n_latam_document_number': 'F001-00000777',
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio',
                'quantity': 1,
                'price_unit': 500.0,
            })],
        })
        bill.action_post()

        handler = self.env['l10n_pe.tax.ple.8.1.report.handler']
        report = self.env['account.report'].search(
            [('custom_handler_model_name', '=',
              'l10n_pe.tax.ple.8.1.report.handler')], limit=1)
        result = handler.with_company(self.company)._get_ple_report_data(
            self._options(report), 'move_id')
        self.assertTrue(result, 'el asiento debería aparecer agrupado')
        keys = [key for key, _columns in result]
        self.assertIn(bill.id, keys)
        columns = dict(result)[bill.id]
        self.assertEqual(columns['company_vat'], '20512528458')
        self.assertEqual(columns['customer_vat'], '20601034809')
