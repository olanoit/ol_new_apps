"""Llena el documento del kardex en los movimientos hechos de compañías peruanas.

Desde la 5.20261006 el documento se guarda por movimiento; el historial se
llena una vez aquí (solo los vacíos, nunca los manuales). Lo que no tenga
comprobante ni guía sigue con el cálculo al vuelo del kardex.
"""
from odoo import SUPERUSER_ID, api

BATCH = 2000


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies = env['res.company'].search([]).filtered(lambda c: c.country_code == 'PE')
    if not companies:
        return
    moves = env['stock.move'].search([
        ('state', '=', 'done'), ('company_id', 'in', companies.ids),
        ('l10n_pe_kardex_doc_type', '=', False)], order='id')
    for start in range(0, len(moves), BATCH):
        moves[start:start + BATCH]._l10n_pe_kardex_fill_documents(force=False)
