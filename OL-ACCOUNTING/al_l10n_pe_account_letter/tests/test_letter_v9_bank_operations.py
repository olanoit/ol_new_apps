# -*- coding: utf-8 -*-
"""Versión 9: operaciones con el banco y configuración sin nombres.

- Liquidación del descuento: banco neto + 6734 + 6391 contra 4511.
- Cobro del banco: cobranza libre (banco contra 1233) y descuento (4511
  contra 1234).
- Protesto: la letra vuelve a cobrarse al cliente; en descuento, el banco
  carga su importe.
- Diarios de letras por campo y cuentas de redondeo de la compañía.
"""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_letter_bank_flow import TestLetterBankFlow


@tagged('post_install', '-at_install')
class TestLetterV9BankOperations(TestLetterBankFlow):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.company
        Account = cls.env['account.account'].with_company(company)
        company._l10n_pe_letter_set_default_accounts()
        for field, code, account_type in (
                ('l10n_pe_letter_loan_account_id', '451191', 'liability_current'),
                ('l10n_pe_letter_interest_account_id', '673491', 'expense'),
                ('l10n_pe_letter_fee_account_id', '639191', 'expense')):
            if not company[field]:
                company[field] = Account.create({'name': 'Letras %s' % code, 'code': code,
                                                 'account_type': account_type})
        cls.loan = company.l10n_pe_letter_loan_account_id
        cls.interest = company.l10n_pe_letter_interest_account_id
        cls.fee = company.l10n_pe_letter_fee_account_id
        cls.bank_journal = cls.env['account.journal'].create({
            'name': 'Banco letras test', 'code': 'BLTS', 'type': 'bank',
            'company_id': company.id})
        cls.letter_journal.l10n_pe_letter_type = 'receivable'

    def _sent(self, letter_type, letters=2, amount=1000.0):
        letter = self._redeemed_letter(letters=letters, amount=amount)
        self.env['l10n_pe.letter.canje.wizard'].create({
            'letter_id': letter.id, 'date_canje': date(2026, 8, 20), 'letter_type': letter_type,
            'canje_type': 'all', 'bank_id': self.bank.id, 'code': 'COD-%s' % letter.name,
        }).action_canje()
        self.assertEqual(set(letter.letter_line_ids.mapped('letter_type')), {letter_type})
        return letter

    def _apply(self, letter, operation, lines=None, when=date(2026, 9, 12), **values):
        wizard = self.env['l10n_pe.letter.bank.wizard'].with_context(
            **letter._action_bank_operation(operation)['context']).create(dict({
                'letter_line_ids': [(6, 0, (lines or letter.letter_line_ids).ids)],
                'date': when, 'bank_journal_id': self.bank_journal.id}, **values))
        wizard.action_apply()
        return wizard

    def _balance(self, move, account):
        return sum(move.line_ids.filtered(lambda l: l.account_id == account).mapped('balance'))

    # ------------------------------------------------------------------
    # Descuento
    # ------------------------------------------------------------------
    def test_liquidacion_del_descuento(self):
        letter = self._sent('discount')
        wizard = self._apply(letter, 'settle_discount', interest_amount=30.0, fee_amount=5.0,
                             when=date(2026, 8, 21))
        self.assertEqual(wizard.net_amount, 965.0)
        move = letter.bank_move_ids
        self.assertEqual(move.state, 'posted')
        self.assertEqual(self._balance(move, self.bank_journal.default_account_id), 965.0)
        self.assertEqual(self._balance(move, self.interest), 30.0)
        self.assertEqual(self._balance(move, self.fee), 5.0)
        self.assertEqual(self._balance(move, self.loan), -1000.0)
        self.assertEqual(set(letter.letter_line_ids.mapped('payment_state')), {'pending'},
                         'descontada no es cobrada: el cliente aún debe la letra')
        self.assertEqual(letter.letter_line_ids.discount_move_id, move)
        with self.assertRaises(UserError, msg='no se liquida dos veces'):
            self._apply(letter, 'settle_discount', interest_amount=1.0)

    def test_descuento_cobrado_cancela_el_prestamo(self):
        letter = self._sent('discount')
        with self.assertRaises(UserError, msg='sin liquidación no hay préstamo que cancelar'):
            self._apply(letter, 'collected')
        self._apply(letter, 'settle_discount', interest_amount=30.0, when=date(2026, 8, 21))
        self._apply(letter, 'collected')
        self.assertEqual(set(letter.letter_line_ids.mapped('payment_state')), {'paid'})
        loan_lines = letter.bank_move_ids.line_ids.filtered(lambda l: l.account_id == self.loan)
        self.assertAlmostEqual(sum(loan_lines.mapped('balance')), 0.0, places=2,
                               msg='el préstamo del banco queda saldado')
        self.assertEqual(letter.state, 'banked')

    def test_protesto_de_letra_descontada(self):
        letter = self._sent('discount')
        self._apply(letter, 'settle_discount', interest_amount=30.0, when=date(2026, 8, 21))
        first, second = letter.letter_line_ids
        self._apply(letter, 'protest', lines=first, fee_amount=12.0,
                    when=date(2026, 8, 25))
        self.assertEqual(first.letter_type, 'protested')
        self.assertEqual(first.protest_date, date(2026, 8, 25))
        self.assertEqual(first.payment_state, 'pending', 'el cliente sigue debiendo la letra')
        self.assertEqual(first.adeudado, 500.0)
        move = first.protest_move_id
        self.assertEqual(self._balance(move, self.loan), 500.0, 'el banco carga la letra')
        self.assertEqual(self._balance(move, self.bank_journal.default_account_id), -512.0)
        self.assertEqual(self._balance(move, self.fee), 12.0)
        protested = move.line_ids.filtered(
            lambda l: l.l10n_pe_letter_line_id == first and l.balance > 0)
        self.assertEqual(protested.account_id, first._l10n_pe_protested_account())
        self.assertFalse(protested.reconciled)
        self.assertEqual(second.letter_type, 'discount')
        # El cliente paga la letra protestada.
        payment = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': self.bank_journal.id, 'date': date(2026, 9, 1),
            'line_ids': [
                (0, 0, {'name': 'Pago', 'account_id': self.bank_journal.default_account_id.id,
                        'debit': 500.0}),
                (0, 0, {'name': 'Pago', 'account_id': protested.account_id.id,
                        'partner_id': self.partner.id, 'credit': 500.0}),
            ]})
        payment.action_post()
        (payment.line_ids.filtered(lambda l: l.account_id == protested.account_id) + protested).reconcile()
        self.assertEqual(first.payment_state, 'paid')

    # ------------------------------------------------------------------
    # Cobranza libre
    # ------------------------------------------------------------------
    def test_cobranza_libre_cobrada(self):
        letter = self._sent('billing')
        with self.assertRaises(UserError, msg='la liquidación es solo para descuento'):
            self._apply(letter, 'settle_discount', interest_amount=1.0)
        wizard = self._apply(letter, 'collected', fee_amount=7.0)
        self.assertEqual(wizard.net_amount, 993.0)
        self.assertEqual(set(letter.letter_line_ids.mapped('payment_state')), {'paid'})
        bank = self.bank_journal.default_account_id
        self.assertAlmostEqual(sum(letter.bank_move_ids.line_ids.filtered(
            lambda l: l.account_id == bank).mapped('balance')), 993.0, places=2)
        self.assertAlmostEqual(sum(letter.bank_move_ids.line_ids.filtered(
            lambda l: l.account_id == self.fee).mapped('balance')), 7.0, places=2)
        with self.assertRaises(UserError, msg='una letra cobrada no se cobra de nuevo'):
            self._apply(letter, 'collected')

    def test_protesto_fuera_de_plazo_avisa(self):
        letter = self._sent('billing', letters=1)
        line = letter.letter_line_ids
        self.assertEqual(line.expiration_date, date(2026, 9, 10))
        self._apply(letter, 'protest', when=date(2026, 10, 1))
        self.assertEqual(line.letter_type, 'protested')
        self.assertFalse(line.protest_move_id.line_ids.filtered(lambda l: l.account_id == self.loan),
                         'en cobranza libre el banco no adelantó nada')
        self.assertIn('Ley 27287', letter.message_ids[:1].body)

    def test_restablecer_con_operaciones_bloqueado(self):
        letter = self._sent('billing', letters=1)
        self._apply(letter, 'collected')
        with self.assertRaises(UserError):
            letter.action_draft()

    # ------------------------------------------------------------------
    # Configuración sin nombres
    # ------------------------------------------------------------------
    def test_diario_marcado(self):
        other = self.env['account.journal'].create({
            'name': 'Canjes clientes', 'code': 'CJTS', 'type': 'general',
            'company_id': self.company.id, 'l10n_pe_letter_type': 'receivable'})
        named = self.env['account.journal'].create({
            'name': 'Letras por cobrar sin marcar', 'code': 'LSMT', 'type': 'general',
            'company_id': self.company.id})
        letter = self.env['l10n_pe.letter'].new({'partner_id': self.partner.id, 'type': 'out_invoice'})
        self.assertIn(other, letter.domain_letter_ids._origin)
        self.assertNotIn(named, letter.domain_letter_ids._origin,
                         'con diarios marcados, el nombre ya no cuenta')

    def test_cuenta_de_redondeo_de_la_compania(self):
        account = self.env['account.account'].with_company(self.company).create({
            'name': 'Diferencias de canje', 'code': '659992', 'account_type': 'expense'})
        self.company.l10n_pe_letter_rounding_loss_account_id = account
        letter = self.env['l10n_pe.letter'].create({
            'partner_id': self.partner.id, 'type': 'out_invoice',
            'journal_id': self.letter_journal.id})
        residual = self.env['l10n_pe.letter.residual'].create({'letter_id': letter.id, 'amount': 0.02})
        self.assertEqual(residual.account_id, account)


# Los tests heredados ya corren en su propia clase.
for _name in dir(TestLetterBankFlow):
    if _name.startswith('test_') and _name not in TestLetterV9BankOperations.__dict__:
        setattr(TestLetterV9BankOperations, _name, None)
