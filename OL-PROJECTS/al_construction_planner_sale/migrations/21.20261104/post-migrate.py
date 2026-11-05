# -*- coding: utf-8 -*-
"""Paquete 1.17, M117-25: lo facturado por partida de las facturas que ya existen."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Recorded = env['construction.valuation.invoiced']
    moves = env['account.move'].search([
        ('construction_valuation_id', '!=', False), ('move_type', '=', 'out_invoice')])
    values = []
    for move in moves:
        company = move.company_id
        for line in move.invoice_line_ids.filtered('sale_line_ids'):
            sale_line = line.sale_line_ids[:1]
            values.append({
                'valuation_id': move.construction_valuation_id.id, 'invoice_id': move.id,
                'sale_line_id': sale_line.id, 'qty': line.quantity,
                'amount': move.currency_id._convert(
                    line.price_subtotal, company.currency_id, company,
                    move.invoice_date or move.date),
            })
    if values:
        Recorded.create(values)
