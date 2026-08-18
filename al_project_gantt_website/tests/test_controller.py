# -*- coding: utf-8 -*-
"""La página web es solo para usuarios internos con el grupo del Gantt.

Lo que se prueba aquí es exactamente eso: quién entra, quién recibe 403 y que
el endpoint de datos devuelve el mismo contrato del módulo base.
"""
from odoo.tests.common import HttpCase, tagged

PASSWORD = 'gantt-web-test-2026'


@tagged('post_install', '-at_install')
class TestGanttWebsiteController(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gantt_user = cls.env['res.users'].create({
            'name': 'Interno con Gantt',
            'login': 'gantt.web.user',
            'password': PASSWORD,
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('al_project_gantt_base.group_gantt_user').id,
            ])],
        })
        cls.plain_user = cls.env['res.users'].create({
            'name': 'Interno sin Gantt',
            'login': 'gantt.web.plain',
            'password': PASSWORD,
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Portal',
            'login': 'gantt.web.portal',
            'password': PASSWORD,
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.project = cls.env['project.project'].create({
            'name': 'Proyecto web de prueba',
            'privacy_visibility': 'employees',
        })
        cls.env['project.task'].create({
            'name': 'Tarea web',
            'project_id': cls.project.id,
            'date_deadline': '2026-10-15 12:00:00',
        })

    # ------------------------------------------------------------------
    # Página
    # ------------------------------------------------------------------
    def test_internal_user_with_group_sees_the_page(self):
        self.authenticate('gantt.web.user', PASSWORD)
        response = self.url_open('/gantt')
        self.assertEqual(response.status_code, 200)
        self.assertIn('algantt-page', response.text)
        self.assertIn('algantt-container', response.text)

    def test_internal_user_without_group_is_forbidden(self):
        self.authenticate('gantt.web.plain', PASSWORD)
        response = self.url_open('/gantt')
        self.assertEqual(response.status_code, 403)

    def test_portal_user_is_forbidden(self):
        self.authenticate('gantt.web.portal', PASSWORD)
        response = self.url_open('/gantt')
        self.assertEqual(response.status_code, 403)

    def test_public_visitor_is_sent_to_login(self):
        response = self.url_open('/gantt', allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertIn('/web/login', response.headers.get('Location', ''))

    # ------------------------------------------------------------------
    # Endpoint de datos
    # ------------------------------------------------------------------
    def test_data_endpoint_returns_the_contract(self):
        self.authenticate('gantt.web.user', PASSWORD)
        payload = self.make_jsonrpc_request('/gantt/data', {
            'project_ids': [self.project.id], 'options': {},
        })
        for key in ('contract_version', 'field_map', 'projects', 'tasks',
                    'links', 'milestones', 'colors', 'meta'):
            self.assertIn(key, payload)
        self.assertEqual([p['id'] for p in payload['projects']], [self.project.id])
        self.assertEqual(len(payload['tasks']), 1)
        self.assertTrue(payload['meta']['editable'],
                        "El usuario tiene permiso de escritura sobre esa tarea")

    def _post_data_endpoint(self):
        return self.url_open(
            '/gantt/data',
            json={'jsonrpc': '2.0', 'method': 'call', 'params': {}},
        ).json()

    def test_data_endpoint_denies_user_without_group(self):
        """JSON-RPC transporta el rechazo en el cuerpo (HTTP 200 por protocolo);
        lo que importa es que no devuelve ningún dato."""
        self.authenticate('gantt.web.plain', PASSWORD)
        body = self._post_data_endpoint()
        self.assertIn('error', body)
        self.assertNotIn('result', body)
        self.assertEqual(body['error']['data']['name'], 'werkzeug.exceptions.Forbidden')

    def test_data_endpoint_denies_portal_user(self):
        self.authenticate('gantt.web.portal', PASSWORD)
        body = self._post_data_endpoint()
        self.assertIn('error', body)
        self.assertNotIn('result', body)
        self.assertEqual(body['error']['data']['name'], 'werkzeug.exceptions.Forbidden')

    # ------------------------------------------------------------------
    # Endpoint de escritura
    # ------------------------------------------------------------------
    def test_apply_endpoint_saves_a_change(self):
        self.authenticate('gantt.web.user', PASSWORD)
        task = self.env['project.task'].search([('project_id', '=', self.project.id)], limit=1)
        result = self.make_jsonrpc_request('/gantt/apply', {
            'changeset': {'tasks': {'update': [{'id': task.id, 'name': 'Renombrada desde la web'}]}},
        })
        self.assertTrue(result['ok'])
        self.assertEqual(result['updated'], [task.id])
        task.invalidate_recordset()
        self.assertEqual(task.name, 'Renombrada desde la web')

    def test_apply_endpoint_denies_user_without_group(self):
        self.authenticate('gantt.web.plain', PASSWORD)
        task = self.env['project.task'].search([('project_id', '=', self.project.id)], limit=1)
        body = self.url_open('/gantt/apply', json={
            'jsonrpc': '2.0', 'method': 'call',
            'params': {'changeset': {'tasks': {'update': [{'id': task.id, 'name': 'Intruso'}]}}},
        }).json()
        self.assertIn('error', body)
        self.assertNotIn('result', body)
        task.invalidate_recordset()
        self.assertNotEqual(task.name, 'Intruso')

    def test_baseline_endpoint(self):
        self.authenticate('gantt.web.user', PASSWORD)
        result = self.make_jsonrpc_request('/gantt/baseline', {
            'project_ids': [self.project.id], 'name': 'Base web',
        })
        self.assertTrue(result['ok'])
        self.assertEqual(result['baselines'][0]['name'], 'Base web')

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------
    def test_library_is_not_in_the_frontend_bundle(self):
        from odoo.modules.module import get_manifest
        bundle = get_manifest('al_project_gantt_website')['assets']['web.assets_frontend']
        self.assertFalse(
            [path for path in bundle if 'dhtmlxgantt' in path],
            "dhtmlxgantt debe cargarse de forma perezosa, no en el bundle del frontend",
        )
