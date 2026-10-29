# -*- coding: utf-8 -*-
"""Conexiones sin token: no se consultan y se dice qué falta (en la conexión,
en los Ajustes, en el contacto y al pulsar el botón)."""
from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, tagged
from odoo.addons.al_account_base.tests.common import use_pe_company


@tagged('post_install', '-at_install')
class TestTokenStatus(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.company = cls.env.company
        cls.company.write({'l10n_pe_ruc_validation': True, 'l10n_pe_dni_validation': True})
        cls.company.l10n_pe_api_connection_ids.enabled = False
        Connection = cls.env['l10n_pe.api.connection']
        cls.api = Connection.create({
            'name': 'API con token (test)', 'engine': 'rest_json', 'document_type': 'both',
            'company_id': cls.company.id, 'base_url': 'https://example.test',
            'endpoint_ruc': '/ruc/{doc}', 'endpoint_dni': '/dni/{doc}', 'auth_type': 'bearer',
            'signup_url': 'https://example.test/registro'})
        cls.sunat = Connection.create({
            'name': 'Portal sin token (test)', 'engine': 'sunat_oficial',
            'document_type': 'ruc', 'company_id': cls.company.id})

    def test_connection_shows_the_missing_token(self):
        self.assertTrue(self.api.needs_token)
        self.assertTrue(self.api.missing_token)
        self.assertFalse(self.sunat.needs_token)
        self.assertFalse(self.sunat.missing_token)
        self.api.token = 'abc'
        self.assertFalse(self.api.missing_token)

    def test_lookup_ready_by_document(self):
        # El RUC se consulta en el portal sin token; el DNI solo con la API.
        self.assertTrue(self.company._l10n_pe_lookup_ready('ruc'))
        self.assertFalse(self.company._l10n_pe_lookup_ready('dni'))
        message = self.company._l10n_pe_lookup_not_ready_message('dni')
        self.assertIn('API con token (test)', message)
        self.assertIn('token', message)
        self.api.token = 'abc'
        self.assertTrue(self.company._l10n_pe_lookup_ready('dni'))
        self.api.enabled = False
        self.assertIn('no hay ninguna conexión habilitada',
                      self.company._l10n_pe_lookup_not_ready_message('dni'))

    def test_partner_form_hides_the_lookup_without_token(self):
        # Odoo 20: el tipo de documento sale de los identificadores; sin
        # número, una persona se consulta por DNI y una empresa por RUC.
        partner = self.env['res.partner'].new({
            'name': 'X', 'company_type': 'person', 'country_id': self.env.ref('base.pe').id})
        self.assertEqual(partner.l10n_pe_lookup_state, 'missing')
        self.assertIn('API con token (test)', partner.l10n_pe_lookup_message)
        partner.company_type = 'company'
        self.assertEqual(partner.l10n_pe_lookup_state, 'ready')
        partner.additional_identifiers = {'PASSPORT': 'AB123456'}
        self.assertEqual(partner.l10n_pe_lookup_state, 'na')
        self.company.l10n_pe_dni_validation = False
        partner.additional_identifiers = {'PE_DNI': '45678901'}
        self.assertEqual(partner.l10n_pe_lookup_state, 'na')

    def test_typing_a_dni_without_token_is_not_an_api_failure(self):
        """Sin conexión utilizable no hubo consulta: no se marca «el servicio
        no respondió» y el botón explica qué falta."""
        with Form(self.env['res.partner']) as form:
            form.name = 'Cliente sin consulta'
            form.additional_identifiers = {'PE_DNI': '45678901'}
            self.assertFalse(form.alert_warning_vat)
            self.assertEqual(form.l10n_pe_lookup_state, 'missing')
            partner = form.save()
        with self.assertRaisesRegex(UserError, 'no está configurada'):
            partner.action_update_document()

    def test_settings_show_the_status(self):
        settings = self.env['res.config.settings'].create({})
        self.assertTrue(settings.l10n_pe_ruc_lookup_ready)
        self.assertFalse(settings.l10n_pe_dni_lookup_ready)
        self.assertEqual(settings.l10n_pe_lookup_missing_token, 'API con token (test)')
