# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.addons.account.tests.common import (
    AccountTestInvoicingCommon, AccountTestInvoicingHttpCommon)
from odoo.tests import tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestDefaultPdfReport(AccountTestInvoicingCommon):
    """Imprimir y Enviar usan Comprobante electrónico (A4) por defecto en compañías peruanas."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.cpe_a4 = cls.env.ref('al_l10n_pe_invoice.report_cpe_invoice_a4')
        cls.cpe_ticket = cls.env.ref('al_l10n_pe_invoice.report_cpe_ticket')
        # Mismos datos que TestInvoiceReport para poder publicar la factura
        cls.env.company.vat = '20512528458'
        cls.company_data['default_journal_sale'].l10n_latam_use_documents = True
        cls.partner_a.write({
            'vat': '20557912879',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
        })
        cls.invoice = cls.init_invoice('out_invoice', products=cls.product_a)

    def _default(self, move=None):
        return self.env['account.move.send']._get_default_pdf_report_id(move or self.invoice)

    def test_cpe_reports_are_invoice_reports(self):
        self.assertTrue(self.cpe_a4.is_invoice_report)
        self.assertTrue(self.cpe_ticket.is_invoice_report)

    def test_default_is_cpe_a4(self):
        self.assertEqual(self._default(), self.cpe_a4)
        action = self.invoice.with_context(discard_logo_check=True).action_print_pdf()
        self.assertEqual(action.get('report_name'), self.cpe_a4.report_name)

    def test_send_wizard_uses_cpe_a4(self):
        self.invoice.action_post()
        wizard = self.env['account.move.send.wizard'].with_context(
            active_model='account.move', active_ids=self.invoice.ids).create({})
        self.assertEqual(wizard.pdf_report_id, self.cpe_a4)

    def test_partner_and_journal_choice_prevail(self):
        self.invoice.journal_id.invoice_template_pdf_report_id = self.cpe_ticket
        self.assertEqual(self._default(), self.cpe_ticket)
        self.invoice.commercial_partner_id.invoice_template_pdf_report_id = \
            self.env.ref('account.account_invoices')
        self.assertEqual(self._default(), self.env.ref('account.account_invoices'))

    def test_proforma_uses_cpe_a4(self):
        """La descarga del portal sin PDF generado sale con el comprobante A4."""
        self.invoice.action_post()
        Report = self.env.registry['ir.actions.report']
        rendered = []

        def _pre_render(report_self, report_ref, res_ids=None, data=None):
            rendered.append(report_ref)
            return {self.invoice.id: {'stream': None}}, 'pdf'

        def _splitted(report_self, report_ref, content, report_type):
            return {self.invoice.id: b'%PDF'}

        with patch.object(Report, '_pre_render_qweb_pdf', _pre_render), \
                patch.object(Report, '_get_splitted_report', _splitted):
            doc = self.invoice._get_invoice_pdf_proforma()
            self.assertEqual(rendered, [self.cpe_a4.report_name])
            self.assertEqual(doc['content'], b'%PDF')
            # Con el formato genérico elegido en el cliente manda el nativo
            self.invoice.commercial_partner_id.invoice_template_pdf_report_id = \
                self.env.ref('account.account_invoices')
            self.invoice._get_invoice_pdf_proforma()
            self.assertEqual(rendered[-1], 'account.account_invoices')


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestPortalPreviewReport(AccountTestInvoicingHttpCommon):
    """La vista previa (portal) muestra el comprobante electrónico (A4)."""

    @classmethod
    @AccountTestInvoicingHttpCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.vat = '20512528458'
        cls.company_data['default_journal_sale'].l10n_latam_use_documents = True
        cls.partner_a.write({
            'vat': '20557912879',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
        })
        cls.invoice = cls.init_invoice('out_invoice', products=cls.product_a, post=True)

    def _preview_html(self):
        res = self.url_open(self.invoice.get_portal_url(report_type='html'))
        self.assertEqual(res.status_code, 200)
        return res.text

    def test_preview_shows_cpe_a4(self):
        self.assertIn('cpe-a4', self._preview_html())

    def test_preview_respects_partner_format(self):
        self.invoice.partner_id.invoice_template_pdf_report_id = \
            self.env.ref('account.account_invoices')
        self.assertNotIn('cpe-a4', self._preview_html())

    def test_preview_respects_journal_format(self):
        self.invoice.journal_id.invoice_template_pdf_report_id = \
            self.env.ref('account.account_invoices')
        self.assertNotIn('cpe-a4', self._preview_html())
