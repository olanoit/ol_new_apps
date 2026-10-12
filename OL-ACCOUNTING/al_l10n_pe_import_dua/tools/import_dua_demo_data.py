# -*- coding: utf-8 -*-
"""Datos «DEMO DUA» para las capturas de la ficha (ejecutar en odoo shell):

    odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 < OL-ACCOUNTING/al_l10n_pe_import_dua/tools/import_dua_demo_data.py
"""
from odoo import Command, fields

company = env.company
Partner = env['res.partner']
customs = Partner.search([('name', '=', 'SUNAT - Superintendencia Nacional de Aduanas')], limit=1) or Partner.create({
    'name': 'SUNAT - Superintendencia Nacional de Aduanas', 'is_company': True,
    'country_id': env.ref('base.pe').id,
    'l10n_latam_identification_type_id': env.ref('l10n_pe.it_RUC').id, 'vat': '20131312955'})
offset = env['account.account'].search([('code', '=', '609190'), *env['account.account']._check_company_domain(company)], limit=1) \
    or env['account.account'].create({'name': 'Valor en aduana por regularizar', 'code': '609190',
                                      'account_type': 'expense'})
company.write({'l10n_pe_dua_partner_id': customs.id, 'l10n_pe_dua_offset_account_id': offset.id})
journal = env['account.journal'].search([*env['account.journal']._check_company_domain(company),
                                         ('type', '=', 'purchase'), ('l10n_latam_use_documents', '=', True)], limit=1)
company.l10n_pe_dua_journal_id = journal
category = env['product.category'].search([('name', '=', 'DEMO DUA importados')], limit=1) or env['product.category'].create({
    'name': 'DEMO DUA importados', 'property_cost_method': 'average', 'property_valuation': 'real_time'})
product = env['product.product'].search([('name', '=', 'DEMO DUA Motobomba importada')], limit=1) or env['product.product'].create({
    'name': 'DEMO DUA Motobomba importada', 'is_storable': True, 'categ_id': category.id,
    'standard_price': 1000.0, 'weight': 45.0})
supplier = Partner.search([('name', '=', 'DEMO DUA Pumps Inc.')], limit=1) or Partner.create({
    'name': 'DEMO DUA Pumps Inc.', 'is_company': True, 'country_id': env.ref('base.us').id})
picking_type = env['stock.picking.type'].search([('code', '=', 'incoming'), ('company_id', '=', company.id)], limit=1)
suppliers_loc = env.ref('stock.stock_location_suppliers')
picking = env['stock.picking'].create({
    'picking_type_id': picking_type.id, 'partner_id': supplier.id, 'origin': 'DEMO DUA',
    'location_id': suppliers_loc.id, 'location_dest_id': picking_type.default_location_dest_id.id,
    'move_ids': [Command.create({'product_id': product.id, 'product_uom_qty': 10.0, 'price_unit': 1000.0,
                                 'location_id': suppliers_loc.id,
                                 'location_dest_id': picking_type.default_location_dest_id.id})]})
picking.action_confirm()
picking.move_ids.quantity = 10.0
picking.button_validate()
foreign = env['account.move'].create({
    'move_type': 'in_invoice', 'partner_id': supplier.id, 'ref': 'DEMO DUA INV-2026-118',
    'invoice_date': fields.Date.from_string('2026-10-01'),
    'invoice_line_ids': [Command.create({'product_id': product.id, 'quantity': 10.0, 'price_unit': 1000.0,
                                         'tax_ids': [Command.clear()]})]})
plain = env['account.journal'].search([('code', '=', 'GIMP'), ('company_id', '=', company.id)], limit=1) or \
    env['account.journal'].create({'name': 'Gastos de importación', 'code': 'GIMP', 'type': 'purchase',
                                   'l10n_latam_use_documents': False})
agent = Partner.search([('name', '=', 'DEMO DUA Agencia de Aduanas')], limit=1) or Partner.create({
    'name': 'DEMO DUA Agencia de Aduanas', 'is_company': True})
expense = env['account.move'].create({
    'move_type': 'in_invoice', 'partner_id': agent.id, 'journal_id': plain.id,
    'invoice_date': fields.Date.from_string('2026-10-06'), 'ref': 'DEMO DUA agente',
    'invoice_line_ids': [Command.create({'product_id': env.ref('al_l10n_pe_import_dua.product_dua_other').id,
                                         'name': 'Comisión y gastos operativos del agente de aduana',
                                         'price_unit': 350.0, 'tax_ids': [Command.clear()]})]})
expense.action_post()
dua = env['account.move'].create({
    'move_type': 'in_invoice', 'partner_id': customs.id, 'journal_id': journal.id,
    'l10n_latam_document_type_id': env.ref('l10n_pe.document_type50').id,
    'invoice_date': fields.Date.from_string('2026-10-05'),
    'l10n_pe_dua_customs_code': '118', 'l10n_pe_dua_year': '2026', 'l10n_pe_dua_regime': '10',
    'l10n_pe_dua_sequence': '204518',
    'l10n_pe_dua_customs_value': 37450.0, 'l10n_pe_dua_ad_valorem': 2247.0,
    'l10n_pe_dua_other_duties': 120.0, 'l10n_pe_dua_perception': 1633.15,
    'l10n_pe_dua_picking_ids': [Command.set(picking.ids)],
    'l10n_pe_dua_expense_move_ids': [Command.set(expense.ids)],
    'l10n_pe_dua_split_method': 'by_quantity'})
dua.l10n_pe_dua_foreign_invoice_ids = foreign
dua.action_l10n_pe_dua_generate_lines()
try:
    dua.action_post()
    action = dua.action_l10n_pe_dua_create_landed_costs()
    print('DEMO DUA', dua.id, dua.l10n_latam_document_number, dua.amount_total, 'costo', action['res_id'])
except Exception as exc:  # noqa: BLE001 - la demo se reporta y sigue
    print('DEMO DUA sin publicar:', exc)
env.cr.commit()
