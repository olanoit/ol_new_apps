# -*- coding: utf-8 -*-
"""Páginas «Facturación PE» y «Contabilidad PE» del formulario de factura.

Cada módulo de la localización pone sus datos en una pestaña interna de
esas dos páginas. Se comprueba sobre la vista ya compuesta con todos los
módulos instalados, que es lo que ve el usuario.
"""
from lxml import etree

from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestInvoiceFormPePages(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        view = cls.env['account.move'].get_view(
            cls.env.ref('account.view_move_form').id, 'form')
        cls.arch = etree.fromstring(view['arch'])

    def _one(self, xpath):
        nodes = self.arch.xpath(xpath)
        self.assertEqual(len(nodes), 1, xpath)
        return nodes[0]

    def _inner_pages(self, notebook_name):
        notebook = self._one("//notebook[@name='%s']" % notebook_name)
        return {page.get('name') for page in notebook.xpath('./page')}

    def test_containers_inside_main_notebook(self):
        invoicing = self._one("//page[@name='l10n_pe_invoicing']")
        accounting = self._one("//page[@name='l10n_pe_accounting']")
        self.assertEqual(invoicing.getparent().tag, 'notebook')
        self.assertEqual(invoicing.getparent(), accounting.getparent())

    def test_invoicing_inner_pages(self):
        pages = self._inner_pages('l10n_pe_invoicing_notebook')
        self.assertTrue({'l10n_pe_edi_document', 'l10n_pe_detraction'} <= pages, pages)
        if 'l10n_pe_retention_eligible' in self.env['account.move']._fields:
            self.assertIn('l10n_pe_retention', pages)

    def test_edi_page_replaced(self):
        """Los datos de la página «Peruvian EDI» de l10n_pe_edi están en
        «Comprobante electrónico» y la página original no se muestra."""
        group = self._one("//group[@name='l10n_pe_edi_electronic_info']")
        self.assertTrue(group.xpath("ancestor::page[@name='l10n_pe_edi_document']"))
        self.assertIn(self._one("//page[@name='l10n_pe_edi']").get('invisible'), ('1', 'True'))
        for field in ('l10n_pe_edi_cancel_reason', 'l10n_pe_edi_legend'):
            self.assertTrue(group.xpath(".//field[@name='%s']" % field), field)

    def test_detraction_only_once(self):
        """La constancia de l10n_pe_reports queda oculta: está en la pestaña
        «Detracción»."""
        self.assertIn(self._one("//group[@name='l10n_pe_group']").get('invisible'), ('1', 'True'))
        page = self._one("//page[@name='l10n_pe_detraction']")
        self.assertTrue(page.xpath(".//field[@name='l10n_pe_detraction_number']"))

    def test_accounting_inner_pages(self):
        pages = self._inner_pages('l10n_pe_accounting_notebook')
        self.assertIn('l10n_pe_books', pages)
        if 'l10n_pe_sire_is_non_domiciled' in self.env['account.move']._fields:
            self.assertIn('l10n_pe_sire_non_domiciled', pages)
        if 'l10n_pe_rce_classification' in self.env['account.move']._fields:
            books = self._one("//page[@name='l10n_pe_books']")
            for xpath in (".//field[@name='l10n_pe_rce_classification']",
                          ".//group[@name='l10n_pe_group_foreign']",
                          ".//group[@name='l10n_pe_sunat_transaction_type']"):
                self.assertTrue(books.xpath(xpath), xpath)

    def test_forms_open(self):
        """El formulario se abre en ventas, compras y asientos (los
        modificadores de las páginas nuevas se evalúan)."""
        for move_type in ('out_invoice', 'in_invoice', 'entry'):
            form = Form(self.env['account.move'].with_context(default_move_type=move_type))
            self.assertEqual(form.move_type, move_type)
