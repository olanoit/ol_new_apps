# -*- coding: utf-8 -*-
"""Agente de retención del RUC: las sucursales toman la configuración de su raíz."""
from odoo import SUPERUSER_ID, api

FIELDS = [
    'l10n_pe_retention_agent',
    'l10n_pe_retention_rate',
    'l10n_pe_retention_min_amount',
    'l10n_pe_retention_tax_id',
    'l10n_pe_retention_outstanding_account_id',
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Company = env['res.company']
    # Padres antes que hijas: cada sucursal toma el valor ya copiado a su padre.
    for branch in Company.search([('parent_id', '!=', False)], order='parent_path'):
        branch.write({
            fname: Company._fields[fname].convert_to_write(branch.parent_id[fname], branch)
            for fname in FIELDS
        })
