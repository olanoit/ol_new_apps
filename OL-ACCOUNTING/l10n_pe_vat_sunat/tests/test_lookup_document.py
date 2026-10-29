# -*- coding: utf-8 -*-
"""Consulta de RUC/DNI sin crear el contacto (``_l10n_pe_lookup_document``),
la que usan el TPV y la tienda en línea."""
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.al_account_base.tests.common import use_pe_company


@tagged('post_install', '-at_install')
class TestLookupDocument(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)
        cls.env.company.write({'l10n_pe_ruc_validation': True, 'l10n_pe_dni_validation': True})
        cls.connection = cls.env['l10n_pe.api.connection'].create({
            'name': 'API consulta test', 'engine': 'rest_json', 'auth_type': 'none',
            'base_url': 'https://api.example.test', 'endpoint_ruc': '/ruc/{doc}'})
        cls.ruc_type = '6'  # catálogo 06 de SUNAT
        cls.district = cls.env['l10n_pe.res.city.district'].search([('city_id', '!=', False)], limit=1)
        cls.Partner = cls.env['res.partner']

    def _lookup(self, number, id_type, vals=None, side_effect=None):
        connection_cls = type(self.connection)
        company_cls = type(self.env['res.company'])
        with patch.object(company_cls, '_get_pe_api_connections', return_value=self.connection), \
                patch.object(connection_cls, 'run', return_value=(vals or {}, {}), side_effect=side_effect) as run:
            result = self.Partner._l10n_pe_lookup_document(number, id_type)
        return result, run

    def test_ruc_returns_form_values_without_creating_a_partner(self):
        count = self.Partner.search_count([])
        city = self.district.city_id
        result, run = self._lookup('20131312955', self.ruc_type, {
            'name': 'SUPERINTENDENCIA NACIONAL DE ADUANAS Y DE ADMINISTRACION TRIBUTARIA',
            'street': 'AV. GARCILASO DE LA VEGA NRO. 1472',
            'l10n_pe_district': self.district.id, 'city_id': city.id,
            'state_id': city.state_id.id, 'zip': self.district.code,
        })
        run.assert_called_once()
        self.assertEqual(result['name'][:28], 'SUPERINTENDENCIA NACIONAL DE')
        self.assertEqual(result['company_type'], 'company')
        self.assertEqual(result['l10n_pe_district'], self.district.id)
        self.assertEqual(result['city_id'], city.id)
        self.assertEqual(result['city'], city.name)
        self.assertEqual(self.Partner.search_count([]), count)

    def test_invalid_ruc_is_not_queried(self):
        result, run = self._lookup('20131312954', self.ruc_type)
        run.assert_not_called()
        self.assertEqual(result, {})

    def test_failed_connection_returns_empty(self):
        result, _run = self._lookup('20131312955', self.ruc_type, side_effect=ValueError('caída'))
        self.assertEqual(result, {})

    def test_other_document_types_are_not_queried(self):
        result, run = self._lookup('AB123456', '7')  # pasaporte
        run.assert_not_called()
        self.assertEqual(result, {})
