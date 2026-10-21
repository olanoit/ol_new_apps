# -*- coding: utf-8 -*-
"""Tipo de cambio pactado en cobros y pagos.

La factura de US$ 1 000 se registra a 3,75; el día del cobro SUNAT publica
3,76; con el cliente o el banco se pacta otro tipo de cambio. Lo que se
comprueba es el importe en soles, que la factura queda pagada y la diferencia
de cambio que registra Odoo.
"""
from datetime import date

from odoo import Command
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

D_INVOICE, D_PAYMENT = date(2026, 3, 10), date(2026, 3, 20)


@tagged('post_install', '-at_install')
class TestPaymentAgreedRate(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.usd = cls.env.ref('base.USD')
        cls.env['res.currency.rate'].search([
            ('currency_id', '=', cls.usd.id), ('company_id', '=', cls.company.id)]).unlink()
        for day, sale in ((D_INVOICE, 3.75), (D_PAYMENT, 3.76)):
            cls.env['res.currency.rate'].create({
                'name': day, 'currency_id': cls.usd.id, 'company_id': cls.company.id,
                'rate_sale': sale, 'rate_purchase': sale - 0.01, 'ref_origin': 'sunat'})
        cls.partner = cls.env['res.partner'].create({'name': 'CLIENTE PACTADO SAC'})
        outstanding = cls.env['account.account'].create({
            'name': 'Pendientes (prueba T.C. pactado)', 'code': '104189', 'account_type': 'asset_current',
            'reconcile': True})
        cls.pen_bank = cls.env['account.journal'].create({'name': 'Banco soles', 'code': 'BKSO', 'type': 'bank'})
        cls.usd_bank = cls.env['account.journal'].create({
            'name': 'Banco dólares', 'code': 'BKDO', 'type': 'bank', 'currency_id': cls.usd.id})
        for journal in (cls.pen_bank, cls.usd_bank):
            (journal.inbound_payment_method_line_ids | journal.outbound_payment_method_line_ids) \
                .payment_account_id = outstanding
        cls.sale_journal = cls.env['account.journal'].create({
            'name': 'Ventas pactado', 'code': 'VTPA', 'type': 'sale', 'l10n_latam_use_documents': False})
        cls.purchase_journal = cls.env['account.journal'].create({
            'name': 'Compras pactado', 'code': 'CPPA', 'type': 'purchase', 'l10n_latam_use_documents': False})
        cls.loss = cls.company.expense_currency_exchange_account_id
        cls.gain = cls.company.income_currency_exchange_account_id

    def _document(self, move_type='out_invoice'):
        move = self.env['account.move'].with_company(self.company).create({
            'move_type': move_type, 'partner_id': self.partner.id,
            'journal_id': (self.sale_journal if move_type == 'out_invoice' else self.purchase_journal).id,
            'invoice_date': D_INVOICE, 'date': D_INVOICE, 'currency_id': self.usd.id,
            'l10n_pe_exchange_rate_type': 'sale',
            'invoice_line_ids': [Command.create({'name': 'Servicio', 'price_unit': 1000,
                                                 'tax_ids': [Command.clear()]})],
        })
        move.action_post()
        return move

    def _register(self, move, journal, agreed, currency=None):
        vals = {'journal_id': journal.id, 'payment_date': D_PAYMENT, 'l10n_pe_agreed_rate': agreed}
        if currency:
            vals['currency_id'] = currency.id
        return self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=move.ids).create(vals)

    def _exchange(self, move):
        """Diferencia de cambio registrada al conciliar: (pérdida, ganancia) en soles."""
        partials = move.line_ids.matched_debit_ids | move.line_ids.matched_credit_ids
        lines = partials.exchange_move_id.line_ids
        return (sum(lines.filtered(lambda l: l.account_id == self.loss).mapped('balance')),
                -sum(lines.filtered(lambda l: l.account_id == self.gain).mapped('balance')))

    @staticmethod
    def _liquidity(payment):
        liquidity, _counterpart, _writeoff = payment._seek_for_lines()
        return liquidity

    # ------------------------------------------------------------------ conversión
    def test_agreed_rate_overrides_purchase_and_sale(self):
        currency = self.env['res.currency']
        pen = self.company.currency_id
        for rate_type in (None, 'sale', 'purchase'):
            ctx = currency.with_context(l10n_pe_agreed_rate=3.72, l10n_pe_exchange_rate_type=rate_type)
            self.assertAlmostEqual(ctx._get_conversion_rate(self.usd, pen, self.company, D_PAYMENT), 3.72)
            self.assertAlmostEqual(ctx._get_conversion_rate(pen, self.usd, self.company, D_PAYMENT), 1 / 3.72)
        self.assertEqual(currency.with_context(l10n_pe_agreed_rate=3.72)._get_conversion_rate(
            self.usd, self.usd, self.company, D_PAYMENT), 1)

    # ------------------------------------------------------------------ cobro en dólares
    def test_dollar_payment_from_soles_bank(self):
        """Cobro de US$ 1 000 a 3,72 en un banco en soles: S/ 3 720 y S/ 30 de pérdida."""
        invoice = self._document()
        wizard = self._register(invoice, self.pen_bank, 3.72)
        self.assertEqual((wizard.amount, wizard.currency_id), (1000.0, self.usd))
        payment = wizard._create_payments()
        self.assertAlmostEqual(payment.l10n_pe_agreed_rate, 3.72)
        self.assertAlmostEqual(self._liquidity(payment).balance, 3720.0)
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))
        self.assertEqual(self._exchange(invoice), (30.0, 0.0))

    def test_dollar_bank_with_bank_rate(self):
        """Banco en dólares con el T.C. del banco 3,80: S/ 50 de ganancia."""
        invoice = self._document()
        payment = self._register(invoice, self.usd_bank, 3.80)._create_payments()
        self.assertAlmostEqual(self._liquidity(payment).balance, 3800.0)
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))
        self.assertEqual(self._exchange(invoice), (0.0, 50.0))

    # ------------------------------------------------------------------ cobro en soles
    def test_soles_payment_of_dollar_invoice(self):
        """Cobro en soles: S/ 3 720; la diferencia con el cambio del día se salda
        contra diferencia de cambio y el resultado es el mismo: S/ 30 de pérdida."""
        invoice = self._document()
        wizard = self._register(invoice, self.pen_bank, 3.72, currency=self.company.currency_id)
        self.assertAlmostEqual(wizard.amount, 3720.0)
        self.assertAlmostEqual(wizard.payment_difference, 40.0, msg='3 760 al cambio del día menos 3 720')
        self.assertEqual(wizard.payment_difference_handling, 'reconcile')
        self.assertEqual(wizard.writeoff_account_id, self.loss)
        self.assertTrue(wizard.writeoff_is_exchange_account)
        payment = wizard._create_payments()
        self.assertAlmostEqual(self._liquidity(payment).balance, 3720.0)
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))
        self.assertAlmostEqual(invoice.amount_residual, 0.0)
        loss, gain = self._exchange(invoice)
        self.assertAlmostEqual(loss - gain, 30.0)

    def test_soles_payment_to_supplier_is_a_gain(self):
        """Pago en soles a 3,72 de una factura de proveedor de US$ 1 000 a 3,75: S/ 30 de ganancia."""
        bill = self._document('in_invoice')
        wizard = self._register(bill, self.pen_bank, 3.72, currency=self.company.currency_id)
        self.assertEqual(wizard.writeoff_account_id, self.gain)
        wizard._create_payments()
        self.assertIn(bill.payment_state, ('paid', 'in_payment'))
        loss, gain = self._exchange(bill)
        self.assertAlmostEqual(gain - loss, 30.0)

    def test_without_agreed_rate_nothing_changes(self):
        invoice = self._document()
        wizard = self._register(invoice, self.pen_bank, 0.0, currency=self.company.currency_id)
        self.assertAlmostEqual(wizard.amount, 3760.0)
        self.assertEqual(wizard.payment_difference_handling, 'open')
        wizard._create_payments()
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))
        self.assertEqual(self._exchange(invoice), (0.0, 10.0))

    # ------------------------------------------------------------------ pago directo
    def test_direct_payment_uses_agreed_rate(self):
        payment = self.env['account.payment'].with_company(self.company).create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': self.partner.id,
            'amount': 500, 'currency_id': self.usd.id, 'date': D_PAYMENT, 'journal_id': self.usd_bank.id,
            'l10n_pe_agreed_rate': 3.79,
        })
        payment.action_post()
        self.assertAlmostEqual(self._liquidity(payment).balance, -1895.0)
        payment.action_draft()
        payment.l10n_pe_agreed_rate = 3.70
        self.assertAlmostEqual(self._liquidity(payment).balance, -1850.0, msg='en borrador se rehace el asiento')
