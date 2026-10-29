# -*- coding: utf-8 -*-
from unittest.mock import patch

from stdnum.pe import ruc as stdnum_ruc

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.al_account_base.tests.common import use_pe_company

LOOKUP = 'odoo.addons.l10n_pe_vat_sunat.models.res_partner.ResPartner._l10n_pe_lookup_document'


@tagged('post_install', '-at_install')
class TestPartnerLookup(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.Partner = cls.env['res.partner']
        # Un RUC válido que no esté en la base (la de demostración tiene
        # varios contactos con el RUC de SUNAT).
        cls.ruc = next(
            number for number in (
                f'2060{index:06d}' + stdnum_ruc.calc_check_digit(f'2060{index:06d}')
                for index in range(1000))
            if not cls.Partner.with_context(active_test=False).search_count([('vat', '=', number)]))
        cls.ruc_values = {
            'name': 'SUPERINTENDENCIA NACIONAL DE ADUANAS Y DE ADMINISTRACION TRIBUTARIA',
            'company_type': 'company', 'street': 'AV. GARCILASO DE LA VEGA NRO. 1472',
        }

    def setUp(self):
        super().setUp()
        # Las pruebas simulan la consulta: las conexiones se dan por configuradas.
        self.patch(type(self.env['res.company']), '_l10n_pe_lookup_ready', lambda company, doc: True)

    def test_creates_partner_from_ruc(self):
        with patch(LOOKUP, return_value=self.ruc_values) as lookup:
            partner_id = self.Partner.l10n_pe_pos_create_from_document(self.ruc)
        partner = self.Partner.browse(partner_id)
        self.assertEqual(lookup.call_args.args[-1], '6')
        self.assertEqual(partner.vat, self.ruc)
        self.assertEqual(partner.l10n_pe_sunat_id_code, '6')
        self.assertTrue(partner.is_company)
        self.assertEqual(partner.street, 'AV. GARCILASO DE LA VEGA NRO. 1472')

    def test_dni_with_spaces(self):
        with patch(LOOKUP, return_value={'name': 'ROSA QUISPE HUAMAN', 'company_type': 'person'}) as lookup:
            partner = self.Partner.browse(self.Partner.l10n_pe_pos_create_from_document(' 4567 8901 '))
        self.assertEqual(lookup.call_args.args[-1], '1')
        self.assertEqual(partner.l10n_pe_sunat_id_value, '45678901')
        self.assertEqual(partner.l10n_pe_sunat_id_code, '1')
        self.assertEqual(partner.name, 'ROSA QUISPE HUAMAN')

    def test_existing_partner_is_returned_without_lookup(self):
        existing = self.Partner.create({
            'name': 'Cliente ya registrado', 'vat': self.ruc,
            'country_id': self.env.ref('base.pe').id})
        with patch(LOOKUP) as lookup:
            self.assertEqual(self.Partner.l10n_pe_pos_create_from_document(self.ruc), existing.id)
        lookup.assert_not_called()

    def test_not_found_and_bad_format(self):
        with patch(LOOKUP, return_value={}), self.assertRaisesRegex(UserError, 'No se encontraron'):
            self.Partner.l10n_pe_pos_create_from_document(self.ruc)
        with self.assertRaisesRegex(UserError, '11 dígitos'):
            self.Partner.l10n_pe_pos_create_from_document('12345')

    def test_requires_create_access(self):
        user = self.env['res.users'].create({
            'name': 'Solo portal', 'login': 'portal_lookup_pe',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]})
        with self.assertRaises(Exception):
            self.Partner.with_user(user).l10n_pe_pos_create_from_document(self.ruc)

    def test_lookup_without_token_says_what_is_missing(self):
        """Sin una conexión con token no se consulta: el cajero lee qué falta,
        no «no se encontraron datos»."""
        self.patch(type(self.env['res.company']), '_l10n_pe_lookup_ready', lambda company, doc: False)
        with patch(LOOKUP) as lookup, self.assertRaisesRegex(UserError, 'no está configurada'):
            self.Partner.l10n_pe_pos_create_from_document('45678901')
        lookup.assert_not_called()
