# -*- coding: utf-8 -*-
"""El recibo CPE no reemplaza nodos del recibo nativo.

Un ``position="replace"`` sobre ``div.pos-receipt`` borraba lo que otros
módulos (pos_loyalty, pos_restaurant, l10n_pe_edi_pos de EE, al_pos_vendedor)
insertan en el recibo y rompía sus xpath. Se comprueba sobre el archivo
fuente porque el recibo es una plantilla OWL del frontend.
"""
from lxml import etree

from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import file_path


@tagged('post_install', '-at_install')
class TestReceiptTemplate(TransactionCase):

    def _arch(self):
        path = file_path('al_l10n_pe_edi_pos/static/src/overrides/order_receipt.xml')
        return etree.parse(path)

    def test_no_replace_en_plantillas_owl(self):
        arch = self._arch()
        self.assertFalse(arch.xpath("//xpath[@position='replace']"),
                         'el recibo nativo no debe reemplazarse')

    def test_recibo_cpe_es_hermano_condicional(self):
        arch = self._arch()
        attrs = arch.xpath("//xpath[@position='attributes']/attribute[@name='t-if']")
        self.assertEqual([a.text for a in attrs], ['!peActive'])
        after = arch.xpath("//xpath[@position='after']/div[@t-if='peActive']")
        self.assertEqual(len(after), 1)
        self.assertIn('pos-receipt', after[0].get('class').split())

    def test_encabezado_ee_sin_factura(self):
        """El encabezado de l10n_pe_edi_pos (EE) se lee con «?.»: con el pago
        en línea el ticket se dibuja antes de que llegue la factura. Si EE
        cambia ese nodo, el xpath deja de encontrarlo y hay que revisarlo."""
        ours = etree.parse(file_path('al_l10n_pe_edi_pos/static/src/overrides/receipt_header.xml'))
        node = ours.xpath("//xpath/attribute[@name='t-out']")[0]
        self.assertTrue(node.text.startswith('order.account_move?.'))
        expr = ours.xpath('//xpath/@expr')[0]
        ee = etree.parse(file_path(
            'l10n_pe_edi_pos/static/src/app/components/receipt/receipt_header/receipt_header.xml'))
        self.assertEqual(len(ee.xpath(expr)), 1,
                         'el nodo de l10n_pe_edi_pos que se corrige ya no existe')
