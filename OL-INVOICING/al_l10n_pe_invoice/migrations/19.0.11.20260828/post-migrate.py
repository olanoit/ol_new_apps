# -*- coding: utf-8 -*-
"""Desglose tributario: exportación (9995) y gratuitas (9996) con casilla
propia, y «otros tributos» solo con el 9999.

Los campos son almacenados: las facturas ya existentes con esos tributos
conservarían el 9996 en «otros» y la exportación sin contar. Las columnas
nuevas (exportación, gratuitas) ya se calculan al crearse; aquí se asegura
el recálculo de todo el desglose de esas facturas.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    moves = env['account.move'].search([
        ('move_type', 'in', ('out_invoice', 'in_invoice', 'out_refund', 'in_refund')),
        ('line_ids.tax_ids.l10n_pe_edi_tax_code', 'in', ('9995', '9996', '9999')),
    ])
    if not moves:
        return
    fields_to_compute = [
        moves._fields[name] for name in moves._TAX_AMOUNT_FIELDS]
    for field in fields_to_compute:
        env.add_to_compute(field, moves)
    moves._recompute_recordset(list(moves._TAX_AMOUNT_FIELDS))
