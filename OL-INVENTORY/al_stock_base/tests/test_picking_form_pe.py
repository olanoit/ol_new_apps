# -*- coding: utf-8 -*-
"""Página «Logística PE»: todos los datos peruanos de la transferencia en un
solo lugar, agrupados por módulo. Se comprueba sobre la vista ya compuesta
con todos los módulos instalados, que es lo que ve el usuario."""
from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPickingFormPe(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        view = cls.env['stock.picking'].get_view(
            cls.env.ref('stock.view_picking_form').id, 'form')
        cls.arch = etree.fromstring(view['arch'])

    def test_page_in_main_notebook(self):
        pages = self.arch.xpath("//page[@name='l10n_pe_stock']")
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].getparent().tag, 'notebook')
        self.assertTrue(pages[0].xpath(".//group[@name='l10n_pe_stock_groups']"))

    def test_pe_fields_live_in_the_page(self):
        """Los campos peruanos de los módulos instalados están en la página
        (y solo una vez en el formulario)."""
        fields = ['l10n_pe_edi_transport_type', 'l10n_pe_edi_reason_for_transfer',
                  'l10n_pe_edi_vehicle_id', 'l10n_pe_edi_operator_id',
                  'l10n_pe_operation_type', 'l10n_pe_consignment',
                  'construction_request_id']
        page = self.arch.xpath("//page[@name='l10n_pe_stock']")[0]
        Picking = self.env['stock.picking']
        for fname in fields:
            if fname not in Picking._fields:
                continue
            visible = [n for n in self.arch.xpath("//field[@name='%s']" % fname)
                       if n.get('invisible') not in ('1', 'True')]
            self.assertEqual(len(visible), 1, fname)
            self.assertTrue(page.xpath(".//field[@name='%s']" % fname), fname)
