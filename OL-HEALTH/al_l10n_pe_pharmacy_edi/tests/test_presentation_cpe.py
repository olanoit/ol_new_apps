# -*- coding: utf-8 -*-
from freezegun import freeze_time

from odoo.addons.l10n_pe_edi.tests.common import TestPeEdiCommon
from odoo.tests import tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPresentationCpe(TestPeEdiCommon):

    def test_presentation_line_in_ubl(self):
        """La línea en la unidad de la presentación sale en el XML con el
        código SUNAT de la caja y su precio, sin precio unitario periódico."""
        box = self.env['pharmacy.presentation'].create({
            'product_tmpl_id': self.product.product_tmpl_id.id,
            'name': 'Caja', 'factor': 100, 'price': 12.0,
        })
        with freeze_time(self.frozen_today):
            move = self._create_invoice_pe(invoice_line_ids=[(0, 0, {
                'product_id': self.product.id,
                'product_uom_id': box.uom_id.id,
                'price_unit': 12.0,
                'quantity': 1,
                'tax_ids': [(6, 0, self.tax_18.ids)],
            })])
            move.action_post()
            # Odoo 20: el XML lo arma la factura (sin account.edi.format).
            edi_xml, errors = move._l10n_pe_edi_generate_invoice_bstr()
        self.assertFalse(errors)
        tree = self.get_xml_tree_from_string(edi_xml)
        quantity = tree.find('.//{*}InvoiceLine/{*}InvoicedQuantity')
        self.assertEqual(quantity.get('unitCode'), 'BX')
        self.assertEqual(float(quantity.text), 1.0)
        self.assertEqual(float(tree.find('.//{*}InvoiceLine/{*}LineExtensionAmount').text), 12.0)
