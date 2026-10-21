"""Cuota fija en soles en facturas en dólares."""
from datetime import date

from odoo import Command
from odoo.tests import TransactionCase, tagged

from odoo.addons.al_account_base.tests.common import use_pe_company

D1 = date(2026, 9, 10)


@tagged('post_install', '-at_install')
class TestPaymentTermCurrency(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        cls.usd = cls.env.ref('base.USD')
        cls.usd.active = True
        cls.env['res.currency.rate'].search([
            ('currency_id', '=', cls.usd.id), ('company_id', 'in', (False, cls.company.id)),
            ('name', '=', D1)]).unlink()
        cls.env['res.currency.rate'].create({
            'name': D1, 'currency_id': cls.usd.id, 'company_id': cls.company.id, 'inverse_company_rate': 3.75})
        cls.partner = cls.env['res.partner'].create({'name': 'CLIENTE CUOTAS SAC'})
        cls.journal = cls.env['account.journal'].create({
            'name': 'Ventas cuotas', 'code': 'VTCU', 'type': 'sale', 'l10n_latam_use_documents': False})
        cls.term = cls._term(in_soles=True)

    @classmethod
    def _term(cls, in_soles, amount=750.0):
        return cls.env['account.payment.term'].create({
            'name': 'S/ %s a la firma y saldo a 30 días' % amount,
            'line_ids': [
                Command.create({'value': 'fixed', 'value_amount': amount, 'nb_days': 0,
                                'l10n_pe_company_currency': in_soles}),
                Command.create({'value': 'percent', 'value_amount': 100, 'nb_days': 30}),
            ],
        })

    def _invoice(self, amount, currency, term=None):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner.id, 'journal_id': self.journal.id,
            'invoice_date': D1, 'date': D1, 'currency_id': currency.id,
            'invoice_payment_term_id': (term or self.term).id,
            'invoice_line_ids': [Command.create({'name': 'Venta', 'price_unit': amount,
                                                 'tax_ids': [Command.clear()]})],
        })
        move.action_post()
        return move

    @staticmethod
    def _installments(move):
        return [(line.amount_currency, line.balance)
                for line in move.line_ids.filtered(lambda l: l.display_type == 'payment_term').sorted('date_maturity')]

    def test_fixed_soles_on_usd_invoice(self):
        """US$ 1 000 a 3,75: la cuota de S/ 750 son US$ 200; el saldo, US$ 800 (S/ 3 000)."""
        move = self._invoice(1000, self.usd)
        self.assertEqual(self._installments(move), [(200.0, 750.0), (800.0, 3000.0)])

    def test_rounding_goes_to_balance(self):
        term = self._term(in_soles=True, amount=1000.0)
        move = self._invoice(1000, self.usd, term)
        first, last = self._installments(move)
        self.assertEqual(first, (266.67, 1000.0))
        self.assertAlmostEqual(first[0] + last[0], 1000.0)
        self.assertAlmostEqual(first[1] + last[1], 3750.0)

    def test_without_flag_amount_is_in_invoice_currency(self):
        move = self._invoice(1000, self.usd, self._term(in_soles=False))
        self.assertEqual(self._installments(move)[0], (750.0, 2812.5))

    def test_pen_invoice_unchanged(self):
        move = self._invoice(1000, self.company.currency_id)
        self.assertEqual(self._installments(move), [(750.0, 750.0), (250.0, 250.0)])

    def test_flag_on_last_line_is_ignored(self):
        """La última cuota siempre es el saldo: la marca no la cambia."""
        def term(flag):
            return self.env['account.payment.term'].create({
                'name': 'Contado con cuota final fija (%s)' % flag,
                'line_ids': [Command.create({'value': 'percent', 'value_amount': 100, 'nb_days': 0}),
                             Command.create({'value': 'fixed', 'value_amount': 10, 'nb_days': 30,
                                             'l10n_pe_company_currency': flag})],
            })
        self.assertEqual(self._installments(self._invoice(1000, self.usd, term(True))),
                         self._installments(self._invoice(1000, self.usd, term(False))))
