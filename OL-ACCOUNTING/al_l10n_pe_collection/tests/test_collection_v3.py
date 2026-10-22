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
        self.company.l10n_pe_collection_interest_rate = 12.0
        invoice = self._invoice(1000, -36)
        line = self._receivable(invoice)
        amount, amount_company, days = self.customer._l10n_pe_collection_interest(line, self.today, self.company)
        self.assertEqual(days, 36)
        self.assertAlmostEqual(amount, 11.40, places=2)  # 1000 × (1.12^(36/360) − 1)
        values = self.customer._l10n_pe_collection_statement_values(self.company)
        self.assertAlmostEqual(values['interest'], 11.40, places=2)
        self.assertEqual(values['total'], 1000.0, 'el interés no facturado no suma al total')
        wizard = self.env['l10n_pe.collection.interest.wizard'].create({
            'partner_ids': [Command.set(self.customer.ids)], 'date': self.today})
        self.assertEqual(len(wizard.line_ids), 1)
        action = wizard.action_create()
        note = self.env['account.move'].browse(action['res_id'])
        self.assertEqual(note.state, 'draft')
        self.assertEqual(note.debit_origin_id, invoice)
        self.assertAlmostEqual(note.amount_untaxed, 11.40, places=2)
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

    def _rate_caps(self, *periods):
        """Reemplaza las tasas máximas del BCRP por las de la prueba: (desde, hasta, moratorio)."""
        caps = self.env['l10n_pe.collection.rate.cap']
        caps.search([]).unlink()
        for date_from, date_to, moratory in periods:
            for currency_type in ('pen', 'foreign'):
                caps.create({'date_from': date_from, 'date_to': date_to, 'currency_type': currency_type,
                             'compensatory_rate': moratory / 0.15, 'moratory_rate': moratory})

    def test_rate_cap_moratory_is_15_percent_and_periods_do_not_overlap(self):
        cap = self.env['l10n_pe.collection.rate.cap'].create({
            'date_from': '2030-05-01', 'date_to': '2030-10-31', 'currency_type': 'pen', 'compensatory_rate': 114.13})
        self.assertAlmostEqual(cap.moratory_rate, 17.12, places=2)
        with self.assertRaises(ValidationError):
            self.env['l10n_pe.collection.rate.cap'].create({
                'date_from': '2030-10-01', 'date_to': '2031-03-31', 'currency_type': 'pen', 'compensatory_rate': 100})
        self.env['l10n_pe.collection.rate.cap'].create({
            'date_from': '2030-10-01', 'date_to': '2031-03-31', 'currency_type': 'foreign', 'compensatory_rate': 100})

    def test_seeded_bcrp_caps(self):
        cap = self.env.ref('al_l10n_pe_collection.rate_cap_2026_11_pen')
        self.assertEqual((cap.compensatory_rate, cap.moratory_rate), (114.68, 17.2))
        self.assertAlmostEqual(self.env.ref('al_l10n_pe_collection.rate_cap_2026_05_foreign').moratory_rate, 14.98)

    def test_interest_is_capped_per_period(self):
        """Tramo antiguo con tope 10 % y tramo actual con tope 30 %: la tasa pactada de 20 % se
        recorta solo en el primero."""
        self._rate_caps((self.today - timedelta(days=60), self.today - timedelta(days=21), 10.0),
                        (self.today - timedelta(days=20), self.today + timedelta(days=100), 30.0))
        self.company.l10n_pe_collection_interest_rate = 20.0
        line = self._receivable(self._invoice(1000, -36))
        detail = self.customer._l10n_pe_collection_interest_detail(line, self.today, self.company)
        expected = 1000 * (1.1 ** (16 / 360) * 1.2 ** (20 / 360) - 1)
        self.assertAlmostEqual(detail['amount'], round(expected, 2), places=2)
        self.assertEqual((detail['days'], detail['capped'], detail['uncovered']), (36, True, 0))

        wizard = self.env['l10n_pe.collection.interest.wizard'].create({
            'partner_ids': [Command.set(self.customer.ids)], 'date': self.today})
        self.assertTrue(wizard.line_ids.capped)
        self.assertIn('tope', wizard.cap_warning)
        note = self.env['account.move'].browse(wizard.action_create()['res_id'])
        self.assertAlmostEqual(note.amount_untaxed, round(expected, 2), places=2)
        self.assertIn('tope del BCRP', note.invoice_line_ids.name)

    def test_interest_without_registered_cap_uses_agreed_rate(self):
        self._rate_caps()
        self.company.l10n_pe_collection_interest_rate = 20.0
        line = self._receivable(self._invoice(1000, -36))
        detail = self.customer._l10n_pe_collection_interest_detail(line, self.today, self.company)
        self.assertAlmostEqual(detail['amount'], 18.40, places=2)  # 1000 × (1.2^(36/360) − 1)
        self.assertEqual((detail['capped'], detail['uncovered']), (False, 36))
        wizard = self.env['l10n_pe.collection.interest.wizard'].create({
            'partner_ids': [Command.set(self.customer.ids)], 'date': self.today})
        self.assertIn('sin tasa máxima', wizard.cap_warning)

    def test_rate_warning_on_settings_and_partner(self):
        caps = self.env['l10n_pe.collection.rate.cap']
        caps.search([]).unlink()
        start, end = self.today - timedelta(days=10), self.today + timedelta(days=100)
        caps.create({'date_from': start, 'date_to': end, 'currency_type': 'pen', 'compensatory_rate': 114.13})
        caps.create({'date_from': start, 'date_to': end, 'currency_type': 'foreign', 'compensatory_rate': 99.84})
        settings = self.env['res.config.settings'].with_company(self.company).create({})
        settings.l10n_pe_collection_interest_rate = 10.0
        self.assertFalse(settings.l10n_pe_collection_interest_warning)
        settings.l10n_pe_collection_interest_rate = 16.0
        warning = settings.l10n_pe_collection_interest_warning
        self.assertIn('14,98 % en moneda extranjera', warning)
        self.assertNotIn('soles', warning)
        partner = self.customer.with_company(self.company)
        partner.l10n_pe_collection_interest_rate = 20.0
        self.assertIn('17,12 % en soles', partner.l10n_pe_collection_interest_warning)
        caps.search([]).unlink()
        partner.invalidate_recordset(['l10n_pe_collection_interest_warning'])
        self.assertIn('No hay tasas máximas', partner.l10n_pe_collection_interest_warning)

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

    # ------------------------------------------------------------------ pago en línea
    def _online_provider(self):
        return self.env['payment.provider'].create({
            'name': 'Pasarela de prueba', 'code': 'none', 'state': 'test', 'company_id': self.company.id})

    def test_payment_url_needs_online_provider_and_balance(self):
        from odoo.addons.payment import utils as payment_utils
        self.env['payment.provider'].search([('code', '!=', 'custom'), ('state', '!=', 'disabled'),
                                             ('company_id', '=', self.company.id)]).state = 'disabled'
        self._invoice(300, -10)
        self.assertFalse(self.customer._l10n_pe_collection_payment_url(self.company), 'sin pasarela en línea')
        self._online_provider()
        url = self.customer._l10n_pe_collection_payment_url(self.company)
        self.assertIn('/payment/pay?', url)
        self.assertIn('reference=COB', url)
        params = dict(item.split('=', 1) for item in url.split('?', 1)[1].split('&'))
        # El mismo token que valida la ruta /payment/pay (que lo calcula con su request.env).
        self.assertEqual(params['access_token'], payment_utils.generate_access_token(
            self.customer.id, 300.0, self.company.currency_id.id, env=self.env))
        self.company.l10n_pe_collection_online_payment = False
        self.assertFalse(self.customer._l10n_pe_collection_payment_url(self.company), 'desactivado')
        self.company.l10n_pe_collection_online_payment = True
        self.assertFalse(self.other_customer._l10n_pe_collection_payment_url(self.company), 'sin saldo')

    def test_payment_link_in_statement_and_mail(self):
        self._online_provider()
        self._invoice(300, -10)
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_collection.report_statement', self.customer.ids)[0].decode()
        self.assertIn('/report/barcode/?barcode_type=QR', html)
        self.assertIn('Pague en línea', html)
        body = self.env.ref('al_l10n_pe_collection.mail_template_followup_overdue')._render_field(
            'body_html', self.customer.ids)[self.customer.id]
        self.assertIn('Pagar en línea', body)
        self.assertIn('/payment/pay?', body)

    def test_balance_payment_goes_to_oldest_invoices(self):
        old = self._invoice(300, -20)
        newer = self._invoice(200, -5)
        self.assertEqual(self.customer._l10n_pe_collection_fifo_invoices(250, self.company), old)
        self.assertEqual(self.customer._l10n_pe_collection_fifo_invoices(350, self.company), old | newer)
        provider = self._online_provider()
        provider.journal_id = self.bank
        # La pasarela de prueba no crea su método de pago en el diario: se crea como en account_payment.
        Method = self.env['account.payment.method'].sudo()
        method = Method.search([('code', '=', 'none'), ('payment_type', '=', 'inbound')], limit=1) or Method.create(
            {'name': 'Pasarela de prueba', 'code': 'none', 'payment_type': 'inbound'})
        if not self.bank.inbound_payment_method_line_ids.filtered(lambda l: l.payment_provider_id == provider):
            self.bank.inbound_payment_method_line_ids = [Command.create({
                'payment_method_id': method.id, 'payment_provider_id': provider.id,
                'payment_account_id': self.bank.inbound_payment_method_line_ids[:1].payment_account_id.id})]
        tx = self.env['payment.transaction'].create({
            'provider_id': provider.id, 'payment_method_id': self.env.ref('payment.payment_method_unknown').id,
            'amount': 300.0, 'currency_id': self.company.currency_id.id, 'partner_id': self.customer.id,
            'reference': 'COB-%s' % self.customer.id, 'operation': 'online_redirect',
        })
        tx._set_done()
        tx._post_process()
        self.assertTrue(tx.payment_id)
        self.assertEqual(tx.invoice_ids, old)
        self.assertIn(old.payment_state, ('paid', 'in_payment'))
        self.assertEqual(newer.payment_state, 'not_paid')
