# -*- coding: utf-8 -*-
"""Generación del archivo RCE 8.4 a partir de facturas de proveedor reales."""
from datetime import date

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

RUC_COMPANY = '20512528458'
RUC_SUPPLIER = '20601034809'


class RceExportCommon(AccountTestInvoicingCommon):
    """Datos compartidos por los tests de los dos formatos del RCE."""


    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.company.vat = RUC_COMPANY
        cls.report = cls.env.ref('l10n_pe_reports.pe_ple_purchase_8_1_report',
                                 raise_if_not_found=False)
        if not cls.report:
            cls.report = cls.env['account.report'].search(
                [('custom_handler_model_name', '=',
                  'l10n_pe.tax.ple.8.1.report.handler')], limit=1)
        cls.supplier = cls.env['res.partner'].create({
            'name': 'EUROCAPITAL SERVICIOS FINANCIEROS S.A.C.',
            'vat': RUC_SUPPLIER,
            'country_id': cls.env.ref('base.pe').id,
            'l10n_latam_identification_type_id': cls.env.ref(
                'l10n_pe.it_RUC').id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Servicio de asesoría RCE',
            'l10n_pe_rce_classification': '5',
        })

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    _sequence = 0

    def _create_bill(self, invoice_date=None, price=1000.0, doc_code='01',
                     post=True):
        doc_type = self.env['l10n_latam.document.type'].search(
            [('code', '=', doc_code), ('country_id', '=', self.env.ref('base.pe').id)],
            limit=1)
        type(self)._sequence += 1
        bill = self.env['account.move'].with_company(self.company).create({
            'move_type': 'in_invoice',
            'partner_id': self.supplier.id,
            'invoice_date': invoice_date or date(2026, 3, 9),
            'date': invoice_date or date(2026, 3, 9),
            'l10n_latam_document_type_id': doc_type.id if doc_type else False,
            'l10n_latam_document_number': 'F001-%08d' % self._sequence,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': price,
            })],
        })
        if post:
            bill.action_post()
        return bill

    def _export(self, year=2026, month=3):
        options = self.report.get_options({
            'date': {
                'date_from': date(year, month, 1).strftime('%Y-%m-%d'),
                'date_to': date(year, month, 28).strftime('%Y-%m-%d'),
                'filter': 'custom',
                'mode': 'range',
            },
            'selected_variant_id': self.report.id,
        })
        handler = self.env[self.report.custom_handler_model_name]
        return handler.with_company(self.company).export_to_txt(options)

    def _lines(self, result):
        content = result['file_content'].decode()
        return [line for line in content.split('\r\n') if line.strip()]


@tagged('post_install', '-at_install')
class TestRce84Export(RceExportCommon):
    """RCE 8.4 — Registro de Compras (41 campos)."""

    def test_export_produces_41_fields(self):
        self._create_bill()
        lines = self._lines(self._export())
        self.assertTrue(lines, 'la factura debería aparecer en el RCE 8.4')
        for line in lines:
            self.assertEqual(
                line.count('|'), 41,
                'cada línea del 8.4 lleva 41 campos y cierra con pipe:\n%s' % line)

    def test_export_filename_is_official(self):
        self._create_bill()
        result = self._export()
        name = result['file_name']
        self.assertEqual(name[:2], 'LE')
        self.assertEqual(name[2:13], RUC_COMPANY)
        self.assertEqual(name[13:19], '202603')
        self.assertEqual(name[21:27], '080400')
        self.assertEqual(len(name), 33)

    def test_header_fields(self):
        bill = self._create_bill()
        fields_ = self._lines(self._export())[0].split('|')
        self.assertEqual(fields_[0], RUC_COMPANY, 'campo 1: RUC del generador')
        self.assertEqual(fields_[2], '202603', 'campo 3: periodo AAAAMM')
        self.assertEqual(fields_[3], '', 'campo 4: el CAR lo asigna SUNAT')
        self.assertEqual(fields_[4], '09/03/2026', 'campo 5: fecha de emisión')
        self.assertEqual(fields_[12], RUC_SUPPLIER, 'campo 13: RUC del proveedor')
        self.assertEqual(bill.state, 'posted')

    def test_amounts_and_total(self):
        self._create_bill(price=1000.0)
        fields_ = self._lines(self._export())[0].split('|')
        # campo 25: importe total del comprobante
        self.assertNotEqual(fields_[24], '0.00',
                            'campo 25: el total no puede ir en cero')
        # los importes se emiten con dos decimales
        for pos in (14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24):
            self.assertRegex(
                fields_[pos], r'^-?\d+\.\d{2}$',
                'el campo %d debe ser un importe con 2 decimales' % (pos + 1))

    def test_classification_comes_from_product(self):
        self._create_bill()
        fields_ = self._lines(self._export())[0].split('|')
        self.assertEqual(fields_[32], '5',
                         'campo 33: clasificación tomada del producto')

    def test_status_is_active_when_posted(self):
        self._create_bill()
        fields_ = self._lines(self._export())[0].split('|')
        self.assertEqual(fields_[39], '1',
                         'campo 40: comprobante publicado = activo')

    def test_status_is_void_when_cancelled(self):
        bill = self._create_bill()
        bill.button_draft()
        bill.button_cancel()
        self.assertEqual(bill.l10n_pe_rce_status, '2',
                         'un comprobante anulado se informa como baja')

    def test_period_filter_excludes_other_months(self):
        self._create_bill(invoice_date=date(2026, 3, 9))
        self._create_bill(invoice_date=date(2026, 5, 9))
        lines = self._lines(self._export(year=2026, month=3))
        for line in lines:
            self.assertEqual(
                line.split('|')[2], '202603',
                'el periodo de la línea debe coincidir con el del reporte')

    def test_no_data_marks_filename(self):
        result = self._export(year=2026, month=7)
        self.assertEqual(result['file_content'], b'')
        self.assertEqual(result['file_name'][30], '0',
                         'sin movimientos el nombre marca «sin información»')

    def test_non_domiciled_bill_is_not_in_84(self):
        """Los comprobantes 91/97/98 pertenecen al 8.5, no al 8.4."""
        self._create_bill(doc_code='91')
        self.assertFalse(
            self._lines(self._export()),
            'un comprobante de no domiciliado no puede aparecer en el 8.4')

    def test_credit_note_is_negative_and_references_origin(self):
        """La nota de crédito va en negativo y arrastra el documento que modifica."""
        origin = self._create_bill(invoice_date=date(2026, 1, 26))
        doc_07 = self.env['l10n_latam.document.type'].search(
            [('code', '=', '07'),
             ('country_id', '=', self.env.ref('base.pe').id)], limit=1)
        # sudo: la reversión toca modelos de otros módulos de la localización
        # (gestión de letras) cuyos grupos no tiene el usuario del test.
        wizard = self.env['account.move.reversal'].sudo().with_company(
            self.company).with_context(
            active_model='account.move', active_ids=origin.ids).create({
                'journal_id': origin.journal_id.id,
                'date': date(2026, 3, 9),
                'reason': 'Descuento',
            })
        refund = self.env['account.move'].sudo().browse(
            wizard.reverse_moves()['res_id'])
        refund.write({
            'invoice_date': date(2026, 3, 9),
            'date': date(2026, 3, 9),
            'l10n_latam_document_type_id': doc_07.id,
            'l10n_latam_document_number': 'F001-00002644',
        })
        refund.action_post()

        fields_ = self._lines(self._export())[0].split('|')
        self.assertEqual(fields_[6], '07', 'campo 7: nota de crédito')
        self.assertTrue(fields_[24].startswith('-'),
                        'campo 25: el abono se informa en negativo')
        self.assertTrue(fields_[14].startswith('-'),
                        'campo 15: la base también va en negativo')
        origin_serie, origin_folio = self.env[
            'l10n_pe.rce.extractor']._rce_serie_folio(origin)
        self.assertEqual(fields_[27], '26/01/2026',
                         'campo 28: fecha del documento modificado')
        self.assertEqual(fields_[28], '01', 'campo 29: tipo del modificado')
        self.assertEqual(fields_[29], origin_serie, 'campo 30: serie')
        self.assertEqual(fields_[31], origin_folio.lstrip('0'),
                         'campo 32: número')


@tagged('post_install', '-at_install')
class TestRce85Export(RceExportCommon):
    """RCE 8.5 — operaciones con sujetos no domiciliados (35 campos)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env['account.report'].search(
            [('custom_handler_model_name', '=',
              'l10n_pe.tax.ple.8.2.report.handler')], limit=1)
        cls.foreign_supplier = cls.env['res.partner'].create({
            'name': 'TVH PARTS NV',
            'vat': 'BE0425399042',
            'street': 'Brabantstraat 15, Waregem',
            'country_id': cls.env.ref('base.be').id,
        })

    def _create_foreign_bill(self, invoice_date=None, price=30930.40,
                             doc_code='91'):
        doc_type = self.env['l10n_latam.document.type'].search(
            [('code', '=', doc_code),
             ('country_id', '=', self.env.ref('base.pe').id)], limit=1)
        type(self)._sequence += 1
        bill = self.env['account.move'].with_company(self.company).create({
            'move_type': 'in_invoice',
            'partner_id': self.foreign_supplier.id,
            'invoice_date': invoice_date or date(2026, 3, 23),
            'date': invoice_date or date(2026, 3, 23),
            'l10n_latam_document_type_id': doc_type.id if doc_type else False,
            'l10n_latam_document_number': '-%08d' % self._sequence,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': price,
                'tax_ids': [(5, 0, 0)],
            })],
        })
        bill.action_post()
        return bill

    def test_export_produces_35_fields(self):
        self._create_foreign_bill()
        lines = self._lines(self._export())
        self.assertTrue(lines, 'la operación con no domiciliado va al 8.5')
        for line in lines:
            self.assertEqual(line.count('|'), 35,
                             'el 8.5 lleva 35 campos:\n%s' % line)

    def test_export_filename_is_official(self):
        self._create_foreign_bill()
        name = self._export()['file_name']
        self.assertEqual(name[21:27], '080500')
        self.assertEqual(name[27:29], '00',
                         'oportunidad 00: RC de no domiciliados informado')
        self.assertEqual(len(name), 33)

    def test_document_number_goes_to_mandatory_field(self):
        """El número va al campo 6 (obligatorio), no al 5 (serie, opcional)."""
        self._create_foreign_bill()
        fields_ = self._lines(self._export())[0].split('|')
        self.assertTrue(fields_[5], 'campo 6: el número es obligatorio')

    def test_document_type_is_allowed(self):
        """La norma solo admite 00, 91, 97 y 98 en el 8.5."""
        self._create_foreign_bill()
        fields_ = self._lines(self._export())[0].split('|')
        self.assertIn(fields_[3], ('00', '91', '97', '98'))

    def test_foreign_supplier_data(self):
        self._create_foreign_bill()
        fields_ = self._lines(self._export())[0].split('|')
        self.assertEqual(fields_[0], '202603', 'campo 1: periodo')
        self.assertEqual(fields_[1], '', 'campo 2: el CAR lo asigna SUNAT')
        self.assertEqual(fields_[17], 'TVH PARTS NV', 'campo 18: razón social')
        self.assertEqual(fields_[18], 'Brabantstraat 15, Waregem',
                         'campo 19: domicilio en el extranjero')
        self.assertEqual(fields_[19], 'BE0425399042', 'campo 20: identificación')

