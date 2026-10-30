# -*- coding: utf-8 -*-
"""El ticket CPE no reemplaza nodos del recibo nativo.

En Odoo 20 el recibo es una plantilla de servidor
(``point_of_sale.pos_order_receipt``) que también dibuja el navegador. Un
``position="replace"`` borraría lo que otros módulos (pos_loyalty,
pos_restaurant, l10n_pe_edi_pos de EE, al_pos_vendedor) insertan en él: el
nativo se oculta con un ``t-if`` y el ticket CPE va como hermano.
"""
from lxml import etree

from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import file_path


@tagged('post_install', '-at_install')
class TestReceiptTemplate(TransactionCase):

    def _arch(self):
        return etree.parse(file_path('al_l10n_pe_edi_pos/receipt/pos_order_receipt.xml'))

    def test_no_replace_en_el_recibo(self):
        self.assertFalse(self._arch().xpath("//xpath[@position='replace']"),
                         'el recibo nativo no debe reemplazarse')

    def test_recibo_cpe_es_hermano_condicional(self):
        arch = self._arch()
        attrs = arch.xpath("//xpath[@position='attributes']/attribute[@name='t-if']")
        self.assertEqual([a.text for a in attrs], ["not conditions.get('al_pe_cpe')"])
        after = arch.xpath("//xpath[@position='after']/div[@t-if=\"conditions.get('al_pe_cpe')\"]")
        self.assertEqual(len(after), 1)

    def test_render_ticket_cpe(self):
        """La plantilla heredada se compila y dibuja el ticket CPE con los
        datos del bloque ``al_pe``."""
        values = {
            'order': {'general_customer_note': False, 'state': 'paid', 'amount_return': 0,
                      'amount_return_currency': 0, 'ticket_code': 'X'},
            'lines': [], 'payments': [], 'partner': False, 'preset': False, 'config': {}, 'company': {},
            'image': {'logo': False, 'invoice_qr_code': False},
            'conditions': {'al_pe_cpe': True, 'basic_receipt': False, 'use_self_invoicing': False,
                           'display_qr_code': False, 'display_url': False},
            'extra_data': {'prices': {}, 'total_item_count': 0, 'al_pe': {
                'company_name': 'EMPRESA SAC', 'company_vat': '20100070970', 'company_street': '',
                'company_phone': '', 'issued': True, 'doc_label': 'BOLETA DE VENTA ELECTRÓNICA',
                'doc_label_lower': 'boleta de venta electrónica', 'doc_number': 'B001-00000001',
                'partner_name': 'CLIENTE VARIOS', 'partner_vat_label': 'DNI', 'partner_vat': '45678912',
                'partner_street': '', 'date': '30/10/2026', 'currency_label': 'SOLES',
                'lines': [{'qty': 1, 'name': 'Agua', 'discount': False, 'note': False,
                           'unit': 'S/ 1.18', 'total': 'S/ 1.18'}],
                'totals': [{'label': 'IMPORTE TOTAL', 'amount': 'S/ 1.18', 'total': True}],
                'words': 'UNO CON 18/100 SOLES', 'payments': [{'name': 'Efectivo', 'amount': 'S/ 1.18'}],
                'change': False, 'cashier': 'Caja', 'seller': False, 'notes': [], 'qr': False,
                'footer': False}},
        }
        html = str(self.env['ir.qweb']._render('point_of_sale.pos_order_receipt', values))
        self.assertIn('B001-00000001', html)
        self.assertIn('alpe-total-row', html)
        self.assertIn('UNO CON 18/100 SOLES', html)
        self.assertNotIn('Subtotal:', html, 'el recibo nativo queda oculto')
