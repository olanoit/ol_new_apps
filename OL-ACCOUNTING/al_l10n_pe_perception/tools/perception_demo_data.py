"""Datos de percepciones de las capturas de la ficha (compañía 1 de ol_pe_v19).

Uso::

    odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < tools/perception_demo_data.py

Idempotente: lo que ya existe no se vuelve a crear.
"""
from datetime import date
from odoo import Command
company = env['res.company'].browse(1)
env = env(context=dict(env.context, allowed_company_ids=[1]))
Account = env['account.account'].with_company(company)
def account(code, name, kind):
    acc = Account.search([('code', '=', code)], limit=1)
    return acc or Account.create({'code': code, 'name': name, 'account_type': kind})
payable = account('401132', 'IGV percepciones por pagar', 'liability_current')
to_apply = account('401131', 'IGV percepciones por aplicar', 'asset_current')
misc = env['account.journal'].browse(3)
company.write({
    'l10n_pe_perception_agent': True, 'l10n_pe_perception_fuel_agent': False,
    'l10n_pe_perception_account_id': payable.id, 'l10n_pe_perception_journal_id': misc.id,
    'l10n_pe_perception_received_account_id': to_apply.id,
    'l10n_pe_perception_received_journal_id': misc.id,
})
ruc = env.ref('l10n_pe.it_RUC')
Partner = env['res.partner']
def partner(name, vat, **kw):
    p = Partner.search([('name', '=', name)], limit=1)
    return p or Partner.create(dict({'name': name, 'vat': vat, 'is_company': True,
        'l10n_latam_identification_type_id': ruc.id, 'country_id': env.ref('base.pe').id,
        'street': 'Av. Industrial 123', 'city': 'Lima'}, **kw))
customer = partner('Ferretería Los Andes SAC', '20601234565')
agent_customer = partner('Distribuidora Agente SAC', '20601234573', l10n_pe_is_perception_agent=True)
supplier = partner('Cementos del Sur SAC', '20601234581', l10n_pe_is_perception_agent=True)
aduana = Partner.search([('name', '=', 'SUNAT Aduanas')], limit=1) or Partner.create({'name': 'SUNAT Aduanas'})
igv = env['account.tax'].search([('company_id', '=', 1), ('type_tax_use', '=', 'sale'), ('amount', '=', 18), ('l10n_pe_edi_tax_code', '=', '1000')], limit=1)
igv_p = env['account.tax'].search([('company_id', '=', 1), ('type_tax_use', '=', 'purchase'), ('amount', '=', 18)], limit=1)
Product = env['product.product']
def product(name, ptype, price):
    p = Product.search([('name', '=', name)], limit=1)
    return p or Product.create({'name': name, 'type': 'consu', 'lst_price': price,
        'l10n_pe_perception_type': ptype, 'taxes_id': [Command.set(igv.ids)],
        'supplier_taxes_id': [Command.set(igv_p.ids)]})
cement = product('Cemento Portland tipo I (bolsa 42,5 kg)', 'internal', 28.0)
rod = product('Fierro corrugado 1/2"', 'internal', 45.0)
sale_j = env['account.journal'].search([('code', '=', 'DPSV'), ('company_id', '=', 1)])
purchase_j = env['account.journal'].search([('code', '=', 'DPSC'), ('company_id', '=', 1)])
Move = env['account.move']
def invoice(p, lines, day, ref):
    m = Move.search([('ref', '=', ref), ('company_id', '=', 1)], limit=1)
    if m:
        return m
    m = Move.create({'move_type': 'out_invoice', 'partner_id': p.id, 'journal_id': sale_j.id,
        'invoice_date': day, 'date': day, 'ref': ref,
        'invoice_line_ids': [Command.create({'product_id': pr.id, 'quantity': q, 'price_unit': pr.lst_price,
                                             'tax_ids': [Command.set(igv.ids)]}) for pr, q in lines]})
    m.action_post()
    return m
inv1 = invoice(customer, [(cement, 100), (rod, 20)], date(2026, 9, 7), 'Percepción V-1')
inv2 = invoice(agent_customer, [(cement, 300)], date(2026, 9, 10), 'Percepción V-2')
inv3 = invoice(customer, [(rod, 40)], date(2026, 9, 15), 'Percepción V-3')
Perception = env['l10n_pe.perception']
if not Perception.search([('partner_id', '=', customer.id)]):
    pay = env['account.payment.register'].with_context(active_model='account.move', active_ids=inv1.ids).create({
        'payment_date': date(2026, 9, 20), 'amount': round(inv1.amount_total + inv1.l10n_pe_perception_amount, 2),
        'payment_difference_handling': 'open'})._create_payments()
    action = pay.action_l10n_pe_create_perception()
    Perception.browse(action['res_id']).action_post()
if not Perception.search([('partner_id', '=', agent_customer.id)]):
    pay = env['account.payment.register'].with_context(active_model='account.move', active_ids=inv2.ids).create({
        'payment_date': date(2026, 9, 25), 'amount': round(inv2.amount_total + inv2.l10n_pe_perception_amount, 2),
        'payment_difference_handling': 'open'})._create_payments()
    action = pay.action_l10n_pe_create_perception()
    Perception.browse(action['res_id']).action_post()
Received = env['l10n_pe.perception.received']
bill = Move.search([('ref', '=', 'Percepción C-1')], limit=1)
if not bill:
    bill = Move.create({'move_type': 'in_invoice', 'partner_id': supplier.id, 'journal_id': purchase_j.id,
        'invoice_date': date(2026, 9, 5), 'date': date(2026, 9, 5), 'ref': 'Percepción C-1',
        'invoice_line_ids': [Command.create({'product_id': cement.id, 'quantity': 500, 'price_unit': 22.0,
                                             'tax_ids': [Command.set(igv_p.ids)]})]})
    bill.action_post()
if not Received.search([('partner_id', '=', supplier.id)]):
    Received.create({'partner_id': supplier.id, 'kind': 'internal', 'document_kind': 'cpe',
        'name': 'P001-00004521', 'date': date(2026, 9, 12),
        'line_ids': [Command.create({'bill_id': bill.id, 'base_amount': bill.amount_total,
                                     'amount': round(bill.amount_total * 0.02, 2)})]}).action_post()
if not Received.search([('partner_id', '=', aduana.id)]):
    Received.create({'partner_id': aduana.id, 'kind': 'import', 'document_kind': 'dua',
        'name': '118-2026-10-045678', 'date': date(2026, 9, 18),
        'line_ids': [Command.create({'reference': 'DAM 118-2026-10-045678', 'base_amount': 42000.0,
                                     'amount': 1470.0})]}).action_post()
env.cr.commit()
print('IDS', inv1.id, inv2.id, inv3.id, bill.id, Perception.search([('company_id', '=', 1)]).ids, Received.search([('company_id', '=', 1)]).ids)
print('PERC', [(p.name, p.amount_collected, p.amount_perception) for p in Perception.search([('company_id', '=', 1)])])
