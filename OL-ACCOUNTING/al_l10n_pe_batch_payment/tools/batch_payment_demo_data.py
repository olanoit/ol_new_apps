# -*- coding: utf-8 -*-
"""Datos de demostración del pago masivo para las capturas (odoo shell, se guarda).

    odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 < tools/batch_payment_demo_data.py
"""
from datetime import date

# El usuario administrador: confiar en cuentas bancarias exige su permiso.
env = env(user=env.ref('base.user_admin'))
company = env.company
pen = env.ref('base.PEN')
Bank = env['res.bank']


def bank(name, fmt):
    return Bank.search([('name', '=', name)], limit=1) or Bank.create(
        {'name': name, 'l10n_pe_batch_format': fmt})


bcp = bank('BCP', 'bcp')
bbva = bank('BBVA', 'bbva')
ibk = bank('Interbank', 'interbank')
journal = env['account.journal'].search([('code', '=', 'DBCP'), ('company_id', '=', company.id)])
if not journal:
    account = env['res.partner.bank'].create({
        'partner_id': company.partner_id.id, 'bank_id': bcp.id, 'account_number': '191-2233445-0-66',
        'currency_id': pen.id})
    journal = env['account.journal'].create({
        'name': 'BCP soles', 'code': 'DBCP', 'type': 'bank', 'currency_id': pen.id,
        'bank_account_id': account.id, 'l10n_pe_batch_service_code': 'P'})
ruc = env.ref('l10n_pe.it_RUC')
suppliers = []
for name, vat, b, acc, cci in (
        ('Maderas del Sur SAC', '20100070970', bcp, '193-7654321-0-22', ''),
        ('Herrajes Lima SAC', '20131312955', bbva, '0011-0456-0200098765',
         '01145600020009876512'),
        ('Transportes Andinos SAC', '20100047218', ibk, '200-3001234567',
         '00320000300123456713')):
    partner = env['res.partner'].search([('name', '=', name)], limit=1) or env['res.partner'].create({
        'name': name, 'is_company': True, 'vat': vat, 'country_id': env.ref('base.pe').id,
        'l10n_latam_identification_type_id': ruc.id})
    bank_account = partner.bank_ids[:1] or env['res.partner.bank'].create({
        'partner_id': partner.id, 'bank_id': b.id, 'account_number': acc, 'l10n_pe_cci': cci or False,
        'allow_out_payment': True})
    bank_account.allow_out_payment = True  # cuenta de confianza: Odoo la exige para pagar
    suppliers.append((partner, bank_account))
line = journal.outbound_payment_method_line_ids.filtered(lambda l: l.code == 'pe_bank_txt')
batch = env['account.batch.payment'].search([('journal_id', '=', journal.id)], limit=1)
if not batch:
    payments = env['account.payment']
    for (partner, bank_account), value in zip(suppliers, (4820.0, 1350.75, 690.0)):
        payments |= env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': partner.id,
            'partner_bank_id': bank_account.id, 'amount': value, 'journal_id': journal.id,
            'payment_method_line_id': line.id, 'date': date(2026, 10, 12),
            'memo': 'F001-%s' % partner.id})
    payments.action_post()
    batch = env['account.batch.payment'].create({
        'journal_id': journal.id, 'batch_type': 'outbound',
        'payment_method_id': env.ref('al_l10n_pe_batch_payment.account_payment_method_pe_bank_txt').id,
        'payment_ids': [(6, 0, payments.ids)]})
    batch.validate_batch()
env.cr.commit()
print('Pago masivo', batch.id, batch.name, batch.export_filename, batch.l10n_pe_export_count, journal.id,
      suppliers[1][1].id)
