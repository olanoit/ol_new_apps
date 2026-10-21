"""App Cobranza: cartera, gestiones, compromisos, proyección, metas, tablero,
estado de cuenta y notificaciones."""
import json
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.al_account_base.tests.common import use_pe_company


@tagged('post_install', '-at_install')
class TestCollection(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        if not cls.company.external_report_layout_id:
            cls.company.external_report_layout_id = cls.env.ref('web.external_layout_standard')
        cls.today = fields.Date.context_today(cls.env['res.partner'])
        group_user = cls.env.ref('al_l10n_pe_collection.group_collection_user')
        cls.collector = cls.env['res.users'].create({
            'name': 'Gestora Cobranza', 'login': 'gestora_cobranza', 'email': 'gestora@example.com',
            'group_ids': [Command.set([group_user.id])],
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
        })
        cls.other_collector = cls.env['res.users'].create({
            'name': 'Otro Gestor', 'login': 'otro_gestor', 'email': 'otro@example.com',
            'group_ids': [Command.set([group_user.id])],
            'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
        })
        cls.zone = cls.env['l10n_pe.collection.zone'].create({'name': 'Lima Norte', 'user_id': cls.collector.id})
        cls.customer, cls.other_customer = cls.env['res.partner'].create([
            {'name': 'CLIENTE COBRANZA SAC', 'email': 'cliente@example.com'},
            {'name': 'OTRO CLIENTE SAC', 'email': 'otro.cliente@example.com'},
        ])
        cls.customer.with_company(cls.company).write({
            'followup_responsible_id': cls.collector.id, 'l10n_pe_collection_zone_id': cls.zone.id})
        cls.other_customer.with_company(cls.company).followup_responsible_id = cls.other_collector
        cls.sale_journal = cls.env['account.journal'].create({
            'name': 'Ventas cobranza', 'code': 'VTCO', 'type': 'sale', 'l10n_latam_use_documents': False})
        outstanding = cls.env['account.account'].create({
            'name': 'Pendientes (prueba cobranza)', 'code': '104188', 'account_type': 'asset_current',
            'reconcile': True})
        cls.bank = cls.env['account.journal'].create({
            'name': 'Banco cobranza', 'code': 'BKCO', 'type': 'bank', 'company_id': cls.company.id})
        (cls.bank.inbound_payment_method_line_ids | cls.bank.outbound_payment_method_line_ids) \
            .payment_account_id = outstanding
        cls.result_promise = cls.env.ref('al_l10n_pe_collection.result_promise')
        cls.result_no_answer = cls.env.ref('al_l10n_pe_collection.result_no_answer')

    # ------------------------------------------------------------------ ayuda
    def _invoice(self, amount, due_in, partner=None, invoice_date=None):
        due = self.today + timedelta(days=due_in)
        move = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': (partner or self.customer).id,
            'journal_id': self.sale_journal.id,
            'invoice_date': invoice_date or min(due, self.today) - timedelta(days=1),
            'invoice_date_due': due,
            'invoice_line_ids': [Command.create({'name': 'Venta', 'price_unit': amount,
                                                 'tax_ids': [Command.clear()]})],
        })
        move.action_post()
        return move

    def _pay(self, invoice, amount=None, day=None):
        vals = {'journal_id': self.bank.id, 'payment_date': day or self.today}
        if amount is not None:
            vals['amount'] = amount
        return self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids).create(vals)._create_payments()

    @staticmethod
    def _receivable(move):
        return move.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')

    def _promise(self, amount, date, lines=None, partner=None):
        return self.env['l10n_pe.collection.promise'].create({
            'partner_id': (partner or self.customer).id, 'user_id': self.collector.id, 'date': date,
            'amount': amount, 'line_ids': [Command.set(lines.ids)] if lines else [],
        })

    # ------------------------------------------------------------------ cartera
    def test_buckets(self):
        Bucket = self.env['l10n_pe.collection.bucket']
        self.assertEqual(Bucket._l10n_pe_for_days(-5).name, 'Por vencer')
        self.assertEqual(Bucket._l10n_pe_for_days(10).name, '1 a 30 días')
        self.assertEqual(Bucket._l10n_pe_for_days(400).name, 'Más de 180 días')

    def test_portfolio_has_collector_zone_and_aging(self):
        invoice = self._invoice(1000, -40)
        self.env['l10n_pe.collection.portfolio'].flush_model()
        row = self.env['l10n_pe.collection.portfolio'].search([('move_id', '=', invoice.id)])
        self.assertEqual((row.user_id, row.zone_id), (self.collector, self.zone))
        self.assertEqual(row.days_overdue, 40)
        self.assertTrue(row.is_overdue)
        self.assertEqual(row.bucket_id.name, '31 a 60 días')
        self.assertAlmostEqual(row.amount_residual, 1000.0)
        action = self.env['l10n_pe.collection.portfolio'].action_open()
        self.assertIn(row, self.env['l10n_pe.collection.portfolio'].search(action['domain']))

    def test_collector_only_sees_own_portfolio_and_promises(self):
        mine = self._invoice(100, -5)
        theirs = self._invoice(200, -5, partner=self.other_customer)
        self._promise(100, self.today + timedelta(days=3))
        self.env['l10n_pe.collection.promise'].create({
            'partner_id': self.other_customer.id, 'user_id': self.other_collector.id,
            'date': self.today + timedelta(days=3), 'amount': 50})
        Portfolio = self.env['l10n_pe.collection.portfolio'].with_user(self.collector)
        moves = Portfolio.search([('move_id', 'in', (mine | theirs).ids)]).move_id
        self.assertEqual(moves, mine)
        promises = self.env['l10n_pe.collection.promise'].with_user(self.collector).search([])
        self.assertEqual(promises.partner_id, self.customer)

    # ------------------------------------------------------------------ gestiones
    def test_action_with_promise_creates_promise_and_activity(self):
        invoice = self._invoice(800, -10)
        action = self.env['l10n_pe.collection.action'].create({
            'partner_id': self.customer.id, 'user_id': self.collector.id, 'channel': 'call',
            'result_id': self.result_promise.id, 'promise_date': self.today + timedelta(days=5),
            'promise_amount': 800, 'line_ids': [Command.set(self._receivable(invoice).ids)],
            'next_action_date': self.today + timedelta(days=6), 'next_action_summary': 'Confirmar el pago',
        })
        promise = action.promise_id
        self.assertEqual((promise.amount, promise.user_id, promise.state), (800.0, self.collector, 'pending'))
        self.assertAlmostEqual(promise.residual_at_agreement, 800.0)
        activity = self.customer.activity_ids.filtered(lambda a: a.summary == 'Confirmar el pago')
        self.assertEqual(activity.user_id, self.collector)
        self.assertIn('Promete pagar', self.customer.message_ids[:3].mapped('body')[1] + self.customer.message_ids[:3].mapped('body')[0])

    def test_promise_result_requires_date_and_amount(self):
        with self.assertRaises(Exception):
            self.env['l10n_pe.collection.action'].create({
                'partner_id': self.customer.id, 'result_id': self.result_promise.id})

    def test_result_schedules_next_action(self):
        action = self.env['l10n_pe.collection.action'].create({
            'partner_id': self.customer.id, 'user_id': self.collector.id, 'channel': 'call',
            'result_id': self.result_no_answer.id})
        self.assertEqual(action.next_action_date, action.date.date() + timedelta(days=1))
        self.assertTrue(self.customer.activity_ids.filtered(lambda a: a.user_id == self.collector))

    # ------------------------------------------------------------------ compromisos
    def test_promise_kept_before_its_date(self):
        invoice = self._invoice(1000, -20)
        promise = self._promise(600, self.today + timedelta(days=10), self._receivable(invoice))
        self._pay(invoice, 600)
        promise._l10n_pe_evaluate()
        self.assertEqual(promise.state, 'kept')
        self.assertAlmostEqual(promise.collected_amount, 600.0)

    def test_promise_partial_and_broken_after_tolerance(self):
        invoice = self._invoice(1000, -30)
        lines = self._receivable(invoice)
        partial = self._promise(500, self.today - timedelta(days=5), lines)
        broken = self._promise(300, self.today - timedelta(days=5), lines, partner=self.customer)
        pending = self._promise(300, self.today, lines)
        self._pay(invoice, 200)
        (partial | broken | pending)._l10n_pe_evaluate()
        self.assertEqual(partial.state, 'partial')
        self.assertEqual(pending.state, 'pending', 'dentro de la tolerancia')
        self.assertTrue(partial.activity_ids.filtered(lambda a: a.user_id == self.collector))
        # Sin cobro alguno desde que se pactó: incumplido.
        lone = self._promise(400, self.today - timedelta(days=10), self._receivable(self._invoice(400, -40)))
        lone._l10n_pe_evaluate()
        self.assertEqual(lone.state, 'broken')
        self.assertEqual(lone.collected_amount, 0.0)

    def test_promise_without_documents_counts_partner_payments(self):
        invoice = self._invoice(700, -15)
        promise = self._promise(700, self.today + timedelta(days=2))
        self._pay(invoice)
        promise._l10n_pe_evaluate()
        self.assertEqual(promise.state, 'kept')

    def test_promise_reminder_is_sent_once(self):
        promise = self._promise(250, self.today + timedelta(days=1))
        self.company.root_id.l10n_pe_collection_promise_reminder_days = 1
        sent = promise._l10n_pe_send_reminders()
        self.assertEqual(sent, promise)
        self.assertTrue(promise.reminder_sent)
        mail = self.env['mail.mail'].search([('model', '=', promise._name), ('res_id', '=', promise.id)])
        self.assertTrue(mail)
        self.assertFalse(promise._l10n_pe_send_reminders(), 'no se repite')

    def test_cron_runs(self):
        self._promise(100, self.today - timedelta(days=10))
        self.env['l10n_pe.collection.promise']._cron_collection_promises()

    def test_only_manager_reopens(self):
        promise = self._promise(100, self.today - timedelta(days=10))
        promise._l10n_pe_evaluate()
        with self.assertRaises(UserError):
            promise.with_user(self.collector).action_reset()
        promise.action_reset()
        self.assertEqual(promise.state, 'pending')

    # ------------------------------------------------------------------ historial de pago
    def test_average_delay(self):
        invoice = self._invoice(500, -30, invoice_date=self.today - timedelta(days=60))
        self._pay(invoice, day=self.today - timedelta(days=20))
        self.assertEqual(self.customer._l10n_pe_collection_average_delay(self.company), 10)
        self.assertEqual(self.other_customer._l10n_pe_collection_average_delay(self.company), 0)

    # ------------------------------------------------------------------ proyección
    def test_forecast_dates_and_probability(self):
        paid = self._invoice(500, -30, invoice_date=self.today - timedelta(days=60))
        self._pay(paid, day=self.today - timedelta(days=20))  # el cliente paga 10 días tarde
        with_promise = self._invoice(1000, -45)
        future = self._invoice(400, 7)
        self._promise(1000, self.today + timedelta(days=3), self._receivable(with_promise))
        other = self._invoice(300, 14, partner=self.other_customer)
        forecast = self.env['l10n_pe.collection.forecast'].create({'name': 'Prueba'})
        line = {l.move_id: l for l in forecast.line_ids}
        self.assertEqual((line[with_promise].source, line[with_promise].expected_date),
                         ('promise', self.today + timedelta(days=3)))
        self.assertEqual((line[future].source, line[future].expected_date),
                         ('behavior', self.today + timedelta(days=17)), 'vence en 7 días + 10 de atraso')
        self.assertEqual((line[other].source, line[other].expected_date), ('due', self.today + timedelta(days=14)))
        self.assertEqual(line[with_promise].bucket_id.name, '31 a 60 días')
        self.assertAlmostEqual(line[with_promise].expected_amount, 1000 * line[with_promise].probability / 100)
        self.assertAlmostEqual(line[future].probability, 98.0)
        self.assertIn(line[future], line[future].period_id.line_ids)
        # Filtro por gestor
        mine = self.env['l10n_pe.collection.forecast'].create({'name': 'Mía', 'user_ids': [Command.set(self.collector.ids)]})
        self.assertNotIn(other, mine.line_ids.move_id)
        self.assertIn(future, mine.line_ids.move_id)

    def test_forecast_edit_survives_refresh_and_export(self):
        invoice = self._invoice(900, 5)
        forecast = self.env['l10n_pe.collection.forecast'].create({'name': 'Ajustes', 'use_probability': False})
        line = forecast.line_ids.filtered(lambda l: l.move_id == invoice)
        later = self.today + timedelta(days=40)
        line.write({'expected_date': later, 'expected_amount': 450})
        forecast.action_refresh()
        line = forecast.line_ids.filtered(lambda l: l.move_id == invoice)
        self.assertEqual((line.expected_date, line.expected_amount, line.source), (later, 450.0, 'manual'))
        line.action_reset()
        line = forecast.line_ids.filtered(lambda l: l.move_id == invoice)
        self.assertNotEqual(line.source, 'manual')
        self.assertEqual(forecast.action_export_xlsx()['type'], 'ir.actions.act_url')

    def test_forecast_compares_collected_in_past_periods(self):
        invoice = self._invoice(600, -20, invoice_date=self.today - timedelta(days=40))
        forecast = self.env['l10n_pe.collection.forecast'].create({
            'name': 'Pasada', 'date_from': self.today - timedelta(days=21), 'period_count': 3})
        self._pay(invoice, day=self.today - timedelta(days=18))
        past = forecast.period_ids.filtered('is_past')
        self.assertTrue(past)
        self.assertGreaterEqual(sum(past.mapped('collected_amount')), 600.0 - 0.01)

    # ------------------------------------------------------------------ metas y tablero
    def test_target_progress(self):
        invoice = self._invoice(1000, -5)
        self._pay(invoice, 400)
        target = self.env['l10n_pe.collection.target'].create({
            'user_id': self.collector.id, 'date_from': self.today.replace(day=1),
            'date_to': self.today.replace(day=1) + timedelta(days=40), 'amount': 1000})
        self.assertAlmostEqual(target.collected_amount, 400.0)
        self.assertAlmostEqual(target.progress, 40.0)
        self.assertAlmostEqual(target.portfolio_amount, 600.0)

    def test_dashboard(self):
        self._invoice(1000, -10)
        self._invoice(500, 3)
        self._promise(200, self.today)
        board = self.env['l10n_pe.collection.dashboard'].create({'user_id': self.collector.id})
        self.assertAlmostEqual(board.portfolio_amount, 1500.0)
        self.assertAlmostEqual(board.overdue_amount, 1000.0)
        self.assertAlmostEqual(board.overdue_percent, 1000 / 1500 * 100, places=1)
        self.assertAlmostEqual(board.due_soon_amount, 500.0)
        self.assertEqual(board.promises_today_count, 1)
        self.assertGreater(board.dso, 0)
        self.assertEqual(board.action_open_overdue()['res_model'], 'l10n_pe.collection.portfolio')
        self.assertTrue(self.env['l10n_pe.collection.dashboard'].action_open_dashboard()['res_id'])

    def test_spreadsheet_dashboard(self):
        """El tablero de la app Tableros: sus fuentes de datos responden con los
        permisos del gestor y solo con su cartera."""
        self._invoice(1000, -10)
        self._invoice(700, -10, partner=self.other_customer)
        self._promise(200, self.today)
        self.env['l10n_pe.collection.portfolio'].flush_model()
        dashboard = self.env.ref('al_l10n_pe_collection.dashboard_collection')
        self.assertIn(dashboard, self.env['spreadsheet.dashboard'].with_user(self.collector).search([]))
        action = self.env.ref('al_l10n_pe_collection.action_collection_spreadsheet_dashboard')
        self.assertEqual(action.params, {'dashboard_id': dashboard.id})
        dashboard._check_spreadsheet_data()  # modelos y campos del JSON existen
        data = json.loads(dashboard.spreadsheet_data)
        for source in list(data['pivots'].values()) + list(data['lists'].values()):
            model = self.env[source['model']].with_user(self.collector)
            model.search_count(source['domain'])  # dominio válido y sin error de acceso
        Portfolio = self.env['l10n_pe.collection.portfolio'].with_user(self.collector)
        groups = Portfolio._read_group([('in_collection', '=', True), ('is_overdue', '=', True)],
                                       aggregates=['amount_residual:sum', 'partner_id:count_distinct'])
        self.assertEqual(groups, [(1000.0, 1)])
        self.assertFalse(Portfolio.search_count([('in_collection', '=', False)]))

    # ------------------------------------------------------------------ estado de cuenta
    def test_statement_pdf_and_send(self):
        overdue = self._invoice(1000, -10)
        self._invoice(250, 10)
        values = self.customer._l10n_pe_collection_statement_values(self.company)
        self.assertEqual((values['overdue'], values['due'], values['total']), (1000.0, 250.0, 1250.0))
        html, _type = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_collection.report_statement', self.customer.ids)
        html = html.decode()
        self.assertIn('Estado de cuenta', html)
        self.assertIn(overdue.name, html)
        wizard = self.env['l10n_pe.collection.statement.send'].create({
            'partner_ids': [Command.set((self.customer | self.other_customer).ids)]})
        wizard.action_send()
        mail = self.env['mail.mail'].search([('model', '=', 'res.partner'), ('res_id', '=', self.customer.id)],
                                            order='id desc', limit=1)
        self.assertTrue(mail.attachment_ids, 'con el PDF adjunto')

    def test_statement_credit_is_separate(self):
        self._invoice(1000, -10)
        refund = self.env['account.move'].create({
            'move_type': 'out_refund', 'partner_id': self.customer.id, 'journal_id': self.sale_journal.id,
            'invoice_date': self.today - timedelta(days=30),
            'invoice_line_ids': [Command.create({'name': 'Devolución', 'price_unit': 100,
                                                 'tax_ids': [Command.clear()]})],
        })
        refund.action_post()
        values = self.customer._l10n_pe_collection_statement_values(self.company)
        self.assertEqual((values['overdue'], values['credit'], values['total']), (1000.0, -100.0, 900.0))
        credit_doc = [d for d in values['documents'] if d['is_credit']][0]
        self.assertEqual((credit_doc['days'], credit_doc['overdue']), (0, False))

    # ------------------------------------------------------------------ notificaciones
    def test_followup_levels_loader(self):
        Line = self.env['account_followup.followup.line']
        Line.search([('company_id', '=', self.company.id)]).unlink()
        Line._l10n_pe_load_levels(self.company)
        levels = Line.search([('company_id', '=', self.company.id)])
        self.assertEqual(sorted(levels.mapped('delay')), [-3, 1, 15, 30, 60])
        self.assertEqual(levels.filtered(lambda l: l.delay == -3).mail_template_id,
                         self.env.ref('al_l10n_pe_collection.mail_template_followup_preventive'))
        Line._l10n_pe_load_levels(self.company)
        self.assertEqual(len(Line.search([('company_id', '=', self.company.id)])), 5, 'no duplica')

    def test_daily_digest(self):
        self._invoice(300, 2)
        self._invoice(150, -1)
        self._promise(100, self.today)
        Dashboard = self.env['l10n_pe.collection.dashboard']
        mail = Dashboard._send_digest(self.collector, self.company, self.today)
        self.assertTrue(mail)
        self.assertIn('gestora@example.com', mail.email_to)
        for text in ('Compromisos de pago', 'Vencen en los próximos 3 días', 'Vencieron ayer'):
            self.assertIn(text, mail.body_html)
        quiet = self.env['res.users'].create({'name': 'Sin cartera', 'login': 'sin_cartera', 'email': 'x@example.com'})
        self.assertFalse(Dashboard._send_digest(quiet, self.company, self.today), 'sin novedades no se envía')
        Dashboard._cron_collection_digest()

    def test_collector_cannot_edit_configuration(self):
        with self.assertRaises(AccessError):
            self.env['l10n_pe.collection.bucket'].with_user(self.collector).create({
                'name': 'X', 'days_from': 0, 'probability': 50})
