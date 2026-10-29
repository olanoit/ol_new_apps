# -*- coding: utf-8 -*-
"""Datos de liquidaciones de compra para la ficha y la documentación (idempotente).

    odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http --max-cron-threads=0 < \\
        myodoo/ol_new_apps/OL-INVOICING/al_l10n_pe_edi_purchase_settlement/tools/purchase_settlement_demo_data.py

Una productora de café de Chinchao (Huánuco) sin RUC y dos liquidaciones del
05/10/2026: café pergamino por S/ 11 875 (retiene IGV y 1,5 % de renta,
confirmada y por enviar) y una compra menor de S/ 600 (sin retención de
renta, en borrador). No se envía nada a SUNAT.
"""
from datetime import date

from odoo import Command

company = env.company
journal = env['account.journal'].search([('company_id', '=', company.id), ('l10n_pe_lce_journal', '=', True)], limit=1)
igv = env['account.tax'].search([('company_id', '=', company.id), ('type_tax_use', '=', 'purchase'),
                                 ('l10n_pe_edi_tax_code', '=', '1000'), ('amount', '=', 18)], limit=1)
kg = env.ref('uom.product_uom_kgm')
district = env.ref('l10n_pe.district_pe_100103')
day = date(2026, 10, 5)

seller = env['res.partner'].search([('name', '=', 'QUISPE MAMANI JUANA')], limit=1)
if not seller:
    seller = env['res.partner'].create({
        'name': 'QUISPE MAMANI JUANA',
        'additional_identifiers': {'PE_DNI': '45612378'},
        'street': 'Caserío Santa Rosa, parcela 14',
        'country_id': env.ref('base.pe').id,
        'state_id': district.city_id.state_id.id,
        'city_id': district.city_id.id,
        'l10n_pe_district': district.id,
    })

product = env['product.product'].search([('name', '=', 'Café pergamino')], limit=1)
if not product:
    product = env['product.product'].create({
        'name': 'Café pergamino', 'default_code': 'CAFE', 'type': 'consu',
        'uom_id': kg.id, 'supplier_taxes_id': [Command.set(igv.ids)]})
gold = env['product.product'].search([('name', '=', 'Oro en bruto')], limit=1)
if not gold:
    gold = env['product.product'].create({
        'name': 'Oro en bruto', 'default_code': 'ORO', 'type': 'consu',
        'l10n_pe_lce_gold': True, 'supplier_taxes_id': [Command.set(igv.ids)]})


def settlement(ref, quantity, price, post):
    move = env['account.move'].search([('ref', '=', ref), ('journal_id', '=', journal.id)], limit=1)
    if move:
        return move
    move = env['account.move'].create({
        'move_type': 'in_invoice', 'journal_id': journal.id, 'partner_id': seller.id,
        'invoice_date': day, 'date': day, 'ref': ref,
        'l10n_pe_lce_place_type': '02', 'l10n_pe_lce_partner_address_type': '02',
        'l10n_pe_lce_license_plate': 'B2C845' if post else False,
        'invoice_line_ids': [Command.create({
            'product_id': product.id, 'name': 'Café pergamino seco, humedad 12 %',
            'quantity': quantity, 'product_uom_id': kg.id, 'price_unit': price,
            'tax_ids': [Command.set(igv.ids)]})],
    })
    move._l10n_pe_lce_sync_taxes()
    if post:
        move.action_post()
    return move


main = settlement('Liquidación de compra 1', 1250.0, 9.5, True)
small = settlement('Liquidación de compra 2', 60.0, 10.0, False)
env.cr.commit()
print('LCE', main.id, main.name, main.amount_total, main.l10n_pe_lce_status, '| borrador', small.id,
      '| oro', gold.product_tmpl_id.id)
