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

    # ------------------------------------------------------------------
    # Borrado: sin cascada en la base de datos
    # ------------------------------------------------------------------
    def test_unlink_destiny_keeps_origin(self):
        """Eliminar el asiento de destino no borra el comprobante de origen."""
        self._configure()
        move = self._post_entry(1000.0)
        dest = move.l10n_pe_destiny_move_id
        dest.button_draft()
        dest.unlink()
        self.assertTrue(move.exists())
        self.assertEqual(move.state, 'posted')
        self.assertFalse(move.l10n_pe_destiny_move_id)

    def test_unlink_origin_removes_destiny(self):
        """Eliminar el origen (en borrador) elimina su destino por el ORM."""
        self._configure()
        move = self._post_entry(1000.0)
        dest = move.l10n_pe_destiny_move_id
        move.button_draft()
        self.assertEqual(dest.state, 'draft')
        move.unlink()
        self.assertFalse(dest.exists())

    # ------------------------------------------------------------------
    # Moneda, compañía y permisos
    # ------------------------------------------------------------------
    def test_foreign_currency_destiny_in_company_currency(self):
        """Con un comprobante en divisa, el destino se lleva en soles y su
        ``amount_currency`` coincide con el balance."""
        self._configure(0.6, 0.4)
        usd = self.env.ref('base.USD')
        usd.active = True
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': self.journal.id,
            'line_ids': [
                Command.create({'account_id': self.exp.id, 'name': 'Gasto',
                                'currency_id': usd.id, 'amount_currency': 100.0,
                                'debit': 375.0, 'credit': 0.0}),
                Command.create({'account_id': self.bank.id, 'name': 'Banco',
                                'currency_id': usd.id, 'amount_currency': -100.0,
                                'debit': 0.0, 'credit': 375.0}),
            ],
        })
        move.action_post()
        dest = move.l10n_pe_destiny_move_id
        self.assertTrue(dest)
        company_currency = self.company.currency_id
        for line in dest.line_ids:
            self.assertEqual(line.currency_id, company_currency)
            self.assertAlmostEqual(line.amount_currency, line.balance, places=2)
        d1 = sum(dest.line_ids.filtered(lambda l: l.account_id == self.d1).mapped('debit'))
        self.assertAlmostEqual(d1, 225.0, places=2)

    def test_destiny_uses_move_company_settings(self):
        """El sentido de la dinámica se toma de la compañía del comprobante,
        no de la compañía activa."""
        self._configure()
        other = self.env['res.company'].create({
            'name': 'Otra compañía destinos',
            'country_id': self.env.ref('base.pe').id,
            'l10n_pe_dest_type': '9a6',
        })
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': self.journal.id,
            'line_ids': [
                Command.create({'account_id': self.exp.id, 'name': 'Gasto',
                                'debit': 200.0, 'credit': 0.0}),
                Command.create({'account_id': self.bank.id, 'name': 'Banco',
                                'debit': 0.0, 'credit': 200.0}),
            ],
        })
        # Compañía activa = la otra (9a6); el comprobante es de la 6a9.
        move.with_context(
            allowed_company_ids=[other.id, self.company.id]).action_post()
        self.assertTrue(move.l10n_pe_destiny_move_id)

    def test_invoicing_user_can_post(self):
        """Un usuario solo de Facturación publica y se genera el destino:
        lee la configuración de destinos y, si el diario GA aún no existe,
        se crea sin exigirle permiso sobre diarios."""
        self._configure()
        user = self.env['res.users'].create({
            'name': 'Facturación destinos', 'login': 'fact_destinos',
            'company_id': self.company.id,
            'company_ids': [Command.set(self.company.ids)],
            'group_ids': [Command.set([self.env.ref('account.group_account_invoice').id])],
        })
        move = self.env['account.move'].with_user(user).create({
            'move_type': 'entry', 'journal_id': self.journal.id,
            'line_ids': [
                Command.create({'account_id': self.exp.id, 'name': 'Gasto',
                                'debit': 100.0, 'credit': 0.0}),
                Command.create({'account_id': self.bank.id, 'name': 'Banco',
                                'debit': 0.0, 'credit': 100.0}),
            ],
        })
        move.action_post()
        self.assertTrue(move.l10n_pe_destiny_move_id)
        self.assertEqual(move.l10n_pe_destiny_move_id.journal_id.code, 'GA')

    def test_destiny_lines_created_one_by_one(self):
        """Desde la lista de destinos se crean líneas de una en una sin que
        la primera choque con la suma del 100 %."""
        Destiny = self.env['l10n_pe.account.destiny']
        self.exp.l10n_pe_load_account_id = self.load
        Destiny.create({'parent_account_id': self.exp.id,
                        'dest_account_id': self.d1.id, 'percentage': 0.6})
        Destiny.create({'parent_account_id': self.exp.id,
                        'dest_account_id': self.d2.id, 'percentage': 0.4})
        move = self._post_entry(100.0)
        self.assertTrue(move.l10n_pe_destiny_move_id)

    # ------------------------------------------------------------------
    # Auditoría del 07/10/2026
    # ------------------------------------------------------------------
    def test_repost_keeps_destiny_number(self):
        """Restablecer y volver a publicar no consume otro número del diario GA."""
        self._configure()
        move = self._post_entry()
        dest = move.l10n_pe_destiny_move_id
        number = dest.name
        move.button_draft()
        move.action_post()
        self.assertEqual(move.l10n_pe_destiny_move_id, dest)
        self.assertEqual(dest.name, number)

    def test_destiny_lines_carry_the_analytic(self):
        self._configure()
        plan = self.env['account.analytic.plan'].create({'name': 'CC destinos test'})
        cc = self.env['account.analytic.account'].create({'name': 'CC Norte', 'plan_id': plan.id})
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': self.journal.id,
            'line_ids': [
                Command.create({'account_id': self.exp.id, 'name': 'Gasto', 'debit': 1000.0,
                                'analytic_distribution': {str(cc.id): 100.0}}),
                Command.create({'account_id': self.bank.id, 'name': 'Banco', 'credit': 1000.0}),
            ]})
        move.action_post()
        dest = move.l10n_pe_destiny_move_id
        nine = dest.line_ids.filtered(lambda l: l.account_id in (self.d1 | self.d2))
        self.assertEqual(set(map(lambda l: tuple(l.analytic_distribution), nine)), {(str(cc.id),)})
        self.assertFalse(dest.line_ids.filtered(lambda l: l.account_id == self.load).analytic_distribution)

    def test_destiny_cancelled_when_nothing_left(self):
        self._configure()
        move = self._post_entry()
        dest = move.l10n_pe_destiny_move_id
        move.button_draft()
        move.line_ids.filtered(lambda l: l.account_id == self.exp).account_id = self.d1
        move.action_post()
        self.assertFalse(move.l10n_pe_destiny_move_id)
        self.assertEqual(dest.state, 'cancel')
