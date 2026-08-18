# -*- coding: utf-8 -*-
"""Elección del tipo de cambio (compra o venta) en cobros y pagos.

Igual que en las facturas, lo que se comprueba es que la elección **cambia el
importe en soles del asiento**, no que el campo exista.
"""
from datetime import date

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

RATE_PURCHASE = 3.700
RATE_SALE = 3.750


@tagged('post_install', '-at_install')
class TestPaymentRateType(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.company.vat = '20512528458'
        cls.usd = cls.env.ref('base.USD')
        # Datos peruanos completos: sin ellos la factura no se puede publicar.
        cls.partner = cls.env['res.partner'].create({
            'name': 'CLIENTE USD S.A.C.',
            'vat': '20601034809',
            'country_id': cls.env.ref('base.pe').id,
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
        })
        cls.env['res.currency.rate'].search([
            ('currency_id', '=', cls.usd.id),
            ('company_id', '=', cls.company.id),
        ]).unlink()
        cls.env['res.currency.rate'].create({
            'name': '2026-03-10',
            'currency_id': cls.usd.id,
            'company_id': cls.company.id,
            'rate_purchase': RATE_PURCHASE,
            'rate_sale': RATE_SALE,
            'ref_origin': 'sunat',
        })
        cls.bank_journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.company.id),
            ('type', '=', 'bank'),
        ], limit=1)

    def _payment(self, payment_type='inbound', rate_type=None, amount=1000.0):
        values = {
            'payment_type': payment_type,
            'partner_type': 'customer' if payment_type == 'inbound' else 'supplier',
            'partner_id': self.partner.id,
            'amount': amount,
            'currency_id': self.usd.id,
            'date': date(2026, 3, 15),
            'journal_id': self.bank_journal.id,
        }
        if rate_type:
            values['l10n_pe_exchange_rate_type'] = rate_type
        return self.env['account.payment'].with_company(self.company).create(values)

    def _balance(self, payment):
        """Importe en soles de la línea de liquidez del asiento."""
        payment.action_post()
        lines = payment.move_id.line_ids.filtered(lambda l: l.balance)
        return sum(abs(line.balance) for line in lines) / 2

    # ------------------------------------------------------------------
    # Valor propuesto
    # ------------------------------------------------------------------
    def test_default_is_sale(self):
        self.assertEqual(self._payment('inbound').l10n_pe_exchange_rate_type,
                         'sale')
        self.assertEqual(self._payment('outbound').l10n_pe_exchange_rate_type,
                         'sale')

    def test_inbound_follows_sales_criterion(self):
        """Un cobro sigue el criterio de ventas; un pago, el de compras."""
        self.company.l10n_pe_exchange_rate_type_out = 'purchase'
        self.company.l10n_pe_exchange_rate_type_in = 'sale'
        self.assertEqual(self._payment('inbound').l10n_pe_exchange_rate_type,
                         'purchase')
        self.assertEqual(self._payment('outbound').l10n_pe_exchange_rate_type,
                         'sale')

    # ------------------------------------------------------------------
    # Efecto sobre el asiento
    # ------------------------------------------------------------------
    def test_sale_rate_converts_with_sale(self):
        payment = self._payment(rate_type='sale', amount=1000.0)
        self.assertAlmostEqual(self._balance(payment), 1000 * RATE_SALE,
                               places=2)

    def test_purchase_rate_converts_with_purchase(self):
        payment = self._payment(rate_type='purchase', amount=1000.0)
        self.assertAlmostEqual(self._balance(payment), 1000 * RATE_PURCHASE,
                               places=2)

    def test_choice_changes_the_amount_in_soles(self):
        with_sale = self._balance(self._payment(rate_type='sale'))
        with_purchase = self._balance(self._payment(rate_type='purchase'))
        self.assertNotEqual(with_sale, with_purchase)
        self.assertAlmostEqual(with_sale - with_purchase,
                               1000 * (RATE_SALE - RATE_PURCHASE), places=2)

    def test_company_currency_payment_is_untouched(self):
        """En soles no hay conversión que elegir."""
        payment = self.env['account.payment'].with_company(self.company).create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 1000.0,
            'currency_id': self.company.currency_id.id,
            'date': date(2026, 3, 15),
            'journal_id': self.bank_journal.id,
        })
        self.assertAlmostEqual(self._balance(payment), 1000.0, places=2)

    # ------------------------------------------------------------------
    # Conversión de moneda
    # ------------------------------------------------------------------
    def test_conversion_rate_respects_context(self):
        """El contexto es lo que hace que la conversión use compra o venta."""
        currency = self.env['res.currency']
        company_currency = self.company.currency_id
        sale = currency.with_context(
            l10n_pe_exchange_rate_type='sale')._get_conversion_rate(
            self.usd, company_currency, self.company, date(2026, 3, 15))
        purchase = currency.with_context(
            l10n_pe_exchange_rate_type='purchase')._get_conversion_rate(
            self.usd, company_currency, self.company, date(2026, 3, 15))
        self.assertAlmostEqual(sale, RATE_SALE, places=3)
        self.assertAlmostEqual(purchase, RATE_PURCHASE, places=3)

    def test_conversion_is_symmetric(self):
        """Convertir desde la moneda de la compañía invierte el factor."""
        currency = self.env['res.currency']
        company_currency = self.company.currency_id
        rate = currency.with_context(
            l10n_pe_exchange_rate_type='purchase')._get_conversion_rate(
            company_currency, self.usd, self.company, date(2026, 3, 15))
        self.assertAlmostEqual(rate, 1 / RATE_PURCHASE, places=6)

    def test_conversion_without_context_is_native(self):
        """Sin indicación explícita se mantiene el comportamiento de Odoo."""
        currency = self.env['res.currency']
        rate = currency._get_conversion_rate(
            self.usd, self.company.currency_id, self.company, date(2026, 3, 15))
        # La tasa nativa se guarda como 1 / venta.
        self.assertAlmostEqual(rate, RATE_SALE, places=3)

    def test_same_currency_returns_one(self):
        currency = self.env['res.currency']
        rate = currency.with_context(
            l10n_pe_exchange_rate_type='purchase')._get_conversion_rate(
            self.usd, self.usd, self.company, date(2026, 3, 15))
        self.assertEqual(rate, 1)

    # ------------------------------------------------------------------
    # Registro de pagos desde la factura
    # ------------------------------------------------------------------
    def test_register_wizard_propagates_the_choice(self):
        sale_journal = self.env['account.journal'].search([
            ('company_id', '=', self.company.id),
            ('type', '=', 'sale'),
            ('l10n_latam_use_documents', '=', True),
        ], limit=1)
        doc_type = self.env['l10n_latam.document.type'].search(
            [('code', '=', '01'),
             ('country_id', '=', self.env.ref('base.pe').id)], limit=1)
        sale_tax = self.env['account.tax'].search([
            ('company_id', '=', self.company.id),
            ('type_tax_use', '=', 'sale'),
        ], limit=1)
        invoice = self.env['account.move'].with_company(self.company).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': sale_journal.id,
            'l10n_latam_document_type_id': doc_type.id,
            'invoice_date': date(2026, 3, 15),
            'currency_id': self.usd.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio',
                'quantity': 1,
                'price_unit': 1000.0,
                'tax_ids': [(6, 0, sale_tax.ids)] if sale_tax else False,
            })],
        })
        invoice.action_post()
        wizard = self.env['account.payment.register'].with_company(
            self.company).with_context(
            active_model='account.move', active_ids=invoice.ids).create({
                'payment_date': date(2026, 3, 15),
                'l10n_pe_exchange_rate_type': 'purchase',
            })
        payment = wizard._create_payments()
        self.assertEqual(payment.l10n_pe_exchange_rate_type, 'purchase',
                         'la elección del asistente debe llegar al pago')
