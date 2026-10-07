# -*- coding: utf-8 -*-
"""Auditoría del 07/10/2026.

- El cron del padrón desmarcaba cada noche lo corregido a mano (y una
  factura de un agente de retención volvía a ser retenible).
- La ubicación por nombre distinguía tildes y resolvía un distrito suelto
  repetido en otra región.
- Respuestas de la API con formato inesperado rompían la consulta.
- Un RUC con dígito verificador inválido se consultaba igual.
"""
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.l10n_pe_vat_sunat.services import http as http_service
from odoo.addons.l10n_pe_vat_sunat.services import sunat_padron, ubigeo


@tagged('post_install', '-at_install')
class TestAudit20261007(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Padron = cls.env['l10n_pe.sunat.padron']
        cls.Padron.search([('kind', '=', 'retention_agent'), ('vat', '=', '20100070970')]).unlink()
        cls.Padron.create({'kind': 'retention_agent', 'vat': '20999999999'})
        cls.partner = cls.env['res.partner'].create({
            'name': 'Agente reciente SAC', 'vat': '20100070970', 'is_company': True})

    def test_manual_mark_survives_the_cron(self):
        self.partner.is_retention_agent = True
        self.assertTrue(self.partner.l10n_pe_padron_manual, 'contradice al padrón')
        sunat_padron._refresh_partners(self.env, 'retention_agent', {'20999999999'})
        self.assertTrue(self.partner.is_retention_agent)

    def test_automatic_values_are_not_manual(self):
        self.partner.with_context(l10n_pe_padron_auto=True).is_retention_agent = True
        self.assertFalse(self.partner.l10n_pe_padron_manual)
        sunat_padron._refresh_partners(self.env, 'retention_agent', {'20999999999'})
        self.assertFalse(self.partner.is_retention_agent, 'sin marca manual manda el padrón')

    def test_mark_back_in_line_with_padron_is_not_manual(self):
        self.partner.is_retention_agent = True
        self.partner.is_retention_agent = False
        self.assertFalse(self.partner.l10n_pe_padron_manual)

    def test_ubigeo_ignores_accents(self):
        district = self.env['l10n_pe.res.city.district'].search([('name', '=ilike', 'Jaén')], limit=1)
        if not district:
            self.skipTest('sin el distrito Jaén en el catálogo')
        vals = ubigeo.resolve_by_names(
            self.env, district='JAEN', city='JAEN', state='CAJAMARCA')
        self.assertEqual(vals.get('l10n_pe_district'), district.id)

    def test_ubigeo_repeated_district_is_not_guessed(self):
        Districts = self.env['l10n_pe.res.city.district']
        if Districts.search_count([('name', '=ilike', 'Santa Rosa')]) < 2:
            self.skipTest('sin distritos repetidos en el catálogo')
        vals = ubigeo.resolve_by_names(self.env, district='SANTA ROSA')
        self.assertNotIn('l10n_pe_district', vals)

    def test_invalid_ruc_check_digit(self):
        with self.assertRaises(UserError):
            self.env['res.partner']._validate_ruc('20100070971')
        self.env['res.partner']._validate_ruc('20100070970')

    def test_list_payload_is_a_connection_error(self):
        connection = self.env['l10n_pe.api.connection'].create({
            'name': 'API lista test', 'engine': 'rest_json', 'auth_type': 'none',
            'base_url': 'https://api.example.test', 'endpoint_ruc': '/ruc/{doc}'})
        response = MagicMock(status_code=200, text='[]')
        response.json.return_value = ['no es un objeto']
        with patch.object(http_service, 'request', return_value=response):
            with self.assertRaises(http_service.HttpError):
                connection._fetch_rest('20100070970', 'ruc')
