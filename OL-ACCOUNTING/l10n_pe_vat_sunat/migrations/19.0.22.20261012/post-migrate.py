# -*- coding: utf-8 -*-
"""Las conexiones por defecto ya creadas reciben la página donde se obtiene
su token (``signup_url``), si no tienen una."""
from odoo import SUPERUSER_ID, api

from odoo.addons.l10n_pe_vat_sunat.models.res_company import DEFAULT_CONNECTIONS


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Connection = env['l10n_pe.api.connection'].with_context(active_test=False)
    for spec in DEFAULT_CONNECTIONS:
        if spec.get('signup_url'):
            Connection.search([('name', '=', spec['name']), ('signup_url', '=', False)]).write(
                {'signup_url': spec['signup_url']})
