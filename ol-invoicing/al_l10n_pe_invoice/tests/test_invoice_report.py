# -*- coding: utf-8 -*-
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import Form, tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestInvoiceReport(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        company = cls.company_data['company']
        company.write({
            'vat': '20512528458',
        })
        cls.company_data['default_journal_sale'].l10n_latam_use_documents = True
        cls.partner_a.write({
            'vat': '20557912879',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
        })
        # El check EDI nativo exige la cuenta del Banco de la Nación para
        # publicar facturas con detracción (mismo setup que TestPeEdiCommon)
        cls.national_bank_account = cls.env['res.partner.bank'].create({
            'acc_number': '00-000-123456',
            'bank_id': cls.env.ref('l10n_pe.peruvian_national_bank').id,
            'partner_id': company.partner_id.id,
            'allow_out_payment': True,
        })

        # l10n_pe_withhold_code (nativo) es Selection del catálogo 54: hay
        # que usar un código real. El catálogo viene sembrado por
        # al_l10n_pe_detraction; el write se revierte al final del test.
        cls.detraction_type = cls.env['l10n_pe.detraction.type'].search(
            [('code', '=', '022')], limit=1)
        if not cls.detraction_type:
            cls.detraction_type = cls.env['l10n_pe.detraction.type'].create({
                'code': '022', 'name': 'Otros servicios empresariales',
                'percentage': 12.0, 'min_amount': 700.0,
            })
        cls.detraction_type.write({'percentage': 12.0, 'min_amount': 700.0})
        cls.product_detraction = cls.env['product.product'].create({
            'name': 'Servicio sujeto a detracción',
            'l10n_pe_detraction_type_id': cls.detraction_type.id,
            'taxes_id': [(6, 0, cls.tax_sale_a.ids)],
        })

    def _create_invoice(self, product, price_unit, operation_type='1001'):
        move_form = Form(self.env['account.move'].with_context(
            default_move_type='out_invoice'))
        move_form.partner_id = self.partner_a
        with move_form.invoice_line_ids.new() as line:
            line.product_id = product
            line.price_unit = price_unit
        move = move_form.save()
        move.l10n_pe_edi_operation_type = operation_type
        move.action_post()
        return move

    def test_tax_breakdown_and_amount_words(self):
        move = self._create_invoice(self.product_detraction, 1000.0)
        self.assertGreater(move.l10n_pe_edi_amount_igv, 0.0)
        self.assertGreater(move.l10n_pe_edi_amount_base, 0.0)
        # Monto en letras: método del core l10n_pe_edi (num2words)
        words = move._l10n_pe_edi_amount_to_text()
        self.assertTrue(words)
        self.assertIn('/100', words)

    def test_detraction_block_uses_new_fields(self):
        move = self._create_invoice(self.product_detraction, 1000.0)
        self.assertTrue(move.l10n_pe_detraction_applies)
        self.assertEqual(move.l10n_pe_detraction_type_id, self.detraction_type)
        self.assertGreater(move.l10n_pe_detraction_amount, 0.0)
        self.assertEqual(
            move._l10n_pe_get_national_bank_account_number(),
            self.national_bank_account.acc_number)

    def test_reports_render_without_error(self):
        move = self._create_invoice(self.product_detraction, 1000.0)
        report = self.env['ir.actions.report']
        html_a4, _ = report._render_qweb_html(
            'al_l10n_pe_invoice.report_cpe_invoice_a4_main', move.ids)
        html_ticket, _ = report._render_qweb_html(
            'al_l10n_pe_invoice.report_cpe_ticket_main', move.ids)
        self.assertTrue(html_a4)
        self.assertTrue(html_ticket)
        # Sin XML firmado aún no hay QR: el bloque QR no debe renderizarse
        # y la información legal ocupa todo el ancho
        self.assertNotIn('CÓDIGO QR'.encode(), html_a4)
        self.assertIn(b'cpe-footer-info-full', html_a4)
