# -*- coding: utf-8 -*-
"""Obligación SIREC del RUC: las sucursales toman el valor de su raíz."""
from odoo import SUPERUSER_ID, api

FIELDS = ['l10n_pe_complaint_sirec']


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Company = env['res.company']
    # Padres antes que hijas: cada sucursal toma el valor ya copiado a su padre.
    for branch in Company.search([('parent_id', '!=', False)], order='parent_path'):
        branch.write({
            fname: Company._fields[fname].convert_to_write(branch.parent_id[fname], branch)
            for fname in FIELDS
        })
