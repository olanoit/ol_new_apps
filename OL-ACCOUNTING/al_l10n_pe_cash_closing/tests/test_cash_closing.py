"""Cierre de caja: saldo según libros, arqueo, diferencia, bloqueo y reapertura."""
from datetime import date

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.al_account_base.tests.common import use_pe_company

D0, D1, D2 = date(2026, 9, 9), date(2026, 9, 10), date(2026, 9, 11)


@tagged('post_install', '-at_install')
class TestCashClosing(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        if not cls.company.external_report_layout_id:
            cls.company.external_report_layout_id = cls.env.ref('web.external_layout_standard')
        cls.partner = cls.env['res.partner'].create({'name': 'CLIENTE CAJA SAC'})
        cls.cash = cls.env['account.journal'].create({
            'name': 'Caja tienda', 'code': 'CJTD', 'type': 'cash', 'company_id': cls.company.id})
        # Pagos directos a la cuenta de la caja (quedan pagados al confirmarse).
        (cls.cash.inbound_payment_method_line_ids | cls.cash.outbound_payment_method_line_ids) \
            .payment_account_id = cls.cash.default_account_id
        cls.other_cash = cls.env['account.journal'].create({
            'name': 'Caja almacén', 'code': 'CJAL', 'type': 'cash', 'company_id': cls.company.id})
        cls.sale_journal = cls.env['account.journal'].create({
            'name': 'Ventas caja', 'code': 'VTCJ', 'type': 'sale', 'l10n_latam_use_documents': False})
        cls.cash_method = cls.env['pe.catalog.payment'].search([], limit=1)
        cls.receivable_staff = cls.env['account.account'].create({
            'name': 'Cuentas por cobrar al personal (prueba)', 'code': '141399',
            'account_type': 'asset_receivable', 'reconcile': True})

    # ------------------------------------------------------------------ ayuda
    def _invoice(self, amount, day):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner.id, 'journal_id': self.sale_journal.id,
            'invoice_date': day, 'date': day,
            'invoice_line_ids': [Command.create({'name': 'Venta', 'price_unit': amount,
                                                 'tax_ids': [Command.clear()]})],
        })
        move.action_post()
        return move

    def _collect(self, invoice, day, journal=None):
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids).create({
                'journal_id': (journal or self.cash).id, 'payment_date': day})
        return wizard._create_payments()

    def _payment(self, payment_type, amount, day, journal=None, **vals):
        payment = self.env['account.payment'].create({
            'payment_type': payment_type,
            'partner_type': 'customer' if payment_type == 'inbound' else 'supplier',
            'partner_id': self.partner.id, 'amount': amount, 'date': day,
            'journal_id': (journal or self.cash).id, 'pe_payment_method_id': self.cash_method.id, **vals,
        })
        payment.action_post()
        return payment

    def _closing(self, day=D1, journal=None):
        return self.env['l10n_pe.cash.closing'].create({'journal_id': (journal or self.cash).id, 'date': day})

    def _count(self, closing, amount):
        """Arqueo con billetes de 100 y el resto en monedas de 1 y 0,10."""
        counts = {c.value: c for c in closing.count_ids}
        hundreds, rest = divmod(round(amount * 100), 10000)
        counts[100.0].quantity = hundreds
        units, tenths = divmod(rest, 100)
        counts[1.0].quantity = units
        counts[0.1].quantity = tenths // 10

    def _day_movements(self):
        """Saldo previo de 1 000 y, el día D1: venta al contado 500, cobranza 200 y pago 100."""
        self._payment('inbound', 1000, D0)
        self._collect(self._invoice(500, D1), D1)
        self._collect(self._invoice(200, D0), D1)
        self._payment('outbound', 100, D1)

    # ------------------------------------------------------------------ libros
    def test_book_balance_and_day_movements(self):
        self._day_movements()
        closing = self._closing()
        self.assertAlmostEqual(closing.balance_start, 1000.0)
        self.assertAlmostEqual(closing.amount_in, 700.0)
        self.assertAlmostEqual(closing.amount_out, 100.0)
        self.assertAlmostEqual(closing.balance_book, 1600.0)
        kinds = {line.amount: (line.category, line.sale_kind) for line in closing.line_ids}
        self.assertEqual(kinds[500.0], ('collection', 'cash'))
        self.assertEqual(kinds[200.0], ('collection', 'credit'))
        self.assertEqual(kinds[-100.0], ('payment', False))
        summary = dict(closing._l10n_pe_summary_by_category())
        self.assertAlmostEqual(summary['Cobro (venta al contado)'], 500.0)

    def test_denominations_are_prefilled(self):
        closing = self._closing()
        values = set(closing.count_ids.mapped('value'))
        self.assertTrue({200.0, 100.0, 0.1} <= values)
        self.assertNotIn(0.05, values, 'la moneda de 5 céntimos ya no circula')

    def test_internal_transfer_is_a_transfer(self):
        self._payment('outbound', 300, D1, destination_account_id=self.company.transfer_account_id.id)
        closing = self._closing()
        self.assertEqual(closing.line_ids.category, 'transfer')

    # ------------------------------------------------------------------ cierre
    def test_exact_count_closes_without_entry(self):
        self._day_movements()
        closing = self._closing()
        self._count(closing, 1600.0)
        self.assertFalse(closing.difference)
        closing.action_close()
        self.assertEqual(closing.state, 'closed')
        self.assertFalse(closing.move_id)

    def test_shortage_books_difference(self):
        self._day_movements()
        closing = self._closing()
        self._count(closing, 1590.0)
        self.assertAlmostEqual(closing.difference, -10.0)
        closing.action_close()
        move = closing.move_id
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.journal_id, self.cash)
        loss = move.line_ids.filtered(lambda l: l.account_id == self.cash.loss_account_id)
        self.assertAlmostEqual(loss.balance, 10.0)
        # Al día siguiente, los libros parten de lo arqueado.
        self.assertAlmostEqual(self._closing(D2).balance_start, 1590.0)

    def test_shortage_charged_to_cashier(self):
        self._payment('inbound', 50, D1)
        closing = self._closing()
        self._count(closing, 45.0)
        closing.write({'shortage_account_id': self.receivable_staff.id, 'shortage_partner_id': self.partner.id})
        closing.action_close()
        line = closing.move_id.line_ids.filtered(lambda l: l.account_id == self.receivable_staff)
        self.assertAlmostEqual(line.balance, 5.0)
        self.assertEqual(line.partner_id, self.partner)

    def test_surplus_goes_to_profit_account(self):
        self._payment('inbound', 50, D1)
        closing = self._closing()
        self._count(closing, 52.0)
        closing.action_close()
        profit = closing.move_id.line_ids.filtered(lambda l: l.account_id == self.cash.profit_account_id)
        self.assertAlmostEqual(profit.balance, -2.0)

    def test_close_requires_count_and_no_draft_payments(self):
        self._payment('inbound', 50, D1)
        closing = self._closing()
        with self.assertRaisesRegex(UserError, 'arqueo'):
            closing.action_close()
        self._count(closing, 50.0)
        self.env['account.payment'].create({
            'payment_type': 'inbound', 'partner_type': 'customer', 'partner_id': self.partner.id,
            'amount': 5, 'date': D1, 'journal_id': self.cash.id})
        with self.assertRaisesRegex(UserError, 'borrador'):
            closing.action_close()

    # ------------------------------------------------------------------ bloqueo
    def test_closed_day_is_locked(self):
        payment = self._payment('inbound', 50, D1)
        closing = self._closing()
        self._count(closing, 50.0)
        closing.action_close()
        with self.assertRaisesRegex(UserError, 'cerrada'):
            self._payment('inbound', 10, D1)
        with self.assertRaisesRegex(UserError, 'cerrada'):
            self._payment('inbound', 10, D0)
        with self.assertRaisesRegex(UserError, 'cerrada'):
            payment.move_id.button_draft()
        self.assertTrue(self._payment('inbound', 10, D2), 'el día siguiente sigue abierto')
        self.assertTrue(self._payment('inbound', 10, D1, journal=self.other_cash), 'otra caja no se bloquea')

    def test_reopen_unlocks_and_cancels_difference(self):
        self._payment('inbound', 50, D1)
        closing = self._closing()
        self._count(closing, 40.0)
        closing.action_close()
        difference = closing.move_id
        closing.action_reopen()
        self.assertEqual(closing.state, 'open')
        self.assertEqual(difference.state, 'cancel')
        self.assertFalse(closing.move_id)
        self.assertTrue(self._payment('inbound', 10, D1))
        closing.action_refresh()
        self.assertAlmostEqual(closing.balance_book, 60.0)

    def test_reopen_order_and_rights(self):
        self._payment('inbound', 50, D1)
        first = self._closing(D1)
        self._count(first, 50.0)
        first.action_close()
        second = self._closing(D2)
        self._count(second, 50.0)
        second.action_close()
        with self.assertRaisesRegex(UserError, 'posterior'):
            first.action_reopen()
        cashier = self.env['res.users'].create({
            'name': 'Cajero', 'login': 'cajero_cierre',
            'group_ids': [Command.set([self.env.ref('account.group_account_invoice').id])],
            'company_id': self.company.id, 'company_ids': [Command.set(self.company.ids)],
        })
        with self.assertRaisesRegex(UserError, 'administrador'):
            second.with_user(cashier).action_reopen()

    def test_one_closing_per_cash_and_day(self):
        self._closing()
        with self.assertRaises(Exception), self.cr.savepoint(), mute_logger('odoo.sql_db'):
            self._closing()
        bank = self.env['account.journal'].search([('type', '=', 'bank'), ('company_id', '=', self.company.id)],
                                                  limit=1)
        with self.assertRaises(ValidationError):
            self._closing(D2, journal=bank)

    def test_pdf_renders(self):
        self._day_movements()
        closing = self._closing()
        self._count(closing, 1590.0)
        closing.action_close()
        html, _type = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_cash_closing.report_cash_closing', closing.ids)
        html = html.decode()
        self.assertIn(closing.name, html)
        self.assertIn('Faltante', html)
        self.assertIn('Cobro (venta al contado)', html)
