# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestModuleFicha(TransactionCase):

    def _module(self, name):
        return self.env['ir.module.module'].search([('name', '=', name)])

    def test_module_with_ficha_has_url(self):
        module = self._module('al_base_module_info')
        self.assertEqual(
            module.al_ficha_url,
            '/al_base_module_info/static/description/index.html')

    def test_odoo_description_is_not_a_ficha(self):
        """«base» trae index.html, pero no es una ficha completa."""
        self.assertFalse(self._module('base').al_ficha_url)

    def test_module_without_description(self):
        self.assertFalse(
            self.env['ir.module.module']._al_ficha_url('modulo_que_no_existe'))

    def test_kanban_offers_the_link(self):
        arch = self.env['ir.module.module'].get_view(
            self.env.ref('base.module_view_kanban').id, 'kanban')['arch']
        self.assertEqual(arch.count('Ver la ficha completa del módulo'), 2)
        self.assertIn('al_ficha_url', arch)
