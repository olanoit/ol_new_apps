# -*- coding: utf-8 -*-
"""Formato común de los documentos impresos: página, encabezado y pie."""
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.image import image_data_uri


@tagged('post_install', '-at_install')
class TestReportPePage(TransactionCase):

    def _render(self, **values):
        company = self.env.company
        # Las variables que ir.actions.report agrega al renderizar un PDF.
        base = {
            'o': company, 'company': company, 'doc_title': 'Documento de prueba',
            'context_timestamp': lambda t: fields.Datetime.context_timestamp(self.env.user, t),
            'image_data_uri': image_data_uri,
        }
        base.update(values)
        return str(self.env['ir.qweb']._render('al_report_base.report_pe_page', base))

    def test_page_has_header_body_and_footer(self):
        html = self._render(doc_number='DP-0001', doc_extra='Periodo 10/2026')
        self.assertIn('class="article"', html)
        self.assertIn('pe-doc-header', html)
        self.assertIn('Documento de prueba', html)
        self.assertIn('N.º <span>DP-0001</span>', html)
        self.assertIn('Periodo 10/2026', html)
        self.assertIn('class="footer pe-doc-footer"', html)
        self.assertIn('class="topage"', html)

    def test_number_is_optional(self):
        html = self._render()
        self.assertNotIn('N.º', html)

    def test_paperformats(self):
        portrait = self.env.ref('al_report_base.paperformat_pe_a4')
        landscape = self.env.ref('al_report_base.paperformat_pe_a4_landscape')
        self.assertEqual((portrait.format, portrait.orientation), ('A4', 'Portrait'))
        self.assertEqual((landscape.format, landscape.orientation), ('A4', 'Landscape'))
