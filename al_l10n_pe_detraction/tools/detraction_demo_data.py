# -*- coding: utf-8 -*-
"""Datos de demostración + validación de detracciones SPOT.

Ejecutar con:  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < detraction_demo_data.py

Crea registros «DEMO SPOT» (idempotente) y valida: cálculo en factura,
bloque spot del XML nativo, depósito con constancia, y su llegada a los
reportes PLE 8.3 y 14.2.
"""
import base64
from datetime import date

YEAR, MONTH = 2026, '07'
company = env.company
results = []


def log(name, ok, detail=''):
    results.append((name, 'OK' if ok else 'FALLA', detail))
    print('  [%s] %s %s' % ('OK' if ok else 'XX', name, detail))


def get_or_create(model, domain, vals):
    rec = env[model].search(domain, limit=1)
    return rec or env[model].create(vals)


print('=== 1. Datos de demostración SPOT ===')
Account = env['account.account'].with_company(company)
acc_inc = Account.search([('account_type', '=', 'income')], limit=1)
acc_exp = Account.search([('account_type', '=', 'expense')], limit=1)
tax_s = env['account.tax'].search([('company_id', '=', company.id),
                                   ('type_tax_use', '=', 'sale'),
                                   ('amount', '=', 18.0)], limit=1)
tax_p = env['account.tax'].search([('company_id', '=', company.id),
                                   ('type_tax_use', '=', 'purchase'),
                                   ('amount', '=', 18.0)], limit=1)
j_sale = get_or_create('account.journal', [('code', '=', 'DPSV')], {
    'name': 'DEMO PLE Ventas Simpl', 'code': 'DPSV', 'type': 'sale',
    'company_id': company.id, 'l10n_latam_use_documents': False})
j_purchase = get_or_create('account.journal', [('code', '=', 'DPSC')], {
    'name': 'DEMO PLE Compras Simpl', 'code': 'DPSC', 'type': 'purchase',
    'company_id': company.id, 'l10n_latam_use_documents': False})
j_bank = env['account.journal'].search(
    [('company_id', '=', company.id), ('type', '=', 'bank')], limit=1)
partner = get_or_create('res.partner', [('name', '=', 'DEMO SPOT Contraparte SAC')], {
    'name': 'DEMO SPOT Contraparte SAC', 'vat': '20131312955'})

# cuenta de detracciones en el Banco de la Nación (requisito del XML)
national_bank = env.ref('l10n_pe.peruvian_national_bank')
bn_account = get_or_create(
    'res.partner.bank',
    [('partner_id', '=', company.partner_id.id),
     ('bank_id', '=', national_bank.id)],
    {'partner_id': company.partner_id.id, 'bank_id': national_bank.id,
     'acc_number': '00-045-123456'})

dtype_37 = env.ref('al_l10n_pe_detraction.detraction_037')  # 12%
service = get_or_create('product.product',
                        [('default_code', '=', 'DEMO-SPOT-01')], {
    'name': 'DEMO SPOT Servicio Empresarial', 'type': 'service',
    'default_code': 'DEMO-SPOT-01',
    'l10n_pe_detraction_type_id': dtype_37.id})
log('producto sync', service.l10n_pe_withhold_code == '037'
    and service.l10n_pe_withhold_percentage == 12.0,
    'código=%s %%=%s' % (service.l10n_pe_withhold_code,
                         service.l10n_pe_withhold_percentage))


def make_invoice(move_type, price, day, ref=False):
    journal = j_sale if move_type == 'out_invoice' else j_purchase
    tax = tax_s if move_type == 'out_invoice' else tax_p
    account = acc_inc if move_type == 'out_invoice' else acc_exp
    move = env['account.move'].create({
        'move_type': move_type, 'partner_id': partner.id,
        'journal_id': journal.id,
        'invoice_date': date(YEAR, int(MONTH), day),
        'date': date(YEAR, int(MONTH), day),
        'ref': ref,
        'invoice_line_ids': [(0, 0, {
            'name': service.name, 'product_id': service.id,
            'quantity': 1.0, 'price_unit': price,
            'account_id': account.id,
            'tax_ids': [(6, 0, tax.ids)]})]})
    move.action_post()
    return move


invoice = env['account.move'].search(
    [('journal_id', '=', j_sale.id), ('partner_id', '=', partner.id),
     ('state', '=', 'posted'),
     ('invoice_line_ids.product_id', '=', service.id)], limit=1)
if not invoice:
    invoice = make_invoice('out_invoice', 5000.0, 21)      # total 5900
bill = env['account.move'].search(
    [('journal_id', '=', j_purchase.id), ('partner_id', '=', partner.id),
     ('state', '=', 'posted'),
     ('invoice_line_ids.product_id', '=', service.id)], limit=1)
if not bill:
    bill = make_invoice('in_invoice', 2000.0, 22,
                        ref='F001-00000888')               # total 2360
env.cr.commit()

print('=== 2. Cálculo y XML (venta) ===')
log('venta aplica', invoice.l10n_pe_detraction_applies
    and invoice.l10n_pe_detraction_percent == 12.0,
    'base=%.2f %%=%.1f' % (abs(invoice.amount_total_signed),
                           invoice.l10n_pe_detraction_percent))
expected = round(abs(invoice.amount_total_signed) * 0.12)
log('venta monto redondeado',
    invoice.l10n_pe_detraction_amount == expected,
    'monto=%.2f esperado=%d neto=%.2f' % (
        invoice.l10n_pe_detraction_amount, expected,
        invoice.l10n_pe_detraction_net))
log('op. EDI 1001 automática',
    invoice.l10n_pe_edi_operation_type == '1001',
    invoice.l10n_pe_edi_operation_type)
spot = invoice._l10n_pe_edi_get_spot()
log('bloque spot XML nativo', bool(spot)
    and spot.get('payment_means_code') == '999'
    and spot.get('payee_financial_account') == bn_account.acc_number,
    'means=%s cuenta BN=%s monto=%s' % (
        spot.get('payment_means_code'),
        spot.get('payee_financial_account'), spot.get('amount')))

print('=== 3. Depósito y constancia (compra) ===')
log('compra aplica', bill.l10n_pe_detraction_applies
    and bill.l10n_pe_detraction_amount == round(
        abs(bill.amount_total_signed) * 0.12),
    'monto=%.2f' % bill.l10n_pe_detraction_amount)
if not bill.l10n_pe_detraction_number:
    wizard = env['l10n_pe.detraction.deposit.wizard'].create({
        'move_id': bill.id, 'journal_id': j_bank.id,
        'payment_date': date(YEAR, int(MONTH), 23),
        'constancy_number': 'DEMO-2026-0001'})
    wizard.action_confirm()
log('constancia registrada',
    bill.l10n_pe_detraction_number == 'DEMO-2026-0001'
    and bool(bill.l10n_pe_detraction_date)
    and bill.payment_state in ('in_payment', 'paid', 'partial'),
    '%s %s estado=%s' % (bill.l10n_pe_detraction_number,
                         bill.l10n_pe_detraction_date, bill.payment_state))
env.cr.commit()

print('=== 4. Llegada a los reportes PLE (8.3 / 14.2) ===')
company.l10n_pe_ple_simplified = True
for label, flag, code, move, checks in (
        ('8.3 constancia', 'export_83', '080300', bill,
         lambda row: row[23] == '23/07/2026' and row[24] == 'DEMO-2026-0001'),
        ('14.2 venta', 'export_142', '140200', invoice,
         lambda row: row[12] == '%.2f' % invoice.amount_untaxed
         and row[16] == '%.2f' % invoice.amount_total)):
    wizard = env['l10n_pe.ple.export.wizard'].create({
        'year': YEAR, 'month': MONTH, 'generate_xlsx': False,
        'export_71': False, flag: True})
    wizard.action_export()
    content = base64.b64decode(wizard.file_data).decode()
    row = next((l.split('|') for l in content.split('\r\n')
                if l and l.split('|')[1] == str(move.id)), None)
    log(label, bool(row) and checks(row),
        'fila encontrada=%s' % bool(row))

env.cr.commit()
print('=== RESUMEN ===')
for name, status, detail in results:
    print('%-26s %-6s %s' % (name, status, detail))
fails = [r for r in results if r[1] != 'OK']
print('TOTAL: %d validaciones, %d fallas' % (len(results), len(fails)))
