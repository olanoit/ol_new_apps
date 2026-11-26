# -*- coding: utf-8 -*-
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestDefaultPdfReport(AccountTestInvoicingCommon):
    """Imprimir y Enviar usan CPE A4 por defecto en compañías peruanas."""

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
