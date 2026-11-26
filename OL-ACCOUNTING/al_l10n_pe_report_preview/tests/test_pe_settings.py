# -*- coding: utf-8 -*-
from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPeSettingsReportPreview(TransactionCase):
    """El ajuste de los reportes PDF aparece en Ajustes ▸ Perú y en Ajustes generales."""

    def test_setting_in_both_apps(self):
        arch = self.env['res.config.settings'].get_view(
            self.env.ref('base.res_config_settings_view_form').id, 'form')['arch']
        tree = etree.fromstring(arch)
        for app in ('al_account_base', 'general_settings'):
            fields = tree.xpath(
                "//app[@name='%s']//field[@name='al_report_preview_scope']" % app)
            self.assertEqual(len(fields), 1, app)

    def test_pe_block_before_docs(self):
        arch = self.env['res.config.settings'].get_view(
            self.env.ref('base.res_config_settings_view_form').id, 'form')['arch']
        blocks = [b.get('name') for b in etree.fromstring(arch).xpath(
            "//app[@name='al_account_base']/block")]
        self.assertLess(blocks.index('pe_report_preview_block'),
                        blocks.index('pe_docs_block'))
