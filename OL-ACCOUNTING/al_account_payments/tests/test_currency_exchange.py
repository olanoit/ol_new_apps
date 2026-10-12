# -*- coding: utf-8 -*-
"""Compra y venta de moneda al tipo de cambio del banco y número de operación
obligatorio por diario."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestCurrencyExchange(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.usd = cls.env.ref('base.USD')
        cls.usd.active = True
        cls.day = date(2031, 3, 10)
        cls.env['res.currency.rate'].create({
            'currency_id': cls.usd.id, 'company_id': cls.company.id, 'name': cls.day,
            'inverse_company_rate': 3.75})
        Journal = cls.env['account.journal']
        cls.bank_pen = Journal.create({'name': 'Banco soles (test)', 'code': 'BPT', 'type': 'bank'})
        cls.bank_usd = Journal.create({'name': 'Banco dólares (test)', 'code': 'BUT', 'type': 'bank',
                                       'currency_id': cls.usd.id})

    def _wizard(self, **vals):
        return self.env['l10n_pe.currency.exchange.wizard'].create(dict({
            'journal_from_id': self.bank_pen.id, 'journal_to_id': self.bank_usd.id,
            'date': self.day, 'amount_from': 3800.0, 'bank_rate': 3.80}, **vals))

    def test_buy_dollars_at_bank_rate(self):
        wizard = self._wizard()
        self.assertAlmostEqual(wizard.amount_to, 1000.0)
        self.assertAlmostEqual(wizard.system_rate, 3.75)
        self.assertAlmostEqual(wizard.difference, -50.0, msg='pérdida frente al T.C. del sistema')
        action = wizard.action_confirm()
        payments = self.env['account.payment'].browse(action['domain'][0][2])
        self.assertEqual(sorted(payments.mapped('payment_type')), ['inbound', 'outbound'])
        transfer = self.company.transfer_account_id
        lines = self.env['account.move.line'].search([
            ('account_id', '=', transfer.id), ('date', '=', self.day),
            ('move_id', 'in', payments.move_id.ids)])
        self.assertTrue(all(lines.mapped('reconciled')))
        loss = self.env['account.move.line'].search([
            ('account_id', '=', self.company.expense_currency_exchange_account_id.id),
            ('date', '=', self.day), ('balance', '=', 50.0)])
        self.assertTrue(loss)

    def test_same_currency_refused(self):
        other_pen = self.env['account.journal'].create({'name': 'Caja (test)', 'code': 'CJT', 'type': 'cash'})
        with self.assertRaises(UserError):
            self._wizard(journal_to_id=other_pen.id).action_confirm()

    def test_operation_number_required(self):
        self.bank_pen.l10n_pe_require_operation_number = True
        partner = self.env['res.partner'].create({'name': 'Proveedor operación (test)'})
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': partner.id,
            'amount': 100.0, 'journal_id': self.bank_pen.id, 'date': self.day})
        with self.assertRaises(UserError):
            payment.action_post()
        payment.bank_operation_number = '00123456'
        payment.action_post()
        self.assertNotEqual(payment.state, 'draft')
