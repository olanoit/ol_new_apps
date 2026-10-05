# -*- coding: utf-8 -*-
"""Seguridad del token, multicompañía, padrón SUNAT y robustez de la consulta.

Cubre las correcciones de la auditoría de septiembre de 2026:

* el token de una conexión solo lo leen los administradores, pero cualquier
  usuario sigue pudiendo consultar (el motor lo lee con ``sudo()``);
* cada compañía solo ve sus conexiones;
* el padrón vacío no pisa lo que devuelve la API y una descarga sin RUCs no
  vacía la caché;
* un estado SUNAT desconocido no rompe la consulta;
* la consulta automática (onchange) es rápida y no crea contactos hijos.
"""
import io
import zipfile
from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

from odoo.addons.l10n_pe_vat_sunat.services import (
    http as http_service,
    sunat_oficial,
    sunat_padron,
)

HTTP_REQUEST = 'odoo.addons.l10n_pe_vat_sunat.services.http.request'
PADRON_GET = 'odoo.addons.l10n_pe_vat_sunat.services.sunat_padron.http.get'
PADRON_DOWNLOAD = ('odoo.addons.l10n_pe_vat_sunat.services.sunat_padron.'
                   '_download_zip')


def _response(status=200, payload=None, content=b'', text=''):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload if payload is not None else {}
    resp.content = content
    resp.text = text
    return resp


def _zip(text, name='padron.txt'):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr(name, text.encode('iso-8859-1'))
    return buf.getvalue()


@tagged('post_install', '-at_install')
class TestSecurityPadron(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pe = cls.env.ref('base.pe')
        cls.company = cls.env['res.company'].create({
            'name': 'AUDITORIA PE S.A.C.',
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.other_company = cls.env['res.company'].create({
            'name': 'OTRA COMPAÑIA S.A.C.',
            'country_id': cls.env.ref('base.pe').id,
        })
        Field = cls.env['ir.model.fields']
        cls.conn = cls.env['l10n_pe.api.connection'].create({
            'name': 'API auditoría',
            'engine': 'rest_json',
            'document_type': 'ruc',
            'company_id': cls.company.id,
            'base_url': 'https://example.test',
            'endpoint_ruc': '/ruc/{doc}',
            'auth_type': 'bearer',
            'token': 'secreto-123',
            'mapping_ids': [
                (0, 0, {'for_document': 'ruc', 'source_path': 'razon_social',
                        'field_id': Field._get('res.partner', 'name').id}),
                (0, 0, {'for_document': 'ruc', 'source_path': 'estado',
                        'field_id': Field._get('res.partner', 'state').id}),
                (0, 0, {'for_document': 'ruc', 'source_path': 'condicion',
                        'field_id': Field._get('res.partner', 'sunat_condition').id}),
            ],
        })
        cls.user = new_test_user(
            cls.env, login='pe_vat_auditor', groups='base.group_user',
            company_id=cls.company.id, company_ids=[cls.company.id])

    # ------------------------------------------------------------------
    # Token solo para administradores
    # ------------------------------------------------------------------
    def test_token_hidden_from_internal_users(self):
        conn = self.conn.with_user(self.user)
        with self.assertRaises(AccessError):
            conn.read(['token'])
        with self.assertRaises(AccessError):
            conn.search_read([('id', '=', conn.id)], ['token'])

    def test_internal_user_can_still_query(self):
        """Sin ver el token, el usuario consulta: el motor lo lee con sudo."""
        conn = self.conn.with_user(self.user)
        self.assertTrue(conn._is_usable())
        payload = {'razon_social': 'ACME SAC', 'estado': 'ACTIVO'}
        with patch(HTTP_REQUEST, return_value=_response(payload=payload)) as req:
            vals, _extra = conn.run('20557912879', 'ruc')
        self.assertEqual(vals['name'], 'ACME SAC')
        headers = req.call_args.kwargs['headers']
        self.assertEqual(headers['Authorization'], 'Bearer secreto-123')

    # ------------------------------------------------------------------
    # Multicompañía
    # ------------------------------------------------------------------
    def test_connections_are_company_bound(self):
        other = self.env['l10n_pe.api.connection'].create({
            'name': 'API de otra compañía', 'engine': 'sunat_oficial',
            'document_type': 'ruc', 'company_id': self.other_company.id,
        })
        Connection = self.env['l10n_pe.api.connection'].with_user(self.user)
        visible = Connection.search([])
        self.assertIn(self.conn, visible)
        self.assertNotIn(other, visible)
        Mapping = self.env['l10n_pe.api.field.mapping'].with_user(self.user)
        self.assertEqual(
            Mapping.search([]).connection_id.company_id, self.company)

    # ------------------------------------------------------------------
    # Selecciones con valores desconocidos
    # ------------------------------------------------------------------
    def test_unknown_selection_value_is_skipped(self):
        data = {'razon_social': 'ACME SAC', 'estado': 'ESTADO INVENTADO',
                'condicion': 'HABIDO'}
        vals = self.conn._apply_mappings(data, 'ruc')
        self.assertNotIn('state', vals)
        self.assertEqual(vals['sunat_condition'], 'HABIDO')
        partner = self.env['res.partner'].create({'name': 'TMP'})
        partner._apply_api_result('ruc', vals, {})
        self.assertEqual(partner.name, 'ACME SAC')

    def test_long_sunat_state_is_truncated(self):
        """SUNAT guarda sus estados recortados a 20 caracteres."""
        vals = self.conn._apply_mappings(
            {'estado': 'inhabilitado-vent.unica'}, 'ruc')
        self.assertEqual(vals['state'], 'INHABILITADO-VENT.UN')

    def test_invalid_json_is_an_http_error(self):
        resp = _response()
        resp.json.side_effect = ValueError('no json')
        with patch(HTTP_REQUEST, return_value=resp):
            with self.assertRaises(http_service.HttpError):
                self.conn._fetch_rest('20557912879', 'ruc')

    # ------------------------------------------------------------------
    # Padrón SUNAT
    # ------------------------------------------------------------------
    def test_empty_padron_keeps_api_flags(self):
        self.env['l10n_pe.sunat.padron'].search([]).unlink()
        partner = self.env['res.partner'].create({
            'name': 'TMP', 'vat': '20557912879', 'country_id': self.pe.id})
        partner._apply_api_result(
            'ruc', {'is_good_taxpayer': True, 'is_retention_agent': True}, {})
        self.assertTrue(partner.is_good_taxpayer)
        self.assertTrue(partner.is_retention_agent)

    def test_loaded_padron_fills_missing_flags(self):
        Padron = self.env['l10n_pe.sunat.padron']
        Padron.search([]).unlink()
        Padron.create([
            {'kind': 'good_taxpayer', 'vat': '20557912879'},
            {'kind': 'retention_agent', 'vat': '20000000001'},
        ])
        partner = self.env['res.partner'].create({
            'name': 'TMP', 'vat': '20557912879', 'country_id': self.pe.id,
            'is_retention_agent': True})
        partner._apply_api_result('ruc', {'name': 'EMPRESA'}, {})
        self.assertTrue(partner.is_good_taxpayer)
        self.assertFalse(partner.is_retention_agent)

    def test_sync_without_rucs_keeps_cache(self):
        Padron = self.env['l10n_pe.sunat.padron']
        Padron.search([]).unlink()
        Padron.create({'kind': 'good_taxpayer', 'vat': '20557912879'})
        with patch(PADRON_DOWNLOAD, return_value=[]):
            counts = sunat_padron.sync(self.env, kinds=['good_taxpayer'])
        self.assertEqual(counts['good_taxpayer'], 0)
        self.assertEqual(
            Padron.search_count([('kind', '=', 'good_taxpayer')]), 1)

    def test_download_accepts_unix_line_breaks(self):
        text = ('RUC|NOMBRE\n20557912879|ACME SAC\n'
                '20000000001|OTRA SAC\r\n10456789012|PERSONA\n')
        with patch(PADRON_GET, return_value=_response(content=_zip(text))):
            rucs = sunat_padron._download_zip('https://example.test/p.zip')
        self.assertEqual(rucs, ['20557912879', '20000000001', '10456789012'])

    def test_sync_refreshes_partner_flags(self):
        listed = self.env['res.partner'].create({
            'name': 'LISTADO', 'vat': '20557912879', 'country_id': self.pe.id})
        dropped = self.env['res.partner'].create({
            'name': 'YA NO', 'vat': '20000000001', 'country_id': self.pe.id,
            'is_good_taxpayer': True})
        with patch(PADRON_DOWNLOAD, return_value=['20557912879']):
            sunat_padron.sync(self.env, kinds=['good_taxpayer'])
        self.assertTrue(listed.is_good_taxpayer)
        self.assertFalse(dropped.is_good_taxpayer)

    def test_cron_method_is_private(self):
        Padron = self.env['l10n_pe.sunat.padron']
        self.assertFalse(hasattr(Padron, 'cron_sync_padron'))
        self.assertFalse(hasattr(Padron, 'action_sync_now'))
        cron = self.env.ref('l10n_pe_vat_sunat.ir_cron_sync_sunat_padron')
        self.assertIn('_cron_sync_padron', cron.code)

    # ------------------------------------------------------------------
    # Consulta automática (onchange) y scrapers
    # ------------------------------------------------------------------
    def test_onchange_lookup_is_quick(self):
        partner = self.env['res.partner'].create({'name': 'TMP',
                                                  'vat': '20557912879', 'country_id': self.pe.id})
        self.company.l10n_pe_api_use_fallback = False
        Connection = type(self.env['l10n_pe.api.connection'])
        with patch.object(type(self.company), '_get_pe_api_connections',
                          return_value=self.conn), \
                patch.object(Connection, 'run',
                             return_value=({}, {})) as run:
            partner.with_company(self.company)._fetch_document('ruc')
        self.assertTrue(run.call_args.kwargs['quick'])
        with patch(HTTP_REQUEST, return_value=_response(
                payload={'razon_social': 'ACME SAC'})) as req:
            self.conn._fetch_rest('20557912879', 'ruc', quick=True)
        self.assertEqual(req.call_args.kwargs['retries'], 0)
        self.assertLessEqual(req.call_args.kwargs['timeout'], 5)

    def test_onchange_does_not_create_children(self):
        extra = {'legal_representatives': [
            {'name': 'JUAN PEREZ', 'position': 'GERENTE GENERAL'}]}
        count = self.env['res.partner'].search_count([])
        new_partner = self.env['res.partner'].new({
            'name': 'NUEVA', 'is_company': True})
        new_partner._apply_api_result('ruc', {'name': 'NUEVA SAC'}, extra)
        self.assertEqual(self.env['res.partner'].search_count([]), count)
        saved = self.env['res.partner'].create({
            'name': 'GUARDADA', 'is_company': True})
        saved._apply_api_result('ruc', {'name': 'GUARDADA SAC'}, extra)
        self.assertEqual(saved.child_ids.mapped('name'), ['JUAN PEREZ'])

    def test_multi_scraper_bad_zip_is_http_error(self):
        captcha = _response(text='1234')
        page = _response(content=b'<a href="https://x.test/r.zip">r.zip</a>')
        with patch.object(sunat_oficial.http, 'post',
                          side_effect=[captcha, page]), \
                patch.object(sunat_oficial.http, 'get',
                             return_value=_response(content=b'no es zip')):
            with self.assertRaises(http_service.HttpError):
                sunat_oficial.fetch_ruc_multi('20557912879')

    def test_network_error_hides_query_token(self):
        import requests
        exc = requests.ConnectionError(
            'Max retries exceeded with url: /ruc?token=secreto-123')
        with patch('requests.request', side_effect=exc):
            with self.assertRaises(http_service.HttpError) as err:
                http_service.request(
                    'GET', 'https://example.test/ruc',
                    params={'token': 'secreto-123'}, retries=0)
        self.assertNotIn('secreto-123', str(err.exception))
