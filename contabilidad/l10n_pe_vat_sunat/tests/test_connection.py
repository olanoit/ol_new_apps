# -*- coding: utf-8 -*-
"""Tests del mapeo config-driven de una conexión hacia el partner."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestConnection(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Field = cls.env['ir.model.fields']
        # Conexión REST de prueba con mapeo explícito.
        cls.conn = cls.env['l10n_pe.api.connection'].create({
            'name': 'API de prueba',
            'engine': 'rest_json',
            'document_type': 'both',
            'company_id': cls.company.id,
            'base_url': 'https://example.test',
            'endpoint_ruc': '/ruc/{doc}',
            'endpoint_dni': '/dni/{doc}',
            'data_root': 'data',
            'success_path': 'success',
            'ubigeo_path': 'ubigeo_sunat',
            'district_path': 'distrito',
            'mapping_ids': [
                (0, 0, {'for_document': 'ruc', 'source_path': 'razon_social',
                        'field_id': cls.Field._get('res.partner', 'name').id}),
                (0, 0, {'for_document': 'ruc', 'source_path': 'estado',
                        'field_id': cls.Field._get('res.partner', 'state').id}),
                (0, 0, {'for_document': 'ruc', 'source_path': 'direccion',
                        'transform': 'upper',
                        'field_id': cls.Field._get('res.partner', 'street').id}),
                (0, 0, {'for_document': 'dni',
                        'source_path': '{nombres} {apellido_paterno}',
                        'transform': 'title',
                        'field_id': cls.Field._get('res.partner', 'name').id}),
            ],
        })

    def test_apply_mappings_ruc(self):
        data = {'razon_social': 'ACME SAC', 'estado': 'ACTIVO',
                'direccion': 'av lima 100', 'ignorado': 'x'}
        vals = self.conn._apply_mappings(data, 'ruc')
        self.assertEqual(vals['name'], 'ACME SAC')
        self.assertEqual(vals['state'], 'ACTIVO')
        self.assertEqual(vals['street'], 'AV LIMA 100')  # transform upper
        # Los mapeos de DNI no aplican a RUC.
        self.assertNotIn('function', vals)

    def test_apply_mappings_dni_template(self):
        data = {'nombres': 'MARIA JOSE', 'apellido_paterno': 'ROJAS'}
        vals = self.conn._apply_mappings(data, 'dni')
        self.assertEqual(vals['name'], 'Maria Jose Rojas')

    def test_skip_if_empty(self):
        # 'direccion' ausente → no debe escribir street.
        vals = self.conn._apply_mappings({'razon_social': 'X'}, 'ruc')
        self.assertNotIn('street', vals)

    def test_priority_ordering(self):
        conns = self.company._get_pe_api_connections('ruc')
        # La conexión de prueba (sequence 10 por defecto) y las sembradas.
        self.assertTrue(conns)
        seqs = conns.mapped('sequence')
        self.assertEqual(seqs, sorted(seqs))

    def test_default_connections_seeded(self):
        names = self.company.l10n_pe_api_connection_ids.mapped('name')
        self.assertIn('apiperu.dev', names)
        self.assertIn('apis.net.pe', names)
        self.assertIn('SUNAT (oficial)', names)
        self.assertIn('json.pe', names)

    def test_jsonpe_post_body(self):
        """json.pe consulta por POST con el número en el body JSON."""
        jp = self.company.l10n_pe_api_connection_ids.filtered(
            lambda c: c.name == 'json.pe')[:1]
        self.assertTrue(jp)
        self.assertEqual(jp.http_method, 'post')
        self.assertEqual(jp.body_ruc, '{"ruc": "{doc}"}')
        # El body se construye con el número inyectado.
        import json
        body = json.loads(jp.body_ruc.replace('{doc}', '20608151771'))
        self.assertEqual(body, {'ruc': '20608151771'})
        # Mapeo del wrapper {success, data:{...}}.
        data = {'nombre_o_razon_social': 'ACME SAC', 'estado': 'ACTIVO'}
        vals = jp._apply_mappings(data, 'ruc')
        self.assertEqual(vals['name'], 'ACME SAC')

    def test_single_vs_fallback(self):
        """Sin fallback usa solo la principal; con fallback, todas."""
        company = self.company
        # Aseguramos ≥2 conexiones RUC activas para el caso cascada.
        self.env['l10n_pe.api.connection'].create({
            'name': 'Extra RUC', 'engine': 'sunat_oficial',
            'document_type': 'ruc', 'company_id': company.id, 'sequence': 99,
        })
        company.l10n_pe_api_use_fallback = False
        single = company._get_pe_api_connections('ruc')
        self.assertEqual(len(single), 1, 'Modo único debe devolver una sola.')

        company.l10n_pe_api_use_fallback = True
        cascade = company._get_pe_api_connections('ruc')
        self.assertGreater(len(cascade), 1, 'Cascada debe devolver varias.')
        # La principal (single) es la de mayor prioridad de la cascada.
        self.assertEqual(single.id, cascade[0].id)

    def test_is_usable(self):
        """Una REST con auth pero sin token no es utilizable; con token sí."""
        conn = self.env['l10n_pe.api.connection'].create({
            'name': 'Sin token', 'engine': 'rest_json', 'document_type': 'ruc',
            'company_id': self.company.id, 'auth_type': 'bearer', 'token': False,
        })
        self.assertFalse(conn._is_usable())
        conn.token = 'abc'
        self.assertTrue(conn._is_usable())
        # Un scraper (sin auth REST) siempre es utilizable.
        scraper = self.env['l10n_pe.api.connection'].create({
            'name': 'Scraper', 'engine': 'sunat_oficial',
            'document_type': 'ruc', 'company_id': self.company.id})
        self.assertTrue(scraper._is_usable())

    def test_usable_filter_excludes_tokenless(self):
        """Las conexiones sin token no entran en la lista a consultar."""
        company = self.env['res.company'].create({'name': 'PE Test Co'})
        company.country_id = self.env.ref('base.pe')
        company._l10n_pe_seed_default_connections()
        # Sin tokens: las REST quedan fuera; solo SUNAT (scraper) es utilizable.
        usable = company._get_pe_api_connections('ruc')
        self.assertTrue(all(u._is_usable() for u in usable))
        self.assertIn('SUNAT (oficial)', usable.mapped('name'))

    def test_apply_result_writes_partner(self):
        partner = self.env['res.partner'].create({'name': 'TMP'})
        vals = {'name': 'EMPRESA X', 'state': 'ACTIVO', 'street': 'AV Y'}
        partner._apply_api_result('ruc', vals, {})
        self.assertEqual(partner.name, 'EMPRESA X')
        self.assertEqual(partner.company_type, 'company')
        self.assertFalse(partner.alert_warning_vat)
