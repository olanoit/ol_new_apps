# -*- coding: utf-8 -*-
"""Cada conexión por defecto enlaza la documentación oficial de su proveedor."""
from odoo.tests import TransactionCase, tagged

from odoo.addons.al_account_base.tests.common import use_pe_company
from odoo.addons.l10n_pe_vat_sunat.models.res_company import DEFAULT_CONNECTIONS


@tagged('post_install', '-at_install')
class TestDocumentationUrl(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        use_pe_company(cls)

    def test_every_default_connection_has_https_documentation(self):
        for spec in DEFAULT_CONNECTIONS:
            with self.subTest(connection=spec['name']):
                self.assertTrue(spec.get('documentation_url', '').startswith('https://'))

    def test_seeded_connections_carry_the_documentation(self):
        company = self.env['res.company'].create({
            'name': 'Compañía PE (documentación)',
            'country_id': self.env.ref('base.pe').id})
        company._l10n_pe_seed_default_connections()
        urls = {spec['name']: spec['documentation_url'] for spec in DEFAULT_CONNECTIONS}
        self.assertEqual(len(company.l10n_pe_api_connection_ids), len(urls))
        for connection in company.l10n_pe_api_connection_ids:
            self.assertEqual(connection.documentation_url, urls[connection.name])
