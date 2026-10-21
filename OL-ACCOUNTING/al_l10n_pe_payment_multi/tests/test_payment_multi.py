"""Pago múltiple: un solo pago para documentos de varios socios, anticipos y otros pagos."""
from datetime import date

from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.al_account_base.tests.common import use_pe_company

D1, D2 = date(2026, 9, 10), date(2026, 9, 20)


@tagged('post_install', '-at_install')
class TestPaymentMulti(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        if not cls.company.external_report_layout_id:
            cls.company.external_report_layout_id = cls.env.ref('web.external_layout_standard')
        ref = cls.env['account.chart.template'].with_company(cls.company).ref
        root = cls.company.root_id
        if not root.l10n_pe_advance_supplier_account_id:
            root.l10n_pe_advance_supplier_account_id = ref('chart422')
        if not root.l10n_pe_advance_customer_account_id:
            root.l10n_pe_advance_customer_account_id = ref('chart122')
        cls.acc_422 = root.l10n_pe_advance_supplier_account_id
        cls.expense = cls.env['account.account'].create({
            'name': 'Gastos bancarios (prueba)', 'code': '639199', 'account_type': 'expense'})
        cls.supplier_a, cls.supplier_b, cls.customer_a, cls.customer_b = cls.env['res.partner'].create([
            {'name': 'PROVEEDOR UNO SAC'}, {'name': 'PROVEEDOR DOS SAC'},
            {'name': 'CLIENTE UNO SAC'}, {'name': 'CLIENTE DOS SAC'},
        ])
        outstanding = cls.env['account.account'].create({
            'name': 'Pendientes (prueba pago múltiple)', 'code': '104197', 'account_type': 'asset_current',
            'reconcile': True,
        })
        cls.outstanding = outstanding
        cls.bank = cls.env['account.journal'].create({
            'name': 'Banco pago múltiple', 'code': 'BKPM', 'type': 'bank', 'company_id': cls.company.id,
            'l10n_pe_receipt_enabled': True,
        })
        (cls.bank.inbound_payment_method_line_ids | cls.bank.outbound_payment_method_line_ids) \
            .payment_account_id = outstanding
        cls.plain_bank = cls.env['account.journal'].create({
            'name': 'Banco sin pendientes', 'code': 'BKPS', 'type': 'bank', 'company_id': cls.company.id,
        })
        (cls.plain_bank.inbound_payment_method_line_ids | cls.plain_bank.outbound_payment_method_line_ids) \
            .payment_account_id = False
        cls.sale_journal = cls.env['account.journal'].create({
            'name': 'Ventas pago múltiple', 'code': 'VTPM', 'type': 'sale', 'l10n_latam_use_documents': False})
        cls.purchase_journal = cls.env['account.journal'].create({
            'name': 'Compras pago múltiple', 'code': 'CPPM', 'type': 'purchase',
            'l10n_latam_use_documents': False})
        cls.usd = cls.env.ref('base.USD')
        cls.usd.active = True
        cls.env['res.currency.rate'].search([
            ('currency_id', '=', cls.usd.id), ('company_id', 'in', (False, cls.company.id)),
            ('name', 'in', (D1, D2))]).unlink()
        for day, rate in ((D1, 3.70), (D2, 3.80)):
            cls.env['res.currency.rate'].create({
                'name': day, 'currency_id': cls.usd.id, 'company_id': cls.company.id,
                'inverse_company_rate': rate})

    # ------------------------------------------------------------------ ayuda
    def _document(self, move_type, partner, amount, currency=None, day=D1):
        move = self.env['account.move'].create({
            'move_type': move_type, 'partner_id': partner.id,
            'journal_id': (self.sale_journal if move_type.startswith('out') else self.purchase_journal).id,
            'invoice_date': day, 'date': day, 'currency_id': (currency or self.company.currency_id).id,
            'invoice_line_ids': [Command.create({'name': 'Servicio', 'price_unit': amount,
                                                 'tax_ids': [Command.clear()]})],
        })
        move.action_post()
        return move

    @staticmethod
    def _open_line(move):
        return move.line_ids.filtered(
            lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable'))

    def _multi(self, payment_type='outbound', journal=None, lines=(), day=D2):
        return self.env['l10n_pe.payment.multi'].create({
            'payment_type': payment_type, 'journal_id': (journal or self.bank).id, 'date': day,
            'line_ids': [Command.create(vals) for vals in lines],
        })

    def _doc_line(self, move, amount=None):
        vals = {'line_type': 'document', 'move_line_id': self._open_line(move).id}
        if amount is not None:
            vals['amount'] = amount
        return vals

    # ------------------------------------------------------------------ pago
    def test_one_payment_for_bills_of_two_suppliers(self):
        bill_a = self._document('in_invoice', self.supplier_a, 1000)
        bill_b = self._document('in_invoice', self.supplier_b, 500)
        multi = self._multi(lines=[self._doc_line(bill_a), self._doc_line(bill_b)])
        self.assertAlmostEqual(multi.amount_total, 1500.0)
        self.assertEqual(multi.partner_count, 2)
        multi.action_post()
        payment = multi.payment_id
        self.assertEqual(multi.state, 'posted')
        self.assertEqual(payment.payment_type, 'outbound')
        self.assertAlmostEqual(payment.amount, 1500.0)
        self.assertFalse(payment.partner_id, 'varios socios: el pago no lleva uno')
        liquidity, counterpart, _writeoff = payment._seek_for_lines()
        self.assertEqual(liquidity.account_id, self.outstanding)
        self.assertAlmostEqual(liquidity.balance, -1500.0)
        self.assertEqual(set(counterpart.partner_id), {self.supplier_a, self.supplier_b})
        for bill in (bill_a, bill_b):
            self.assertIn(bill.payment_state, ('paid', 'in_payment'))
        self.assertEqual(payment.reconciled_bill_ids, bill_a | bill_b)
        self.assertTrue(multi.receipt_number.startswith('RE-BKPM-'))

    def test_partial_and_credit_note_reduce_the_payment(self):
        bill = self._document('in_invoice', self.supplier_a, 1000)
        refund = self._document('in_refund', self.supplier_a, 200)
        multi = self._multi(lines=[self._doc_line(bill, 600), self._doc_line(refund)])
        refund_line = multi.line_ids.filtered(lambda l: l.move_id == refund)
        self.assertEqual(refund_line.direction, 'in')
        self.assertAlmostEqual(multi.amount_total, 400.0)
        multi.action_post()
        self.assertAlmostEqual(multi.payment_id.amount, 400.0)
        self.assertEqual(multi.payment_id.partner_id, self.supplier_a, 'un solo socio: el pago lo lleva')
        self.assertAlmostEqual(bill.amount_residual, 400.0)
        self.assertIn(refund.payment_state, ('paid', 'in_payment'))

    def test_advance_and_other_payment_lines(self):
        bill = self._document('in_invoice', self.supplier_a, 300)
        multi = self._multi(lines=[
            self._doc_line(bill),
            {'line_type': 'advance', 'partner_id': self.supplier_b.id, 'amount': 250},
            {'line_type': 'other', 'name': 'Comisión bancaria', 'account_id': self.expense.id, 'amount': 15},
        ])
        advance = multi.line_ids.filtered(lambda l: l.line_type == 'advance')
        self.assertEqual(advance.account_id, self.acc_422)
        self.assertAlmostEqual(multi.amount_total, 565.0)
        multi.action_post()
        lines = multi.move_id.line_ids
        self.assertAlmostEqual(lines.filtered(lambda l: l.account_id == self.acc_422).balance, 250.0)
        self.assertEqual(lines.filtered(lambda l: l.account_id == self.acc_422).partner_id, self.supplier_b)
        self.assertAlmostEqual(lines.filtered(lambda l: l.account_id == self.expense).balance, 15.0)
        self.assertIn(bill.payment_state, ('paid', 'in_payment'))
        # El anticipo queda pendiente para aplicarlo después (P3).
        others = multi.payment_id._l10n_pe_receipt_other_lines()
        self.assertEqual(set(others.mapped('name')), {'Anticipo: PROVEEDOR DOS SAC', 'Comisión bancaria'})
        self.assertFalse(multi.payment_id._l10n_pe_receipt_unapplied(), 'todo detallado en el comprobante')
        pending = self.env['l10n_pe.payment.application'].action_open_pending_advances('supplier')
        self.assertIn(lines.filtered(lambda l: l.account_id == self.acc_422),
                      self.env['account.move.line'].search(pending['domain']))

    def test_usd_bill_from_pen_bank_books_exchange_difference(self):
        """Factura de 100 USD a 3,70 pagada desde un banco en soles el día que el
        dólar vale 3,80: salen S/ 380 y Odoo registra la diferencia de S/ 10."""
        bill = self._document('in_invoice', self.supplier_a, 100, currency=self.usd, day=D1)
        multi = self._multi(lines=[self._doc_line(bill)], day=D2)
        line = multi.line_ids
        self.assertAlmostEqual(line.amount, 100.0)
        self.assertAlmostEqual(line.amount_company, 380.0)
        self.assertAlmostEqual(multi.amount_total, 380.0)
        multi.action_post()
        self.assertIn(bill.payment_state, ('paid', 'in_payment'))
        exchange = bill.line_ids.matched_debit_ids.exchange_move_id | bill.line_ids.matched_credit_ids.exchange_move_id
        self.assertTrue(exchange)
        self.assertAlmostEqual(sum(abs(l.balance) for l in exchange.line_ids) / 2, 10.0)

    def test_inbound_collects_invoices_of_two_customers(self):
        inv_a = self._document('out_invoice', self.customer_a, 800)
        inv_b = self._document('out_invoice', self.customer_b, 200)
        multi = self._multi('inbound', lines=[self._doc_line(inv_a), self._doc_line(inv_b)])
        self.assertEqual(set(multi.line_ids.mapped('direction')), {'in'})
        multi.action_post()
        self.assertEqual(multi.payment_id.payment_type, 'inbound')
        self.assertAlmostEqual(multi.payment_id.amount, 1000.0)
        self.assertTrue(multi.receipt_number.startswith('RI-BKPM-'))
        for invoice in (inv_a, inv_b):
            self.assertIn(invoice.payment_state, ('paid', 'in_payment'))

    def test_journal_without_outstanding_account_still_books(self):
        bill = self._document('in_invoice', self.supplier_a, 120)
        multi = self._multi(journal=self.plain_bank, lines=[self._doc_line(bill)])
        multi.action_post()
        self.assertTrue(multi.move_id, 'sin cuenta de pendientes se usa la de Odoo')
        liquidity, _counterpart, _writeoff = multi.payment_id._seek_for_lines()
        self.assertEqual(liquidity.account_id, multi.payment_id.outstanding_account_id)
        self.assertIn(bill.payment_state, ('paid', 'in_payment'))

    # ------------------------------------------------------------------ carga
    def test_load_documents_by_partner(self):
        bill_a = self._document('in_invoice', self.supplier_a, 100)
        bill_b = self._document('in_invoice', self.supplier_b, 100)
        invoice = self._document('out_invoice', self.supplier_a, 100)
        multi = self._multi()
        multi.partner_ids = self.supplier_a
        multi.action_load_documents()
        self.assertEqual(multi.line_ids.move_id, bill_a)
        multi.partner_ids = self.supplier_a | self.supplier_b
        multi.action_load_documents()
        self.assertEqual(multi.line_ids.move_id, bill_a | bill_b, 'sin duplicar ni traer cuentas por cobrar')
        self.assertNotIn(invoice, multi.line_ids.move_id)
        self.assertAlmostEqual(multi.line_ids[:1].amount, 100.0, 'por defecto, el saldo completo')

    def test_action_from_bills_list(self):
        bills = self._document('in_invoice', self.supplier_a, 70) | self._document('in_invoice', self.supplier_b, 30)
        action = self.env['l10n_pe.payment.multi']._l10n_pe_open_from_moves(bills)
        multi = self.env['l10n_pe.payment.multi'].browse(action['res_id'])
        self.assertEqual(multi.payment_type, 'outbound')
        self.assertEqual(multi.line_ids.move_id, bills)
        self.assertAlmostEqual(multi.amount_total, 100.0)

    # ------------------------------------------------------------------ anular
    def test_cancel_reopens_documents(self):
        bill_a = self._document('in_invoice', self.supplier_a, 100)
        bill_b = self._document('in_invoice', self.supplier_b, 100)
        multi = self._multi(lines=[self._doc_line(bill_a), self._doc_line(bill_b)])
        multi.action_post()
        payment = multi.payment_id
        with self.assertRaisesRegex(UserError, 'pago múltiple'):
            payment.action_draft()
        multi.action_cancel()
        self.assertEqual(multi.state, 'cancel')
        self.assertEqual(payment.state, 'canceled')
        self.assertAlmostEqual(bill_a.amount_residual, 100.0)
        self.assertAlmostEqual(bill_b.amount_residual, 100.0)
        multi.action_draft()
        self.assertEqual(multi.state, 'draft')
        multi.action_post()
        self.assertNotEqual(multi.payment_id, payment, 'al validar de nuevo se crea otro pago')

    # ------------------------------------------------------------------ errores
    def test_amount_over_residual_is_refused(self):
        bill = self._document('in_invoice', self.supplier_a, 100)
        multi = self._multi(lines=[self._doc_line(bill, 150)])
        with self.assertRaisesRegex(UserError, 'supera su saldo'):
            multi.action_post()

    def test_negative_total_is_refused(self):
        bill = self._document('in_invoice', self.supplier_a, 100)
        refund = self._document('in_refund', self.supplier_a, 300)
        multi = self._multi(lines=[self._doc_line(bill), self._doc_line(refund)])
        with self.assertRaisesRegex(UserError, 'debe ser positivo'):
            multi.action_post()

    def test_other_line_cannot_move_cash(self):
        bank_account = self.bank.default_account_id
        multi = self._multi(lines=[{'line_type': 'other', 'name': 'Traspaso', 'account_id': bank_account.id,
                                    'amount': 10}])
        with self.assertRaisesRegex(UserError, 'transferencia interna'):
            multi.action_post()

    # ------------------------------------------------------------------ comprobante
    def test_receipt_lists_each_partner(self):
        bill_a = self._document('in_invoice', self.supplier_a, 100)
        bill_b = self._document('in_invoice', self.supplier_b, 50)
        multi = self._multi(lines=[self._doc_line(bill_a), self._doc_line(bill_b)])
        multi.action_post()
        docs = {doc['move']: doc for doc in multi.payment_id._l10n_pe_receipt_documents()}
        self.assertEqual(set(docs), {bill_a, bill_b})
        self.assertEqual(docs[bill_b]['partner'], self.supplier_b)
        html, _type = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_payment_receipt.report_payment_receipt_pe', multi.payment_id.ids)
        html = html.decode()
        self.assertIn('Varios (ver detalle)', html)
        self.assertIn('PROVEEDOR DOS SAC', html)
        self.assertEqual(multi.action_print_receipt()['type'], 'ir.actions.report')

    def test_document_held_by_a_third_party_is_refused(self):
        """Letra en el banco o factura cedida con recurso (gancho de al_account_base)."""
        held = self._document('in_invoice', self.supplier_a, 100)
        free = self._document('in_invoice', self.supplier_b, 100)
        AML = self.env.registry['account.move.line']
        original = AML._l10n_pe_payment_block_reason

        def block(line):
            return 'En el banco' if line.move_id == held else original(line)
        with patch.object(AML, '_l10n_pe_payment_block_reason', block):
            multi = self._multi()
            multi.partner_ids = self.supplier_a | self.supplier_b
            multi.action_load_documents()
            self.assertEqual(multi.line_ids.move_id, free, 'no se carga')
            multi.line_ids = [Command.create(self._doc_line(held))]
            with self.assertRaisesRegex(UserError, 'En el banco'):
                multi.action_post()
