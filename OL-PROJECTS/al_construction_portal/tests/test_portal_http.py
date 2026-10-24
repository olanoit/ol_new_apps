# -*- coding: utf-8 -*-
"""Servicios JSON del portal de obra por HTTP (requerimiento CREVAL v1.0,
4.11): ingreso con usuario y clave, QR y PIN, token y la aplicación
instalable."""
import json

from odoo.tests import HttpCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestPortalHttp(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['project.project'].create({
            'name': 'Obra del portal (test http)', 'is_construction_site': True,
            'construction_portal_qr_login': True})
        cls.project.action_construction_portal_new_code()
        cls.user = new_test_user(cls.env, 'portal_http_capataz', groups='base.group_portal',
                                 password='portal_http_capataz', name='Capataz HTTP (test)')
        cls.member = cls.env['construction.portal.member'].create({
            'project_id': cls.project.id, 'user_id': cls.user.id, 'role': 'foreman'})
        cls.member.action_set_pin('4321')

    def _post(self, path, body, token=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer %s' % token
        return self.url_open('/construction/api/v1' + path, data=json.dumps(body),
                             headers=headers)

    def _get(self, path, token=None):
        headers = {'Authorization': 'Bearer %s' % token} if token else {}
        return self.url_open('/construction/api/v1' + path, headers=headers)

    def test_login_token_and_app(self):
        bad = self._post('/login', {'login': 'portal_http_capataz', 'password': 'mala'})
        self.assertEqual(bad.status_code, 401)
        response = self._post('/login', {'login': 'portal_http_capataz',
                                         'password': 'portal_http_capataz'})
        self.assertEqual(response.status_code, 200, response.text)
        token = response.json()['token']
        me = self._get('/me', token)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()['projects'][0]['id'], self.project.id)
        self.assertEqual(self._get('/me').status_code, 401)
        self.assertEqual(self._get('/me', 'falso').status_code, 401)
        sync = self._get('/sync/%s' % self.project.id, token)
        self.assertEqual(sync.status_code, 200)
        self.assertEqual(sync.json()['roles'], ['foreman'])
        rejected = self._post('/progress', {'uuid': 'x', 'project_id': self.project.id,
                                            'plan_line_id': 0}, token)
        self.assertEqual(rejected.status_code, 403)
        self.assertIn('error', rejected.json())
        # La aplicación instalable.
        page = self.url_open('/obra/app/')
        self.assertEqual(page.status_code, 200)
        self.assertIn('manifest.webmanifest', page.text)
        # Pantalla 1: el nombre y las iniciales de la empresa antes de ingresar.
        self.assertIn('data-initials=', page.text)
        manifest = self.url_open('/obra/app/manifest.webmanifest').json()
        self.assertEqual(manifest['display'], 'standalone')
        worker = self.url_open('/obra/app/sw.js')
        self.assertEqual(worker.headers.get('Service-Worker-Allowed'), '/obra/app/')

    def test_qr_and_pin(self):
        code = self.project.construction_portal_code
        site = self._get('/site/%s' % code)
        self.assertEqual(site.status_code, 200)
        self.assertEqual(site.json()['members'][0]['id'], self.member.id)
        self.assertEqual(self._get('/site/nada').status_code, 404)
        wrong = self._post('/pin', {'code': code, 'member_id': self.member.id, 'pin': '0000'})
        self.assertEqual(wrong.status_code, 401)
        right = self._post('/pin', {'code': code, 'member_id': self.member.id, 'pin': '4321'})
        self.assertEqual(right.status_code, 200, right.text)
        self.assertEqual(self._get('/me', right.json()['token']).status_code, 200)
