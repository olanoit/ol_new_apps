# -*- coding: utf-8 -*-
"""Ayuda contextual: mapa pantalla → guía que usa el botón «?»."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user

from odoo.addons.al_docs_help.models.al_docs_help import DOCS_URL_DEFAULT, DOCS_URL_PARAM


@tagged('post_install', '-at_install')
class TestDocsHelp(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Help = cls.env['al.docs.help']
        cls.user = new_test_user(cls.env, login='docs_help_user', groups='base.group_user')

    def test_generated_map_covers_own_screens(self):
        own = self.Help.search([('key', '=', 'al.docs.help')])
        self.assertEqual(own.module, 'al_docs_help')
        self.assertTrue(own.path.startswith('applications/general/contextual_help/'))

    def test_base_url_from_settings_or_default(self):
        params = self.env['ir.config_parameter'].sudo()
        params.set_param(DOCS_URL_PARAM, False)
        help_map = self.Help.get_help_map()
        self.assertTrue(help_map['al.docs.help']['url'].startswith(DOCS_URL_DEFAULT))
        params.set_param(DOCS_URL_PARAM, 'https://docs.ejemplo.pe/19.0')
        help_map = self.Help.get_help_map()
        own = self.Help.search([('key', '=', 'al.docs.help')])
        self.assertEqual(help_map['al.docs.help']['url'], 'https://docs.ejemplo.pe/19.0/' + own.path)

    def test_only_installed_modules(self):
        self.Help.create({'key': 'x.no.instalado', 'module': 'modulo_que_no_existe',
                          'path': 'applications/general/x/'})
        self.Help.create({'key': 'x.instalado', 'module': 'al_docs_help',
                          'path': 'applications/general/contextual_help/#configuración'})
        help_map = self.Help.get_help_map()
        self.assertNotIn('x.no.instalado', help_map)
        self.assertTrue(help_map['x.instalado']['url'].endswith('#configuración'))

    def test_internal_user_reads_map_but_cannot_edit(self):
        help_map = self.Help.with_user(self.user).get_help_map()
        self.assertIn('al.docs.help', help_map)
        self.assertFalse(self.Help.with_user(self.user).has_access('write'))

    def test_open_action(self):
        line = self.Help.search([('key', '=', 'al.docs.help')])
        action = line.action_open()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertEqual(action['target'], 'new')
        self.assertTrue(action['url'].endswith(line.path))
