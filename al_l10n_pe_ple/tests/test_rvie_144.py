# -*- coding: utf-8 -*-
"""RVIE 14.4 — Registro de Ventas e Ingresos.

Estructura del Anexo N.º 2 de la RS N.° 000112-2021/SUNAT: 33 campos, ya que
la nota 7 excluye del archivo los campos 34 a 40.
"""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

RUC_COMPANY = '20512528458'
RUC_CUSTOMER = '20601034809'


@tagged('post_install', '-at_install')
class TestRvie144(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.company.vat = RUC_COMPANY
        cls.handler = cls.env['l10n_pe.tax.ple.14.1.report.handler']
        cls.report = cls.env['account.report'].search(
            [('custom_handler_model_name', '=',
              'l10n_pe.tax.ple.14.1.report.handler')], limit=1)
        cls.customer = cls.env['res.partner'].create({
            'name': 'CLIENTE DEMO S.A.C.',
            'vat': RUC_CUSTOMER,
            'country_id': cls.env.ref('base.pe').id,
            'l10n_latam_identification_type_id': cls.env.ref(
                'l10n_pe.it_RUC').id,
        })
        cls.product = cls.env['product.product'].create({'name': 'Producto'})
        cls.sale_journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.company.id),
            ('type', '=', 'sale'),
            ('l10n_latam_use_documents', '=', True),
        ], limit=1)
        cls.sale_tax = cls.env['account.tax'].search([
            ('company_id', '=', cls.company.id),
            ('type_tax_use', '=', 'sale'),
            ('amount', '=', 18),
        ], limit=1)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _create_invoice(self, invoice_date=None, price=1000.0, doc_code='01',
                        post=True):
        doc_type = self.env['l10n_latam.document.type'].search(
            [('code', '=', doc_code),
             ('country_id', '=', self.env.ref('base.pe').id)], limit=1)
        invoice = self.env['account.move'].with_company(self.company).create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'journal_id': self.sale_journal.id,
            'invoice_date': invoice_date or date(2026, 3, 15),
            'date': invoice_date or date(2026, 3, 15),
            'l10n_latam_document_type_id': doc_type.id if doc_type else False,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': price,
                'tax_ids': [(6, 0, self.sale_tax.ids)] if self.sale_tax else False,
            })],
        })
        if post:
            invoice.action_post()
        return invoice

    def _create_credit_note(self, origin, refund_date):
        """Nota de crédito (tipo 07) que rectifica ``origin``."""
        doc_07 = self.env['l10n_latam.document.type'].search(
            [('code', '=', '07'),
             ('country_id', '=', self.env.ref('base.pe').id)], limit=1)
        # sudo: la reversión toca modelos de otros módulos de la localización.
        wizard = self.env['account.move.reversal'].sudo().with_company(
            self.company).with_context(
            active_model='account.move', active_ids=origin.ids).create({
                'journal_id': origin.journal_id.id,
                'date': refund_date,
                'reason': 'Anulación parcial',
            })
        refund = self.env['account.move'].sudo().browse(
            wizard.reverse_moves()['res_id'])
        refund.write({
            'invoice_date': refund_date,
            'date': refund_date,
            'l10n_latam_document_type_id': doc_07.id,
        })
        refund.action_post()
        return refund

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
        return self.handler.with_company(self.company).export_to_txt(options)

    def _lines(self, result):
        return [line for line in result['file_content'].decode().split('\r\n')
                if line.strip()]

    # ------------------------------------------------------------------
    # Estructura
    # ------------------------------------------------------------------
    def test_export_produces_33_fields(self):
        """La nota 7 del anexo 2 excluye los campos 34 a 40 del archivo."""
        self._create_invoice()
        lines = self._lines(self._export())
        self.assertTrue(lines, 'la factura debería aparecer en el RVIE')
        for line in lines:
            self.assertEqual(line.count('|'), 33,
                             'el RVIE 14.4 lleva 33 campos:\n%s' % line)

    def test_wrong_field_count_is_rejected(self):
        for size in (32, 34, 35):
            with self.assertRaises(UserError,
                                   msg='%d campos debería fallar' % size):
                self.handler._l10n_pe_rvie_serialize([['x'] * size])

    def test_filename_is_official(self):
        self._create_invoice()
        name = self._export()['file_name']
        self.assertEqual(len(name), 33)
        self.assertEqual(name[:2], 'LE')
        self.assertEqual(name[2:13], RUC_COMPANY)
        self.assertEqual(name[13:19], '202603')
        self.assertEqual(name[19:21], '00')
        self.assertEqual(name[21:27], '140400')
        self.assertEqual(name[32], '2', 'generado por el SIRE')

    # ------------------------------------------------------------------
    # Importes
    # ------------------------------------------------------------------
    def test_sale_amounts_are_positive(self):
        """En ventas el ingreso va al haber; el registro los informa positivos."""
        self._create_invoice(price=1000.0)
        fields_ = self._lines(self._export())[0].split('|')
        self.assertEqual(fields_[14], '1000.00', 'campo 15: base gravada')
        self.assertEqual(fields_[16], '180.00', 'campo 17: IGV')
        self.assertEqual(fields_[25], '1180.00', 'campo 26: total')

    def test_header_fields(self):
        self._create_invoice()
        fields_ = self._lines(self._export())[0].split('|')
        self.assertEqual(fields_[0], RUC_COMPANY, 'campo 1: RUC del generador')
        self.assertEqual(fields_[2], '202603', 'campo 3: periodo')
        self.assertEqual(fields_[3], '', 'campo 4: el CAR lo asigna SUNAT')
        self.assertEqual(fields_[4], '15/03/2026', 'campo 5: fecha de emisión')
        self.assertEqual(fields_[11], RUC_CUSTOMER, 'campo 12: RUC del cliente')

    def test_cancelled_invoice_is_reported_with_zero(self):
        """Nota 4 del anexo: los anulados se anotan en cero, no se excluyen."""
        invoice = self._create_invoice()
        invoice.button_draft()
        invoice.button_cancel()
        lines = self._lines(self._export())
        self.assertTrue(lines, 'el comprobante anulado sigue en el registro')
        fields_ = lines[0].split('|')
        self.assertEqual(fields_[14], '0.00', 'campo 15 en cero')
        self.assertEqual(fields_[16], '0.00', 'campo 17 en cero')
        self.assertEqual(fields_[25], '0.00', 'campo 26 en cero')

    # ------------------------------------------------------------------
    # Notas de crédito
    # ------------------------------------------------------------------
    def test_credit_note_same_period_is_negative(self):
        """Si rectifica un comprobante del mismo periodo, va en negativo."""
        origin = self._create_invoice(invoice_date=date(2026, 3, 5))
        self._create_credit_note(origin, date(2026, 3, 20))
        line = [l for l in self._lines(self._export())
                if l.split('|')[6] == '07'][0]
        fields_ = line.split('|')
        self.assertTrue(fields_[14].startswith('-'),
                        'campo 15: base gravada en negativo')
        self.assertEqual(fields_[15], '0.00', 'campo 16: sin descuento')
        self.assertTrue(fields_[25].startswith('-'),
                        'campo 26: total en negativo')

    def test_credit_note_previous_period_goes_to_discount(self):
        """Si rectifica un periodo anterior, se informa como descuento."""
        origin = self._create_invoice(invoice_date=date(2026, 1, 20))
        self._create_credit_note(origin, date(2026, 3, 20))
        line = [l for l in self._lines(self._export())
                if l.split('|')[6] == '07'][0]
        fields_ = line.split('|')
        self.assertEqual(fields_[14], '0.00',
                         'campo 15: la base va al campo de descuento')
        self.assertNotEqual(fields_[15], '0.00', 'campo 16: descuento de base')
        self.assertEqual(fields_[16], '0.00',
                         'campo 17: el IGV va al campo de descuento')
        self.assertNotEqual(fields_[17], '0.00', 'campo 18: descuento de IGV')

    def test_credit_note_references_origin(self):
        origin = self._create_invoice(invoice_date=date(2026, 3, 5))
        self._create_credit_note(origin, date(2026, 3, 20))
        line = [l for l in self._lines(self._export())
                if l.split('|')[6] == '07'][0]
        fields_ = line.split('|')
        self.assertEqual(fields_[28], '05/03/2026',
                         'campo 29: fecha del documento modificado')
        self.assertEqual(fields_[29], '01', 'campo 30: tipo del modificado')
        self.assertTrue(fields_[31], 'campo 32: número del modificado')

    # ------------------------------------------------------------------
    # Periodo
    # ------------------------------------------------------------------
    def test_period_filter(self):
        self._create_invoice(invoice_date=date(2026, 3, 15))
        self._create_invoice(invoice_date=date(2026, 5, 15))
        for line in self._lines(self._export(year=2026, month=3)):
            self.assertEqual(line.split('|')[2], '202603')

    def test_no_data_marks_filename(self):
        result = self._export(year=2026, month=7)
        self.assertEqual(result['file_content'], b'')
        self.assertEqual(result['file_name'][30], '0')
