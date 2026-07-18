# -*- coding: utf-8 -*-
"""Tests de la dinámica de cuentas destino (asiento de destino 6→9)."""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDestinations(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.l10n_pe_dest_type = '6a9'
        Account = cls.env['account.account']

        def acc(code, name):
            rec = Account.search([('code', '=', code)], limit=1)
            return rec or Account.create(
                {'code': code, 'name': name, 'account_type': 'expense'})

        cls.exp = acc('631900', 'Gasto transporte (6)')
        cls.d1 = acc('941900', 'Gastos admin (9)')
        cls.d2 = acc('951900', 'Gastos ventas (9)')
        cls.load = acc('791900', 'Cargas imputables (79)')
        cls.bank = Account.search([('account_type', '=', 'asset_cash')], limit=1) \
            or acc('101900', 'Caja')
        cls.journal = cls.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', cls.company.id)], limit=1)

    def _configure(self, p1=0.6, p2=0.4):
        self.exp.write({
            'l10n_pe_load_account_id': self.load.id,
            'l10n_pe_destiny_ids': [
                Command.clear(),
                Command.create({'dest_account_id': self.d1.id, 'percentage': p1}),
                Command.create({'dest_account_id': self.d2.id, 'percentage': p2}),
            ],
        })

    def _post_entry(self, amount=1000.0):
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': self.journal.id,
            'line_ids': [
                Command.create({'account_id': self.exp.id, 'name': 'Gasto',
                                'debit': amount, 'credit': 0.0}),
                Command.create({'account_id': self.bank.id, 'name': 'Banco',
                                'debit': 0.0, 'credit': amount}),
            ],
        })
        move.action_post()
        return move

    def test_work_destinies_flag(self):
        self.assertTrue(self.exp.l10n_pe_work_destinies)   # 6 con compañía 6a9
        self.assertFalse(self.d1.l10n_pe_work_destinies)   # 9 no trabaja en 6a9

    def test_percentage_must_sum_100(self):
        with self.assertRaises(UserError):
            self.exp.write({
                'l10n_pe_load_account_id': self.load.id,
                'l10n_pe_destiny_ids': [
                    Command.create({'dest_account_id': self.d1.id, 'percentage': 0.5}),
                    Command.create({'dest_account_id': self.d2.id, 'percentage': 0.3}),
                ],
            })

    def test_destiny_entry_generated_and_balanced(self):
        self._configure(0.6, 0.4)
        move = self._post_entry(1000.0)
        dest = move.l10n_pe_destiny_move_id
        self.assertTrue(dest)
        self.assertTrue(dest.l10n_pe_is_destiny_entry)
        self.assertEqual(dest.state, 'posted')
        self.assertEqual(dest.l10n_pe_origin_move_id, move)
        d1 = sum(l.debit for l in dest.line_ids if l.account_id == self.d1)
        d2 = sum(l.debit for l in dest.line_ids if l.account_id == self.d2)
        cload = sum(l.credit for l in dest.line_ids if l.account_id == self.load)
        self.assertAlmostEqual(d1, 600.0, places=2)
        self.assertAlmostEqual(d2, 400.0, places=2)
        self.assertAlmostEqual(cload, 1000.0, places=2)
        self.assertAlmostEqual(sum(dest.line_ids.mapped('debit')),
                               sum(dest.line_ids.mapped('credit')), places=2)

    def test_rounding_remainder_on_last_line(self):
        self.exp.write({
            'l10n_pe_load_account_id': self.load.id,
            'l10n_pe_destiny_ids': [
                Command.clear(),
                Command.create({'dest_account_id': self.d1.id, 'percentage': 1 / 3}),
                Command.create({'dest_account_id': self.d2.id, 'percentage': 1 / 3}),
                Command.create({'dest_account_id': self.load.id, 'percentage': 1 / 3}),
            ],
        })
        move = self._post_entry(100.0)
        dest = move.l10n_pe_destiny_move_id
        self.assertAlmostEqual(sum(dest.line_ids.mapped('debit')),
                               sum(dest.line_ids.mapped('credit')), places=2)

    def test_no_destiny_skips(self):
        self._configure()
        self.exp.l10n_pe_no_destiny = True
        move = self._post_entry(500.0)
        self.assertFalse(move.l10n_pe_destiny_move_id)

    def test_no_recursion(self):
        self._configure()
        move = self._post_entry(1000.0)
        dest = move.l10n_pe_destiny_move_id
        self.assertFalse(dest.l10n_pe_destiny_move_id)
