# -*- coding: utf-8 -*-
"""Conexión Decolecta para consulta de RUC y DNI.

Decolecta consulta el RUC contra SUNAT y el DNI contra RENIEC. Su respuesta es
plana —sin envoltorio de datos ni indicador de éxito— y devuelve el nombre de
la persona partido en tres campos, que hay que recomponer.
"""
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.l10n_pe_vat_sunat.models.res_company import DEFAULT_CONNECTIONS

# Respuestas reales de la API (documentación de Decolecta).
RUC_RESPONSE = {
    'razon_social': 'REXTIE S.A.C.',
    'numero_documento': '20601030013',
    'estado': 'ACTIVO',
    'condicion': 'HABIDO',
    'direccion': 'AV. JAVIER PRADO ESTE NRO. 123',
    'ubigeo': '150131',
    'distrito': 'SAN ISIDRO',
    'provincia': 'LIMA',
    'departamento': 'LIMA',
    'es_agente_retencion': False,
    'es_buen_contribuyente': True,
}
DNI_RESPONSE = {
    'first_name': 'ROXANA KARINA',
    'first_last_name': 'DELGADO',
    'second_last_name': 'HUAMANI',
    'full_name': 'DELGADO HUAMANI ROXANA KARINA',
    'document_number': '46027897',
}


@tagged('post_install', '-at_install')
class TestDecolectaConnection(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'DECOLECTA TEST S.A.C.',
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.company._l10n_pe_seed_default_connections()
        cls.connection = cls.company.l10n_pe_api_connection_ids.filtered(
            lambda c: c.name == 'Decolecta')

    # ------------------------------------------------------------------
    # Alta de la conexión
    # ------------------------------------------------------------------
    def test_decolecta_is_a_default_connection(self):
        names = [spec['name'] for spec in DEFAULT_CONNECTIONS]
        self.assertIn('Decolecta', names)

    def test_connection_is_created_for_pe_company(self):
        self.assertTrue(self.connection, 'la compañía peruana debe tenerla')
        self.assertEqual(self.connection.engine, 'rest_json')
        self.assertEqual(self.connection.document_type, 'both')
        self.assertEqual(self.connection.auth_type, 'bearer')

    def test_endpoints_are_the_official_ones(self):
        self.assertEqual(self.connection.base_url, 'https://api.decolecta.com')
        self.assertEqual(self.connection.endpoint_ruc,
                         '/v1/sunat/ruc?numero={doc}')
        self.assertEqual(self.connection.endpoint_dni,
                         '/v1/reniec/dni?numero={doc}')

    def test_response_is_read_from_the_root(self):
        """La respuesta es plana: sin raíz de datos ni flag de éxito."""
        self.assertFalse(self.connection.data_root)
        self.assertFalse(self.connection.success_path)

    def test_without_token_it_is_not_usable(self):
        """Una conexión bearer sin token siempre daría 401."""
        self.assertFalse(self.connection._is_usable())
        self.connection.token = 'un-token'
        self.assertTrue(self.connection._is_usable())

    def test_ensure_connection_is_idempotent(self):
        """Volver a asegurarla no duplica ni pisa lo configurado."""
        self.connection.token = 'mi-token'
        self.company._l10n_pe_ensure_connection('Decolecta')
        found = self.company.l10n_pe_api_connection_ids.filtered(
            lambda c: c.name == 'Decolecta')
        self.assertEqual(len(found), 1)
        self.assertEqual(found.token, 'mi-token')

    # ------------------------------------------------------------------
    # Mapeo de la respuesta
    # ------------------------------------------------------------------
    def test_ruc_mapping(self):
        self.connection.token = 'fake'
        with patch.object(type(self.connection), '_fetch_data',
                          return_value=RUC_RESPONSE):
            vals, _extra = self.connection.run('20601030013', 'ruc')
        self.assertEqual(vals['name'], 'REXTIE S.A.C.')
        self.assertEqual(vals['state'], 'ACTIVO')
        self.assertEqual(vals['sunat_condition'], 'HABIDO')
        self.assertEqual(vals['street'], 'AV. JAVIER PRADO ESTE NRO. 123')
        self.assertTrue(vals['is_good_taxpayer'])
        self.assertFalse(vals['is_retention_agent'])

    def test_dni_mapping_rebuilds_the_name(self):
        """RENIEC devuelve el nombre partido; se recompone con apellidos delante."""
        self.connection.token = 'fake'
        with patch.object(type(self.connection), '_fetch_data',
                          return_value=DNI_RESPONSE):
            vals, _extra = self.connection.run('46027897', 'dni')
        self.assertEqual(vals['name'], 'Delgado Huamani Roxana Karina')

    def test_ruc_mapping_ignores_dni_rows(self):
        """El mapeo de DNI no debe aplicarse a una consulta de RUC."""
        self.connection.token = 'fake'
        with patch.object(type(self.connection), '_fetch_data',
                          return_value=RUC_RESPONSE):
            vals, _extra = self.connection.run('20601030013', 'ruc')
        self.assertEqual(vals['name'], 'REXTIE S.A.C.',
                         'la plantilla del DNI dejaría el nombre en blanco')
