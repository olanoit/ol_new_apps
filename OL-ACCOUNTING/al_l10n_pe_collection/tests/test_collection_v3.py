"""App Cobranza v3: reclamos, protección al consumidor, calificación y bloqueo,
intereses moratorios, provisión y castigo, centrales de riesgo y expediente."""
import ast
from datetime import datetime, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, tagged

from .common import CollectionCommon


@tagged('post_install', '-at_install')
class TestCollectionV3(CollectionCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.collector.tz = 'America/Lima'
        cls.result_claim = cls.env.ref('al_l10n_pe_collection.result_claim')
        cls.reason_price = cls.env.ref('al_l10n_pe_collection.dispute_reason_price')
        cls.consumer = cls.env['res.partner'].create({
            'name': 'Juana Pérez', 'email': 'juana@example.com',
            'l10n_pe_collection_debtor_type': 'consumer'})
        cls.consumer.with_company(cls.company).followup_responsible_id = cls.collector

    def _dispute(self, invoice):
        return self.env['l10n_pe.collection.dispute'].create({
            'partner_id': self.customer.id, 'user_id': self.collector.id, 'reason_id': self.reason_price.id,
            'line_ids': [Command.set(self._receivable(invoice).ids)]})

    # ------------------------------------------------------------------ reclamos
    def test_dispute_pauses_followup_and_portfolio(self):
        invoice = self._invoice(500, -20)
        line = self._receivable(invoice)
        dispute = self._dispute(invoice)
        self.assertTrue(line.no_followup)
        self.assertTrue(line.l10n_pe_collection_in_dispute)
        self.assertAlmostEqual(dispute.amount, 500.0)
        self.env['l10n_pe.collection.portfolio'].flush_model()
        row = self.env['l10n_pe.collection.portfolio'].search([('move_id', '=', invoice.id)])
        self.assertTrue(row.in_dispute)
        with self.assertRaises(UserError):
            dispute.action_resolve_company()  # sin solución
        dispute.resolution = 'El precio era el pactado.'
        dispute.action_resolve_company()
        self.assertEqual(dispute.state, 'company')
        self.assertFalse(line.no_followup)
        self.assertFalse(line.l10n_pe_collection_in_dispute)

    def test_dispute_keeps_manual_no_followup(self):
        invoice = self._invoice(300, -5)
        line = self._receivable(invoice)
        dispute = self._dispute(invoice)
        dispute.action_cancel()
        self.assertFalse(line.no_followup, 'el reclamo devuelve lo que sacó')
        other = self._invoice(200, -5)
        other_line = self._receivable(other)
        other_line.no_followup = True
        self.assertTrue(other_line.no_followup, 'sin reclamo, la marca manual no se toca')

    def test_dispute_credit_note_action(self):
        invoice = self._invoice(400, -5)
        dispute = self._dispute(invoice)
        dispute.resolution = 'Se aplica descuento.'
        dispute.action_resolve_customer()
        action = dispute.action_credit_note()
        self.assertEqual(action['res_model'], 'account.move.reversal')
        self.assertEqual(action['context']['active_ids'], invoice.ids)

    def test_claim_result_opens_dispute(self):
        invoice = self._invoice(700, -15)
        action = self.env['l10n_pe.collection.action'].create({
            'partner_id': self.customer.id, 'user_id': self.collector.id, 'channel': 'email',
            'result_id': self.result_claim.id, 'dispute_reason_id': self.reason_price.id,
            'line_ids': [Command.set(self._receivable(invoice).ids)], 'note': 'Reclama el precio'})
        self.assertTrue(action.dispute_id)
        self.assertEqual(action.dispute_id.state, 'open')
        self.assertEqual(self.customer.l10n_pe_collection_dispute_count, 1)
        with self.assertRaises(ValidationError):
            self.env['l10n_pe.collection.action'].create({
                'partner_id': self.customer.id, 'channel': 'email', 'result_id': self.result_claim.id})

    # ------------------------------------------------------------------ consumidor
    def _call(self, partner, local_dt, channel='call'):
        """Gestión a la hora local de Lima (UTC-5)."""
        return self.env['l10n_pe.collection.action'].create({
            'partner_id': partner.id, 'user_id': self.collector.id, 'channel': channel,
            'result_id': self.result_no_answer.id, 'date': local_dt + timedelta(hours=5)})

    def test_consumer_detection(self):
        dni = self.env.ref('l10n_pe.it_DNI')
        ruc = self.env.ref('l10n_pe.it_RUC')
        person = self.env['res.partner'].create({'name': 'Luis Soto', 'l10n_latam_identification_type_id': dni.id,
                                                 'vat': '45678912'})
        company = self.env['res.partner'].create({'name': 'EMPRESA SAC', 'is_company': True,
                                                  'l10n_latam_identification_type_id': ruc.id})
        self.assertTrue(person._l10n_pe_collection_is_consumer())
        self.assertFalse(company._l10n_pe_collection_is_consumer())
        person.l10n_pe_collection_debtor_type = 'business'
        self.assertFalse(person._l10n_pe_collection_is_consumer())

    def test_consumer_contact_hours(self):
        wednesday = datetime(2026, 10, 21)
        self._call(self.consumer, wednesday.replace(hour=10))
        self._call(self.consumer, wednesday.replace(hour=10), channel='email')
        with self.assertRaises(ValidationError):
            self._call(self.consumer, wednesday.replace(hour=21))
        with self.assertRaises(ValidationError):
            self._call(self.consumer, wednesday.replace(hour=6, minute=30), channel='whatsapp')
        with self.assertRaises(ValidationError):
            self._call(self.consumer, datetime(2026, 10, 24, 10), channel='visit')  # sábado
        self._call(self.customer, wednesday.replace(hour=21))  # empresa: sin límite
        self.company.l10n_pe_collection_consumer_guard = False
        self._call(self.consumer, wednesday.replace(hour=21))

    def test_consumer_holiday(self):
        Leaves = self.env.get('resource.calendar.leaves')
        if Leaves is None:
            self.skipTest('resource no está instalado')
        holiday = datetime(2026, 10, 8)  # jueves
        Leaves.create({'name': 'Combate de Angamos', 'date_from': holiday, 'date_to': holiday + timedelta(days=1),
                       'calendar_id': False, 'resource_id': False, 'company_id': self.company.id})
        with self.assertRaises(ValidationError):
            self._call(self.consumer, holiday.replace(hour=11))

    def test_preventive_followup_needs_consent(self):
        Line = self.env['account_followup.followup.line']
        Line.search([('company_id', '=', self.company.id)]).unlink()
        Line._l10n_pe_load_levels(self.company)
        self._invoice(100, 2, partner=self.consumer)
        self.consumer.invalidate_recordset()
        self.assertEqual(self.consumer.followup_line_id.delay, -3)
        self.assertTrue(self.consumer._l10n_pe_collection_skip_preventive())
        self.assertFalse(self.consumer._execute_followup_partner())
        self.consumer.l10n_pe_collection_reminder_consent = True
        self.assertFalse(self.consumer._l10n_pe_collection_skip_preventive())

    # ------------------------------------------------------------------ calificación y bloqueo
    def test_rating_and_automatic_hold(self):
        self.company.l10n_pe_collection_hold_days = 60
        self._invoice(1000, -130)
        for days in (40, 30, 20):
            promise = self._promise(100, self.today - timedelta(days=days))
            promise._l10n_pe_evaluate()
        self.assertEqual(promise.state, 'broken')
        self.customer._l10n_pe_collection_rate(self.company, self.today)
        partner = self.customer.with_company(self.company)
        self.assertIn(partner.l10n_pe_collection_rating, ('C', 'D'))
        self.assertEqual(partner.l10n_pe_collection_max_days, 130)
        self.assertEqual(partner.l10n_pe_collection_hold, 'auto')
        self.assertTrue(partner._l10n_pe_collection_is_on_hold(self.company))
        self.assertGreater(partner.l10n_pe_collection_priority, 1000)
        partner.action_l10n_pe_collection_release()
        self.assertEqual(partner.l10n_pe_collection_hold, 'released')
        self.assertFalse(partner._l10n_pe_collection_is_on_hold(self.company))
        partner._l10n_pe_collection_rate(self.company, self.today)
        self.assertEqual(partner.l10n_pe_collection_hold, 'released', 'respeta la liberación')
        partner._l10n_pe_collection_rate(self.company, self.today + timedelta(days=8))
        self.assertEqual(partner.l10n_pe_collection_hold, 'auto', 'vencida la liberación, vuelve a bloquear')

    def test_old_debt_without_payment_history_is_rated_d(self):
        """Un cliente que nunca pagó no tiene historial: su atraso es el de lo vencido."""
        self._invoice(12400, -400)
        self.customer._l10n_pe_collection_rate(self.company, self.today)
        self.assertEqual(self.customer.with_company(self.company).l10n_pe_collection_rating, 'D')

    def test_good_payer_is_rated_a(self):
        invoice = self._invoice(500, -30, invoice_date=self.today - timedelta(days=60))
        self._pay(invoice, day=self.today - timedelta(days=30))
        self._invoice(200, 10)
        self.customer._l10n_pe_collection_rate(self.company, self.today)
        partner = self.customer.with_company(self.company)
        self.assertEqual((partner.l10n_pe_collection_rating, partner.l10n_pe_collection_hold), ('A', False))
        self.env['res.partner']._cron_l10n_pe_collection_rating()

    def test_collector_registers_action(self):
        action = self.env['l10n_pe.collection.action'].with_user(self.collector).create({
            'partner_id': self.customer.id, 'channel': 'email', 'result_id': self.result_no_answer.id,
            'note': 'Sin respuesta'})
        self.assertEqual(action.user_id, self.collector)
        invoice = self._invoice(400, -10)
        promise_action = self.env['l10n_pe.collection.action'].with_user(self.collector).create({
            'partner_id': self.customer.id, 'channel': 'email', 'result_id': self.result_promise.id,
            'promise_date': self.today + timedelta(days=3), 'promise_amount': 400,
            'line_ids': [Command.set(self._receivable(invoice).ids)]})
        self.assertTrue(promise_action.promise_id)
        dispute = self.env['l10n_pe.collection.dispute'].with_user(self.collector).create({
            'partner_id': self.customer.id, 'reason_id': self.reason_price.id,
            'line_ids': [Command.set(self._receivable(self._invoice(50, -3)).ids)]})
        self.assertEqual(dispute.state, 'open')
        self.assertIn('Gestión de cobranza', self.customer.message_ids.mapped('body')[-1] + ''.join(
            self.customer.message_ids.mapped('body')))

    def test_manual_hold_only_manager_releases(self):
        self.customer.with_user(self.collector).action_l10n_pe_collection_hold()
        self.assertEqual(self.customer.with_company(self.company).l10n_pe_collection_hold, 'manual')
        with self.assertRaises(UserError):
            self.customer.with_user(self.collector).action_l10n_pe_collection_release()

    # ------------------------------------------------------------------ intereses
    def test_interest_statement_and_debit_note(self):
        self.company.l10n_pe_collection_interest_rate = 20.0
        invoice = self._invoice(1000, -36)
        line = self._receivable(invoice)
        amount, amount_company, days = self.customer._l10n_pe_collection_interest(line, self.today, self.company)
        self.assertEqual(days, 36)
        self.assertAlmostEqual(amount, 18.40, places=2)  # 1000 × (1.2^(36/360) − 1)
        values = self.customer._l10n_pe_collection_statement_values(self.company)
        self.assertAlmostEqual(values['interest'], 18.40, places=2)
        self.assertEqual(values['total'], 1000.0, 'el interés no facturado no suma al total')
        wizard = self.env['l10n_pe.collection.interest.wizard'].create({
            'partner_ids': [Command.set(self.customer.ids)], 'date': self.today})
        self.assertEqual(len(wizard.line_ids), 1)
        action = wizard.action_create()
        note = self.env['account.move'].browse(action['res_id'])
        self.assertEqual(note.state, 'draft')
        self.assertEqual(note.debit_origin_id, invoice)
        self.assertAlmostEqual(note.amount_untaxed, 18.40, places=2)
        if 'l10n_pe_edi_charge_reason' in note._fields:
            self.assertEqual(note.l10n_pe_edi_charge_reason, '01')
        line.invalidate_recordset(['l10n_pe_collection_interest_date'])
        self.assertEqual(line.l10n_pe_collection_interest_date, self.today)
        self.assertEqual(self.customer._l10n_pe_collection_interest(line, self.today, self.company)[0], 0.0)
        note.button_cancel()
        line.invalidate_recordset(['l10n_pe_collection_interest_date'])
        self.assertFalse(line.l10n_pe_collection_interest_date, 'la nota anulada no cuenta')

    def test_partner_rate_and_disputed_lines(self):
        self.company.l10n_pe_collection_interest_rate = 20.0
        self.customer.with_company(self.company).l10n_pe_collection_interest_rate = 10.0
        invoice = self._invoice(1000, -36)
        line = self._receivable(invoice)
        amount = self.customer._l10n_pe_collection_interest(line, self.today, self.company)[0]
        self.assertAlmostEqual(amount, 9.58, places=2)  # 1000 × (1.1^(0.1) − 1)
        self._dispute(invoice)
        self.assertEqual(self.customer._l10n_pe_collection_interest(line, self.today, self.company)[0], 0.0)

    # ------------------------------------------------------------------ provisión y castigo
    def _provision_journal(self):
        # Código propio: la base puede tener ya un diario «PROV» de datos reales.
        return self.env['account.journal'].create({'name': 'Provisiones (prueba)', 'code': 'TPRV', 'type': 'general'})

    def test_provision_requires_actions_and_posts(self):
        old = self._invoice(1000, -400, invoice_date=self.today - timedelta(days=430))
        unsupported = self._invoice(500, -400, partner=self.other_customer,
                                    invoice_date=self.today - timedelta(days=430))
        recent = self._invoice(300, -100)
        self.env['l10n_pe.collection.action'].create({
            'partner_id': self.customer.id, 'user_id': self.collector.id, 'channel': 'email',
            'result_id': self.result_no_answer.id})
        provision = self.env['l10n_pe.collection.provision'].create({'journal_id': self._provision_journal().id})
        provision.action_load()
        by_move = {line.move_id: line for line in provision.line_ids}
        self.assertNotIn(recent, by_move)
        self.assertTrue(by_move[old].selected and by_move[old].supported)
        self.assertEqual(by_move[old].action_count, 1)
        self.assertFalse(by_move[unsupported].selected)
        by_move[unsupported].selected = True
        with self.assertRaises(UserError):
            provision.action_post()
        by_move[unsupported].judicial = True
        provision.action_post()
        self.assertEqual(provision.state, 'posted')
        self.assertEqual(provision.move_id.state, 'posted')
        self.assertAlmostEqual(provision.amount, 1500.0)
        provision_account = self.company._l10n_pe_collection_account('l10n_pe_collection_provision_account_id')
        self.assertAlmostEqual(sum(provision.move_id.line_ids.filtered(
            lambda l: l.account_id == provision_account).mapped('credit')), 1500.0)
        # La estimación (19) no es cartera.
        self.env['l10n_pe.collection.portfolio'].flush_model()
        portfolio = self.env['l10n_pe.collection.portfolio'].search(
            self.env['l10n_pe.collection.portfolio'].action_open()['domain'])
        self.assertNotIn(provision_account, portfolio.account_id)
        # Una segunda provisión no repite los documentos.
        again = self.env['l10n_pe.collection.provision'].create({'journal_id': provision.journal_id.id})
        again.action_load()
        self.assertFalse(again.line_ids.filtered(lambda l: l.move_id in (old | unsupported)))

    def test_provision_recovery_and_write_off(self):
        old = self._invoice(1000, -400, invoice_date=self.today - timedelta(days=430))
        self.env['l10n_pe.collection.action'].create({
            'partner_id': self.customer.id, 'user_id': self.collector.id, 'channel': 'letter',
            'result_id': self.result_no_answer.id})
        provision = self.env['l10n_pe.collection.provision'].create({'journal_id': self._provision_journal().id})
        provision.action_load()
        provision.action_post()
        self._pay(old, amount=300)
        line = provision.line_ids
        self.assertAlmostEqual(line.recoverable_amount, 300.0)
        provision.action_recover()
        self.assertAlmostEqual(line.recovered_amount, 300.0)
        self.assertAlmostEqual(line.recoverable_amount, 0.0)
        self.assertTrue(line.write_off_allowed, '1000 ≤ 3 UIT')
        line.action_write_off()
        self.assertTrue(self._receivable(old).reconciled)
        self.assertAlmostEqual(line.write_off_amount, 700.0)
        with self.assertRaises(UserError):
            provision.action_cancel()

    def test_write_off_over_three_uit_needs_judicial(self):
        self.company.l10n_pe_collection_uit = 100.0
        self._invoice(1000, -400, invoice_date=self.today - timedelta(days=430))
        self.env['l10n_pe.collection.action'].create({
            'partner_id': self.customer.id, 'user_id': self.collector.id, 'channel': 'email',
            'result_id': self.result_no_answer.id})
        provision = self.env['l10n_pe.collection.provision'].create({'journal_id': self._provision_journal().id})
        provision.action_load()
        provision.action_post()
        line = provision.line_ids
        self.assertFalse(line.write_off_allowed)
        with self.assertRaises(UserError):
            line.action_write_off()
        line.judicial_exhausted = True
        line.action_write_off()
        self.assertTrue(line.write_off_move_id)

    def test_collector_has_no_provision_access(self):
        with self.assertRaises(AccessError):
            self.env['l10n_pe.collection.provision'].with_user(self.collector).search([])

    # ------------------------------------------------------------------ centrales de riesgo
    def _bureau(self, invoice):
        return self.env['l10n_pe.collection.bureau'].create({
            'partner_id': self.customer.id, 'user_id': self.collector.id, 'bureau': 'sentinel',
            'line_ids': [Command.set(self._receivable(invoice).ids)]})

    def test_bureau_flow(self):
        invoice = self._invoice(900, -45)
        report = self._bureau(invoice)
        report.action_send_notice()
        self.assertEqual(report.state, 'notified')
        self.assertEqual(report.date_eligible, self.today + timedelta(days=7))
        with self.assertRaises(UserError):
            report.action_report()  # aún en el plazo del aviso
        report.date_notice = self.today - timedelta(days=8)
        report.action_report()
        self.assertEqual((report.state, report.amount_reported), ('reported', 900.0))
        report._cron_collection_bureau()
        self.assertEqual(report.state, 'reported', 'sigue debiendo')
        self._pay(invoice)
        report._cron_collection_bureau()
        self.assertEqual(report.state, 'to_withdraw')
        self.assertTrue(report.activity_ids)
        report.action_withdraw()
        self.assertEqual(report.state, 'withdrawn')
        action = report.action_export_xlsx()
        self.assertEqual(action['type'], 'ir.actions.act_url')

    def test_bureau_rejects_disputed_not_due_and_old(self):
        disputed = self._invoice(100, -30)
        self._dispute(disputed)
        with self.assertRaises(UserError):
            self._bureau(disputed).action_send_notice()
        with self.assertRaises(UserError):
            self._bureau(self._invoice(100, 10)).action_send_notice()
        old = self._invoice(100, -(5 * 366 + 2), invoice_date=self.today - timedelta(days=5 * 366 + 10))
        with self.assertRaises(UserError):
            self._bureau(old).action_send_notice()

    def test_bureau_onchange_proposes_overdue_lines(self):
        overdue = self._invoice(100, -30)
        self._invoice(100, 10)
        with Form(self.env['l10n_pe.collection.bureau']) as form:
            form.partner_id = self.customer
            self.assertEqual(len(form.line_ids), 1)
        report = form.save()
        self.assertEqual(report.line_ids.move_id, overdue)

    # ------------------------------------------------------------------ expediente
    def test_collection_file_report(self):
        invoice = self._invoice(800, -20)
        self.env['l10n_pe.collection.action'].create({
            'partner_id': self.customer.id, 'user_id': self.collector.id, 'channel': 'email',
            'result_id': self.result_no_answer.id, 'note': 'Correo sin respuesta'})
        self._dispute(self._invoice(50, -5))
        self._promise(100, self.today + timedelta(days=3))
        html, _type = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_collection.report_collection_file', self.customer.ids)
        html = html.decode()
        for text in ('Expediente de cobranza', invoice.name, 'Correo sin respuesta', 'Compromisos de pago',
                     'Reclamos', 'En reclamo'):
            self.assertIn(text, html)
        self.assertEqual(self.customer.action_l10n_pe_collection_file()['report_name'],
                         'al_l10n_pe_collection.report_collection_file')

    def test_worklist_action(self):
        self._invoice(500, -50)
        self.customer._l10n_pe_collection_rate(self.company, fields.Date.context_today(self.customer))
        action = self.env['ir.actions.act_window']._for_xml_id('al_l10n_pe_collection.action_collection_worklist')
        partners = self.env['res.partner'].search(ast.literal_eval(action['domain']))
        self.assertIn(self.customer, partners)
        mine = self.env['res.partner'].with_user(self.collector).action_l10n_pe_collection_worklist()
        self.assertIn('search_default_mine', str(mine['context']), 'el gestor ve sus clientes')
        everyone = self.env['res.partner'].action_l10n_pe_collection_worklist()
        self.assertFalse(everyone['context'], 'el administrador ve a todos')
