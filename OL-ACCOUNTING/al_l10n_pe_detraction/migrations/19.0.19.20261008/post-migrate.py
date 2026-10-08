# -*- coding: utf-8 -*-
"""Productos con el código del catálogo 54 de l10n_pe_edi pero sin tipo de
detracción (configurados antes del módulo o importados): reciben el tipo del
catálogo con ese código, así la factura lo toma y el TXT lleva código."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Template = env['product.template'].with_context(active_test=False)
    for template in Template.search([('l10n_pe_withhold_code', '!=', False),
                                     ('l10n_pe_detraction_type_id', '=', False)]):
        dtype = template._l10n_pe_detraction_type()
        if dtype:
            template.l10n_pe_detraction_type_id = dtype
