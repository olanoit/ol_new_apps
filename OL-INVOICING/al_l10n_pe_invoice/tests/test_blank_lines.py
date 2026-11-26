# -*- coding: utf-8 -*-
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestCpeBlankLines(AccountTestInvoicingCommon):
    """El detalle del comprobante A4 se completa con filas en blanco."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.vat = '20512528458'
        cls.company_data['default_journal_sale'].l10n_latam_use_documents = True
        cls.partner_a.write({
            'vat': '20557912879',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
        })
        cls.invoice = cls.init_invoice('out_invoice', products=cls.product_a + cls.product_b)

    def _blank(self):
        return self.invoice._cpe_report_blank_lines(self.invoice.invoice_line_ids)

    def _html(self):
        return self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_invoice.report_cpe_invoice_a4_main', self.invoice.ids)[0].decode()

    def test_default_minimum(self):
        self.assertEqual(self.env.company.cpe_min_detail_lines, 10)
        self.assertEqual(self._blank(), 8)

    def test_no_filler_when_enough_lines(self):
        self.env.company.cpe_min_detail_lines = 2
        self.assertEqual(self._blank(), 0)
        self.env.company.cpe_min_detail_lines = 1
        self.assertEqual(self._blank(), 0)

    def test_zero_disables(self):
        self.env.company.cpe_min_detail_lines = 0
        self.assertEqual(self._blank(), 0)
        self.assertNotIn('cpe-blank-line', self._html())

    def test_multiline_description_counts_its_rows(self):
        self.invoice.invoice_line_ids[0].name = 'Servicio\nDetalle uno\nDetalle dos'
        self.assertEqual(self._blank(), 6)

    def test_report_renders_the_blank_rows(self):
        self.env.company.cpe_min_detail_lines = 5
        self.assertEqual(self._html().count('cpe-blank-line'), 3)

    def test_settings_field(self):
        self.env['res.config.settings'].create({'cpe_min_detail_lines': 15}).execute()
        self.assertEqual(self.env.company.cpe_min_detail_lines, 15)
