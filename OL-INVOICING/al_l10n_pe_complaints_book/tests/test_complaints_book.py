from datetime import date, datetime

from freezegun import freeze_time

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user

# 02/10/2026 es viernes; 10:00 en Lima son las 15:00 UTC.
SUBMITTED = datetime(2026, 10, 2, 15, 0)


@tagged('post_install', '-at_install')
class TestComplaintsBook(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Lunes a viernes (reclamos)', 'tz': 'America/Lima', 'company_id': cls.company.id})
        cls.company.write({'l10n_pe_complaint_calendar_id': cls.calendar.id,
                           'l10n_pe_complaint_alert_days': 5})
        cls.responsible = new_test_user(cls.env, login='atencion_reclamos',
                                        groups='al_l10n_pe_complaints_book.group_complaint_user',
                                        tz='America/Lima')
        cls.book = cls.env['l10n_pe.complaint.book'].create({
            'name': 'Tienda virtual', 'code': 'TV-TEST', 'book_type': 'virtual',
            'user_ids': [(6, 0, cls.responsible.ids)], 'sirec_site_code': '123456',
        })
        cls.env = cls.env(context=dict(cls.env.context, tz='America/Lima'))

    def _complaint(self, **vals):
        values = {
            'book_id': self.book.id,
            'consumer_name': 'Rosa Quispe Mamani',
            'consumer_doc_type': 'dni',
            'consumer_doc_number': '45678912',
            'consumer_address': 'Av. Arequipa 123, Lima',
            'consumer_email': 'rosa@example.com',
            'consumer_phone': '987654321',
            'good_type': 'product',
            'amount_claimed': 150.0,
            'good_description': 'Licuadora',
            'claim_type': 'claim',
            'detail': 'La licuadora llegó con la jarra rota.',
            'consumer_request': 'Cambio del producto.',
            'date_submitted': SUBMITTED,
        }
        values.update(vals)
        return self.env['l10n_pe.complaint'].create(values)

    # ------------------------------------------------------------------
    # Numeración y datos mínimos
    # ------------------------------------------------------------------

    def test_correlative_number_per_book_and_year(self):
        first, second = self._complaint(), self._complaint()
        self.assertEqual(first.name, '000000001-2026')
        self.assertEqual(second.name, '000000002-2026')
        other = self.env['l10n_pe.complaint.book'].create({'name': 'Local Miraflores', 'code': 'MF-TEST'})
        self.assertEqual(self._complaint(book_id=other.id).name, '000000001-2026', 'cada libro numera aparte')
        self.assertEqual(self._complaint(date_submitted=datetime(2027, 1, 5, 15)).name, '000000001-2027')

    def test_minimum_data_or_not_presented(self):
        """Art. 5: sin nombre, documento, domicilio o correo y detalle, no se tiene por presentada."""
        with self.assertRaises(ValidationError):
            self._complaint(detail=' ')
        with self.assertRaises(ValidationError):
            self._complaint(consumer_address=False, consumer_email=False,
                            preferred_response_channel='letter')
        with self.assertRaisesRegex(ValidationError, 'DNI'):
            self._complaint(consumer_doc_number='1234567')
        with self.assertRaisesRegex(ValidationError, 'representante'):
            self._complaint(is_minor=True)
        self._complaint(consumer_address=False)  # el correo basta

    def test_response_channel_needs_its_data(self):
        with self.assertRaisesRegex(ValidationError, 'correo'):
            self._complaint(consumer_email=False)
        with self.assertRaisesRegex(ValidationError, 'domicilio'):
            self._complaint(consumer_address=False, preferred_response_channel='letter')

    # ------------------------------------------------------------------
    # Plazo de 15 días hábiles
    # ------------------------------------------------------------------

    def test_deadline_is_fifteen_business_days(self):
        complaint = self._complaint()
        # Desde el lunes 05/10: 5, 12 y 19 de octubre empiezan las tres semanas.
        self.assertEqual(complaint.deadline_date, date(2026, 10, 23))

    def test_holidays_extend_the_deadline(self):
        self.env['resource.calendar.leaves'].create({
            'name': 'Combate de Angamos', 'calendar_id': self.calendar.id,
            'date_from': datetime(2026, 10, 8, 5, 0), 'date_to': datetime(2026, 10, 9, 4, 59),
        })
        self.assertEqual(self._complaint().deadline_date, date(2026, 10, 26))

    def test_without_calendar_counts_weekdays(self):
        self.company.l10n_pe_complaint_calendar_id = False
        self.company.resource_calendar_id = False
        self.assertEqual(self._complaint().deadline_date, date(2026, 10, 23))

    def test_overdue(self):
        complaint = self._complaint()
        with freeze_time('2026-10-23 17:00'):
            complaint.invalidate_recordset(['is_overdue', 'days_left'])
            self.assertFalse(complaint.is_overdue)
            self.assertEqual(complaint.days_left, 0)
        with freeze_time('2026-10-26 17:00'):
            complaint.invalidate_recordset(['is_overdue', 'days_left'])
            self.assertTrue(complaint.is_overdue)
            self.assertEqual(complaint.days_left, -1)
            self.assertIn(complaint, self.env['l10n_pe.complaint'].search([('is_overdue', '=', True)]))

    # ------------------------------------------------------------------
    # Constancia y respuesta
    # ------------------------------------------------------------------

    def _mails_to(self, email):
        return self.env['mail.mail'].search([('email_to', 'ilike', email)])

    def test_acknowledgement_with_the_sheet(self):
        complaint = self._complaint()
        mail = self._mails_to('rosa@example.com')
        self.assertEqual(len(mail), 1)
        self.assertIn(complaint.name, mail.subject)
        self.assertTrue(mail.attachment_ids.filtered(lambda a: a.name.endswith('.pdf')))
        self.assertTrue(complaint.ack_sent_date)
        self.assertIn(self.responsible.partner_id, complaint.message_partner_ids)

    def test_response_flow(self):
        complaint = self._complaint()
        complaint.with_user(self.responsible).action_start()
        self.assertEqual(complaint.state, 'in_progress')
        with self.assertRaisesRegex(UserError, 'observaciones'):
            complaint.action_send_response()
        complaint.provider_observations = 'Cambiamos la licuadora el 05/10/2026.'
        with freeze_time('2026-10-06 17:00'):
            complaint.with_user(self.responsible).action_send_response()
        self.assertEqual(complaint.state, 'answered')
        self.assertEqual(complaint.response_date, date(2026, 10, 6))
        self.assertEqual(len(self._mails_to('rosa@example.com')), 2)
        complaint.action_close()
        self.assertEqual(complaint.state, 'closed')

    def test_letter_response_does_not_email(self):
        complaint = self._complaint(preferred_response_channel='letter')
        complaint.provider_observations = 'Respuesta por carta.'
        complaint.action_send_response()
        self.assertEqual(len(self._mails_to('rosa@example.com')), 1, 'solo la constancia')

    def test_consumer_data_is_frozen_once_handled(self):
        complaint = self._complaint()
        complaint.detail = 'Corrección antes de atender.'
        complaint.action_start()
        with self.assertRaisesRegex(UserError, 'no se modifica'):
            complaint.with_user(self.responsible).detail = 'Otro texto'

    def test_reclassify_complaint_as_claim(self):
        complaint = self._complaint(claim_type='complaint')
        complaint.action_reclassify_as_claim()
        self.assertEqual(complaint.claim_type, 'claim')
        self.assertEqual(complaint.original_claim_type, 'complaint')

    # ------------------------------------------------------------------
    # Solución acordada (art. 6-A)
    # ------------------------------------------------------------------

    def _offer(self, complaint, mode='remote', accepted=False):
        wizard = self.env['l10n_pe.complaint.settlement.wizard'].create({
            'complaint_id': complaint.id, 'mode': mode, 'offer': 'Cambio inmediato del producto.',
            'accepted': accepted})
        wizard.action_confirm()

    def test_remote_offer_suspends_the_deadline(self):
        complaint = self._complaint()
        with freeze_time('2026-10-06 17:00'):
            self._offer(complaint)
        self.assertEqual(complaint.state, 'suspended')
        with freeze_time('2026-10-09 17:00'):
            complaint.action_settlement_rejected()
        self.assertEqual(complaint.suspension_days, 3)
        self.assertEqual(complaint.deadline_date, date(2026, 10, 28))
        self.assertEqual(complaint.state, 'in_progress')

    def test_suspension_is_at_most_five_business_days(self):
        complaint = self._complaint()
        with freeze_time('2026-10-06 17:00'):
            self._offer(complaint)
        with freeze_time('2026-10-20 17:00'):
            self.env['l10n_pe.complaint']._cron_deadline_alerts()
        self.assertEqual(complaint.state, 'in_progress')
        self.assertEqual(complaint.suspension_days, 5)

    def test_accepted_offer_ends_the_claim(self):
        complaint = self._complaint()
        with freeze_time('2026-10-06 17:00'):
            self._offer(complaint)
            complaint.action_settlement_accepted()
        self.assertEqual(complaint.state, 'settled')
        complaint.action_close()

    def test_in_person_offer_needs_the_signature(self):
        complaint = self._complaint()
        with self.assertRaisesRegex(UserError, 'firmando'):
            self._offer(complaint, mode='in_person')
        self._offer(complaint, mode='in_person', accepted=True)
        self.assertEqual(complaint.state, 'settled')

    # ------------------------------------------------------------------
    # Alertas, conservación, SIREC y multicompañía
    # ------------------------------------------------------------------

    def test_deadline_alerts(self):
        complaint = self._complaint()
        with freeze_time('2026-10-19 17:00'):
            self.env['l10n_pe.complaint']._cron_deadline_alerts()
        self.assertTrue(complaint.alert_sent)
        self.assertEqual(complaint.activity_ids.user_id, self.responsible)
        with freeze_time('2026-10-27 17:00'):
            complaint.invalidate_recordset(['is_overdue', 'days_left'])
            self.env['l10n_pe.complaint']._cron_deadline_alerts()
        self.assertTrue(complaint.overdue_alert_sent)
        self.assertEqual(len(complaint.activity_ids), 2)

    def test_retention_of_two_years(self):
        complaint = self._complaint()
        self.assertEqual(complaint.retention_until, date(2028, 10, 2))
        with self.assertRaisesRegex(UserError, 'conservarse'):
            complaint.unlink()
        with freeze_time('2028-10-03 17:00'):
            complaint.unlink()

    def test_users_cannot_delete(self):
        complaint = self._complaint()
        with self.assertRaises(AccessError):
            complaint.with_user(self.responsible).unlink()

    def test_sirec_file(self):
        complaint = self._complaint(is_minor=True, guardian_name='Juan Quispe')
        complaint.provider_observations = 'Producto cambiado.'
        with freeze_time('2026-10-06 17:00'):
            complaint.action_send_response()
        wizard = self.env['l10n_pe.complaint.sirec.wizard'].create({
            'date_from': date(2026, 10, 1), 'date_to': date(2026, 10, 31),
            'book_ids': [(6, 0, self.book.ids)]})
        wizard.action_export()
        import base64
        rows = base64.b64decode(wizard.file).decode().split('\r\n')
        self.assertEqual(len(rows), 1)
        fields_ = rows[0].split('|')
        self.assertEqual(len(fields_), 18)
        self.assertEqual(fields_[:4], ['123456', '000000001', '2026', '2026-10-02'])
        self.assertEqual(fields_[9], 'Juan Quispe')
        self.assertEqual((fields_[10], fields_[13]), ('P', 'R'))
        self.assertEqual(fields_[16], '2026-10-06')
        self.assertEqual(complaint.sirec_state, 'reported')

    def test_sirec_needs_the_site_code(self):
        self.book.sirec_site_code = False
        self._complaint()
        wizard = self.env['l10n_pe.complaint.sirec.wizard'].create({
            'date_from': date(2026, 10, 1), 'date_to': date(2026, 10, 31),
            'book_ids': [(6, 0, self.book.ids)]})
        with self.assertRaisesRegex(UserError, 'código de sede'):
            wizard.action_export()

    def test_multi_company(self):
        complaint = self._complaint()
        other_company = self.env['res.company'].create({'name': 'Otra empresa SAC'})
        other_user = new_test_user(self.env, login='atencion_otra',
                                   groups='al_l10n_pe_complaints_book.group_complaint_manager',
                                   company_id=other_company.id, company_ids=[(6, 0, other_company.ids)])
        Complaint = self.env['l10n_pe.complaint'].with_user(other_user)
        self.assertFalse(Complaint.search([('id', '=', complaint.id)]))
        other_book = self.env['l10n_pe.complaint.book'].with_user(other_user).create(
            {'name': 'Tienda', 'code': 'TV-TEST'})
        self.assertEqual(other_book.company_id, other_company, 'el mismo código vale en otra compañía')
        sheet = Complaint.create({**self._complaint_vals(), 'book_id': other_book.id})
        self.assertEqual(sheet.company_id, other_company)
        self.assertEqual(sheet.name, '000000001-2026')

    def _complaint_vals(self):
        return {
            'consumer_name': 'Luis Torres', 'consumer_doc_number': '12345678',
            'consumer_email': 'luis@example.com', 'detail': 'Demora en la entrega.',
            'date_submitted': SUBMITTED,
        }

    def test_books_need_websites_of_their_company(self):
        other_company = self.env['res.company'].create({'name': 'Tercera SAC'})
        website = self.env['website'].create({'name': 'Otra web', 'company_id': other_company.id})
        with self.assertRaises(ValidationError):
            self.book.website_ids = website

    def test_notice_report(self):
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_complaints_book.action_report_book_notice', self.book.ids)[0]
        self.assertIn(b'Libro de Reclamaciones', html)
        self.assertIn(b'libroreclamaciones@indecopi.gob.pe', html)
        self.assertIn(b'(virtual)', html)

    def test_sheet_report_has_the_legal_notes(self):
        complaint = self._complaint()
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_complaints_book.action_report_complaint', complaint.ids)[0].decode()
        self.assertIn('HOJA DE RECLAMACIÓN', html)
        self.assertIn(complaint.name, html)
        self.assertIn('quince (15) días hábiles, el cual es improrrogable', html)
        self.assertIn('ni es requisito previo para interponer una denuncia ante el INDECOPI', html)
        self.assertIn('02/10/2026', html)
        self.assertIn('10:00', html, 'hora de Lima')
