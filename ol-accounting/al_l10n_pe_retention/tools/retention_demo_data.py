# -*- coding: utf-8 -*-
"""Datos demo + validación integral de retenciones IGV (prefijo DEMO RET).

Ejecutar con:  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < retention_demo_data.py
"""
import base64
from datetime import date

YEAR, MONTH = 2026, '07'
company = env.company
results = []


def log(name, ok, detail=''):
    results.append((name, 'OK' if ok else 'FALLA', detail))
    print('  [%s] %-34s %s' % ('OK' if ok else 'XX', name, detail))


def get_or_create(model, domain, vals):
    rec = env[model].search(domain, limit=1)
    return rec or env[model].create(vals)


print('=== 1. Configuración del agente ===')
Account = env['account.account'].with_company(company)
acc_ret = get_or_create('account.account', [('code', '=', '401141')], {
    'code': '401141', 'name': 'IGV Retenciones por pagar (DEMO)',
    'account_type': 'liability_current'})
acc_suf = get_or_create('account.account', [('code', '=', '401142')], {
    'code': '401142', 'name': 'IGV Retenciones sufridas (DEMO)',
    'account_type': 'asset_current'})
sequence = get_or_create('ir.sequence', [('code', '=', 'l10n_pe.cre.demo')], {
    'name': 'CRE DEMO', 'code': 'l10n_pe.cre.demo', 'prefix': 'R001-',
    'padding': 8, 'company_id': company.id})
tax = env['account.tax'].search(
    [('company_id', '=', company.id),
     ('name', '=', 'Retención IGV 3%')], limit=1)
if not tax:
    tax = env['account.tax'].create({
        'name': 'Retención IGV 3%', 'amount': -3.0,
        'amount_type': 'percent', 'type_tax_use': 'purchase',
        'is_withholding_tax_on_payment': True,
        'withholding_sequence_id': sequence.id, 'company_id': company.id})
    tax.invoice_repartition_line_ids.filtered(
        lambda l: l.repartition_type == 'tax').account_id = acc_ret
    tax.refund_repartition_line_ids.filtered(
        lambda l: l.repartition_type == 'tax').account_id = acc_ret
acc_out = get_or_create('account.account', [('code', '=', '104901')], {
    'code': '104901', 'name': 'Pagos pendientes (DEMO)',
    'account_type': 'asset_current', 'reconcile': True})
company.write({
    'l10n_pe_retention_agent': True, 'l10n_pe_retention_rate': 3.0,
    'l10n_pe_retention_min_amount': 700.0,
    'l10n_pe_retention_tax_id': tax.id,
    'l10n_pe_retention_received_account_id': acc_suf.id,
    'l10n_pe_retention_outstanding_account_id': acc_out.id})
log('configuración agente', bool(company.l10n_pe_retention_tax_id),
    'impuesto=%s' % tax.name)

acc_exp = Account.search([('account_type', '=', 'expense')], limit=1)
acc_inc = Account.search([('account_type', '=', 'income')], limit=1)
tax_p = env['account.tax'].search([('company_id', '=', company.id),
                                   ('type_tax_use', '=', 'purchase'),
                                   ('amount', '=', 18.0)], limit=1)
tax_s = env['account.tax'].search([('company_id', '=', company.id),
                                   ('type_tax_use', '=', 'sale'),
                                   ('amount', '=', 18.0)], limit=1)
j_purchase = get_or_create('account.journal', [('code', '=', 'DPSC')], {
    'name': 'DEMO PLE Compras Simpl', 'code': 'DPSC', 'type': 'purchase',
    'company_id': company.id, 'l10n_latam_use_documents': False})
j_sale = get_or_create('account.journal', [('code', '=', 'DPSV')], {
    'name': 'DEMO PLE Ventas Simpl', 'code': 'DPSV', 'type': 'sale',
    'company_id': company.id, 'l10n_latam_use_documents': False})
partner = get_or_create('res.partner', [('name', '=', 'DEMO RET Proveedor SAC')], {
    'name': 'DEMO RET Proveedor SAC', 'vat': '20131312955'})

print('=== 2. Compra: retención en el pago ===')
bill = env['account.move'].search(
    [('invoice_origin', '=', 'DEMO RET compra'),
     ('state', '=', 'posted')], limit=1)
if not bill:
    bill = env['account.move'].create({
        'move_type': 'in_invoice', 'partner_id': partner.id,
        'journal_id': j_purchase.id, 'invoice_origin': 'DEMO RET compra',
        'invoice_date': date(YEAR, int(MONTH), 16),
        'date': date(YEAR, int(MONTH), 16), 'ref': 'F00T-00000901',
        'invoice_line_ids': [(0, 0, {
            'name': 'Servicio con retención', 'quantity': 1,
            'price_unit': 2000.0, 'account_id': acc_exp.id,
            'tax_ids': [(6, 0, tax_p.ids)]})]})
    bill.action_post()
log('aplica y estima', bill.l10n_pe_retention_applies
    and abs(bill.l10n_pe_retention_amount - 70.80) < 0.01,
    'total=%.2f estimado=%.2f' % (bill.amount_total,
                                  bill.l10n_pe_retention_amount))
log('impuesto inyectado sin alterar total',
    tax in bill.invoice_line_ids.tax_ids and bill.amount_total == 2360.0,
    'total=%.2f' % bill.amount_total)
payment = env['account.payment'].search(
    [('partner_id', '=', partner.id),
     ('l10n_pe_retention_number', '!=', False)], limit=1)
if not payment:
    wizard = env['account.payment.register'].with_context(
        active_model='account.move', active_ids=bill.ids).create({
            'payment_date': date(YEAR, int(MONTH), 17)})
    wh = wizard.withholding_line_ids
    log('wizard propone 3%% del pago', len(wh) == 1
        and abs(wh.amount - 70.80) < 0.01, 'monto=%.2f' % wh.amount)
    payment = wizard._create_payments()
else:
    log('wizard propone 3% del pago', True, '(pago ya existente)')
log('comprobante numerado', bool(payment.l10n_pe_retention_number)
    and payment.l10n_pe_retention_number.startswith('R001-'),
    payment.l10n_pe_retention_number or '-')
action = payment.action_l10n_pe_generate_cre_xml()
attachment = env['ir.attachment'].search(
    [('res_model', '=', 'account.payment'), ('res_id', '=', payment.id),
     ('mimetype', '=', 'application/xml')], limit=1, order='id desc')
xml = attachment.raw.decode()
log('XML CRE generado', xml.startswith('<?xml')
    and 'SUNATRetentionDocumentReference' in xml
    and (company.vat or '') in xml, attachment.name)

print('=== 3. Venta: retención sufrida ===')
invoice = env['account.move'].search(
    [('invoice_origin', '=', 'DEMO RET venta'),
     ('state', '=', 'posted')], limit=1)
if not invoice:
    invoice = env['account.move'].create({
        'move_type': 'out_invoice', 'partner_id': partner.id,
        'journal_id': j_sale.id, 'invoice_origin': 'DEMO RET venta',
        'invoice_date': date(YEAR, int(MONTH), 16),
        'date': date(YEAR, int(MONTH), 16),
        'invoice_line_ids': [(0, 0, {
            'name': 'Venta a cliente agente', 'quantity': 1,
            'price_unit': 3000.0, 'account_id': acc_inc.id,
            'tax_ids': [(6, 0, tax_s.ids)]})]})
    invoice.action_post()
received = env['l10n_pe.retention.received'].search(
    [('move_id', '=', invoice.id)], limit=1)
if not received:
    received = env['l10n_pe.retention.received'].create({
        'name': 'R777-00000055', 'date': date(YEAR, int(MONTH), 18),
        'partner_id': partner.id, 'move_id': invoice.id,
        'amount': 106.20})
    received.action_post()
log('retención sufrida registrada', received.state == 'posted'
    and received.entry_id.state == 'posted'
    and abs(invoice.amount_residual - (3540.0 - 106.20)) < 0.01,
    'residual=%.2f asiento=%s' % (invoice.amount_residual,
                                  received.entry_id.name))

print('=== 4. Reportes ===')
summary = env['l10n_pe.retention.summary.wizard'].create(
    {'year': YEAR, 'month': MONTH})
summary.action_export()
content = base64.b64decode(summary.file_data).decode()
log('resumen 626', partner.vat in content and '70.80' in content,
    summary.file_name)
company.l10n_pe_ple_simplified = True
ple = env['l10n_pe.ple.export.wizard'].create({
    'year': YEAR, 'month': MONTH, 'generate_xlsx': False,
    'export_71': False, 'export_83': True})
ple.action_export()
ple_content = base64.b64decode(ple.file_data).decode()
row = next((l.split('|') for l in ple_content.split('\r\n')
            if l and l.split('|')[1] == str(bill.id)), None)
log('marca retención en PLE 8.3', bool(row) and row[25] == '1',
    'campo 26=%s' % (row[25] if row else '-'))

env.cr.commit()
print('=== RESUMEN ===')
for name, status, detail in results:
    print('%-36s %-6s %s' % (name, status, detail))
fails = [r for r in results if r[1] != 'OK']
print('TOTAL: %d validaciones, %d fallas' % (len(results), len(fails)))
