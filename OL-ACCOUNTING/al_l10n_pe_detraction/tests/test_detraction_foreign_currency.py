# -*- coding: utf-8 -*-
"""Detracción de comprobantes en moneda extranjera (auditoría 07/10/2026).

R.S. 183-2004/SUNAT: el importe en moneda extranjera se convierte al tipo de
cambio venta publicado por la SBS en la fecha de la operación. Antes se
tomaba el total en soles de la factura, que depende del T.C. que use la
factura (compra con ``al_l10n_pe_currency`` o editado a mano): la detracción
del PDF, la contabilidad y el XML (el nativo convierte siempre con la tasa
oficial) no coincidían.
"""
from datetime import date

from odoo.tests import tagged

from .test_detraction import TestDetraction


@tagged('post_install', '-at_install')
class TestDetractionForeignCurrency(TestDetraction):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref('base.USD')
        cls.usd.active = True
        rate_vals = {'name': date(2025, 6, 10), 'currency_id': cls.usd.id,
                     'company_id': cls.company.root_id.id, 'rate': 1 / 3.80}
        if 'rate_sale' in cls.env['res.currency.rate']._fields:
            rate_vals.update(rate_sale=3.80, rate_purchase=3.70)
        cls.env['res.currency.rate'].search([
            ('name', '=', '2025-06-10'), ('currency_id', '=', cls.usd.id),
            ('company_id', '=', cls.company.root_id.id)]).unlink()
        cls.env['res.currency.rate'].create(rate_vals)

    def _usd_invoice(self, invoice_rate=None):
        move = self._invoice('out_invoice', 1000.0)  # 1 180 USD con IGV
        move.currency_id = self.usd
        if invoice_rate:
            move.invoice_currency_rate = 1 / invoice_rate
        return move

    def test_official_sale_rate(self):
        move = self._usd_invoice()
        # 1 180 × 3.80 = 4 484 → 12 % = 538.08 → 538
        self.assertEqual(move.l10n_pe_detraction_amount, 538.0)

    def test_invoice_rate_does_not_change_the_detraction(self):
        """La factura a T.C. compra (3.70) no cambia la detracción."""
        move = self._usd_invoice(invoice_rate=3.70)
        self.assertAlmostEqual(abs(move.amount_total_signed), 4366.0, places=2)
        self.assertEqual(move.l10n_pe_detraction_amount, 538.0)
        move.action_post()
        self.assertEqual(move._l10n_pe_edi_get_spot()['amount'], 538.0,
                         'el XML informa el mismo monto en soles')


# Los tests heredados ya corren en su propia clase.
for _name in dir(TestDetraction):
    if _name.startswith('test_') and _name not in TestDetractionForeignCurrency.__dict__:
        setattr(TestDetractionForeignCurrency, _name, None)
