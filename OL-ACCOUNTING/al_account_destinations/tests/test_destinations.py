# -*- coding: utf-8 -*-
"""Tests de la dinámica de cuentas destino (asiento de destino 6→9)."""
from odoo import Command
from odoo.exceptions import UserError, ValidationError
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
        # Diario de destinos de Ajustes ▸ Perú (ya no se busca ni crea el «GA»).
        cls.destination_journal = cls.env['account.journal'].create({
            'name': 'Asientos de destino (prueba)', 'code': 'DSTT', 'type': 'general',
            'company_id': cls.company.id})
        cls.company.l10n_pe_destination_journal_id = cls.destination_journal

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
        self.assertEqual(move.l10n_pe_destiny_move_id.journal_id, self.destination_journal)

    def test_destination_journal_is_required(self):
        """Sin diario de destinos en Ajustes no se genera nada por código:
        se pide configurarlo."""
        self._configure()
        self.company.l10n_pe_destination_journal_id = False
        with self.assertRaisesRegex(UserError, 'Ajustes'):
            self._post_entry(100.0)
        self.assertFalse(self.env['account.journal'].search(
            [('code', '=', 'GA'), ('company_id', '=', self.company.id),
             ('create_date', '>=', self.destination_journal.create_date)]))

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

    # ------------------------------------------------------------------
    # Refactor 08/10/2026: reparto por analítica, carga por compañía,
    # destinos por compañía y destinos del periodo
    # ------------------------------------------------------------------
    def _analytic(self, name, dest_account=None):
        plan = self.env['account.analytic.plan'].search(
            [('name', '=', 'Destino (prueba)')], limit=1) \
            or self.env['account.analytic.plan'].create({'name': 'Destino (prueba)'})
        return self.env['account.analytic.account'].create({
            'name': name, 'plan_id': plan.id,
            'l10n_pe_destination_account_id': dest_account.id if dest_account else False,
        })

    def _post_with_analytic(self, distribution, amount=1000.0):
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': self.journal.id,
            'line_ids': [
                Command.create({'account_id': self.exp.id, 'name': 'Gasto',
                                'debit': amount, 'credit': 0.0,
                                'analytic_distribution': distribution}),
                Command.create({'account_id': self.bank.id, 'name': 'Banco',
                                'debit': 0.0, 'credit': amount}),
            ],
        })
        move.action_post()
        return move

    def _amounts(self, dest):
        result = {}
        for line in dest.line_ids:
            result[line.account_id] = result.get(line.account_id, 0.0) + line.debit - line.credit
        return result

    def test_analytic_cost_centers_decide_the_destination(self):
        """Sin reparto por cuenta: 70 % Administración (94) y 30 % Ventas (95)
        por la analítica, contra la carga por defecto de la compañía."""
        self.exp.write({'l10n_pe_destiny_ids': [Command.clear()],
                        'l10n_pe_load_account_id': False})
        self.company.l10n_pe_destination_load_account_id = self.load
        admin = self._analytic('Administración', self.d1)
        sales = self._analytic('Ventas', self.d2)
        move = self._post_with_analytic({str(admin.id): 70.0, str(sales.id): 30.0})
        amounts = self._amounts(move.l10n_pe_destiny_move_id)
        self.assertAlmostEqual(amounts[self.d1], 700.0, places=2)
        self.assertAlmostEqual(amounts[self.d2], 300.0, places=2)
        self.assertAlmostEqual(amounts[self.load], -1000.0, places=2)
        admin_line = move.l10n_pe_destiny_move_id.line_ids.filtered(
            lambda l: l.account_id == self.d1)
        self.assertEqual(admin_line.analytic_distribution, {str(admin.id): 100.0})

    def test_analytic_rest_uses_account_split(self):
        """40 % con centro de costo; el 60 % restante, con el reparto de la
        cuenta (60/40)."""
        self._configure(0.6, 0.4)
        admin = self._analytic('Administración', self.d1)
        other = self._analytic('Proyecto sin destino')
        move = self._post_with_analytic({str(admin.id): 40.0, str(other.id): 60.0})
        amounts = self._amounts(move.l10n_pe_destiny_move_id)
        self.assertAlmostEqual(amounts[self.d1], 400.0 + 360.0, places=2)
        self.assertAlmostEqual(amounts[self.d2], 240.0, places=2)
        self.assertAlmostEqual(amounts[self.load], -1000.0, places=2)

    def test_partial_analytic_without_account_split_is_an_error(self):
        from odoo.exceptions import ValidationError
        self.exp.write({'l10n_pe_destiny_ids': [Command.clear()]})
        self.company.l10n_pe_destination_load_account_id = self.load
        admin = self._analytic('Administración', self.d1)
        other = self._analytic('Proyecto sin destino')
        with self.assertRaises(ValidationError):
            self._post_with_analytic({str(admin.id): 40.0, str(other.id): 60.0})

    def test_unconfigured_account_has_no_destination(self):
        """Una cuenta 6 sin reparto ni centro de costo no genera destino ni
        error (p. ej. la 60 o la 69, que no se destinan)."""
        self.exp.write({'l10n_pe_destiny_ids': [Command.clear()]})
        move = self._post_entry(500.0)
        self.assertEqual(move.state, 'posted')
        self.assertFalse(move.l10n_pe_destiny_move_id)

    def test_account_split_is_per_company(self):
        """El reparto de otra compañía sobre la misma cuenta no se usa."""
        self._configure(0.6, 0.4)
        other_company = self.env['res.company'].create({'name': 'Otra compañía destinos'})
        for account in (self.exp, self.d2):
            # v19: una cuenta compartida necesita su código en cada compañía.
            account.with_company(other_company).code = account.code
            account.company_ids |= other_company
        self.env['l10n_pe.account.destiny'].create({
            'company_id': other_company.id, 'parent_account_id': self.exp.id,
            'dest_account_id': self.d2.id, 'percentage': 1.0})
        self.assertEqual(len(self.exp.l10n_pe_destiny_ids), 2)
        move = self._post_entry(1000.0)
        amounts = self._amounts(move.l10n_pe_destiny_move_id)
        self.assertAlmostEqual(amounts[self.d1], 600.0, places=2)
        self.assertAlmostEqual(amounts[self.d2], 400.0, places=2)

    def test_company_journal_is_used(self):
        journal = self.env['account.journal'].create({
            'name': 'Destinos (prueba)', 'code': 'DSTP', 'type': 'general',
            'company_id': self.company.id})
        self.company.l10n_pe_destination_journal_id = journal
        self._configure()
        move = self._post_entry(100.0)
        self.assertEqual(move.l10n_pe_destiny_move_id.journal_id, journal)

    def test_period_wizard_balance_and_regenerate(self):
        """El cuadre 79 vs Elemento 9 sale de los destinos del periodo, y
        regenerar aplica la configuración nueva a lo ya contabilizado."""
        self._configure(0.6, 0.4)
        move = self._post_entry(1000.0)
        wizard = self.env['l10n_pe.destination.period.wizard'].create({
            'date_from': move.date, 'date_to': move.date})
        self.assertGreaterEqual(wizard.balance_79, 1000.0)
        self.assertGreaterEqual(wizard.balance_9, 1000.0)
        self.assertGreaterEqual(wizard.move_count, 1)
        self.exp.write({'l10n_pe_destiny_ids': [
            Command.clear(),
            Command.create({'dest_account_id': self.d2.id, 'percentage': 1.0})]})
        wizard.action_regenerate()
        amounts = self._amounts(move.l10n_pe_destiny_move_id)
        self.assertAlmostEqual(amounts.get(self.d2, 0.0), 1000.0, places=2)
        self.assertFalse(amounts.get(self.d1))

    # ------------------------------------------------------------------
    # Patrón multicompañía de Odoo 19 (como el código de la cuenta)
    # ------------------------------------------------------------------
    def test_branch_uses_root_configuration(self):
        """Una sucursal usa el sentido, el reparto y la carga de su raíz."""
        self._configure(0.6, 0.4)
        branch = self.env['res.company'].create({
            'name': 'Sucursal destinos', 'parent_id': self.company.id,
            'country_id': self.company.country_id.id})
        self.env.user.company_ids |= branch
        journal = self.env['account.journal'].create({
            'name': 'Varios sucursal', 'code': 'VSUC', 'type': 'general',
            'company_id': branch.id})
        move = self.env['account.move'].with_company(branch).create({
            'move_type': 'entry', 'journal_id': journal.id, 'company_id': branch.id,
            'line_ids': [
                Command.create({'account_id': self.exp.id, 'name': 'Gasto',
                                'debit': 100.0, 'credit': 0.0}),
                Command.create({'account_id': self.bank.id, 'name': 'Banco',
                                'debit': 0.0, 'credit': 100.0}),
            ],
        })
        move.action_post()
        amounts = self._amounts(move.l10n_pe_destiny_move_id)
        self.assertAlmostEqual(amounts[self.d1], 60.0, places=2)
        self.assertAlmostEqual(amounts[self.load], -100.0, places=2)
        # Leída desde la sucursal, la cuenta muestra la configuración de la raíz.
        exp_branch = self.exp.with_company(branch)
        self.assertEqual(exp_branch.l10n_pe_load_account_id, self.load)
        self.assertEqual(len(exp_branch.l10n_pe_destiny_ids), 2)

    def test_load_account_is_company_dependent(self):
        """La carga propia de la cuenta es de cada compañía raíz."""
        other_company = self.env['res.company'].create({'name': 'Otra raíz destinos'})
        self.exp.with_company(other_company).code = self.exp.code
        self.exp.company_ids |= other_company
        self.exp.l10n_pe_load_account_id = self.load
        self.assertEqual(self.exp.l10n_pe_load_account_id, self.load)
        self.assertFalse(self.exp.with_company(other_company).l10n_pe_load_account_id)

    def test_branch_cannot_change_root_fields(self):
        """Sentido y carga son campos delegados a la raíz (como el ejercicio
        fiscal en Odoo): la sucursal los recibe y no puede cambiarlos."""
        branch = self.env['res.company'].create({
            'name': 'Sucursal delegados', 'parent_id': self.company.id,
            'country_id': self.company.country_id.id})
        self.assertEqual(branch.l10n_pe_dest_type, self.company.l10n_pe_dest_type)
        self.assertEqual(branch.l10n_pe_destination_load_account_id,
                         self.company.l10n_pe_destination_load_account_id)
        other = '9a6' if self.company.l10n_pe_dest_type == '6a9' else '6a9'
        with self.assertRaises(ValidationError):
            branch.l10n_pe_dest_type = other
