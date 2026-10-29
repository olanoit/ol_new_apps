# -*- coding: utf-8 -*-
"""Sección «Documentación» de Ajustes ▸ Perú: abre el sitio MkDocs de la
suite y sus secciones en una pestaña nueva."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestDocsSettings(TransactionCase):

    def _settings(self, url):
        settings = self.env['res.config.settings'].create({'al_docs_url': url})
        settings.execute()
        return settings

    def test_open_home_and_sections(self):
        settings = self._settings('https://docs.ejemplo.pe/19.0')
        action = settings.action_al_docs_open()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['url'], 'https://docs.ejemplo.pe/19.0/')
        action = settings.with_context(al_docs_page='guides').action_al_docs_open()
        self.assertEqual(action['url'], 'https://docs.ejemplo.pe/19.0/applications/')
        action = settings.with_context(al_docs_page='desconocida').action_al_docs_open()
        self.assertEqual(action['url'], 'https://docs.ejemplo.pe/19.0/')

    def test_url_required_and_valid(self):
        self.env['ir.config_parameter'].sudo().set_str('al_account_base.docs_url', False)
        with self.assertRaises(UserError):
            self.env['res.config.settings'].create({}).action_al_docs_open()
        with self.assertRaises(ValidationError):
            self.env['res.config.settings'].create({'al_docs_url': 'docs.ejemplo.pe'})

    def test_block_is_last_in_peru_page(self):
        arch = self.env['res.config.settings'].get_view(view_type='form')['arch']
        start = arch.index('name="al_account_base"')
        end = arch.index('</app>', start)
        app = arch[start:end]
        self.assertIn('name="pe_docs_block"', app)
        self.assertNotIn('<block', app[app.index('name="pe_docs_block"'):])
