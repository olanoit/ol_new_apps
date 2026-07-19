# -*- coding: utf-8 -*-
"""Datos de demostración + validación integral del módulo SIRE.

Ejecutar con:  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < sire_demo_data.py

Crea un periodo RVIE y uno RCE en modo carga manual con un TXT de propuesta
simulado (prefijo "DEMO SIRE", idempotente), despliega SIRE y Sistema, compara
y genera los exportables, validando cada paso.
"""
import base64

YEAR, MONTH = 2026, '07'
PERIOD = '%s%s' % (YEAR, MONTH)
company = env.company
results = []


def log(step, ok, detail=''):
    results.append((step, 'OK' if ok else 'FALLA', detail))
    print('  [%s] %s %s' % ('OK' if ok else 'XX', step, detail))


def get_or_create(model, domain, vals):
    rec = env[model].search(domain, limit=1)
    return rec or env[model].create(vals)


print('=== 1. Requisitos ===')
log('RUC de compañía', bool(company.vat and len(company.vat) == 11), company.vat or 'SIN RUC')

partner = get_or_create('res.partner', [('name', '=', 'DEMO SIRE SOCIO SAC')], {
    'name': 'DEMO SIRE SOCIO SAC',
    'vat': '20131312955',
    'country_id': env.ref('base.pe').id,
    'l10n_latam_identification_type_id': env['l10n_latam.identification.type'].search(
        [('l10n_pe_vat_code', '=', '6')], limit=1).id,
})

tax_sale = env['account.tax'].search([
    ('company_id', '=', company.id), ('type_tax_use', '=', 'sale'),
    ('amount', '=', 18), ('l10n_pe_edi_tax_code', '=', '1000')], limit=1)
tax_purchase = env['account.tax'].search([
    ('company_id', '=', company.id), ('type_tax_use', '=', 'purchase'),
    ('amount', '=', 18), ('l10n_pe_edi_tax_code', '=', '1000')], limit=1)
log('IGV 18%% venta/compra', bool(tax_sale and tax_purchase))

print('=== 2. Facturas de demostración ===')
invoice = env['account.move'].search([
    ('company_id', '=', company.id), ('move_type', '=', 'out_invoice'),
    ('partner_id', '=', partner.id), ('invoice_date', '=', '%s-%s-10' % (YEAR, MONTH)),
    ('state', '=', 'posted')], limit=1)
if not invoice:
    invoice = env['account.move'].create({
        'move_type': 'out_invoice',
        'partner_id': partner.id,
        'invoice_date': '%s-%s-10' % (YEAR, MONTH),
        'invoice_line_ids': [(0, 0, {
            'name': 'DEMO SIRE venta',
            'quantity': 1,
            'price_unit': 2500.0,
            'tax_ids': [(6, 0, tax_sale.ids)],
        })],
    })
    invoice.action_post()
log('Factura de venta', invoice.state == 'posted', invoice.name)

doc_type = env['l10n_latam.document.type'].search(
    [('code', '=', '01'), ('country_id.code', '=', 'PE')], limit=1)
bill = env['account.move'].search([
    ('company_id', '=', company.id), ('move_type', '=', 'in_invoice'),
    ('partner_id', '=', partner.id), ('ref', '=', 'F077-771'),
    ('state', '=', 'posted')], limit=1)
if not bill:
    bill = env['account.move'].create({
        'move_type': 'in_invoice',
        'partner_id': partner.id,
        'invoice_date': '%s-%s-12' % (YEAR, MONTH),
        'l10n_latam_document_type_id': doc_type.id,
        'l10n_latam_document_number': 'F077-771',
        'ref': 'F077-771',
        'l10n_pe_sire_goods_class': '1',
        'invoice_line_ids': [(0, 0, {
            'name': 'DEMO SIRE compra',
            'quantity': 1,
            'price_unit': 1800.0,
            'tax_ids': [(6, 0, tax_purchase.ids)],
        })],
    })
    bill.action_post()
log('Factura de compra', bill.state == 'posted', bill.name)

print('=== 3. Periodo RVIE (carga manual) ===')
rvie = get_or_create('l10n_pe.sire.rvie',
                     [('year', '=', YEAR), ('month', '=', MONTH),
                      ('company_id', '=', company.id)],
                     {'year': YEAR, 'month': MONTH, 'company_id': company.id,
                      'download_manual': True})
if rvie.state == 'done':
    log('RVIE ya realizado, se omite', True, rvie.name)
else:
    rvie.action_reset()
    rvie.download_manual = True
    # TXT de propuesta simulado con la misma factura del sistema
    serie, folio = invoice.name.split(' ')[-1].split('-') if '-' in invoice.name else ('F001', '1')
    folio = folio.lstrip('0') or '1'
    car = '%s%s%s%s' % (company.vat, '01', serie.zfill(4), folio.zfill(10))
    cols = [''] * 40
    cols[0], cols[1], cols[2], cols[3] = company.vat, company.name, PERIOD, car
    cols[4] = invoice.invoice_date.strftime('%d/%m/%Y')
    cols[6], cols[7], cols[8] = '01', serie, folio
    cols[10], cols[11], cols[12] = '6', partner.vat, partner.name
    cols[13] = '0.00'
    cols[14] = '%.2f' % invoice.amount_untaxed
    cols[15] = '0.00'
    cols[16] = '%.2f' % invoice.amount_tax
    cols[17] = cols[18] = cols[19] = cols[20] = cols[21] = cols[22] = cols[23] = cols[24] = '0.00'
    cols[25] = '%.2f' % invoice.amount_total
    cols[26] = 'PEN'
    cols[34] = '1'
    cols[36] = '0.00'
    cols[37] = '0101'
    txt = 'CABECERA\n' + '|'.join(cols)
    rvie.proposal_file = base64.b64encode(txt.encode('utf-8'))
    rvie.action_request_proposal()
    rvie.action_load_sire()
    log('RVIE desplegar SIRE', len(rvie.sire_line_ids) == 1, '%s líneas' % len(rvie.sire_line_ids))
    rvie.action_load_system()
    log('RVIE desplegar sistema', bool(rvie.system_line_ids), '%s líneas' % len(rvie.system_line_ids))
    rvie.action_compare()
    match = rvie.sire_line_ids.filtered(lambda l: l.car_sunat == car)
    log('RVIE comparación', rvie.state == 'compared',
        'estado línea demo: %s' % (match.compare_state or '-'))
    rvie.action_export_xlsx()
    log('RVIE XLSX', bool(rvie.export_file), rvie.export_filename)
    rvie.action_export_replacement()
    log('RVIE TXT reemplazo', bool(rvie.export_file), rvie.export_filename)

print('=== 4. Periodo RCE (carga manual) ===')
rce = get_or_create('l10n_pe.sire.rce',
                    [('year', '=', YEAR), ('month', '=', MONTH),
                     ('company_id', '=', company.id)],
                    {'year': YEAR, 'month': MONTH, 'company_id': company.id,
                     'download_manual': True})
if rce.state == 'done':
    log('RCE ya realizado, se omite', True, rce.name)
else:
    rce.action_reset()
    rce.download_manual = True
    car = '%s%s%s%s' % (partner.vat, '01', 'F077'.zfill(4), '771'.zfill(10))
    cols = [''] * 41
    cols[0], cols[1], cols[2], cols[3] = company.vat, company.name, PERIOD, car
    cols[4] = bill.invoice_date.strftime('%d/%m/%Y')
    cols[6], cols[7], cols[9] = '01', 'F077', '771'
    cols[11], cols[12], cols[13] = '6', partner.vat, partner.name
    cols[14] = '%.2f' % bill.amount_untaxed
    cols[15] = '%.2f' % bill.amount_tax
    for i in range(16, 24):
        cols[i] = '0.00'
    cols[24] = '%.2f' % bill.amount_total
    cols[25] = 'PEN'
    cols[32] = '1'
    cols[39] = '1'
    txt = 'CABECERA\n' + '|'.join(cols)
    rce.proposal_file = base64.b64encode(txt.encode('utf-8'))
    rce.action_request_proposal()
    rce.action_load_sire()
    log('RCE desplegar SIRE', len(rce.sire_line_ids) == 1, '%s líneas' % len(rce.sire_line_ids))
    rce.action_load_system()
    log('RCE desplegar sistema', bool(rce.system_line_ids), '%s líneas' % len(rce.system_line_ids))
    rce.action_compare()
    match = rce.sire_line_ids.filtered(lambda l: l.car_sunat == car)
    log('RCE comparación', rce.state == 'compared',
        'estado línea demo: %s' % (match.compare_state or '-'))
    rce.action_export_xlsx()
    log('RCE XLSX', bool(rce.export_file), rce.export_filename)
    rce.action_export_replacement()
    log('RCE TXT reemplazo', bool(rce.export_file), rce.export_filename)

env.cr.commit()
print('=== RESUMEN ===')
for step, status, detail in results:
    print('%-30s %s %s' % (step, status, detail))
fails = [r for r in results if r[1] == 'FALLA']
print('TOTAL: %s pasos, %s fallas' % (len(results), len(fails)))
