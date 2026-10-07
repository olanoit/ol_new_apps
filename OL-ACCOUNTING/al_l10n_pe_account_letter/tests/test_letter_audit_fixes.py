# -*- coding: utf-8 -*-
"""Correcciones de la auditoría de la versión 7.

Cubre: el canje masivo ya no lee ni escribe las líneas de otro canje, la
refinanciación solo desde el canje (no desde el masivo), el borrador de un
canje refinanciado, los pagos de varios canjes a la vez, la cuenta y el
redondeo de la compañía del canje, el adeudado al cambiar el importe, la
cancelación de un canje contabilizado, el envío al banco de «todas» las
letras tras enviar alguna, y los permisos sobre la configuración de cuentas.
"""
from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged('post_install', '-at_install')
class TestLetterAuditFixes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.pen = cls.company.currency_id
        Account = cls.env['account.account'].with_company(cls.company)
        receivable = Account.search([('account_type', '=', 'asset_receivable')], limit=1)
        cls.income = Account.search([('account_type', '=', 'income')], limit=1)
        Config = cls.env['l10n_pe.letter.account.config']
        for letter_type in ('portfolio', 'billing', 'discount'):
            if not Config.search([('account_type', '=', 'asset_receivable'),
                                  ('letter_type', '=', letter_type),
                                  ('currency_id', '=', cls.pen.id),
                                  ('company_id', '=', cls.company.id)], limit=1):
                Config.create({'account_type': 'asset_receivable', 'letter_type': letter_type,
                               'currency_id': cls.pen.id, 'account_id': receivable.id,
                               'company_id': cls.company.id})
        cls.letter_journal = cls.env['account.journal'].create({
            'name': 'Letras por cobrar auditoría', 'code': 'LTAU', 'type': 'general',
            'company_id': cls.company.id, 'currency_id': cls.pen.id})
        cls.sale_journal = cls.env['account.journal'].create({
            'name': 'Ventas letras auditoría', 'code': 'VLAU', 'type': 'sale',
            'company_id': cls.company.id, 'l10n_latam_use_documents': False})
        cls.partner = cls.env['res.partner'].create({
            'name': 'CLIENTE LETRAS AUDITORIA SAC', 'vat': '20100070970'})
        cls.bank = cls.env['res.bank'].search([], limit=1) or \
            cls.env['res.bank'].create({'name': 'Banco test'})
        cls.doc_type = cls.env.ref('l10n_pe.document_type01')
        cls.Letter = cls.env['l10n_pe.letter']

    # ------------------------------------------------------------------
    # Ayudantes (mismo flujo que test_letter_bank_flow)
    # ------------------------------------------------------------------
    def _invoice(self, amount=3000.0):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner.id,
            'journal_id': self.sale_journal.id,
            'invoice_date': date(2026, 8, 5), 'date': date(2026, 8, 5),
            'invoice_line_ids': [(0, 0, {
                'name': 'Venta', 'quantity': 1, 'price_unit': amount,
                'account_id': self.income.id, 'tax_ids': [(6, 0, [])]})],
        })
        move.action_post()
        return move

    def _checked_letter(self, letters=2, amount=3000.0):
        invoice = self._invoice(amount)
        term_line = invoice.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        letter = self.Letter.create({
            'partner_id': self.partner.id, 'type': 'out_invoice',
            'journal_id': self.letter_journal.id,
            'invoice_line_ids': [(0, 0, {
                'document_type_id': self.doc_type.id,
                'move_line_id': term_line.id,
                'account_id': term_line.account_id.id,
                'imp_div': abs(term_line.amount_residual_currency),
            })],
        })
        letter.invoice_date = date(2026, 8, 10)
        letter.action_checked()
        letter.write({'number_letter': letters, 'letter_end_date': date(2026, 9, 10),
                      'range_date': 30})
        letter.create_letters()
        for index, line in enumerate(letter.letter_line_ids, start=1):
            line.nro_letter = 'LAU-%d-%03d' % (letter.id, index)
        return letter

    def _redeemed_letter(self, letters=2, amount=3000.0):
        letter = self._checked_letter(letters, amount)
        letter.action_redeemed()
        self.assertEqual(letter.state, 'redeemed')
        return letter

    def _send_to_bank(self, letter, when, line=None):
        self.env['l10n_pe.letter.canje.wizard'].create({
            'letter_id': letter.id,
            'date_canje': when,
            'letter_type': 'billing',
            'canje_type': 'one' if line else 'all',
            'letter_line_id': line.id if line else False,
            'bank_id': self.bank.id,
            'code': 'COD-%s' % (line.nro_letter if line else letter.name),
        }).action_canje()

    # ------------------------------------------------------------------
    # Métodos de borrado masivo eliminados
    # ------------------------------------------------------------------
    def test_mass_delete_methods_removed(self):
        """Ya no existen los métodos públicos que vaciaban las tablas."""
        self.assertFalse(hasattr(self.Letter, 'delete_all_invoices'))
        self.assertFalse(hasattr(self.Letter, 'delete_all_residual'))

    # ------------------------------------------------------------------
    # Canje masivo sin líneas ajenas
    # ------------------------------------------------------------------
    def test_massive_does_not_share_lines_with_letters(self):
        letter_a = self._redeemed_letter(amount=1000.0)
        letter_b = self._redeemed_letter(amount=500.0)
        massive = self.Letter.with_context(
            active_ids=(letter_a | letter_b).ids).action_multi_redeemed('billing')
        self.assertFalse(massive.letter_line_ids)
        self.assertFalse(massive.invoice_line_ids)
        self.assertFalse(massive.letter_residual_ids)
        self.assertEqual(massive.letter_move_ids,
                         letter_a.letter_line_ids | letter_b.letter_line_ids)
        # Aunque exista un canje normal con el mismo id, sus líneas no se ven
        same_id = self.Letter.browse(massive.id).exists()
        if same_id:
            self.assertFalse(massive.letter_line_ids & same_id.letter_line_ids)
        with self.assertRaises(UserError):
            massive.action_draft()
        with self.assertRaises(UserError):
            massive.create_letters()

    def test_refinance_wizard_rejects_massive_context(self):
        letter = self._redeemed_letter()
        wizard = self.env['l10n_pe.letter.refinance.wizard'].with_context(
            active_model='l10n_pe.letter.massive', active_id=letter.id,
        ).create({'letter_id': letter.id, 'refinance_date': date(2026, 8, 30)})
        with self.assertRaises(UserError):
            wizard.create_refinance()
        self.assertFalse(letter.refinance_id)

    # ------------------------------------------------------------------
    # Refinanciamiento
    # ------------------------------------------------------------------
    def test_refinanced_letter_can_return_to_draft(self):
        letter = self._redeemed_letter()
        child = self.Letter.create_refinance(letter, date(2026, 8, 30))
        self.assertTrue(letter.is_refinance_parent)
        letter.action_draft()
        self.assertEqual(letter.state, 'draft')
        self.assertFalse(letter.refinance_id)
        self.assertFalse(child.exists(), 'el refinanciamiento se elimina')

    def test_refinance_requires_redeemed_and_only_once(self):
        draft_letter = self._checked_letter()
        with self.assertRaises(UserError):
            self.Letter.create_refinance(draft_letter, date(2026, 8, 30))
        letter = self._redeemed_letter()
        self.Letter.create_refinance(letter, date(2026, 8, 30))
        with self.assertRaises(UserError):
            self.Letter.create_refinance(letter, date(2026, 8, 31))

    # ------------------------------------------------------------------
    # Pagos y adeudado
    # ------------------------------------------------------------------
    def test_payment_ids_recomputes_several_letters(self):
        letters = self._redeemed_letter(amount=1000.0) | self._redeemed_letter(amount=500.0)
        letters.compute_payment_ids()  # antes: «Expected singleton»
        self.assertFalse(letters.payment_ids)

    def test_adeudado_follows_imp_div(self):
        letter = self._checked_letter(letters=1)
        line = letter.letter_line_ids
        line.imp_div = 1234.0
        self.assertAlmostEqual(line.adeudado, 1234.0, places=2)

    def test_adeudado_reads_the_linked_move_line(self):
        letter = self._redeemed_letter(letters=2)
        for line in letter.letter_line_ids:
            move_line = letter.account_id.line_ids.filtered(
                lambda ml: ml.l10n_pe_letter_line_id == line)
            self.assertAlmostEqual(line.adeudado, abs(move_line.amount_residual_currency), places=2)
        self.assertFalse(letter.is_all_paid)

    # ------------------------------------------------------------------
    # Multicompañía: cuentas de letras y de redondeo
    # ------------------------------------------------------------------
    def test_letter_account_config_is_per_company(self):
        eur = self.env.ref('base.EUR')
        eur.active = True
        Config = self.env['l10n_pe.letter.account.config']
        Config.search([('currency_id', '=', eur.id)]).unlink()
        company_b = self.env['res.company'].create({'name': 'Compañía B letras'})
        Config.create({'account_type': 'asset_receivable', 'letter_type': 'portfolio',
                       'currency_id': eur.id, 'company_id': company_b.id})
        journal = self.env['account.journal'].create({
            'name': 'Letras EUR auditoría', 'code': 'LTEU', 'type': 'general',
            'company_id': self.company.id, 'currency_id': eur.id})
        letter = self.Letter.create({
            'partner_id': self.partner.id, 'type': 'out_invoice', 'journal_id': journal.id})
        with self.assertRaises(UserError, msg='no usa la configuración de otra compañía'):
            self.env['l10n_pe.letter.line'].create({
                'letter_id': letter.id, 'expiration_date': date(2026, 9, 10), 'imp_div': 10.0})

    def test_residual_account_is_from_letter_company(self):
        Account = self.env['account.account']
        self.company.write({'l10n_pe_letter_rounding_loss_account_id': False,
                            'l10n_pe_letter_rounding_gain_account_id': False})
        Account.with_company(self.company).search(
            [('name', '=', 'Redondeo')]).write({'name': 'Redondeo anterior'})
        company_b = self.env['res.company'].create({'name': 'Compañía B redondeo'})
        Account.with_company(company_b).create({
            'name': 'Redondeo', 'account_type': 'expense', 'code': '659993',
            'company_ids': [(6, 0, company_b.ids)]})
        letter = self.Letter.create({
            'partner_id': self.partner.id, 'type': 'out_invoice',
            'journal_id': self.letter_journal.id})
        residual = self.env['l10n_pe.letter.residual'].create({
            'letter_id': letter.id, 'amount': 5.0})
        self.assertFalse(residual.account_id,
                         'la cuenta «Redondeo» de otra compañía no se usa')

    # ------------------------------------------------------------------
    # Cancelación y envío al banco
    # ------------------------------------------------------------------
    def test_redeemed_letter_cannot_be_cancelled(self):
        letter = self._redeemed_letter()
        with self.assertRaises(UserError):
            letter.action_cancel()
        self.assertEqual(letter.state, 'redeemed')

    def test_send_all_after_one_skips_the_sent_letter(self):
        letter = self._redeemed_letter(letters=2)
        first, second = letter.letter_line_ids
        self._send_to_bank(letter, date(2026, 8, 20), line=first)
        self._send_to_bank(letter, date(2026, 8, 25))
        self.assertEqual(letter.canje_move_id.line_ids.l10n_pe_letter_line_id, second,
                         'el envío de «todas» solo lleva la letra que seguía en cartera')
        self.assertEqual(letter.state, 'banked')

    # ------------------------------------------------------------------
    # Permisos
    # ------------------------------------------------------------------
    def test_letter_user_cannot_edit_account_config(self):
        user = new_test_user(
            self.env, login='letras_auditoria',
            groups='base.group_user,al_l10n_pe_account_letter.app_group_user')
        config = self.env['l10n_pe.letter.account.config'].search(
            [('company_id', '=', self.company.id)], limit=1)
        config.with_user(user).read(['account_type'])
        with self.assertRaises(AccessError):
            config.with_user(user).write({'letter_type': 'protested'})

    def test_massive_and_config_have_company_rules(self):
        self.assertTrue(self.env.ref('al_l10n_pe_account_letter.account_letter_massive_rule_company'))
        self.assertTrue(self.env.ref('al_l10n_pe_account_letter.account_letter_account_config_rule_company'))

    # ------------------------------------------------------------------
    # Revisión del 07/10/2026
    # ------------------------------------------------------------------
    def test_draft_unreconciles_invoice(self):
        """Restablecer a borrador libera la factura: deja de figurar pagada y
        se puede volver a canjear."""
        letter = self._redeemed_letter()
        invoice = letter.invoice_line_ids.move_line_id.move_id
        self.assertEqual(invoice.payment_state, 'paid')
        letter.action_draft()
        self.assertNotEqual(invoice.payment_state, 'paid')
        self.assertFalse(letter.invoice_line_ids.move_line_id.reconciled)
        letter.action_cancel()
        self.assertEqual(letter.account_id.state, 'cancel')

    def test_same_invoice_cannot_be_redeemed_twice(self):
        """Dos canjes con la misma factura: el segundo no se contabiliza."""
        first = self._checked_letter()
        term_line = first.invoice_line_ids.move_line_id
        second = self.Letter.create({
            'partner_id': self.partner.id, 'type': 'out_invoice',
            'journal_id': self.letter_journal.id,
            'invoice_line_ids': [(0, 0, {
                'document_type_id': self.doc_type.id, 'move_line_id': term_line.id,
                'account_id': term_line.account_id.id, 'imp_div': 3000.0})],
        })
        second.invoice_date = date(2026, 8, 10)
        with self.assertRaises(UserError):
            second.action_checked()
        first.action_redeemed()
        with self.assertRaises(UserError):
            second._l10n_pe_check_invoice_balances()

    def test_partial_difference_is_not_rounding(self):
        """Letras por menos de lo que se canjea: no va a la cuenta de redondeo."""
        letter = self._checked_letter()
        letter.letter_line_ids[-1].imp_div -= 400.0
        with self.assertRaises(UserError):
            letter.action_redeemed()

    def test_redeem_twice_is_blocked(self):
        letter = self._redeemed_letter()
        with self.assertRaises(UserError):
            letter.action_redeemed()
