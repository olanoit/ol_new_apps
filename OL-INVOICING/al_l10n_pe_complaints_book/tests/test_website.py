import re
import time

from odoo.tests import HttpCase, tagged
from odoo.tools.misc import hmac


@tagged('post_install', '-at_install')
class TestComplaintsBookWebsite(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].search([('company_id', '=', cls.env.company.id)], limit=1)
        cls.book = cls.env['l10n_pe.complaint.book'].create({
            'name': 'Tienda virtual', 'code': 'WEB-TEST', 'book_type': 'virtual',
            'website_ids': [(6, 0, cls.website.ids)], 'notify_email': 'reclamos@example.com',
        })

    def setUp(self):
        super().setUp()
        # Servidor con varias bases: la sesión anónima fija la base de la prueba.
        self.authenticate(None, None)

    def _form_values(self, **values):
        page = self.url_open('/libro-reclamaciones')
        self.assertEqual(page.status_code, 200)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        timestamp = int(time.time()) - 30
        data = {
            'csrf_token': csrf,
            'form_ts': str(timestamp),
            'form_token': hmac(self.env(su=True), 'l10n_pe_complaint_form', str(timestamp)),
            'book_id': str(self.book.id),
            'consumer_name': 'Carmen Flores',
            'consumer_doc_type': 'dni',
            'consumer_doc_number': '41234567',
            'consumer_address': 'Jr. Lampa 456, Lima',
            'consumer_email': 'carmen@example.com',
            'good_type': 'service',
            'amount_claimed': '89.90',
            'good_description': 'Servicio de instalación',
            'claim_type': 'complaint',
            'detail': 'El técnico no llegó en la fecha acordada.',
            'consumer_request': 'Reprogramar la visita.',
            'preferred_response_channel': 'email',
            'consumer_confirmed': 'on',
        }
        data.update(values)
        return data

    def _complaints(self):
        return self.env['l10n_pe.complaint'].search([('book_id', '=', self.book.id)])

    def test_form_is_public(self):
        page = self.url_open('/libro-reclamaciones')
        self.assertEqual(page.status_code, 200)
        self.assertIn('IDENTIFICACIÓN DEL CONSUMIDOR'.lower(), page.text.lower())
        self.assertIn('quince (15) días hábiles', ' '.join(page.text.split()))
        self.assertIn(self.env.company.name, page.text)

    def test_submit_creates_the_sheet(self):
        response = self.url_open('/libro-reclamaciones/enviar', data=self._form_values())
        complaint = self._complaints()
        self.assertEqual(len(complaint), 1)
        self.assertEqual(complaint.channel, 'web')
        self.assertTrue(complaint.consumer_confirmed)
        self.assertEqual(complaint.claim_type, 'complaint')
        self.assertEqual(complaint.amount_claimed, 89.90)
        self.assertRegex(complaint.name, r'^\d{9}-\d{4}$')
        self.assertIn('/libro-reclamaciones/hoja/%s' % complaint.id, response.url)
        self.assertIn(complaint.name, response.text)
        self.assertTrue(self.env['mail.mail'].search([('email_to', 'ilike', 'carmen@example.com')]))
        self.assertTrue(self.env['mail.mail'].search([('email_to', 'ilike', 'reclamos@example.com')]))

    def test_pdf_with_token_only(self):
        self.url_open('/libro-reclamaciones/enviar', data=self._form_values())
        complaint = self._complaints()
        token = complaint.sudo()._portal_ensure_token()
        ok = self.url_open('/libro-reclamaciones/hoja/%s/pdf?access_token=%s' % (complaint.id, token))
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.url_open('/libro-reclamaciones/hoja/%s?access_token=falso'
                                       % complaint.id).status_code, 404)
        self.assertEqual(self.url_open('/libro-reclamaciones/hoja/%s/pdf' % complaint.id).status_code, 404)

    def test_required_data(self):
        response = self.url_open('/libro-reclamaciones/enviar', data=self._form_values(
            detail='', consumer_email='', consumer_address=''))
        self.assertFalse(self._complaints())
        self.assertIn('Describa su reclamo o queja', response.text)
        self.assertIn('domicilio o su correo', response.text)

    def test_honeypot_and_fast_bots(self):
        self.url_open('/libro-reclamaciones/enviar', data=self._form_values(website_url='http://spam'))
        now = int(time.time())
        self.url_open('/libro-reclamaciones/enviar', data=self._form_values(
            form_ts=str(now),
            form_token=hmac(self.env(su=True), 'l10n_pe_complaint_form', str(now))))
        self.url_open('/libro-reclamaciones/enviar', data=self._form_values(form_token='falso'))
        self.assertFalse(self._complaints())

    def test_minor_needs_a_guardian(self):
        response = self.url_open('/libro-reclamaciones/enviar', data=self._form_values(is_minor='on'))
        self.assertFalse(self._complaints())
        self.assertIn('padre, la madre o el representante', response.text)

    def test_footer_link_on_every_page(self):
        home = self.url_open('/')
        self.assertIn('href="/libro-reclamaciones"', home.text)
        self.website.l10n_pe_complaint_show_link = False
        self.assertNotIn('href="/libro-reclamaciones"', self.url_open('/').text)

    def test_no_book_no_form(self):
        self.env['l10n_pe.complaint.book'].search([('website_ids', 'in', self.website.ids)]).write(
            {'website_ids': [(3, self.website.id)]})
        self.assertEqual(self.url_open('/libro-reclamaciones').status_code, 404)
