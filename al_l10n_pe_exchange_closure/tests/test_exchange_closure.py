# -*- coding: utf-8 -*-
"""Pruebas del cierre mensual de tipo de cambio.

Escenario base: cuentas en dólares con saldos registrados al T.C. de la
operación, que se revalúan al T.C. de la fecha de balance.
"""
from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestExchangeClosure(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Compañía propia: el cierre valida unicidad de período y orden
        # cronológico contra los cierres existentes, así que las pruebas no
        # pueden compartir compañía con los datos reales de la base.
        cls.pen = cls.env.ref('base.PEN')
        cls.usd = cls.env.ref('base.USD')
        cls.usd.active = True
        cls.company = cls.env['res.company'].create({
            'name': 'Cierre TC Test S.A.C.',
            'currency_id': cls.pen.id,
        })
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))

        Account = cls.env['account.account'].with_company(cls.company)
        cls.acc_bank = Account.create({
            'name': 'Bancos ME (test)', 'code': 'TCB104',
            'account_type': 'asset_current', 'currency_id': cls.usd.id,
            'l10n_pe_exchange_closing': 'summary',
        })
        cls.acc_receivable = Account.create({
            'name': 'Facturas por cobrar ME (test)', 'code': 'TCB121',
            'account_type': 'asset_receivable', 'reconcile': True,
            'currency_id': cls.usd.id,
            'l10n_pe_exchange_closing': 'detail',
        })
        cls.acc_payable = Account.create({
            'name': 'Facturas por pagar ME (test)', 'code': 'TCB421',
            'account_type': 'liability_payable', 'reconcile': True,
            'currency_id': cls.usd.id,
            'l10n_pe_exchange_closing': 'detail',
        })
        cls.acc_loan = Account.create({
            'name': 'Préstamos ME (test)', 'code': 'TCB451',
            'account_type': 'liability_non_current', 'currency_id': cls.usd.id,
            'l10n_pe_exchange_closing': 'summary',
        })
        # Contrapartida neutra: no entra al cierre.
        cls.acc_other = Account.create({
            'name': 'Contrapartida (test)', 'code': 'TCB999',
            'account_type': 'equity', 'currency_id': cls.usd.id,
        })
        cls.acc_gain = Account.create({
            'name': 'Ganancia por dif. de cambio (test)', 'code': 'TCB776',
            'account_type': 'income_other',
        })
        cls.acc_loss = Account.create({
            'name': 'Pérdida por dif. de cambio (test)', 'code': 'TCB676',
            'account_type': 'expense',
        })
        cls.company.income_currency_exchange_account_id = cls.acc_gain
        cls.company.expense_currency_exchange_account_id = cls.acc_loss

        cls.journal = cls.env['account.journal'].create({
            'name': 'Cierre T.C. (test)', 'code': 'TCTC', 'type': 'general',
            'company_id': cls.company.id,
        })
        cls.company.l10n_pe_exchange_closing_journal_id = cls.journal

        cls.partner_a = cls.env['res.partner'].create({'name': 'Cliente A TC'})
        cls.partner_b = cls.env['res.partner'].create({'name': 'Cliente B TC'})

        # Analítica: un plan con dos centros de costo.
        cls.acc_income = Account.create({
            'name': 'Ventas ME (test)', 'code': 'TCB701',
            'account_type': 'income',
        })
        cls.plan = cls.env['account.analytic.plan'].create(
            {'name': 'Centros de costo TC'})
        cls.cc_north = cls.env['account.analytic.account'].create({
            'name': 'Norte TC', 'plan_id': cls.plan.id,
            'company_id': cls.company.id})
        cls.cc_south = cls.env['account.analytic.account'].create({
            'name': 'Sur TC', 'plan_id': cls.plan.id,
            'company_id': cls.company.id})
        cls.dist_north = {str(cls.cc_north.id): 100.0}
        cls.dist_south = {str(cls.cc_south.id): 100.0}

    # ------------------------------------------------------------------ #
    # Utilidades                                                          #
    # ------------------------------------------------------------------ #
    def _entry(self, move_date, lines):
        """Crea y publica un asiento en dólares.

        `lines` es una lista de (cuenta, importe_usd, importe_pen, socio) con
        una distribución analítica opcional como quinto elemento: importes
        positivos al debe, negativos al haber.
        """
        move = self.env['account.move'].with_company(self.company).create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'date': move_date,
            'line_ids': [(0, 0, {
                'account_id': line[0].id,
                'partner_id': line[3].id if line[3] else False,
                'currency_id': self.usd.id,
                'amount_currency': line[1],
                'balance': line[2],
                'analytic_distribution': line[4] if len(line) > 4 else False,
            }) for line in lines],
        })
        move.action_post()
        return move

    def _closure(self, month, year, purchase, sale, **kwargs):
        vals = {
            'company_id': self.company.id,
            'currency_id': self.usd.id,
            'month': month,
            'year': year,
            'rate_purchase': purchase,
            'rate_sale': sale,
            'journal_id': self.journal.id,
        }
        vals.update(kwargs)
        return self.env['l10n_pe.exchange.closure'].with_company(
            self.company).create(vals)

    def _line_of(self, closure, account, partner=None):
        lines = closure.line_ids.filtered(
            lambda l: l.account_id == account
            and (not partner or l.partner_id == partner))
        self.assertEqual(len(lines), 1,
                         'Se esperaba un único renglón para %s' % account.code)
        return lines

    # ------------------------------------------------------------------ #
    # Fechas y tipo de cambio                                             #
    # ------------------------------------------------------------------ #
    def test_dates_last_and_previous_day(self):
        closure = self._closure('02', 2024, 3.70, 3.72)
        self.assertEqual(closure.date, date(2024, 2, 29), 'año bisiesto')
        self.assertEqual(closure.rate_date, date(2024, 2, 29))
        self.assertEqual(closure.name, 'Febrero 2024')
        closure.rate_day = 'previous'
        self.assertEqual(closure.rate_date, date(2024, 2, 28))
        self.assertEqual(closure.date, date(2024, 2, 29),
                         'la fecha del asiento sigue siendo el fin de mes')

    def test_fetch_rate_from_registry(self):
        self.env['res.currency.rate'].create({
            'currency_id': self.usd.id,
            'company_id': self.company.id,
            'name': '2024-03-31',
            'rate': 1 / 3.760,
            'rate_purchase': 3.738,
            'rate_sale': 3.760,
        })
        closure = self._closure('03', 2024, 0.0, 0.0)
        closure.action_fetch_rate()
        self.assertAlmostEqual(closure.rate_purchase, 3.738, places=3)
        self.assertAlmostEqual(closure.rate_sale, 3.760, places=3)

    # ------------------------------------------------------------------ #
    # Cálculo del ajuste                                                  #
    # ------------------------------------------------------------------ #
    def test_asset_summary_gain(self):
        """Activo revaluado al alza: cargo a la cuenta y ganancia."""
        self._entry('2024-01-15', [
            (self.acc_bank, 1000.0, 3700.0, None),
            (self.acc_other, -1000.0, -3700.0, None),
        ])
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()

        line = self._line_of(closure, self.acc_bank)
        self.assertEqual(line.rate_type, 'purchase', 'activo → T.C. compra')
        self.assertAlmostEqual(line.amount_currency, 1000.0)
        self.assertAlmostEqual(line.balance, 3700.0)
        self.assertAlmostEqual(line.balance_adjusted, 3800.0)
        self.assertAlmostEqual(line.adjustment, 100.0)
        self.assertAlmostEqual(closure.amount_gain, 100.0)
        self.assertAlmostEqual(closure.amount_loss, 0.0)

        closure.action_post()
        self.assertEqual(closure.state, 'posted')
        move_lines = closure.move_id.line_ids
        self.assertEqual(len(move_lines), 2)
        bank_line = move_lines.filtered(lambda l: l.account_id == self.acc_bank)
        self.assertAlmostEqual(bank_line.debit, 100.0)
        self.assertAlmostEqual(bank_line.amount_currency, 0.0,
                               msg='el ajuste no mueve moneda extranjera')
        self.assertAlmostEqual(bank_line.l10n_pe_closing_rate, 3.80, places=3)
        gain_line = move_lines.filtered(lambda l: l.account_id == self.acc_gain)
        self.assertAlmostEqual(gain_line.credit, 100.0)
        self.assertEqual(closure.move_id.state, 'posted')
        self.assertEqual(closure.move_id.l10n_pe_exchange_closure_id, closure)

    def test_liability_summary_loss(self):
        """Pasivo revaluado al alza: abono a la cuenta y pérdida."""
        self._entry('2024-01-20', [
            (self.acc_other, 2000.0, 7400.0, None),
            (self.acc_loan, -2000.0, -7400.0, None),
        ])
        closure = self._closure('01', 2024, purchase=3.78, sale=3.80)
        closure.action_compute()

        line = self._line_of(closure, self.acc_loan)
        self.assertEqual(line.rate_type, 'sale', 'pasivo → T.C. venta')
        self.assertAlmostEqual(line.balance, -7400.0)
        self.assertAlmostEqual(line.balance_adjusted, -7600.0)
        self.assertAlmostEqual(line.adjustment, -200.0)
        self.assertAlmostEqual(closure.amount_loss, 200.0)
        self.assertAlmostEqual(closure.amount_gain, 0.0)

        closure.action_post()
        move_lines = closure.move_id.line_ids
        loan_line = move_lines.filtered(lambda l: l.account_id == self.acc_loan)
        self.assertAlmostEqual(loan_line.credit, 200.0)
        loss_line = move_lines.filtered(lambda l: l.account_id == self.acc_loss)
        self.assertAlmostEqual(loss_line.debit, 200.0)

    def test_gain_and_loss_are_not_netted(self):
        """Ganancias y pérdidas van a cuentas de resultado distintas."""
        self._entry('2024-01-10', [
            (self.acc_bank, 1000.0, 3700.0, None),
            (self.acc_loan, -1000.0, -3700.0, None),
        ])
        # Compra sube (ganancia en el activo) y venta sube (pérdida en el pasivo).
        closure = self._closure('01', 2024, purchase=3.75, sale=3.75)
        closure.action_compute()
        self.assertAlmostEqual(closure.amount_gain, 50.0)
        self.assertAlmostEqual(closure.amount_loss, 50.0)
        self.assertAlmostEqual(closure.amount_net, 0.0)

        closure.action_post()
        accounts = closure.move_id.line_ids.mapped('account_id')
        self.assertIn(self.acc_gain, accounts)
        self.assertIn(self.acc_loss, accounts,
                      'no se debe netear la pérdida contra la ganancia')

    def test_detail_by_partner(self):
        """Las cuentas con detalle abren un renglón por socio."""
        self._entry('2024-01-05', [
            (self.acc_receivable, 1000.0, 3700.0, self.partner_a),
            (self.acc_other, -1000.0, -3700.0, None),
        ])
        self._entry('2024-01-06', [
            (self.acc_receivable, 500.0, 1855.0, self.partner_b),
            (self.acc_other, -500.0, -1855.0, None),
        ])
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()

        self.assertEqual(len(closure.line_ids), 2)
        line_a = self._line_of(closure, self.acc_receivable, self.partner_a)
        self.assertAlmostEqual(line_a.adjustment, 100.0)  # 3800 - 3700
        line_b = self._line_of(closure, self.acc_receivable, self.partner_b)
        self.assertAlmostEqual(line_b.adjustment, 45.0)   # 1900 - 1855

        closure.action_post()
        partners = closure.move_id.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable).mapped('partner_id')
        self.assertEqual(partners, self.partner_a | self.partner_b)

    def test_rate_type_override(self):
        """El forzado de T.C. gana sobre la naturaleza de la cuenta."""
        self.acc_bank.l10n_pe_exchange_rate_type = 'sale'
        self._entry('2024-01-15', [
            (self.acc_bank, 1000.0, 3700.0, None),
            (self.acc_other, -1000.0, -3700.0, None),
        ])
        closure = self._closure('01', 2024, purchase=3.80, sale=3.90)
        closure.action_compute()
        line = self._line_of(closure, self.acc_bank)
        self.assertEqual(line.rate_type, 'sale')
        self.assertAlmostEqual(line.adjustment, 200.0)

    def test_settled_balance_is_skipped(self):
        """Una partida ya saldada no genera renglón."""
        self._entry('2024-01-05', [
            (self.acc_receivable, 1000.0, 3700.0, self.partner_a),
            (self.acc_other, -1000.0, -3700.0, None),
        ])
        self._entry('2024-01-25', [
            (self.acc_other, 1000.0, 3700.0, None),
            (self.acc_receivable, -1000.0, -3700.0, self.partner_a),
        ])
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()
        self.assertFalse(closure.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable))

    def test_unmarked_account_is_ignored(self):
        self._entry('2024-01-15', [
            (self.acc_bank, 1000.0, 3700.0, None),
            (self.acc_other, -1000.0, -3700.0, None),
        ])
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()
        self.assertNotIn(self.acc_other, closure.line_ids.mapped('account_id'))

    def test_draft_entries_are_ignored(self):
        move = self.env['account.move'].with_company(self.company).create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'date': '2024-01-15',
            'line_ids': [
                (0, 0, {'account_id': self.acc_bank.id,
                        'currency_id': self.usd.id,
                        'amount_currency': 1000.0, 'balance': 3700.0}),
                (0, 0, {'account_id': self.acc_other.id,
                        'currency_id': self.usd.id,
                        'amount_currency': -1000.0, 'balance': -3700.0}),
            ],
        })
        self.assertEqual(move.state, 'draft')
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()
        self.assertFalse(closure.line_ids)

    # ------------------------------------------------------------------ #
    # Acumulado entre meses: el punto crítico del proceso                 #
    # ------------------------------------------------------------------ #
    def test_second_month_only_books_the_delta(self):
        """El cierre de febrero no vuelve a ajustar lo ya ajustado en enero."""
        self._entry('2024-01-15', [
            (self.acc_bank, 1000.0, 3700.0, None),
            (self.acc_other, -1000.0, -3700.0, None),
        ])
        january = self._closure('01', 2024, purchase=3.80, sale=3.82)
        january.action_compute()
        january.action_post()
        self.assertAlmostEqual(january.amount_gain, 100.0)

        # Febrero sin movimientos nuevos y con el T.C. más alto: solo el delta.
        february = self._closure('02', 2024, purchase=3.90, sale=3.92)
        february.action_compute()
        line = self._line_of(february, self.acc_bank)
        self.assertAlmostEqual(line.balance, 3800.0,
                               msg='el saldo contable ya incluye el ajuste '
                                   'de enero')
        self.assertAlmostEqual(line.balance_adjusted, 3900.0)
        self.assertAlmostEqual(line.adjustment, 100.0,
                               msg='debe ajustar solo la variación de enero '
                                   'a febrero, no 200')

    def test_second_month_without_variation_has_nothing_to_post(self):
        self._entry('2024-01-15', [
            (self.acc_bank, 1000.0, 3700.0, None),
            (self.acc_other, -1000.0, -3700.0, None),
        ])
        january = self._closure('01', 2024, purchase=3.80, sale=3.82)
        january.action_compute()
        january.action_post()

        february = self._closure('02', 2024, purchase=3.80, sale=3.82)
        february.action_compute()
        line = self._line_of(february, self.acc_bank)
        self.assertAlmostEqual(line.adjustment, 0.0)
        with self.assertRaises(UserError):
            february.action_post()

    def test_recompute_after_cancel_excludes_own_move(self):
        """Recalcular tras cancelar no arrastra el ajuste propio."""
        self._entry('2024-01-15', [
            (self.acc_bank, 1000.0, 3700.0, None),
            (self.acc_other, -1000.0, -3700.0, None),
        ])
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()
        closure.action_post()
        closure.action_cancel()
        self.assertEqual(closure.move_id.state, 'cancel')

        closure.action_draft()
        self.assertFalse(closure.move_id)
        closure.rate_purchase = 3.90
        closure.action_compute()
        line = self._line_of(closure, self.acc_bank)
        self.assertAlmostEqual(line.balance, 3700.0)
        self.assertAlmostEqual(line.adjustment, 200.0)

    def test_realized_difference_is_absorbed(self):
        """La diferencia de cambio realizada por Odoo ya está en el saldo."""
        self._entry('2024-01-05', [
            (self.acc_receivable, 1000.0, 3700.0, self.partner_a),
            (self.acc_other, -1000.0, -3700.0, None),
        ])
        # Cobro al T.C. 3.75: la conciliación de Odoo llevaría los 50 de
        # diferencia realizada a la cuenta por cobrar (amount_currency = 0).
        self._entry('2024-01-28', [
            (self.acc_other, 1000.0, 3750.0, None),
            (self.acc_receivable, -1000.0, -3750.0, self.partner_a),
        ])
        self._entry('2024-01-28', [
            (self.acc_receivable, 0.0, 50.0, self.partner_a),
            (self.acc_gain, 0.0, -50.0, None),
        ])
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()
        self.assertFalse(
            closure.line_ids.filtered(
                lambda l: l.account_id == self.acc_receivable),
            'saldada en ambas monedas: no hay nada que revaluar')

    # ------------------------------------------------------------------ #
    # Distribución analítica                                              #
    # ------------------------------------------------------------------ #
    def _invoice_like(self, move_date, partner, usd, pen, distribution):
        """Factura simplificada: la analítica va en la línea de ingreso."""
        return self._entry(move_date, [
            (self.acc_receivable, usd, pen, partner),
            (self.acc_income, -usd, -pen, None, distribution),
        ])

    def test_analytic_inherited_from_the_income_line(self):
        """La cuenta por cobrar no lleva analítica: se hereda del documento."""
        self._invoice_like('2024-01-15', self.partner_a, 1000.0, 3700.0,
                           self.dist_north)
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()

        line = self._line_of(closure, self.acc_receivable, self.partner_a)
        self.assertEqual(line.analytic_distribution, self.dist_north)

        closure.action_post()
        move_lines = closure.move_id.line_ids
        recv_line = move_lines.filtered(
            lambda l: l.account_id == self.acc_receivable)
        gain_line = move_lines.filtered(
            lambda l: l.account_id == self.acc_gain)
        self.assertFalse(
            recv_line.analytic_distribution,
            'la línea de balance no debe llevar analítica: su apunte '
            'analítico anularía el de la contrapartida')
        self.assertEqual(gain_line.analytic_distribution, self.dist_north)

    def test_analytic_items_are_not_cancelled_out(self):
        """El asiento produce apuntes analíticos por el importe del ajuste."""
        self._invoice_like('2024-01-15', self.partner_a, 1000.0, 3700.0,
                           self.dist_north)
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()
        closure.action_post()

        analytic_lines = self.env['account.analytic.line'].search([
            ('move_line_id', 'in', closure.move_id.line_ids.ids)])
        self.assertTrue(analytic_lines, 'debe generar analítica')
        # Cada plan analítico tiene su propia columna en el apunte analítico.
        self.assertEqual(analytic_lines[self.plan._column_name()],
                         self.cc_north)
        self.assertAlmostEqual(sum(analytic_lines.mapped('amount')), 100.0,
                               msg='la ganancia de 100 debe llegar entera al '
                                   'centro de costo, no anularse')

    def test_analytic_weighted_merge(self):
        """Varios documentos: la analítica se pondera por importe."""
        self._invoice_like('2024-01-10', self.partner_a, 6000.0, 22200.0,
                           self.dist_north)
        self._invoice_like('2024-01-11', self.partner_a, 4000.0, 14800.0,
                           self.dist_south)
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()

        line = self._line_of(closure, self.acc_receivable, self.partner_a)
        self.assertEqual(line.analytic_distribution, {
            str(self.cc_north.id): 60.0,
            str(self.cc_south.id): 40.0,
        }, 'ponderación 22.200 / 14.800 sobre 37.000')

    def test_analytic_merge_keeps_a_full_hundred(self):
        """Tres partes iguales: el redondeo no puede dejar 99,99."""
        for day, distribution in ((10, self.dist_north), (11, self.dist_south),
                                  (12, self.dist_north)):
            self._invoice_like('2024-01-%d' % day, self.partner_a,
                               1000.0, 3700.0, distribution)
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()
        line = self._line_of(closure, self.acc_receivable, self.partner_a)
        self.assertAlmostEqual(sum(line.analytic_distribution.values()), 100.0,
                               places=2)

    def test_analytic_counterpart_is_split_by_distribution(self):
        """Dos analíticas distintas abren dos líneas de resultado."""
        self._invoice_like('2024-01-10', self.partner_a, 1000.0, 3700.0,
                           self.dist_north)
        self._invoice_like('2024-01-11', self.partner_b, 1000.0, 3700.0,
                           self.dist_south)
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()
        closure.action_post()

        gain_lines = closure.move_id.line_ids.filtered(
            lambda l: l.account_id == self.acc_gain)
        self.assertEqual(len(gain_lines), 2)
        self.assertEqual(
            sorted(gain_lines.mapped('analytic_distribution'),
                   key=lambda d: sorted(d)),
            sorted([self.dist_north, self.dist_south],
                   key=lambda d: sorted(d)))
        self.assertAlmostEqual(sum(gain_lines.mapped('credit')), 200.0)

    def test_analytic_same_distribution_is_grouped(self):
        """La misma analítica sigue produciendo una sola línea de resultado."""
        self._invoice_like('2024-01-10', self.partner_a, 1000.0, 3700.0,
                           self.dist_north)
        self._invoice_like('2024-01-11', self.partner_b, 1000.0, 3700.0,
                           self.dist_north)
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()
        closure.action_post()
        gain_lines = closure.move_id.line_ids.filtered(
            lambda l: l.account_id == self.acc_gain)
        self.assertEqual(len(gain_lines), 1)
        self.assertAlmostEqual(gain_lines.credit, 200.0)

    def test_analytic_does_not_leak_from_the_previous_closing_entry(self):
        """El asiento de cierre agrupa socios: no debe contagiar analítica."""
        self._invoice_like('2024-01-10', self.partner_a, 1000.0, 3700.0,
                           self.dist_north)
        # Cliente B sin analítica, en el mismo cierre que el cliente A.
        self._entry('2024-01-11', [
            (self.acc_receivable, 1000.0, 3700.0, self.partner_b),
            (self.acc_income, -1000.0, -3700.0, None),
        ])
        january = self._closure('01', 2024, purchase=3.80, sale=3.82)
        january.action_compute()
        january.action_post()

        february = self._closure('02', 2024, purchase=3.90, sale=3.92)
        february.action_compute()
        line_a = self._line_of(february, self.acc_receivable, self.partner_a)
        line_b = self._line_of(february, self.acc_receivable, self.partner_b)
        self.assertEqual(line_a.analytic_distribution, self.dist_north,
                         'el cliente con analítica la conserva')
        self.assertFalse(
            line_b.analytic_distribution,
            'el cliente sin analítica no puede heredar la del otro a través '
            'del asiento de cierre de enero')

    def test_analytic_prefers_siblings_of_the_same_partner(self):
        """En un asiento con varios socios manda el del propio apunte."""
        self._entry('2024-01-10', [
            (self.acc_receivable, 1000.0, 3700.0, self.partner_a),
            (self.acc_receivable, 1000.0, 3700.0, self.partner_b),
            (self.acc_income, -1000.0, -3700.0, self.partner_a,
             self.dist_north),
            (self.acc_income, -1000.0, -3700.0, self.partner_b,
             self.dist_south),
        ])
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()
        self.assertEqual(
            self._line_of(closure, self.acc_receivable,
                          self.partner_a).analytic_distribution,
            self.dist_north)
        self.assertEqual(
            self._line_of(closure, self.acc_receivable,
                          self.partner_b).analytic_distribution,
            self.dist_south)

    def test_analytic_fixed_distribution(self):
        """Modo fijo: la analítica del cierre se aplica a todo."""
        self._invoice_like('2024-01-10', self.partner_a, 1000.0, 3700.0,
                           self.dist_north)
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82,
                                analytic_source='fixed',
                                analytic_distribution=self.dist_south)
        closure.action_compute()
        line = self._line_of(closure, self.acc_receivable, self.partner_a)
        self.assertEqual(line.analytic_distribution, self.dist_south,
                         'la fija debe ganar sobre la del origen')

    def test_analytic_fixed_is_the_fallback_when_inheriting(self):
        """Sin analítica en el origen se usa la del cierre como respaldo."""
        self._entry('2024-01-15', [
            (self.acc_bank, 1000.0, 3700.0, None),
            (self.acc_other, -1000.0, -3700.0, None),
        ])
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82,
                                analytic_distribution=self.dist_south)
        closure.action_compute()
        line = self._line_of(closure, self.acc_bank)
        self.assertEqual(line.analytic_distribution, self.dist_south)

    def test_analytic_none(self):
        self._invoice_like('2024-01-10', self.partner_a, 1000.0, 3700.0,
                           self.dist_north)
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82,
                                analytic_source='none',
                                analytic_distribution=self.dist_south)
        closure.action_compute()
        closure.action_post()
        self.assertFalse(any(closure.move_id.line_ids.mapped(
            'analytic_distribution')))

    def test_analytic_can_be_corrected_before_posting(self):
        """El contador puede cambiar la analítica del renglón calculado."""
        self._invoice_like('2024-01-10', self.partner_a, 1000.0, 3700.0,
                           self.dist_north)
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()
        line = self._line_of(closure, self.acc_receivable, self.partner_a)
        line.analytic_distribution = self.dist_south
        closure.action_post()
        gain_line = closure.move_id.line_ids.filtered(
            lambda l: l.account_id == self.acc_gain)
        self.assertEqual(gain_line.analytic_distribution, self.dist_south)

    # ------------------------------------------------------------------ #
    # Validaciones                                                        #
    # ------------------------------------------------------------------ #
    def test_only_balance_accounts_can_be_marked(self):
        with self.assertRaises(ValidationError):
            self.acc_gain.l10n_pe_exchange_closing = 'summary'

    def test_unique_period(self):
        self._closure('01', 2024, purchase=3.80, sale=3.82)
        with self.assertRaises(ValidationError):
            self._closure('01', 2024, purchase=3.80, sale=3.82)

    def test_cancelled_period_can_be_redone(self):
        first = self._closure('01', 2024, purchase=3.80, sale=3.82)
        first.action_cancel()
        second = self._closure('01', 2024, purchase=3.80, sale=3.82)
        self.assertEqual(second.state, 'draft')

    def test_closures_must_be_chronological(self):
        self._entry('2024-01-15', [
            (self.acc_bank, 1000.0, 3700.0, None),
            (self.acc_other, -1000.0, -3700.0, None),
        ])
        february = self._closure('02', 2024, purchase=3.90, sale=3.92)
        february.action_compute()
        february.action_post()

        january = self._closure('01', 2024, purchase=3.80, sale=3.82)
        with self.assertRaises(UserError):
            january.action_compute()

    def test_rates_are_required(self):
        closure = self._closure('01', 2024, purchase=0.0, sale=0.0)
        with self.assertRaises(UserError):
            closure.action_compute()

    def test_exchange_accounts_are_required(self):
        self.company.income_currency_exchange_account_id = False
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        with self.assertRaises(UserError):
            closure.action_compute()

    def test_currency_must_differ_from_company(self):
        with self.assertRaises(ValidationError):
            self._closure('01', 2024, purchase=3.80, sale=3.82,
                          currency_id=self.pen.id)

    def test_posted_closure_cannot_be_deleted(self):
        self._entry('2024-01-15', [
            (self.acc_bank, 1000.0, 3700.0, None),
            (self.acc_other, -1000.0, -3700.0, None),
        ])
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()
        closure.action_post()
        with self.assertRaises(UserError):
            closure.unlink()

    def test_draft_requires_cancelling_the_move_first(self):
        self._entry('2024-01-15', [
            (self.acc_bank, 1000.0, 3700.0, None),
            (self.acc_other, -1000.0, -3700.0, None),
        ])
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        closure.action_compute()
        closure.action_post()
        with self.assertRaises(UserError):
            closure.action_draft()

    def test_post_requires_computed_state(self):
        closure = self._closure('01', 2024, purchase=3.80, sale=3.82)
        with self.assertRaises(UserError):
            closure.action_post()
