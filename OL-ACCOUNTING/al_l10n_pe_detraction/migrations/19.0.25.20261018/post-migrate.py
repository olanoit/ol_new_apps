# -*- coding: utf-8 -*-
"""Los registros de demostración ya no llevan «DEMO» en el nombre: en las
bases que ya los tienen se renombran (solo si conservan el nombre viejo)."""
from odoo import SUPERUSER_ID, api

RENAMES = {
    'al_l10n_pe_detraction.demo_product_service': {
        'DEMO SPOT Servicio empresarial': {'name': 'Servicio de asesoría empresarial',
                                           'default_code': 'SRV-037'}},
    'al_l10n_pe_detraction.demo_partner': {
        'DEMO SPOT Contraparte S.A.C.': {'name': 'Consultores Asociados del Sur S.A.C.'}},
    'al_l10n_pe_detraction.demo_journal_sale': {'DEMO SPOT Ventas': {'name': 'Ventas con detracción'}},
    'al_l10n_pe_detraction.demo_journal_purchase': {'DEMO SPOT Compras': {'name': 'Compras con detracción'}},
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, by_old_name in RENAMES.items():
        record = env.ref(xmlid, raise_if_not_found=False)
        if record and record.name in by_old_name:
            record.write(by_old_name[record.name])
    # Las líneas de las facturas de la demo llevan el nombre del producto.
    for line in env['account.move.line'].search([('name', 'like', 'DEMO SPOT Servicio empresarial')]):
        line.name = line.name.replace('[DEMO-SPOT-01] ', '[SRV-037] ').replace(
            'DEMO SPOT Servicio empresarial', 'Servicio de asesoría empresarial')
