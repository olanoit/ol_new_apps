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
