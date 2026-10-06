# -*- coding: utf-8 -*-
"""Exportación a Excel de los registros del SIRE."""
from datetime import date
from io import BytesIO
import zipfile

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from odoo.addons.al_l10n_pe_ple.models.ple_xlsx import PLE_XLSX_HEADERS

HANDLERS = (
    ('8.4', 'l10n_pe.tax.ple.8.1.report.handler', '080400', 41),
    ('8.5', 'l10n_pe.tax.ple.8.2.report.handler', '080500', 35),
    ('14.4', 'l10n_pe.tax.ple.14.1.report.handler', '140400', 33),
)


@tagged('post_install', '-at_install')
class TestSireXlsx(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.company.vat = '20512528458'

    def _options(self, handler_name):
        report = self.env['account.report'].search(
            [('custom_handler_model_name', '=', handler_name)], limit=1)
        return report.get_options({
            'date': {
                'date_from': '2026-03-01',
                'date_to': '2026-03-31',
                'filter': 'custom',
                'mode': 'range',
            },
            'selected_variant_id': report.id,
        })

    # ------------------------------------------------------------------
    # Cabeceras
    # ------------------------------------------------------------------
    def test_headers_match_official_field_count(self):
        """La hoja debe tener una columna por campo del archivo legal."""
        for label, _handler, book_code, expected in HANDLERS:
            with self.subTest(book=label):
                self.assertIn(book_code, PLE_XLSX_HEADERS)
                self.assertEqual(
                    len(PLE_XLSX_HEADERS[book_code]), expected,
                    'el %s tiene %d campos' % (label, expected))

    def test_headers_are_unique(self):
        for label, _handler, book_code, _count in HANDLERS:
            headers = PLE_XLSX_HEADERS[book_code]
            with self.subTest(book=label):
                self.assertEqual(len(headers), len(set(headers)),
                                 'no debe haber cabeceras repetidas')

    # ------------------------------------------------------------------
    # Generación
    # ------------------------------------------------------------------
    def test_export_produces_valid_workbook(self):
        for label, handler_name, _book, _count in HANDLERS:
            with self.subTest(book=label):
                handler = self.env[handler_name].with_company(self.company)
                result = handler.l10n_pe_sire_export_to_xlsx(
                    self._options(handler_name))
                self.assertEqual(result['file_type'], 'xlsx')
                content = result['file_content']
                self.assertTrue(content)
                # Un XLSX es un ZIP: si abre, el archivo es válido.
                with zipfile.ZipFile(BytesIO(content)) as workbook:
                    self.assertIn('xl/workbook.xml', workbook.namelist())

    def test_button_is_offered_next_to_txt(self):
        for label, handler_name, _book, _count in HANDLERS:
            with self.subTest(book=label):
                options = self._options(handler_name)
                names = [button['name'] for button in options.get('buttons', [])]
                self.assertTrue(
                    any('XLSX' in name and label in name for name in names),
                    'debe ofrecerse el XLSX del %s junto al TXT: %s'
                    % (label, names))

    def test_export_includes_the_invoice_rows(self):
        """El Excel lleva las mismas líneas que el TXT."""
        doc_type = self.env['l10n_latam.document.type'].search(
            [('code', '=', '01'),
             ('country_id', '=', self.env.ref('base.pe').id)], limit=1)
        supplier = self.env['res.partner'].create({
            'name': 'PROVEEDOR XLSX S.A.C.',
            'vat': '20601034809',
            'country_id': self.env.ref('base.pe').id,
            'l10n_latam_identification_type_id': self.env.ref('l10n_pe.it_RUC').id,
        })
        bill = self.env['account.move'].with_company(self.company).create({
            'move_type': 'in_invoice',
            'partner_id': supplier.id,
            'invoice_date': date(2026, 3, 12),
            'date': date(2026, 3, 12),
            'l10n_latam_document_type_id': doc_type.id,
            'l10n_latam_document_number': 'F001-00000999',
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio',
                'quantity': 1,
                'price_unit': 800.0,
            })],
        })
        bill.action_post()

        handler = self.env['l10n_pe.tax.ple.8.1.report.handler'].with_company(
            self.company)
        options = self._options('l10n_pe.tax.ple.8.1.report.handler')
        txt = handler.export_to_txt(options)
        self.assertTrue(txt['file_content'], 'el TXT debe traer la factura')

        xlsx = handler.l10n_pe_sire_export_to_xlsx(options)
        with zipfile.ZipFile(BytesIO(xlsx['file_content'])) as workbook:
            shared = workbook.read('xl/sharedStrings.xml').decode('utf-8')
        self.assertIn('20601034809', shared,
                      'el RUC del proveedor debe aparecer en la hoja')
