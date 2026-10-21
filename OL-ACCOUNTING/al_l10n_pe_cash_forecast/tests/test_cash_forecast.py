"""Flujo de caja proyectado: saldo inicial, partidas por periodo, escenario y real."""
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.al_account_base.tests.common import use_pe_company


@tagged('post_install', '-at_install')
class TestCashForecast(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        cls.today = fields.Date.context_today(cls.env['res.partner'])
        cls.partner = cls.env['res.partner'].create({'name': 'SOCIO FLUJO SAC'})
        cls.outstanding = cls.env['account.account'].create({
            'name': 'Pendientes (prueba flujo)', 'code': '104195', 'account_type': 'asset_current',
            'reconcile': True})
        cls.bank = cls.env['account.journal'].create({
            'name': 'Banco flujo', 'code': 'BKFL', 'type': 'bank', 'company_id': cls.company.id})
        (cls.bank.inbound_payment_method_line_ids | cls.bank.outbound_payment_method_line_ids) \
            .payment_account_id = cls.outstanding
        cls.restricted = cls.env['account.journal'].create({
            'name': 'Detracciones BN (prueba)', 'code': 'BKBN', 'type': 'bank', 'company_id': cls.company.id,
            'l10n_pe_forecast_exclude': True})
        cls.sale_journal = cls.env['account.journal'].create({
            'name': 'Ventas flujo', 'code': 'VTFL', 'type': 'sale', 'l10n_latam_use_documents': False})
        cls.purchase_journal = cls.env['account.journal'].create({
            'name': 'Compras flujo', 'code': 'CPFL', 'type': 'purchase', 'l10n_latam_use_documents': False})
        cls.misc = cls.env['account.journal'].search([
            *cls.env['account.journal']._check_company_domain(cls.company), ('type', '=', 'general')], limit=1)
        cls.equity = cls.env['account.account'].search([
            ('account_type', '=', 'equity'), ('company_ids', 'in', cls.company.root_id.id)], limit=1)

    # ------------------------------------------------------------------ ayuda
    def _deposit(self, journal, amount, day):
        """Saldo de un banco: asiento contra el patrimonio."""
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': self.misc.id, 'date': day,
            'line_ids': [Command.create({'account_id': journal.default_account_id.id, 'balance': amount}),
                         Command.create({'account_id': self.equity.id, 'balance': -amount})],
        })
        move.action_post()
        return move

    def _document(self, move_type, amount, due):
        move = self.env['account.move'].create({
            'move_type': move_type, 'partner_id': self.partner.id,
            'journal_id': (self.sale_journal if move_type.startswith('out') else self.purchase_journal).id,
            'invoice_date': self.today - timedelta(days=40), 'invoice_date_due': due,
            'invoice_line_ids': [Command.create({'name': 'Servicio', 'price_unit': amount,
                                                 'tax_ids': [Command.clear()]})],
        })
        move.action_post()
        return move

    def _forecast(self, **vals):
        return self.env['l10n_pe.cash.forecast'].create({'name': 'Prueba', **vals})

    @staticmethod
    def _line(forecast, move):
        return forecast.line_ids.filtered(lambda l: l.move_id == move)

    # ------------------------------------------------------------------ saldo inicial
    def test_opening_excludes_restricted_funds(self):
        self._deposit(self.bank, 10000, self.today - timedelta(days=3))
        self._deposit(self.restricted, 500, self.today - timedelta(days=3))
        forecast = self._forecast()
        self.assertAlmostEqual(forecast.opening_balance, self._forecast_opening_without(forecast))
        self.assertAlmostEqual(forecast.restricted_balance, 500.0)

    def _forecast_opening_without(self, forecast):
        """Saldo inicial esperado: bancos y cajas disponibles según libros."""
        journals = forecast._l10n_pe_journals().filtered(lambda j: not j.l10n_pe_forecast_exclude)
        journals -= forecast._l10n_pe_check_portfolio_journals(journals)
        accounts = journals.default_account_id.filtered(lambda a: a.account_type == 'asset_cash')
        return sum(self.env['account.move.line'].search([
            ('account_id', 'in', accounts.ids), ('parent_state', '=', 'posted'),
            ('date', '<=', forecast.date_from)]).mapped('balance'))

    def test_opening_moves_with_new_bank_balance(self):
        forecast = self._forecast()
        opening = forecast.opening_balance
        self._deposit(self.bank, 2500, self.today)
        self._deposit(self.restricted, 900, self.today)
        forecast.action_refresh()
        self.assertAlmostEqual(forecast.opening_balance - opening, 2500.0)

    # ------------------------------------------------------------------ partidas
    def test_documents_by_due_date(self):
        invoice = self._document('out_invoice', 1200, self.today + timedelta(days=9))
        bill = self._document('in_invoice', 800, self.today + timedelta(days=20))
        overdue = self._document('out_invoice', 300, self.today - timedelta(days=15))
        forecast = self._forecast()
        periods = forecast.period_ids.sorted('sequence')
        self.assertEqual(len(periods), 13, '12 semanas y «Desde…» para lo posterior')
        inv_line, bill_line, overdue_line = (self._line(forecast, m) for m in (invoice, bill, overdue))
        self.assertEqual((inv_line.category, inv_line.amount), ('receivable', 1200.0))
        self.assertEqual((bill_line.category, bill_line.amount), ('payable', -800.0))
        self.assertTrue(overdue_line.is_overdue)
        self.assertEqual(overdue_line.date_expected, forecast.date_from)
        self.assertEqual(overdue_line.period_id, periods[0])
        self.assertLessEqual(inv_line.period_id.date_start, inv_line.date_expected)
        self.assertGreaterEqual(inv_line.period_id.date_end, inv_line.date_expected)
        self.assertIn(inv_line, inv_line.period_id.line_ids)

    def test_payment_in_transit(self):
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': self.partner.id,
            'amount': 450, 'journal_id': self.bank.id, 'date': self.today})
        payment.action_post()
        forecast = self._forecast()
        lines = forecast.line_ids.filtered(lambda l: l.move_id == payment.move_id)
        transit = lines.filtered(lambda l: l.category == 'transit')
        self.assertEqual(transit.amount, -450.0, 'el banco aún no lo debita')
        # Pago a cuenta: el saldo a favor del proveedor reduce lo que se le pagará después.
        self.assertEqual(lines.filtered(lambda l: l.category == 'payable').amount, 450.0)

    def test_period_balances_chain(self):
        self._document('out_invoice', 1000, self.today + timedelta(days=8))
        forecast = self._forecast()
        balance = forecast.opening_balance
        for period in forecast.period_ids.sorted('sequence'):
            self.assertAlmostEqual(period.opening, balance)
            balance = period.closing
        self.assertAlmostEqual(balance, forecast.closing_balance)
        self.assertAlmostEqual(forecast.closing_balance,
                               forecast.opening_balance + sum(forecast.line_ids.mapped('amount')))
        self.assertLessEqual(forecast.min_balance, forecast.closing_balance)

    def test_months(self):
        forecast = self._forecast(period_type='month', period_count=3)
        periods = forecast.period_ids.sorted('sequence')
        self.assertEqual(len(periods), 4)
        self.assertEqual(periods[0].date_start, self.today.replace(day=1))
        self.assertFalse(periods[-1].date_end)
        with self.assertRaises(ValidationError):
            forecast.period_count = 0

    # ------------------------------------------------------------------ escenario
    def test_edited_line_survives_refresh_and_reset(self):
        invoice = self._document('out_invoice', 700, self.today + timedelta(days=3))
        forecast = self._forecast()
        line = self._line(forecast, invoice)
        later = self.today + timedelta(days=45)
        line.write({'date_expected': later, 'amount': 600})
        self.assertTrue(line.is_edited)
        forecast.action_refresh()
        line = self._line(forecast, invoice)
        self.assertEqual((line.date_expected, line.amount, line.is_edited), (later, 600.0, True))
        line.action_reset()
        line = self._line(forecast, invoice)
        self.assertEqual((line.date_expected, line.amount, line.is_edited),
                         (self.today + timedelta(days=3), 700.0, False))

    def test_manual_line_is_kept(self):
        forecast = self._forecast()
        forecast.line_ids = [Command.create({'name': 'Planilla de octubre', 'amount': -3000,
                                             'date_expected': self.today + timedelta(days=25)})]
        manual = forecast.line_ids.filtered(lambda l: l.category == 'manual')
        self.assertTrue(manual.period_id)
        forecast.action_refresh()
        self.assertIn(manual, forecast.line_ids)
        self.assertTrue(manual.period_id)
        with self.assertRaises(ValidationError):
            forecast.line_ids = [Command.create({'name': 'X', 'amount': 1, 'category': 'receivable',
                                                 'date_expected': self.today})]

    def test_paid_document_leaves_forecast(self):
        invoice = self._document('out_invoice', 500, self.today + timedelta(days=5))
        forecast = self._forecast()
        self.assertTrue(self._line(forecast, invoice))
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids).create({'journal_id': self.bank.id})
        payment = wizard._create_payments()
        forecast.action_refresh()
        self.assertFalse(self._line(forecast, invoice), 'cobrada: ya no se espera')
        self.assertEqual(forecast.line_ids.filtered(lambda l: l.move_id == payment.move_id).category, 'transit')

    # ------------------------------------------------------------------ real
    def test_actual_versus_projected(self):
        start = self.today - timedelta(days=14)
        forecast = self._forecast(date_from=start)
        self._deposit(self.bank, 1500, start + timedelta(days=1))
        past = forecast.period_ids.filtered('is_past')
        self.assertTrue(past)
        period = past.filtered(lambda p: p.date_start <= start + timedelta(days=1)
                               and (not p.date_end or p.date_end >= start + timedelta(days=1)))
        period.invalidate_recordset(['actual_net', 'variance'])
        self.assertGreaterEqual(period.actual_net, 1500.0 - 1e-6)
        self.assertAlmostEqual(period.variance, period.actual_net - period.net)
        current = forecast.period_ids.filtered(lambda p: not p.date_end or p.date_end >= self.today)
        self.assertFalse(any(current.mapped('is_past')), 'solo periodos terminados')

    # ------------------------------------------------------------------ exportar
    def test_export_xlsx(self):
        self._document('in_invoice', 250, self.today + timedelta(days=2))
        forecast = self._forecast()
        action = forecast.action_export_xlsx()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        attachment = self.env['ir.attachment'].search([('res_model', '=', forecast._name),
                                                       ('res_id', '=', forecast.id)])
        self.assertTrue(attachment.name.endswith('.xlsx'))
        self.assertGreater(attachment.file_size, 1000)
        pivot = forecast.action_open_lines()
        self.assertEqual(pivot['res_model'], 'l10n_pe.cash.forecast.line')
