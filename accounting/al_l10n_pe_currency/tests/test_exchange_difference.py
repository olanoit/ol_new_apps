# -*- coding: utf-8 -*-
"""Diferencia de cambio al conciliar factura y cobro con tipos distintos.

Una factura valorada al tipo de cambio venta y cobrada al de compra deja una
diferencia en soles aunque en dólares esté saldada. Odoo la registra como
ganancia o pérdida de cambio al conciliar; lo que se comprueba aquí es que esa
diferencia sea **exactamente** la que resulta de los dos tipos elegidos.
"""
from datetime import date

from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

RATE_PURCHASE = 3.700
RATE_SALE = 3.750


@tagged('post_install', '-at_install')
class TestExchangeDifference(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.company.vat = '20512528458'
        cls.usd = cls.env.ref('base.USD')
        cls.pe = cls.env.ref('base.pe')

        # Sin cuentas de diferencia de cambio Odoo no puede registrar el ajuste.
        if not cls.company.income_currency_exchange_account_id:
            cls.company.income_currency_exchange_account_id = \
                cls.company_data['default_account_revenue'].id
        if not cls.company.expense_currency_exchange_account_id:
            cls.company.expense_currency_exchange_account_id = \
                cls.company_data['default_account_expense'].id

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

        cls.customer = cls.env['res.partner'].create({
            'name': 'CLIENTE USD S.A.C.',
            'vat': '20601034809',
            'country_id': cls.pe.id,
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
        })
        cls.sale_journal = cls.env['account.journal'].search([
            ('company_id', '=', cls.company.id),
            ('type', '=', 'sale'),
            ('l10n_latam_use_documents', '=', True),
        ], limit=1)
        cls.doc_type = cls.env['l10n_latam.document.type'].search(
            [('code', '=', '01'), ('country_id', '=', cls.pe.id)], limit=1)
        cls.sale_tax = cls.env['account.tax'].search([
            ('company_id', '=', cls.company.id),
            ('type_tax_use', '=', 'sale'),
            ('amount', '=', 18),
        ], limit=1)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _invoice(self, rate_type, price=1000.0):
        invoice = self.env['account.move'].with_company(self.company).create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'journal_id': self.sale_journal.id,
            'l10n_latam_document_type_id': self.doc_type.id,
            'invoice_date': date(2026, 3, 15),
            'currency_id': self.usd.id,
            'l10n_pe_exchange_rate_type': rate_type,
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio',
                'quantity': 1,
                'price_unit': price,
                'tax_ids': [(6, 0, self.sale_tax.ids)] if self.sale_tax else False,
            })],
        })
        invoice.action_post()
        return invoice

    def _pay(self, invoice, rate_type):
        wizard = self.env['account.payment.register'].with_company(
            self.company).with_context(
            active_model='account.move', active_ids=invoice.ids).create({
                'payment_date': date(2026, 3, 20),
                'l10n_pe_exchange_rate_type': rate_type,
            })
        return wizard._create_payments()

    def _receivable(self, invoice):
        return invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == 'asset_receivable')

    def _exchange_moves(self, invoice):
        line = self._receivable(invoice)
        partials = line.matched_credit_ids | line.matched_debit_ids
        return partials.exchange_move_id

    # ------------------------------------------------------------------
    # Factura a venta, cobro a compra → pérdida
    # ------------------------------------------------------------------
    def test_sale_invoice_paid_at_purchase_rate(self):
        invoice = self._invoice('sale')
        total = invoice.amount_total
        receivable = self._receivable(invoice)
        self.assertAlmostEqual(receivable.balance, total * RATE_SALE, places=2,
                               msg='la factura se valora al tipo venta')

        self._pay(invoice, 'purchase')
        # En Odoo 19 el cobro pasa por una cuenta transitoria, así que la
        # factura queda «en proceso de pago» hasta conciliar el extracto; lo
        # que importa aquí es que no quede saldo pendiente.
        self.assertIn(invoice.payment_state, ('in_payment', 'paid'))
        self.assertAlmostEqual(invoice.amount_residual, 0.0, places=2,
                               msg='en dólares la factura queda saldada')

    def test_exchange_difference_matches_the_two_rates(self):
        """La diferencia debe ser el importe por la distancia entre tipos."""
        invoice = self._invoice('sale')
        total = invoice.amount_total
        self._pay(invoice, 'purchase')

        exchange = self._exchange_moves(invoice)
        self.assertTrue(exchange, 'debe generarse un asiento de diferencia')
        difference = sum(
            abs(line.balance) for line in exchange.line_ids) / 2
        self.assertAlmostEqual(
            difference, total * (RATE_SALE - RATE_PURCHASE), places=2,
            msg='la diferencia no coincide con la distancia entre tipos')

    def test_difference_is_a_loss_when_collecting_at_purchase(self):
        """Cobrar a un tipo menor que el facturado es una pérdida."""
        invoice = self._invoice('sale')
        self._pay(invoice, 'purchase')

        exchange = self._exchange_moves(invoice)
        expense_account = self.company.expense_currency_exchange_account_id
        loss_lines = exchange.line_ids.filtered(
            lambda line: line.account_id == expense_account)
        self.assertTrue(loss_lines, 'la diferencia debe ir a pérdida de cambio')
        self.assertGreater(sum(loss_lines.mapped('balance')), 0,
                           'una pérdida se anota al debe')

    def test_receivable_is_fully_cancelled(self):
        """La cuenta por cobrar queda a cero: importe más diferencia."""
        invoice = self._invoice('sale')
        self._pay(invoice, 'purchase')
        receivable = self._receivable(invoice)
        self.assertTrue(receivable.reconciled)
        self.assertAlmostEqual(receivable.amount_residual, 0.0, places=2)
        self.assertAlmostEqual(receivable.amount_residual_currency, 0.0,
                               places=2)

    # ------------------------------------------------------------------
    # Factura a compra, cobro a venta → ganancia
    # ------------------------------------------------------------------
    def test_difference_is_a_gain_when_collecting_at_sale(self):
        """El caso inverso da ganancia, no pérdida."""
        invoice = self._invoice('purchase')
        total = invoice.amount_total
        self._pay(invoice, 'sale')

        exchange = self._exchange_moves(invoice)
        self.assertTrue(exchange)
        income_account = self.company.income_currency_exchange_account_id
        gain_lines = exchange.line_ids.filtered(
            lambda line: line.account_id == income_account)
        self.assertTrue(gain_lines, 'la diferencia debe ir a ganancia de cambio')
        self.assertLess(sum(gain_lines.mapped('balance')), 0,
                        'una ganancia se anota al haber')
        difference = sum(abs(line.balance) for line in exchange.line_ids) / 2
        self.assertAlmostEqual(
            difference, total * (RATE_SALE - RATE_PURCHASE), places=2)

    # ------------------------------------------------------------------
    # Sin diferencia
    # ------------------------------------------------------------------
    def test_same_rate_leaves_no_difference(self):
        """Con el mismo tipo en factura y cobro no hay nada que ajustar."""
        invoice = self._invoice('sale')
        self._pay(invoice, 'sale')
        self.assertIn(invoice.payment_state, ('in_payment', 'paid'))
        exchange = self._exchange_moves(invoice)
        difference = sum(abs(line.balance) for line in exchange.line_ids) / 2 \
            if exchange else 0.0
        self.assertAlmostEqual(difference, 0.0, places=2)
