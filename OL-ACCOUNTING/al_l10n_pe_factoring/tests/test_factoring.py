# -*- coding: utf-8 -*-
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestFactoring(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.today = fields.Date.context_today(cls.env['res.users'])
        Account = cls.env['account.account'].with_company(cls.company)
        cls.income = Account.search([('account_type', '=', 'income')], limit=1)
        cls.sale_journal = cls.env['account.journal'].create({
            'name': 'Ventas factoring test', 'code': 'VFTS', 'type': 'sale',
            'company_id': cls.company.id, 'l10n_latam_use_documents': False})
        cls.bank_journal = cls.env['account.journal'].create({
            'name': 'Banco factoring test', 'code': 'BFTS', 'type': 'bank',
            'company_id': cls.company.id})
        cls.misc_journal = cls.env['account.journal'].create({
            'name': 'Factoring test', 'code': 'FTS', 'type': 'general',
            'company_id': cls.company.id})
        cls.customer = cls.env['res.partner'].create({'name': 'CLIENTE FACTORING SAC', 'vat': '20100070970'})
        cls.factor = cls.env['res.partner'].create({'name': 'FACTOR CAPITAL SAC', 'vat': '20100047218'})
        cls.Config = cls.env['l10n_pe.factoring.account.config']
        for modality in ('without_recourse', 'with_recourse'):
            cls.assertTrue(cls, cls.Config._l10n_pe_get(cls.company, modality, cls.company.currency_id))

    # ------------------------------------------------------------------
    # Ayudantes
    # ------------------------------------------------------------------
    def _invoice(self, amount=1000.0, currency=None):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.customer.id,
            'journal_id': self.sale_journal.id, 'invoice_date': self.today,
            'currency_id': (currency or self.company.currency_id).id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio', 'quantity': 1, 'price_unit': amount,
                'account_id': self.income.id, 'tax_ids': [(6, 0, [])]})],
        })
        move.action_post()
        return move

    def _operation(self, invoices, modality='without_recourse', percent=90.0, currency=None):
        return self.env['l10n_pe.factoring'].create({
            'factor_id': self.factor.id, 'modality': modality, 'journal_id': self.misc_journal.id,
            'currency_id': (currency or self.company.currency_id).id,
            'default_advance_percent': percent,
            'line_ids': [(0, 0, {'move_id': inv.id, 'advance_percent': percent}) for inv in invoices],
        })

    def _wizard(self, operation, kind, **vals):
        wizard = self.env['l10n_pe.factoring.wizard'].create(dict({
            'factoring_id': operation.id, 'operation': kind, 'date': self.today,
            'bank_journal_id': self.bank_journal.id}, **vals))
        if kind in ('settle', 'repurchase') and 'line_ids' not in vals:
            wizard.line_ids = operation.line_ids.filtered(lambda l: l.state == 'assigned')
        wizard.action_apply()
        return wizard

    def _balance(self, operation, account, partner=None):
        lines = operation.move_ids.filtered(lambda m: m.state == 'posted').line_ids.filtered(
            lambda l: l.account_id == account and (not partner or l.partner_id == partner))
        return self.company.currency_id.round(sum(lines.mapped('balance')))

    def _assert_balanced(self, operation):
        for move in operation.move_ids:
            self.assertFalse(self.company.currency_id.round(sum(move.line_ids.mapped('balance'))),
                             'el asiento %s cuadra' % move.ref)

    # ------------------------------------------------------------------
    # Sin recurso
    # ------------------------------------------------------------------
    def test_without_recourse_flow(self):
        invoice = self._invoice(1000.0)
        operation = self._operation(invoice)
        config = operation._config()
        self.assertEqual(operation.line_ids.nominal_amount, 1000.0)
        self.assertEqual(operation.advance_amount, 900.0)
        self.assertEqual(operation.retained_amount, 100.0)

        operation.action_assign()
        self.assertEqual(operation.state, 'assigned')
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'), 'sin recurso la factura se da de baja')
        self.assertEqual(invoice.l10n_pe_factoring_state, 'assigned')
        self.assertEqual(self._balance(operation, config.assigned_account_id, self.factor), 1000.0,
                         'la deuda pasa al factor')

        self._wizard(operation, 'disburse', interest_amount=20.0, fee_amount=10.0, expense_amount=5.0)
        self.assertEqual(operation.state, 'disbursed')
        self.assertEqual(operation.net_amount, 865.0)
        self.assertEqual(self._balance(operation, self.bank_journal.default_account_id), 865.0)
        self.assertEqual(self._balance(operation, config.interest_account_id), 20.0)
        self.assertEqual(self._balance(operation, config.fee_account_id), 15.0)
        self.assertEqual(self._balance(operation, config.assigned_account_id, self.factor), 100.0,
                         'queda el retenido por cobrar al factor')

        self._wizard(operation, 'settle')
        self.assertEqual(operation.state, 'done')
        self.assertEqual(operation.line_ids.state, 'collected')
        self.assertEqual(self._balance(operation, config.assigned_account_id), 0.0)
        self.assertEqual(self._balance(operation, self.bank_journal.default_account_id), 965.0)
        self.assertTrue(operation.line_ids.assignment_line_id.reconciled)
        self._assert_balanced(operation)

    def test_without_recourse_has_no_repurchase(self):
        operation = self._operation(self._invoice())
        operation.action_assign()
        self._wizard(operation, 'disburse')
        with self.assertRaises(UserError):
            self._wizard(operation, 'repurchase')

    # ------------------------------------------------------------------
    # Con recurso
    # ------------------------------------------------------------------
    def test_with_recourse_collected(self):
        invoice = self._invoice(2000.0)
        operation = self._operation(invoice, modality='with_recourse', percent=80.0)
        config = operation._config()
        operation.action_assign()
        self.assertFalse(operation.move_ids, 'con recurso la cesión no genera asiento')
        self.assertEqual(invoice.payment_state, 'not_paid', 'la cuenta por cobrar no se da de baja (NIIF 9)')
        self.assertEqual(invoice.l10n_pe_factoring_state, 'assigned')

        self._wizard(operation, 'disburse', interest_amount=30.0)
        self.assertEqual(self._balance(operation, config.obligation_account_id, self.factor), -1600.0,
                         'el adelanto es una obligación con el factor')
        self.assertEqual(self._balance(operation, config.deferred_interest_account_id), 30.0)
        self.assertEqual(operation.interest_pending_amount, 30.0)

        self._wizard(operation, 'accrue', amount=10.0)
        self.assertEqual(operation.interest_pending_amount, 20.0)
        with self.assertRaises(UserError, msg='no se devenga más de lo pendiente'):
            self._wizard(operation, 'accrue', amount=50.0)

        self.assertEqual(invoice.payment_state, 'not_paid', 'pendiente hasta que el cliente paga al factor')
        self._wizard(operation, 'settle')
        self.assertEqual(operation.state, 'done')
        self.assertIn(invoice.payment_state, ('paid', 'in_payment'), 'el cobro del factor cancela la factura')
        self.assertEqual(operation.interest_pending_amount, 0.0, 'al cerrar se devenga el resto')
        self.assertEqual(self._balance(operation, config.obligation_account_id), 0.0)
        self.assertEqual(self._balance(operation, config.interest_account_id), 30.0)
        self.assertEqual(self._balance(operation, self.bank_journal.default_account_id), 1970.0,
                         'adelanto neto 1570 + retenido 400')
        self._assert_balanced(operation)

    def test_with_recourse_repurchase_keeps_the_invoice(self):
        invoice = self._invoice(1500.0)
        operation = self._operation(invoice, modality='with_recourse', percent=100.0)
        config = operation._config()
        operation.action_assign()
        self.assertEqual(invoice.payment_state, 'not_paid')
        self._wizard(operation, 'disburse', fee_amount=15.0)

        self._wizard(operation, 'repurchase')
        self.assertEqual(operation.state, 'repurchased')
        self.assertEqual(operation.line_ids.state, 'repurchased')
        self.assertEqual(invoice.payment_state, 'not_paid', 'la factura sigue pendiente')
        self.assertEqual(invoice.amount_residual, 1500.0)
        self.assertEqual(self._balance(operation, config.obligation_account_id), 0.0)
        self.assertEqual(self._balance(operation, self.bank_journal.default_account_id), -15.0,
                         'solo cuesta la comisión')
        self._assert_balanced(operation)

        # Recomprada, la factura se puede volver a ceder.
        again = self._operation(invoice)
        self.assertEqual(again.line_ids.nominal_amount, 1500.0)

    # ------------------------------------------------------------------
    # Reglas
    # ------------------------------------------------------------------
    def test_invoice_cannot_be_assigned_twice(self):
        invoice = self._invoice()
        first = self._operation(invoice)
        with self.assertRaises(ValidationError):
            self._operation(invoice)
        first.action_assign()
        first.action_cancel()
        self.assertEqual(invoice.payment_state, 'not_paid', 'cancelada, la factura vuelve al cliente')
        self.assertFalse(invoice.l10n_pe_factoring_state)
        self._operation(invoice)

    def test_nominal_cannot_exceed_residual(self):
        operation = self._operation(self._invoice(500.0))
        operation.line_ids.nominal_amount = 600.0
        with self.assertRaises(UserError):
            operation.action_assign()

    def test_charges_cannot_exceed_advance(self):
        operation = self._operation(self._invoice(100.0), percent=50.0)
        operation.action_assign()
        with self.assertRaises(UserError):
            self._wizard(operation, 'disburse', interest_amount=60.0)

    def test_create_from_invoice_list(self):
        invoices = self._invoice(300.0) + self._invoice(700.0)
        action = invoices.action_l10n_pe_factoring_create()
        operation = self.env['l10n_pe.factoring'].browse(action['res_id'])
        self.assertEqual(operation.state, 'draft')
        self.assertEqual(sorted(operation.line_ids.mapped('nominal_amount')), [300.0, 700.0])
        self.assertTrue(operation.name.startswith('FAC/'))
        with self.assertRaises(ValidationError, msg='ya están en una operación'):
            invoices.action_l10n_pe_factoring_create()

    def test_foreign_currency(self):
        usd = self.env.ref('base.USD')
        usd.active = True
        self.env['res.currency.rate'].create({
            'name': self.today, 'currency_id': usd.id, 'company_id': self.company.id,
            'inverse_company_rate': 3.75})
        invoice = self._invoice(1000.0, currency=usd)
        operation = self._operation(invoice, currency=usd, percent=90.0)
        operation.action_assign()
        self._wizard(operation, 'disburse', interest_amount=10.0)
        bank = operation.move_ids.line_ids.filtered(
            lambda l: l.account_id == self.bank_journal.default_account_id)
        self.assertEqual(bank.amount_currency, 890.0)
        self.assertEqual(bank.currency_id, usd)
        self.assertAlmostEqual(bank.balance, 890.0 * 3.75, places=2)
        self._wizard(operation, 'settle')
        self.assertEqual(operation.state, 'done')
        self._assert_balanced(operation)

    def test_multicompany(self):
        other = self.env['res.company'].create({'name': 'Otra compañía factoring'})
        journal = self.env['account.journal'].create({
            'name': 'Varios', 'code': 'VOTR', 'type': 'general', 'company_id': other.id})
        foreign = self.env['l10n_pe.factoring'].with_company(other).create({
            'company_id': other.id, 'journal_id': journal.id, 'currency_id': other.currency_id.id})
        # Las reglas de registro no se aplican al superusuario de los tests.
        visible = self.env['l10n_pe.factoring'].with_user(self.env.ref('base.user_admin')).with_context(
            allowed_company_ids=[self.company.id]).search([('id', '=', foreign.id)])
        self.assertFalse(visible, 'una operación de otra compañía no se ve')
        with self.assertRaises(UserError, msg='la factura debe ser de la misma compañía'):
            self.env['l10n_pe.factoring.line'].with_company(other).create({
                'factoring_id': foreign.id, 'move_id': self._invoice().id})

    def test_form_proposes_invoice_amounts(self):
        invoice = self._invoice(450.0)
        form = Form(self.env['l10n_pe.factoring'])
        form.factor_id = self.factor
        form.default_advance_percent = 85.0
        with form.line_ids.new() as line:
            line.move_id = invoice
        operation = form.save()
        self.assertEqual(operation.line_ids.nominal_amount, 450.0)
        self.assertEqual(operation.line_ids.advance_percent, 85.0)
        self.assertEqual(operation.line_ids.due_date, invoice.invoice_date_due)
