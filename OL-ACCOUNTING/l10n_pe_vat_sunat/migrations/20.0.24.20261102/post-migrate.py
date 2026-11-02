# -*- coding: utf-8 -*-
"""Las conexiones por defecto ya creadas reciben el enlace a la documentación
oficial de su proveedor (``documentation_url``), si no tienen uno."""
from odoo import SUPERUSER_ID, api

from odoo.addons.l10n_pe_vat_sunat.models.res_company import DEFAULT_CONNECTIONS


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Connection = env['l10n_pe.api.connection'].with_context(active_test=False)
    for spec in DEFAULT_CONNECTIONS:
        if spec.get('documentation_url'):
            Connection.search([('name', '=', spec['name']), ('documentation_url', '=', False)]).write(
                {'documentation_url': spec['documentation_url']})
