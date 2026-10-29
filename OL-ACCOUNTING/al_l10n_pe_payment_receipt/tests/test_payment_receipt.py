"""Comprobante de pago: numeración por diario y sentido, detalle de lo aplicado y PDF."""
from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.al_account_base.tests.common import use_pe_company


@tagged('post_install', '-at_install')
class TestPaymentReceipt(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        # Sin diseño de documentos, Odoo abre su asistente antes del reporte.
        if not cls.company.external_report_layout_id:
            cls.company.external_report_layout_id = cls.env.ref('web.external_layout_standard')
        cls.partner = cls.env['res.partner'].create({
            'name': 'CLIENTE RECIBO SAC', 'vat': '20557912879',
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.bank = cls.env['account.journal'].create({
            'name': 'Caja recibos', 'code': 'CJRC', 'type': 'cash',
            'company_id': cls.company.id, 'l10n_pe_receipt_enabled': True,
        })
        cls.plain_bank = cls.env['account.journal'].create({
            'name': 'Banco sin recibo', 'code': 'BKSR', 'type': 'bank', 'company_id': cls.company.id,
        })
        # Con cuenta de pendientes el pago lleva asiento al confirmarse; sin
        # ella (como en la caja) no lo tiene hasta conciliar el extracto.
        outstanding = cls.env['account.account'].create({
            'name': 'Cobros pendientes (prueba)', 'code': '104199', 'account_type': 'asset_current',
            'reconcile': True,
        })
        cls.bank_moves = cls.env['account.journal'].create({
            'name': 'Banco con asiento', 'code': 'BKAS', 'type': 'bank',
            'company_id': cls.company.id, 'l10n_pe_receipt_enabled': True,
        })
        (cls.bank_moves.inbound_payment_method_line_ids | cls.bank_moves.outbound_payment_method_line_ids) \
            .payment_account_id = outstanding
        # Diario de ventas sin documentos LATAM: la factura no pasa por el EDI.
        cls.sale_journal = cls.env['account.journal'].create({
            'name': 'Ventas recibos', 'code': 'VTRC', 'type': 'sale',
            'company_id': cls.company.id, 'l10n_latam_use_documents': False,
        })

    def _invoice(self, amount):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner.id,
            'journal_id': self.sale_journal.id, 'invoice_date': fields.Date.today(),
            'invoice_line_ids': [Command.create({'name': 'Servicio', 'price_unit': amount,
                                                 'tax_ids': [Command.clear()]})],
        })
        move.action_post()
        return move

    def _pay(self, moves, amount=None, journal=None, group=True):
        vals = {'journal_id': (journal or self.bank).id, 'group_payment': group}
        if amount is not None:
            vals['amount'] = amount
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=moves.ids).create(vals)
        return wizard._create_payments()

    def _payment(self, payment_type='inbound', amount=100.0, journal=None):
        payment = self.env['account.payment'].create({
            'payment_type': payment_type, 'partner_type': 'customer' if payment_type == 'inbound' else 'supplier',
            'partner_id': self.partner.id, 'amount': amount, 'journal_id': (journal or self.bank).id,
        })
        payment.action_post()
        return payment

    def test_sequences_are_created_per_journal(self):
        self.assertTrue(self.bank.l10n_pe_receipt_in_sequence_id)
        self.assertEqual(self.bank.l10n_pe_receipt_in_sequence_id.prefix, 'RI-CJRC-')
        self.assertEqual(self.bank.l10n_pe_receipt_out_sequence_id.prefix, 'RE-CJRC-')
        self.assertFalse(self.plain_bank.l10n_pe_receipt_in_sequence_id)
        self.plain_bank.l10n_pe_receipt_enabled = True
        self.assertEqual(self.plain_bank.l10n_pe_receipt_out_sequence_id.prefix, 'RE-BKSR-')

    def test_number_on_post_by_direction(self):
        inbound = self._payment('inbound')
        outbound = self._payment('outbound')
        self.assertEqual(inbound.l10n_pe_receipt_number, 'RI-CJRC-000001')
        self.assertEqual(outbound.l10n_pe_receipt_number, 'RE-CJRC-000001')
        self.assertFalse(self._payment(journal=self.plain_bank).l10n_pe_receipt_number)

    def test_number_survives_draft(self):
        payment = self._payment()
        number = payment.l10n_pe_receipt_number
        payment.action_draft()
        payment.action_post()
        self.assertEqual(payment.l10n_pe_receipt_number, number)
        self.assertEqual(self._payment().l10n_pe_receipt_number, 'RI-CJRC-000002', 'sin huecos')
        self.assertFalse(payment.copy().l10n_pe_receipt_number)

    def test_partial_payment_details(self):
        for journal in (self.bank, self.bank_moves):
            with self.subTest(journal=journal.name):
                invoice = self._invoice(1180.0)
                payment = self._pay(invoice, amount=500.0, journal=journal)
                self.assertEqual(bool(payment.move_id), journal == self.bank_moves)
                docs = payment._l10n_pe_receipt_documents()
                self.assertEqual(len(docs), 1)
                self.assertEqual(docs[0]['move'], invoice)
                self.assertAlmostEqual(docs[0]['applied'], 500.0)
                self.assertAlmostEqual(docs[0]['residual'], 680.0)
                self.assertFalse(payment._l10n_pe_receipt_unapplied())

    def test_one_payment_for_two_invoices(self):
        for journal in (self.bank, self.bank_moves):
            with self.subTest(journal=journal.name):
                invoices = self._invoice(100.0) | self._invoice(250.0)
                payment = self._pay(invoices, journal=journal)
                self.assertEqual(len(payment), 1)
                docs = {doc['move']: doc['applied'] for doc in payment._l10n_pe_receipt_documents()}
                self.assertEqual(set(docs), set(invoices))
                self.assertAlmostEqual(sum(docs.values()), 350.0)

    def test_payment_on_account(self):
        for journal in (self.bank, self.bank_moves):
            with self.subTest(journal=journal.name):
                payment = self._payment(amount=75.0, journal=journal)
                self.assertFalse(payment._l10n_pe_receipt_documents())
                self.assertAlmostEqual(payment._l10n_pe_receipt_unapplied(), 75.0)

    def test_amount_in_words(self):
        payment = self._payment(amount=118.5)
        self.assertEqual(payment._l10n_pe_receipt_amount_words(), 'CIENTO DIECIOCHO Y 50/100 SOLES')

    def test_pdf_renders(self):
        invoice = self._invoice(300.0)
        payment = self._pay(invoice)
        html, _type = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_payment_receipt.report_payment_receipt_pe', payment.ids)
        html = html.decode()
        self.assertIn(payment.l10n_pe_receipt_number, html)
        self.assertIn('TRESCIENTOS Y 00/100 SOLES', html)
        self.assertIn(invoice.name, html)

    def test_print_requires_a_number(self):
        payment = self._payment(journal=self.plain_bank)
        with self.assertRaises(UserError):
            payment.action_l10n_pe_receipt_print()
        self.assertEqual(self._payment().action_l10n_pe_receipt_print()['type'], 'ir.actions.report')
