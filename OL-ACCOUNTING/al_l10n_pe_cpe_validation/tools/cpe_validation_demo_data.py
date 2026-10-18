# -*- coding: utf-8 -*-
"""Datos DEMO CPE para las capturas: tres facturas de proveedor con el
resultado de la consulta ya registrado (sin llamar a SUNAT).

    odoo-bin shell -c <cfg> -d <base> < tools/cpe_validation_demo_data.py
"""
from stdnum.pe import ruc as stdnum_ruc

company = env.company
pe = env.ref('base.pe')
ruc_type = env.ref('l10n_pe.it_RUC')
invoice_type = env.ref('l10n_pe.document_type01')
journal = env['account.journal'].search([('type', '=', 'purchase'), ('company_id', '=', company.id)], limit=1)
Partner = env['res.partner']


def vendor(name, body):
    vat = body + stdnum_ruc.calc_check_digit(body)
    return Partner.search([('vat', '=', vat)], limit=1) or Partner.create({
        'name': name, 'country_id': pe.id, 'l10n_latam_identification_type_id': ruc_type.id,
        'vat': vat, 'is_company': True})


rows = [
    (vendor('DEMO CPE DISTRIBUIDORA S.A.C.', '2061000111'), 'F001-00004521', 2360.0,
     {'estadoCp': '1', 'estadoRuc': '00', 'condDomiRuc': '00', 'observaciones': []}),
    (vendor('DEMO CPE SERVICIOS GENERALES E.I.R.L.', '2061000222'), 'F002-00000318', 840.0,
     {'estadoCp': '1', 'estadoRuc': '00', 'condDomiRuc': '12', 'observaciones': []}),
    (vendor('DEMO CPE IMPORTACIONES S.R.L.', '2061000333'), 'F001-00009910', 1180.0,
     {'estadoCp': '0', 'estadoRuc': '00', 'condDomiRuc': '00',
      'observaciones': ['- El comprobante de pago consultado no ha sido informado a SUNAT.']}),
]
for partner, number, amount, data in rows:
    move = env['account.move'].search([('partner_id', '=', partner.id), ('move_type', '=', 'in_invoice'), ('ref', '=', number)], limit=1)
    if not move:
        move = env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': partner.id, 'journal_id': journal.id,
            'invoice_date': '2026-10-05', 'l10n_latam_document_type_id': invoice_type.id,
            'l10n_latam_document_number': number, 'ref': number,
            'invoice_line_ids': [(0, 0, {'name': 'Mercadería', 'quantity': 1, 'price_unit': amount})],
        })
    move._l10n_pe_cpe_apply(data)
    print('DEMO', move.id, move.name, move.l10n_pe_cpe_result)
env.cr.commit()
