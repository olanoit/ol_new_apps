# -*- coding: utf-8 -*-
"""Flujo completo del canje hasta el banco.

Cubre los defectos corregidos en la versión 6: el estado «Bancarizado»
nunca se alcanzaba, el asiento del envío al banco tomaba la fecha del canje,
la refinanciación masiva mostraba 0 como importe pendiente y el botón
«Canjes» aparecía en todos los asientos.
"""
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestLetterBankFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        pen = cls.company.currency_id
        Account = cls.env['account.account'].with_company(cls.company)
        receivable = Account.search([('account_type', '=', 'asset_receivable')], limit=1)
        cls.income = Account.search([('account_type', '=', 'income')], limit=1)
        Config = cls.env['l10n_pe.letter.account.config']
        for letter_type in ('portfolio', 'billing', 'discount'):
            if not Config.search([('account_type', '=', 'asset_receivable'),
                                  ('letter_type', '=', letter_type),
                                  ('currency_id', '=', pen.id),
                                  ('company_id', '=', cls.company.id)], limit=1):
                Config.create({'account_type': 'asset_receivable', 'letter_type': letter_type,
                               'currency_id': pen.id, 'account_id': receivable.id,
                               'company_id': cls.company.id})
        for account_type, code in (('expense', '659991'), ('income_other', '759991')):
            if not Account.search([('name', '=', 'Redondeo'), ('account_type', '=', account_type)],
                                  limit=1):
                Account.create({'name': 'Redondeo', 'account_type': account_type, 'code': code})
        cls.letter_journal = cls.env['account.journal'].create({
            'name': 'Letras por cobrar test', 'code': 'LTTS', 'type': 'general',
            'company_id': cls.company.id, 'currency_id': pen.id})
        cls.sale_journal = cls.env['account.journal'].create({
            'name': 'Ventas letras test', 'code': 'VLTS', 'type': 'sale',
            'company_id': cls.company.id, 'l10n_latam_use_documents': False})
        cls.partner = cls.env['res.partner'].create({
            'name': 'CLIENTE LETRAS TEST SAC', 'vat': '20100070970'})
        cls.bank = cls.env['res.bank'].search([], limit=1) or \
            cls.env['res.bank'].create({'name': 'Banco test'})
        cls.doc_type = cls.env.ref('l10n_pe.document_type01')

    # ------------------------------------------------------------------
    # Ayudantes
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

    def _redeemed_letter(self, letters=2, amount=3000.0):
        """Canje en estado «Canjeado» con ``letters`` letras numeradas."""
        invoice = self._invoice(amount)
        term_line = invoice.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        letter = self.env['l10n_pe.letter'].create({
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
        letter.action_create_letters()
        for index, line in enumerate(letter.letter_line_ids, start=1):
            line.nro_letter = 'LTS-%d-%03d' % (letter.id, index)
        letter.action_redeemed()
        self.assertEqual(letter.state, 'redeemed')
        return letter

    def _send_to_bank(self, letter, when, line=None):
        wizard = self.env['l10n_pe.letter.canje.wizard'].create({
            'letter_id': letter.id,
            'date_canje': when,
            'letter_type': 'billing',
            'canje_type': 'one' if line else 'all',
            'letter_line_id': line.id if line else False,
            'bank_id': self.bank.id,
            'code': 'COD-%s' % (line.nro_letter if line else letter.name),
        })
        wizard.action_canje()
        return wizard

    # ------------------------------------------------------------------
    # Estado «Bancarizado» y fecha del envío
    # ------------------------------------------------------------------
    def test_sending_all_letters_marks_banked(self):
        letter = self._redeemed_letter()
        self._send_to_bank(letter, date(2026, 8, 20))
        self.assertEqual(letter.state, 'banked')

    def test_bank_entry_uses_the_wizard_date(self):
        letter = self._redeemed_letter()
        self._send_to_bank(letter, date(2026, 8, 20))
        self.assertEqual(letter.canje_move_id.date, date(2026, 8, 20),
                         'el asiento del banco lleva la fecha del envío, no la del canje')

    def test_banked_only_when_the_last_letter_is_sent(self):
        letter = self._redeemed_letter(letters=2)
        first, second = letter.letter_line_ids
        self._send_to_bank(letter, date(2026, 8, 20), line=first)
        self.assertEqual(letter.state, 'redeemed',
                         'con una letra aún en cartera el canje sigue «Canjeado»')
        self.assertEqual(letter.canje_move_ids.date, date(2026, 8, 20))
        self._send_to_bank(letter, date(2026, 8, 25), line=second)
        self.assertEqual(letter.state, 'banked')

    def test_removing_bank_data_returns_to_redeemed(self):
        letter = self._redeemed_letter()
        self._send_to_bank(letter, date(2026, 8, 20))
        letter.letter_line_ids[:1].code = False
        self.assertEqual(letter.state, 'redeemed')

    # ------------------------------------------------------------------
    # Refinanciación masiva y botones del asiento
    # ------------------------------------------------------------------
    def test_massive_refinance_shows_the_owed_amount(self):
        letter_a = self._redeemed_letter(amount=1000.0)
        letter_b = self._redeemed_letter(amount=500.0)
        letters = letter_a | letter_b
        self.assertAlmostEqual(letter_a.rest_amount_currency, 0.0, places=2,
                               msg='con todas las letras creadas no queda nada por convertir')
        wizard = self.env['l10n_pe.letter.refinance.massive.wizard'].with_context(
            active_ids=letters.ids).create({'refinance_date': date(2026, 8, 30)})
        self.assertAlmostEqual(wizard.total_amount, 1500.0, places=2)
        self.assertAlmostEqual(letter_a.refinance_pending_amount, 1000.0, places=2)

    def test_letters_button_only_on_moves_with_letters(self):
        move = self._invoice()
        self.assertEqual(move.l10n_pe_letter_count, 0)
        arch = self.env['account.move'].get_view(
            self.env.ref('account.view_move_form').id, 'form')['arch']
        self.assertIn('invisible="not l10n_pe_letter_ids"', arch)

    # ------------------------------------------------------------------
    # Menú Perú ▸ Letras de cambio
    # ------------------------------------------------------------------
    def _action_records(self, xmlid):
        from odoo.tools.safe_eval import safe_eval
        action = self.env.ref(xmlid)
        return self.env[action.res_model].search(safe_eval(action.domain or '[]'))

    def test_letter_menu_lists(self):
        """Cada lista del menú muestra lo suyo: letras por cobrar (no por
        pagar), letras enviadas al banco y el análisis."""
        letter = self._redeemed_letter(letters=2, amount=1000.0)
        lines = letter.letter_line_ids
        module = 'al_l10n_pe_account_letter.'
        self.assertTrue(lines <= self._action_records(module + 'account_move_letter_action_clientes'))
        self.assertFalse(lines & self._action_records(module + 'account_move_letter_action_proveedores'))
        self.assertFalse(lines & self._action_records(module + 'action_letter_line_bank_clientes'))
        self._send_to_bank(letter, date(2026, 8, 20))
        self.assertTrue(lines <= self._action_records(module + 'action_letter_line_bank_clientes'))
        self.assertTrue(lines <= self._action_records(module + 'action_letter_line_analysis'))
        letter.is_refinance_children = True
        self.assertIn(letter, self._action_records(module + 'action_letter_refinance_clientes'))
        self.assertNotIn(letter, self._action_records(module + 'action_letter_refinance_proveedores'))

    def test_letter_analysis_groups(self):
        """El análisis agrupa por contacto, moneda, tipo y estado de la letra
        (campos relacionados guardados)."""
        letter = self._redeemed_letter(letters=2, amount=1000.0)
        groups = self.env['l10n_pe.letter.line']._read_group(
            [('id', 'in', letter.letter_line_ids.ids)],
            ['partner_id', 'currency_id', 'move_invoice_type', 'state'], ['imp_div:sum'])
        self.assertEqual(len(groups), 1)
        partner, currency, move_type, state, total = groups[0]
        self.assertEqual((partner, move_type, state), (self.partner, 'out_invoice', 'redeemed'))
        self.assertAlmostEqual(total, 1000.0)
