# -*- coding: utf-8 -*-
"""Datos de cuarta categoría para la ficha y la documentación (idempotente).

    odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < \\
        myodoo/ol_new_apps/OL-ACCOUNTING/al_l10n_pe_fourth_category/tools/fourth_category_demo_data.py

Dos prestadores: QUISPE (recibos de S/ 2 000 con retención y de S/ 1 200
bajo el tope) y TORRES (constancia de suspensión, recibo de S/ 5 000 sin
retención); todos pagados el 10/10/2026.
"""
from datetime import date

from stdnum.pe import ruc as stdnum_ruc

company = env.company
company.write({'l10n_pe_fourth_category_agent': True})
receipt_type = env.ref('l10n_pe.document_type03')
journal = env['account.journal'].search([('type', '=', 'purchase'), ('company_id', '=', company.id)], limit=1)
bank = env['account.journal'].search([('type', '=', 'bank'), ('company_id', '=', company.id)], limit=1)
day = date(2026, 10, 5)
paid_on = date(2026, 10, 10)


def provider(name, body):
    vat = body + stdnum_ruc.calc_check_digit(body)
    partner = env['res.partner'].search([('vat', '=', vat)], limit=1)
    return partner or env['res.partner'].create({
        'name': name, 'country_id': env.ref('base.pe').id, 'vat': vat})


quispe = provider('QUISPE ROJAS ANA', '1047382956')
torres = provider('TORRES PAZ LUIS', '1041122334')
Suspension = env['l10n_pe.fourth.category.suspension']
if not Suspension.search([('partner_id', '=', torres.id), ('number', '=', '1609-26-000184')]):
    Suspension.create({'partner_id': torres.id, 'number': '1609-26-000184',
                       'date_issued': date(2026, 2, 3),
                       'note': 'Constancia entregada por el prestador el 05/02/2026.'})


def receipt(partner, number, amount, concept):
    move = env['account.move'].search([
        ('partner_id', '=', partner.id), ('ref', '=', number),
        ('move_type', '=', 'in_invoice')], limit=1)
    if not move:
        move = env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': partner.id, 'journal_id': journal.id,
            'invoice_date': day, 'date': day,
            'l10n_latam_document_type_id': receipt_type.id,
            'l10n_latam_document_number': number, 'ref': number,
            'invoice_line_ids': [(0, 0, {'name': concept, 'quantity': 1,
                                         'price_unit': amount, 'tax_ids': [(6, 0, [])]})],
        })
        move.action_post()
    if move.payment_state == 'not_paid':
        env['account.payment.register'].with_context(
            active_model='account.move', active_ids=move.ids).create({
                'payment_date': paid_on, 'journal_id': bank.id})._create_payments()
    return move


r1 = receipt(quispe, 'E001-58', 2000.0, 'Asesoría contable de septiembre')
r2 = receipt(quispe, 'E001-59', 1200.0, 'Capacitación al personal')
r3 = receipt(torres, 'E001-12', 5000.0, 'Diseño de la campaña publicitaria')
env.cr.commit()
for move in (r1, r2, r3):
    print('4TA', move.id, move.l10n_latam_document_number, move.l10n_pe_fourth_category_status,
          move.l10n_pe_fourth_category_amount, move.amount_residual, move.payment_state)
print('4TA partners', quispe.id, torres.id)
