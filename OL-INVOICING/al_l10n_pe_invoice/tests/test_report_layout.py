# -*- coding: utf-8 -*-
from lxml import html

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestCpeReportLayout(AccountTestInvoicingCommon):
    """Diseño del comprobante A4 y del ticket (versión 27)."""

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

    def _tree(self, report):
        content = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_invoice.%s' % report, self.invoice.ids)[0]
        return html.fromstring(content)

    # ------------------------------------------------------------------ A4
    def test_party_rows_skip_empty_values(self):
        self.invoice.invoice_user_id = False
        self.invoice.invoice_payment_term_id = False
        labels = [pair[0] for row in self.invoice._l10n_pe_report_party_rows() for pair in row]
        self.assertIn('Señor(es)', labels)
        self.assertIn('Fecha de emisión', labels)
        for missing in ('Condición', 'Tipo de cambio', 'Vendedor', 'Pedido de venta', 'O/C externa'):
            self.assertNotIn(missing, labels)

    def test_party_rows_show_values_when_set(self):
        self.invoice.invoice_payment_term_id = self.env.ref('account.account_payment_term_30days')
        self.invoice.invoice_user_id = self.env.user
        rows = self.invoice._l10n_pe_report_party_rows()
        pairs = dict(pair for row in rows for pair in row if pair[0])
        self.assertEqual(pairs['Condición'], self.invoice.invoice_payment_term_id.name)
        self.assertEqual(pairs['Vendedor'], self.env.user.name)
        self.assertEqual(rows[0][0], ('Señor(es)', self.invoice.commercial_partner_id.name))

    def test_qr_digest(self):
        qr = '20557912879|01|F001|123|603.61|3957.01|2026-11-26|6|20462509236|5zVcyL443M1vVGhdFNi+H9jcslo=|\r\n'
        self.assertEqual(self.invoice._l10n_pe_report_qr_digest(qr), '5zVcyL443M1vVGhdFNi+H9jcslo=')
        self.assertEqual(self.invoice._l10n_pe_report_qr_digest(False), '')
        self.assertEqual(self.invoice._l10n_pe_report_qr_digest('a|b'), '')

    def test_a4_totals_block_and_grand_total(self):
        tree = self._tree('report_cpe_invoice_a4_main')
        grand = tree.xpath("//table[contains(@class, 'cpe-detail')]//tr[contains(@class, 'cpe-grand')]")
        self.assertEqual(len(grand), 1)
        self.assertIn('IMPORTE TOTAL', grand[0].text_content())
        words = tree.xpath("//td[contains(@class, 'cpe-words')]")[0].text_content()
        self.assertIn('SON:', words)

    def test_a4_blank_rows_have_one_cell_per_column(self):
        self.env.company.cpe_min_detail_lines = 4
        tree = self._tree('report_cpe_invoice_a4_main')
        blanks = tree.xpath("//tr[contains(@class, 'cpe-blank-line')]")
        self.assertEqual(len(blanks), 2)
        columns = len(tree.xpath("//table[contains(@class, 'cpe-detail')]/thead/tr/td"))
        self.assertEqual(len(blanks[0].xpath('./td')), columns)

    def test_a4_detraction_box(self):
        tree = self._tree('report_cpe_invoice_a4_main')
        self.assertFalse(tree.xpath("//table[contains(@class, 'cpe-spot')]"))
        self.assertEqual(len(tree.xpath("//table[contains(@class, 'cpe-legal')]")), 1)

    # -------------------------------------------------------------- Ticket
    def test_ticket_lines_two_rows_each(self):
        tree = self._tree('report_cpe_ticket_main')
        lines = self.invoice.invoice_line_ids
        self.assertEqual(len(tree.xpath("//tr[contains(@class, 'cpe-desc')]")), len(lines))
        calc = tree.xpath("//tr[contains(@class, 'cpe-calc')]")
        self.assertEqual(len(calc), len(lines))
        self.assertIn('×', calc[0].text_content())

    def test_ticket_total_and_client_table(self):
        tree = self._tree('report_cpe_ticket_main')
        total = tree.xpath("//tr[contains(@class, 'cpe-total-row')]")[0].text_content()
        self.assertIn('IMPORTE TOTAL', total)
        client = tree.xpath("//table[contains(@class, 'cpe-ticket-kv')]")[0].text_content()
        self.assertIn(self.invoice.commercial_partner_id.name, client)
