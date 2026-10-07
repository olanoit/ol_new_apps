# -*- coding: utf-8 -*-
"""Generación del archivo RCE 8.4 a partir de facturas de proveedor reales."""
from datetime import date

from odoo.exceptions import UserError
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

    def _export(self, year=2026, month=3, full_row=False):
        options = self.report.get_options({
            'date': {
                'date_from': date(year, month, 1).strftime('%Y-%m-%d'),
                'date_to': date(year, month, 28).strftime('%Y-%m-%d'),
                'filter': 'custom',
                'mode': 'range',
            },
            'selected_variant_id': self.report.id,
        })
        handler = self.env[self.report.custom_handler_model_name].with_context(
            l10n_pe_rce_full_row=full_row)
        return handler.with_company(self.company).export_to_txt(options)

    def _lines(self, result):
        content = result['file_content'].decode()
        return [line for line in content.split('\r\n') if line.strip()]


@tagged('post_install', '-at_install')
class TestRce84Export(RceExportCommon):
    """RCE 8.4 — Registro de Compras (37 campos en el TXT)."""

    def test_export_produces_37_fields(self):
        self._create_bill()
        lines = self._lines(self._export())
        self.assertTrue(lines, 'la factura debería aparecer en el RCE 8.4')
        for line in lines:
            self.assertEqual(
                line.count('|'), 37,
                'cada línea del 8.4 lleva 37 campos y cierra con pipe:\n%s' % line)

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
        fields_ = self._lines(self._export(full_row=True))[0].split('|')
        self.assertEqual(fields_[39], '1',
                         'campo 40 (solo en el Excel): comprobante publicado = activo')
        txt = self._lines(self._export())[0].split('|')
        self.assertEqual(len(txt), 38, 'el TXT no lleva los campos 38-41 (37 + cierre)')

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



@tagged('post_install', '-at_install')
class TestRceAudit20261007(RceExportCommon):
    """Auditoría del 07/10/2026 contra los anexos oficiales."""

    def test_credit_note_uses_origin_rate(self):
        """Nota sobre un comprobante en USD: T.C. del documento modificado."""
        extractor = self.env['l10n_pe.rce.extractor']
        usd = self.env.ref('base.USD')
        bill = self._create_bill()
        bill.button_draft()
        bill.currency_id = usd
        bill.invoice_currency_rate = 1 / 3.712
        bill.action_post()
        nc_type = self.env['l10n_latam.document.type'].search(
            [('code', '=', '07'), ('country_id', '=', self.env.ref('base.pe').id)], limit=1)
        refund = bill._reverse_moves([{
            'invoice_date': bill.invoice_date, 'ref': 'NC',
            'l10n_latam_document_type_id': nc_type.id,
            'l10n_latam_document_number': 'FC01-00000001'}])
        refund.invoice_currency_rate = 1 / 3.800
        self.assertAlmostEqual(extractor._rce_exchange_rate(refund), 3.712, 3)


@tagged('post_install', '-at_install')
class TestRce84Review(RceExportCommon):
    """Revisión del 07/10/2026: ISC y líneas sin impuesto en el 8.4."""

    def _row(self, bill):
        number = bill.l10n_latam_document_number.partition('-')[2].lstrip('0')
        return next(line.split('|') for line in self._lines(self._export())
                    if line.split('|')[9] == number)

    def test_isc_goes_into_the_taxed_base(self):
        """Nota 3 del anexo 11: el ISC de un ítem gravado va en la base
        (campo 15), no en el campo 22."""
        igv = self.env['account.tax'].search([
            ('company_id', '=', self.company.id),
            ('type_tax_use', '=', 'purchase'), ('amount', '=', 18.0),
            ('amount_type', '=', 'percent')], limit=1)
        isc_group = self.env.ref(
            'account.%s_tax_group_isc' % self.company.id,
            raise_if_not_found=False)
        if not (igv and isc_group):
            self.skipTest('sin IGV o grupo ISC en la localización')
        isc = self.env['account.tax'].create({
            'name': 'ISC 10% prueba', 'amount': 10.0, 'sequence': 0,
            'type_tax_use': 'purchase', 'include_base_amount': True,
            'tax_group_id': isc_group.id, 'company_id': self.company.id,
        })
        bill = self._create_bill(post=False)
        bill.invoice_line_ids.tax_ids = isc | igv
        bill.action_post()
        row = self._row(bill)
        self.assertEqual(row[14], '1100.00', 'campo 15 = valor + ISC')
        self.assertEqual(row[15], '198.00')
        self.assertEqual(row[21], '0.00', 'campo 22: ISC no deducible')
        self.assertEqual(row[24], '1298.00')

    def test_untaxed_line_goes_to_field_21(self):
        """Lo que no tiene impuesto va al campo 21: los campos 15-24 suman
        el total (campo 25)."""
        bill = self._create_bill(post=False)
        bill.write({'invoice_line_ids': [(0, 0, {
            'name': 'Cargo sin impuesto', 'quantity': 1, 'price_unit': 50.0,
            'tax_ids': False})]})
        bill.action_post()
        row = self._row(bill)
        self.assertEqual(row[20], '50.00')
        self.assertAlmostEqual(
            sum(float(value) for value in row[14:24]), float(row[24]))

    def test_orphan_credit_note_blocks_txt_but_not_review(self):
        """Una NC sin documento de origen bloquea el TXT con su nombre; el
        Excel de revisión (fila completa) sí se genera."""
        doc_07 = self.env['l10n_latam.document.type'].search(
            [('code', '=', '07'),
             ('country_id', '=', self.env.ref('base.pe').id)], limit=1)
        if not doc_07:
            self.skipTest('sin tipo 07 en la localización')
        note = self.env['account.move'].with_company(self.company).create({
            'move_type': 'in_refund',
            'partner_id': self.supplier.id,
            'invoice_date': date(2026, 3, 9),
            'date': date(2026, 3, 9),
            'l10n_latam_document_type_id': doc_07.id,
            'l10n_latam_document_number': 'FC01-00000077',
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id, 'quantity': 1,
                'price_unit': 100.0})],
        })
        note.action_post()
        with self.assertRaises(UserError):
            self._export()
        self.assertTrue(self._export(full_row=True)['file_content'])
