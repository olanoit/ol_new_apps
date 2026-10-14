# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.al_website_sale_pe.controllers.main import MAX_LOOKUPS_PER_SESSION

LOOKUP = 'odoo.addons.l10n_pe_vat_sunat.models.res_partner.ResPartner._l10n_pe_lookup_document'
ROUTE = '/shop/l10n_pe/document_lookup'


@tagged('post_install', '-at_install')
class TestWebsiteSalePe(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref('base.main_company')
        if cls.company.country_id.code != 'PE':
            cls.skipTest(cls, 'la compañía principal no es peruana')
        cls.website = cls.env['website'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.ruc_type = cls.env.ref('l10n_pe.it_RUC')
        cls.dni_type = cls.env.ref('l10n_pe.it_DNI')
        cls.portal_user = new_test_user(cls.env, login='pe_portal_shop', groups='base.group_portal')
        cls.portal_user.partner_id.write({
            'country_id': cls.env.ref('base.pe').id,
            'l10n_latam_identification_type_id': cls.dni_type.id,
        })

    def setUp(self):
        super().setUp()
        # Con varias bases en el servidor, la sesión anónima debe fijar la
        # base de la prueba para que la ruta pública la encuentre.
        self.authenticate(None, None)

    def _lookup(self, number, identification_type):
        return self.make_jsonrpc_request(ROUTE, {
            'number': number, 'identification_type_id': identification_type.id})

    def test_lookup_returns_values(self):
        values = {'name': 'SUNAT', 'street': 'AV. GARCILASO DE LA VEGA 1472', 'state_id': False}
        with patch(LOOKUP, return_value=values) as lookup:
            result = self._lookup('20131312955', self.ruc_type)
        self.assertTrue(result['found'])
        self.assertEqual(result['values']['name'], 'SUNAT')
        self.assertEqual(lookup.call_args.args[-2:], ('20131312955', self.ruc_type))

    def test_lookup_not_found(self):
        with patch(LOOKUP, return_value={}):
            result = self._lookup('20131312955', self.ruc_type)
        self.assertFalse(result['found'])
        self.assertIn('a mano', result['message'])

    def test_lookup_only_for_ruc_and_dni(self):
        passport = self.env['l10n_latam.identification.type'].search(
            [('l10n_pe_vat_code', 'not in', ('1', '6'))], limit=1)
        with patch(LOOKUP) as lookup:
            result = self._lookup('AB123456', passport)
        lookup.assert_not_called()
        self.assertFalse(result['found'])

    def test_lookups_are_limited_per_session(self):
        with patch(LOOKUP, return_value={'name': 'ROSA QUISPE'}) as lookup:
            for _index in range(MAX_LOOKUPS_PER_SESSION):
                self.assertTrue(self._lookup('45678901', self.dni_type)['found'])
            result = self._lookup('45678901', self.dni_type)
        self.assertFalse(result['found'])
        self.assertIn('límite', result['message'])
        self.assertEqual(lookup.call_count, MAX_LOOKUPS_PER_SESSION)

    def test_address_form_shows_receipt_and_lookup(self):
        self.authenticate('pe_portal_shop', 'pe_portal_shop')
        response = self.url_open('/my/account')
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn('id="l10n_pe_receipt_boleta"', html)
        self.assertIn('id="l10n_pe_receipt_factura"', html)
        self.assertIn(f'data-identification-type-id="{self.ruc_type.id}"', html)
        self.assertIn('o_l10n_pe_document_lookup', html)
        # Con DNI, la boleta queda marcada.
        boleta = html[html.index('id="l10n_pe_receipt_boleta"') - 300:html.index('id="l10n_pe_receipt_boleta"') + 300]
        self.assertIn('checked', boleta)
