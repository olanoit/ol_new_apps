# -*- coding: utf-8 -*-
"""Elección del tipo de cambio (compra o venta) en la factura.

Lo que importa no es que el campo exista, sino que **cambie el importe en
soles**: si elegir compra no altera la conversión, el campo es decorativo.
"""
from datetime import date

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

RATE_PURCHASE = 3.700
RATE_SALE = 3.750


@tagged('post_install', '-at_install')
class TestInvoiceRateType(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.usd = cls.env.ref('base.USD')
        cls.partner = cls.env['res.partner'].create({'name': 'CLIENTE USD'})
        cls.product = cls.env['product.product'].create({'name': 'Servicio'})
        # Un único tipo de cambio con compra y venta distintas.
        cls.env['res.currency.rate'].search([
            ('currency_id', '=', cls.usd.id),
            ('company_id', '=', cls.company.id),
        ]).unlink()
        cls.rate = cls.env['res.currency.rate'].create({
            'name': '2026-03-10',
            'currency_id': cls.usd.id,
            'company_id': cls.company.id,
            'rate_purchase': RATE_PURCHASE,
            'rate_sale': RATE_SALE,
            'ref_origin': 'sunat',
        })

    def _invoice(self, move_type='out_invoice', rate_type=None, price=100.0):
        values = {
            'move_type': move_type,
            'partner_id': self.partner.id,
            'invoice_date': date(2026, 3, 15),
            'date': date(2026, 3, 15),
            'currency_id': self.usd.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': price,
                'tax_ids': [(5, 0, 0)],
            })],
        }
        if rate_type:
            values['l10n_pe_exchange_rate_type'] = rate_type
        return self.env['account.move'].with_company(self.company).create(values)

    # ------------------------------------------------------------------
    # Valor propuesto
    # ------------------------------------------------------------------
    def test_default_is_sale_on_both_directions(self):
        """Por defecto se usa la venta, que es lo que exige el IGV."""
        self.assertEqual(self._invoice('out_invoice').l10n_pe_exchange_rate_type,
                         'sale')
        self.assertEqual(self._invoice('in_invoice').l10n_pe_exchange_rate_type,
                         'sale')

    def test_company_criterion_is_applied(self):
        self.company.l10n_pe_exchange_rate_type_out = 'purchase'
        self.company.l10n_pe_exchange_rate_type_in = 'sale'
        self.assertEqual(self._invoice('out_invoice').l10n_pe_exchange_rate_type,
                         'purchase')
        self.assertEqual(self._invoice('in_invoice').l10n_pe_exchange_rate_type,
                         'sale')

    def test_entries_have_no_rate_type(self):
        move = self.env['account.move'].with_company(self.company).create({
            'move_type': 'entry',
            'date': date(2026, 3, 15),
        })
        self.assertFalse(move.l10n_pe_exchange_rate_type)

    # ------------------------------------------------------------------
    # Efecto sobre la conversión
    # ------------------------------------------------------------------
    def test_sale_rate_converts_with_sale(self):
        invoice = self._invoice(rate_type='sale', price=100.0)
        self.assertAlmostEqual(invoice.invoice_currency_rate, 1 / RATE_SALE,
                               places=6)
        self.assertAlmostEqual(invoice.l10n_pe_exchange_rate, RATE_SALE,
                               places=3)

    def test_purchase_rate_converts_with_purchase(self):
        invoice = self._invoice(rate_type='purchase', price=100.0)
        self.assertAlmostEqual(invoice.invoice_currency_rate, 1 / RATE_PURCHASE,
                               places=6)
        self.assertAlmostEqual(invoice.l10n_pe_exchange_rate, RATE_PURCHASE,
                               places=3)

    def test_choice_changes_the_amount_in_soles(self):
        """La prueba de fondo: el importe contabilizado debe diferir."""
        with_sale = self._invoice(rate_type='sale', price=100.0)
        with_purchase = self._invoice(rate_type='purchase', price=100.0)
        self.assertAlmostEqual(abs(with_sale.amount_total_signed),
                               100 * RATE_SALE, places=2)
        self.assertAlmostEqual(abs(with_purchase.amount_total_signed),
                               100 * RATE_PURCHASE, places=2)
        self.assertNotEqual(with_sale.amount_total_signed,
                            with_purchase.amount_total_signed)

    def test_switching_type_recomputes_the_rate(self):
        """Cambiar de venta a compra debe recalcular, no quedarse pegado."""
        invoice = self._invoice(rate_type='sale', price=100.0)
        invoice.l10n_pe_exchange_rate_type = 'purchase'
        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.invoice_currency_rate, 1 / RATE_PURCHASE,
                               places=6)

    def test_info_label_shows_which_rate_was_used(self):
        invoice = self._invoice(rate_type='purchase')
        self.assertIn('Compra', invoice.l10n_pe_exchange_rate_info)
        self.assertIn('3.700', invoice.l10n_pe_exchange_rate_info)

    # ------------------------------------------------------------------
    # Casos límite
    # ------------------------------------------------------------------
    def test_company_currency_invoice_is_untouched(self):
        """En soles no hay conversión que elegir."""
        invoice = self.env['account.move'].with_company(self.company).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': date(2026, 3, 15),
            'currency_id': self.company.currency_id.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 1,
                'price_unit': 100.0,
                'tax_ids': [(5, 0, 0)],
            })],
        })
        self.assertEqual(invoice.l10n_pe_exchange_rate, 0.0)
        self.assertFalse(invoice.l10n_pe_exchange_rate_info)

    def test_without_peruvian_rate_falls_back_to_native(self):
        """Sin compra/venta registradas se mantiene el comportamiento de Odoo."""
        self.rate.write({'rate_purchase': 0.0, 'rate_sale': 0.0, 'rate': 0.25})
        invoice = self._invoice(rate_type='purchase', price=100.0)
        self.assertAlmostEqual(invoice.invoice_currency_rate, 0.25, places=6)

    def test_manual_rate_still_wins(self):
        """El usuario puede seguir forzando la tasa a mano."""
        invoice = self._invoice(rate_type='sale', price=100.0)
        invoice.invoice_currency_rate = 0.2
        self.assertAlmostEqual(invoice.invoice_currency_rate, 0.2, places=6)
