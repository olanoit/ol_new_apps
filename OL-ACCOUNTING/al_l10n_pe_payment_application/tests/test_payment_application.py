"""Anticipos (122/422), aplicación a facturas, compensación y reversión."""
from datetime import date
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.al_account_base.tests.common import use_pe_company

D0, D1, D2 = date(2026, 9, 1), date(2026, 9, 10), date(2026, 9, 20)


@tagged('post_install', '-at_install')
class TestPaymentApplication(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        ref = cls.env['account.chart.template'].with_company(cls.company).ref
        root = cls.company.root_id
        if not root.l10n_pe_advance_customer_account_id:
            root.l10n_pe_advance_customer_account_id = ref('chart122')
        if not root.l10n_pe_advance_supplier_account_id:
            root.l10n_pe_advance_supplier_account_id = ref('chart422')
        if not root.l10n_pe_application_journal_id:
            root.l10n_pe_application_journal_id = cls.env['account.journal'].create({
                'name': 'Aplicaciones (prueba)', 'code': 'APLT', 'type': 'general'})
        cls.acc_122 = root.l10n_pe_advance_customer_account_id
        cls.acc_422 = root.l10n_pe_advance_supplier_account_id
        cls.partner = cls.env['res.partner'].create({
            'name': 'SOCIO ANTICIPOS SAC', 'vat': '20557912879',
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.other = cls.env['res.partner'].create({'name': 'OTRO SOCIO SAC'})
        # Con cuenta de pendientes el pago lleva asiento al confirmarse.
        outstanding = cls.env['account.account'].create({
            'name': 'Pendientes (prueba anticipos)', 'code': '104198', 'account_type': 'asset_current',
            'reconcile': True,
        })
        cls.bank = cls.env['account.journal'].create({
            'name': 'Banco anticipos', 'code': 'BKAN', 'type': 'bank', 'company_id': cls.company.id})
        (cls.bank.inbound_payment_method_line_ids | cls.bank.outbound_payment_method_line_ids) \
            .payment_account_id = outstanding
        cls.sale_journal = cls.env['account.journal'].create({
            'name': 'Ventas anticipos', 'code': 'VTAN', 'type': 'sale', 'l10n_latam_use_documents': False})
        cls.purchase_journal = cls.env['account.journal'].create({
            'name': 'Compras anticipos', 'code': 'CPAN', 'type': 'purchase', 'l10n_latam_use_documents': False})
        cls.usd = cls.env.ref('base.USD')
        cls.usd.active = True
        cls.env['res.currency.rate'].search([
            ('currency_id', '=', cls.usd.id), ('company_id', 'in', (False, cls.company.id)),
            ('name', 'in', (D0, D1, D2))]).unlink()
        for day, rate in ((D0, 3.60), (D1, 3.70), (D2, 3.80)):
            cls.env['res.currency.rate'].create({
                'name': day, 'currency_id': cls.usd.id, 'company_id': cls.company.id,
                'inverse_company_rate': rate})

    # ------------------------------------------------------------------ ayuda
    def _advance(self, partner_type, amount, currency=None, day=D0):
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound' if partner_type == 'customer' else 'outbound',
            'partner_type': partner_type, 'partner_id': self.partner.id, 'amount': amount,
            'journal_id': self.bank.id, 'date': day, 'l10n_pe_is_advance': True,
            'currency_id': (currency or self.company.currency_id).id,
        })
        payment.action_post()
        return payment

    def _document(self, move_type, amount, currency=None, day=D1, partner=None):
        move = self.env['account.move'].create({
            'move_type': move_type, 'partner_id': (partner or self.partner).id,
            'journal_id': (self.sale_journal if move_type.startswith('out') else self.purchase_journal).id,
            'invoice_date': day, 'date': day, 'currency_id': (currency or self.company.currency_id).id,
            'invoice_line_ids': [Command.create({'name': 'Servicio', 'price_unit': amount,
                                                 'tax_ids': [Command.clear()]})],
        })
        move.action_post()
        return move

    def _apply_from(self, move, day=D2):
        action = move.action_l10n_pe_apply_advances()
        application = self.env['l10n_pe.payment.application'].browse(action['res_id'])
        application.date = day
        application.action_distribute()
        return application

    # ------------------------------------------------------------------ anticipo
    def test_advance_goes_to_122_and_422(self):
        customer = self._advance('customer', 500)
        supplier = self._advance('supplier', 300)
        self.assertEqual(customer.destination_account_id, self.acc_122)
        self.assertEqual(supplier.destination_account_id, self.acc_422)
        self.assertIn(self.acc_122, customer.move_id.line_ids.account_id)
        self.assertIn(self.acc_422, supplier.move_id.line_ids.account_id)
        self.assertAlmostEqual(customer._l10n_pe_receipt_unapplied(), 500.0)

    def test_advance_requires_configured_account(self):
        root = self.company.root_id
        root.l10n_pe_advance_supplier_account_id = False
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': self.partner.id,
            'amount': 10, 'journal_id': self.bank.id, 'l10n_pe_is_advance': True})
        with self.assertRaisesRegex(UserError, 'cuenta de anticipos'):
            payment.action_post()

    # ------------------------------------------------------------------ aplicación
    def test_apply_supplier_advance_in_full(self):
        advance = self._advance('supplier', 1000)
        bill = self._document('in_invoice', 1000)
        self.assertEqual(bill.l10n_pe_advance_count, 1)
        application = self._apply_from(bill)
        application.action_post()
        self.assertEqual(application.state, 'posted')
        self.assertEqual(application.move_id.journal_id, self.company.root_id.l10n_pe_application_journal_id)
        self.assertIn(bill.payment_state, ('paid', 'in_payment'))
        advance_line = advance.move_id.line_ids.filtered(lambda l: l.account_id == self.acc_422)
        self.assertTrue(advance_line.reconciled)
        bill.invalidate_recordset(['l10n_pe_advance_count'])
        self.assertEqual(bill.l10n_pe_advance_count, 0)

    def test_apply_partial_advance(self):
        self._advance('supplier', 300)
        bill = self._document('in_invoice', 1000)
        application = self._apply_from(bill)
        application.action_post()
        self.assertAlmostEqual(bill.amount_residual, 700.0)
        self.assertEqual(bill.payment_state, 'partial')

    def test_apply_customer_advance_from_payment(self):
        advance = self._advance('customer', 400)
        invoice = self._document('out_invoice', 250)
        action = advance.action_l10n_pe_apply_advance()
        application = self.env['l10n_pe.payment.application'].browse(action['res_id'])
        self.assertIn(invoice, application.line_ids.move_id)
        application.action_post()
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'))
        advance_line = advance.move_id.line_ids.filtered(lambda l: l.account_id == self.acc_122)
        self.assertAlmostEqual(abs(advance_line.amount_residual), 150.0)

    def test_pen_advance_to_usd_bill_books_exchange_difference(self):
        """Factura de 100 USD a 3,70 cancelada con un anticipo en soles el día que
        el dólar vale 3,80: se aplican S/ 380 y Odoo registra la diferencia de cambio."""
        self._advance('supplier', 380)
        bill = self._document('in_invoice', 100, currency=self.usd, day=D1)
        self.assertAlmostEqual(abs(bill.line_ids.filtered(
            lambda l: l.account_id.account_type == 'liability_payable').balance), 370.0)
        application = self._apply_from(bill, day=D2)
        usd_line = application.line_ids.filtered(lambda l: l.currency_id == self.usd)
        self.assertAlmostEqual(usd_line.amount, 100.0)
        self.assertAlmostEqual(usd_line.amount_company, 380.0)
        self.assertFalse(application.amount_difference)
        application.action_post()
        self.assertIn(bill.payment_state, ('paid', 'in_payment'))
        exchange = bill.line_ids.matched_debit_ids.exchange_move_id | bill.line_ids.matched_credit_ids.exchange_move_id
        self.assertTrue(exchange, 'diferencia de cambio de S/ 10')
        self.assertAlmostEqual(sum(abs(l.balance) for l in exchange.line_ids) / 2, 10.0)

    def test_netting_receivable_and_payable(self):
        invoice = self._document('out_invoice', 500)
        bill = self._document('in_invoice', 200)
        application = self.env['l10n_pe.payment.application'].create({
            'partner_id': self.partner.id, 'application_type': 'netting', 'date': D2})
        application.action_load_documents()
        self.assertEqual(set(application.line_ids.move_id), {invoice, bill})
        application.action_distribute()
        application.action_post()
        self.assertAlmostEqual(invoice.amount_residual, 300.0)
        self.assertIn(bill.payment_state, ('paid', 'in_payment'))

    def test_reversal_reopens_documents(self):
        self._advance('supplier', 1000)
        bill = self._document('in_invoice', 1000)
        application = self._apply_from(bill)
        application.action_post()
        application.action_cancel()
        self.assertEqual(application.state, 'cancel')
        self.assertTrue(application.reversal_move_id)
        self.assertAlmostEqual(bill.amount_residual, 1000.0)
        bill.invalidate_recordset(['l10n_pe_advance_count'])
        self.assertEqual(bill.l10n_pe_advance_count, 1)

    # ------------------------------------------------------------------ errores
    def test_unbalanced_application_is_refused(self):
        self._advance('supplier', 1000)
        bill = self._document('in_invoice', 1000)
        application = self._apply_from(bill)
        application.line_ids.filtered(lambda l: l.move_id == bill).amount = 600
        with self.assertRaisesRegex(UserError, 'debe ser igual'):
            application.action_post()

    def test_amount_over_residual_is_refused(self):
        self._advance('supplier', 1000)
        bill = self._document('in_invoice', 500)
        application = self._apply_from(bill)
        application.line_ids.write({'amount': 800})
        with self.assertRaisesRegex(UserError, 'supera su saldo'):
            application.action_post()

    def test_other_partner_is_refused(self):
        self._advance('supplier', 100)
        foreign = self._document('in_invoice', 100, partner=self.other)
        bill = self._document('in_invoice', 100)
        application = self._apply_from(bill)
        application.line_ids = [Command.create({
            'move_line_id': foreign.line_ids.filtered(
                lambda l: l.account_id.account_type == 'liability_payable').id, 'amount': 1})]
        with self.assertRaisesRegex(UserError, 'otro socio'):
            application.action_post()

    def test_pending_advances_action(self):
        advance = self._advance('customer', 90)
        action = self.env['l10n_pe.payment.application'].action_open_pending_advances('customer')
        lines = self.env['account.move.line'].search(action['domain'])
        self.assertIn(advance.move_id.line_ids.filtered(lambda l: l.account_id == self.acc_122), lines)
        self.assertFalse(lines.filtered(lambda l: l.account_id == self.acc_422))

    def test_document_held_by_a_third_party_is_refused(self):
        """Letra en el banco o factura cedida con recurso (gancho de al_account_base)."""
        self._advance('supplier', 500)
        bill = self._document('in_invoice', 500)
        AML = self.env.registry['account.move.line']
        original = AML._l10n_pe_payment_block_reason

        def block(line):
            return 'Cedida al factor' if line.move_id == bill else original(line)
        with patch.object(AML, '_l10n_pe_payment_block_reason', block):
            application = self.env['l10n_pe.payment.application'].create({
                'partner_id': self.partner.id, 'application_type': 'advance', 'date': D2})
            application.action_load_documents()
            self.assertNotIn(bill, application.line_ids.move_id, 'no se carga')
            application.line_ids = [Command.create({'move_line_id': bill.line_ids.filtered(
                lambda l: l.account_id.account_type == 'liability_payable').id, 'amount': 500})]
            application.action_distribute()
            with self.assertRaisesRegex(UserError, 'Cedida al factor'):
                application.action_post()
