# -*- coding: utf-8 -*-
"""Datos de demostración + validación integral de los reportes PLE.

Ejecutar con:  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < ple_demo.py

Crea registros con prefijo "DEMO PLE" (idempotente: si ya existen, los
reutiliza) y luego genera cada TXT validando nombre y estructura.
"""
import base64
from datetime import date, datetime

YEAR, MONTH = 2026, '07'
BALANCE = date(2026, 7, 31)
company = env.company
mixin = env['l10n_pe.ple.mixin']
Account = env['account.account'].with_company(company)
results = []


def log(fmt, ok, detail=''):
    results.append((fmt, 'OK' if ok else 'FALLA', detail))
    print('  [%s] %s %s' % ('OK' if ok else 'XX', fmt, detail))


def get_or_create(model, domain, vals):
    rec = env[model].search(domain, limit=1)
    return rec or env[model].create(vals)


print('=== 1. Datos de demostración ===')
acc_fixed = Account.search([('account_type', '=', 'asset_fixed')], limit=1)
acc_dep = Account.search([('account_type', '=', 'asset_fixed'),
                          ('id', '!=', acc_fixed.id)], limit=1)
acc_exp = Account.search([('account_type', '=', 'expense')], limit=1)
acc_inc = Account.search([('account_type', '=', 'income')], limit=1)
acc_34 = Account.search([('code', '=like', '34%')], limit=1)
journal_gen = env['account.journal'].search(
    [('company_id', '=', company.id), ('type', '=', 'general')], limit=1)

usd = env.ref('base.USD')
usd.active = True
dni = env['l10n_latam.identification.type'].search(
    [('l10n_pe_vat_code', '=', '1')], limit=1)
ruc = env['l10n_latam.identification.type'].search(
    [('l10n_pe_vat_code', '=', '6')], limit=1)

p_dni = get_or_create('res.partner', [('name', '=', 'DEMO PLE Prestador')], {
    'name': 'DEMO PLE Prestador',
    'l10n_latam_identification_type_id': dni.id, 'vat': '46779810'})
p_ruc = get_or_create('res.partner', [('name', '=', 'DEMO PLE Consignatario SAC')], {
    'name': 'DEMO PLE Consignatario SAC',
    'l10n_latam_identification_type_id': ruc.id, 'vat': '20131312955'})

# --- Libro 7: activos fijos ---------------------------------------------
asset_vals = {
    'method': 'linear', 'method_number': 5, 'method_period': '12',
    'account_asset_id': acc_fixed.id, 'account_depreciation_id': acc_dep.id,
    'account_depreciation_expense_id': acc_exp.id, 'journal_id': journal_gen.id,
}
a1 = get_or_create('account.asset', [('name', '=', 'DEMO PLE Camioneta')], dict(
    asset_vals, name='DEMO PLE Camioneta', original_value=60000.0,
    acquisition_date=date(2026, 1, 15), prorata_date=date(2026, 1, 15),
    l10n_pe_ple_code='AF-DEMO-001', l10n_pe_asset_type='1',
    l10n_pe_brand='Toyota', l10n_pe_model='Hilux', l10n_pe_plate='DEM-001'))
a2 = get_or_create('account.asset', [('name', '=', 'DEMO PLE Montacargas Leasing')], dict(
    asset_vals, name='DEMO PLE Montacargas Leasing', original_value=45000.0,
    acquisition_date=date(2026, 2, 1), prorata_date=date(2026, 2, 1),
    l10n_pe_ple_code='AF-DEMO-002', l10n_pe_asset_type='1',
    l10n_pe_is_leasing=True, l10n_pe_leasing_contract='CT-2026-0099',
    l10n_pe_leasing_date=date(2026, 1, 20), l10n_pe_leasing_start=date(2026, 2, 1),
    l10n_pe_leasing_installments=36, l10n_pe_leasing_total=52000.0))
a3 = get_or_create('account.asset', [('name', '=', 'DEMO PLE Servidor USD')], dict(
    asset_vals, name='DEMO PLE Servidor USD', original_value=15000.0,
    acquisition_date=date(2026, 3, 10), prorata_date=date(2026, 3, 10),
    l10n_pe_ple_code='AF-DEMO-003', l10n_pe_asset_type='1',
    l10n_pe_fx_currency_id=usd.id, l10n_pe_fx_amount=4000.0,
    l10n_pe_fx_rate=3.750))
a4 = get_or_create('account.asset', [('name', '=', 'DEMO PLE Licencia ERP')], dict(
    asset_vals, name='DEMO PLE Licencia ERP', original_value=12000.0,
    acquisition_date=date(2026, 1, 2), prorata_date=date(2026, 1, 2),
    account_asset_id=acc_34.id, method_number=4,
    l10n_pe_ple_code='AF-DEMO-004', l10n_pe_asset_type='1'))
assets = a1 | a2 | a3 | a4
assets.filtered(lambda a: a.state == 'draft').write({'state': 'open'})
if not env['account.move'].search([('asset_id', 'in', assets.ids)], limit=1):
    for asset, amount in ((a1, 1000.0), (a2, 750.0), (a3, 250.0), (a4, 250.0)):
        move = env['account.move'].create({
            'move_type': 'entry', 'date': date(2026, 7, 15),
            'journal_id': journal_gen.id, 'asset_id': asset.id,
            'ref': 'DEMO PLE depreciación %s' % asset.name,
            'line_ids': [
                (0, 0, {'account_id': acc_exp.id, 'debit': amount, 'credit': 0}),
                (0, 0, {'account_id': acc_dep.id, 'debit': 0, 'credit': amount}),
            ]})
        move.action_post()

# --- 4.1 retenciones -----------------------------------------------------
if not env['l10n_pe.ple.withholding'].search([('partner_id', '=', p_dni.id)], limit=1):
    env['l10n_pe.ple.withholding'].create([
        {'date': date(2026, 7, 10), 'partner_id': p_dni.id,
         'gross_amount': 6000.0, 'withheld_amount': 480.0},
        {'date': date(2026, 7, 24), 'partner_id': p_dni.id,
         'gross_amount': 2500.0, 'withheld_amount': 0.0},
    ])

# --- 9.1 / 9.2 consignaciones -------------------------------------------
prod = get_or_create('product.product', [('default_code', '=', 'DEMO-CONS-01')], {
    'name': 'DEMO PLE Producto Consignado', 'type': 'consu',
    'default_code': 'DEMO-CONS-01', 'l10n_pe_type_of_existence': '1'})
pt_out = env['stock.picking.type'].search(
    [('code', '=', 'outgoing'), ('company_id', '=', company.id)], limit=1)
pt_in = env['stock.picking.type'].search(
    [('code', '=', 'incoming'), ('company_id', '=', company.id)], limit=1)


def make_picking(pt, kind, qty, day):
    dest = pt.default_location_dest_id or env.ref('stock.stock_location_customers')
    src = pt.default_location_src_id or env.ref('stock.stock_location_suppliers')
    picking = env['stock.picking'].create({
        'picking_type_id': pt.id, 'partner_id': p_ruc.id,
        'origin': 'DEMO PLE %s' % kind,
        'location_id': src.id, 'location_dest_id': dest.id,
        'l10n_pe_consignment': kind,
        'move_ids': [(0, 0, {
            'product_id': prod.id, 'product_uom_qty': qty,
            'product_uom': prod.uom_id.id,
            'location_id': src.id, 'location_dest_id': dest.id})],
    })
    picking.move_ids.write({'state': 'done',
                            'date': datetime(2026, 7, day, 12, 0)})
    picking.write({'state': 'done'})
    return picking


if not env['stock.picking'].search([('origin', 'like', 'DEMO PLE')], limit=1):
    make_picking(pt_out, 'out_delivery', 10.0, 5)
    make_picking(pt_out, 'out_return', 2.0, 12)
    make_picking(pt_out, 'out_sale', 3.0, 20)
    make_picking(pt_in, 'in_receipt', 7.0, 8)

# --- Libro 3: 3.8 y 3.19 -------------------------------------------------
if not env['l10n_pe.ple.investment'].search([('date', '=', BALANCE)], limit=1):
    env['l10n_pe.ple.investment'].create({
        'date': BALANCE, 'issuer_name': 'DEMO Minera Andina S.A.A.',
        'title_code': '1', 'nominal_value': 10.0, 'quantity': 800,
        'book_cost': 8800.0, 'provision': 400.0})
rubric = env['l10n_pe_reports_lib.financial.rubric'].search(
    [('name', '=like', '4%')], limit=2) or \
    env['l10n_pe_reports_lib.financial.rubric'].search([], limit=2)
if not env['l10n_pe.ple.equity'].search([('date', '=', BALANCE)], limit=1):
    env['l10n_pe.ple.equity'].create([
        {'date': BALANCE, 'rubric_id': rubric[0].id, 'capital': 250000.0,
         'legal_reserves': 12000.0, 'net_result': 34000.0},
        {'date': BALANCE, 'rubric_id': rubric[-1].id,
         'retained_earnings': 18000.0, 'period_result': 34000.0},
    ])

# --- Libro 10 ------------------------------------------------------------
get_or_create('l10n_pe.ple.cost.sales', [('year', '=', YEAR),
                                         ('company_id', '=', company.id)], {
    'year': YEAR, 'initial_finished': 20000.0, 'production_cost': 90000.0,
    'final_finished': 15000.0, 'adjustments': 500.0})
for month, mat in (('06', 7000.0), ('07', 7500.0)):
    get_or_create('l10n_pe.ple.cost.element',
                  [('year', '=', YEAR), ('month', '=', month),
                   ('company_id', '=', company.id)],
                  {'year': YEAR, 'month': month, 'direct_materials': mat,
                   'direct_labor': 4000.0, 'gif_materials': 900.0})
get_or_create('l10n_pe.ple.cost.production',
              [('year', '=', YEAR), ('process_code', '=', 'DEMO-PR1')],
              {'year': YEAR, 'process_code': 'DEMO-PR1',
               'process_name': 'DEMO Proceso de ensamblaje',
               'direct_materials': 14500.0, 'direct_labor': 8000.0,
               'initial_wip': 3000.0, 'final_wip': 1800.0,
               'grouping_code': '1'})
get_or_create('l10n_pe.ple.cost.center',
              [('year', '=', YEAR), ('cost_center_code', '=', 'DEMO-CC1')],
              {'year': YEAR, 'operation_unit_code': 'DEMO-UO1',
               'operation_unit_name': 'DEMO Unidad Lima',
               'cost_center_code': 'DEMO-CC1',
               'cost_center_name': 'DEMO Planta Lima'})

# --- Simplificados: facturas ---------------------------------------------
company.l10n_pe_ple_simplified = True
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
if not env['account.move'].search([('journal_id', '=', j_sale.id),
                                   ('state', '=', 'posted')], limit=1):
    inv = env['account.move'].create({
        'move_type': 'out_invoice', 'partner_id': p_ruc.id,
        'journal_id': j_sale.id, 'invoice_date': date(2026, 7, 18),
        'date': date(2026, 7, 18),
        'invoice_line_ids': [(0, 0, {
            'name': 'DEMO PLE venta gravada', 'quantity': 1.0,
            'price_unit': 1000.0, 'account_id': acc_inc.id,
            'tax_ids': [(6, 0, tax_s.ids)]})]})
    inv.action_post()
    bill = env['account.move'].create({
        'move_type': 'in_invoice', 'partner_id': p_ruc.id,
        'journal_id': j_purchase.id, 'invoice_date': date(2026, 7, 17),
        'date': date(2026, 7, 17), 'ref': 'F001-00000777',
        'invoice_line_ids': [(0, 0, {
            'name': 'DEMO PLE compra gravada', 'quantity': 1.0,
            'price_unit': 500.0, 'account_id': acc_exp.id,
            'tax_ids': [(6, 0, tax_p.ids)]})]})
    bill.action_post()

env.cr.commit()
print('Datos de demostración listos.')

# ========================================================================
print('=== 2. Validación de los 15 TXT del wizard ===')
CASES = [
    ('7.1', {'export_71': True}, '070100'),
    ('7.3', {'export_73': True}, '070300'),
    ('7.4', {'export_74': True}, '070400'),
    ('4.1', {'export_41': True}, '040100'),
    ('9.1', {'export_91': True}, '090100'),
    ('9.2', {'export_92': True}, '090200'),
    ('3.8', {'export_38': True}, '030800'),
    ('3.9', {'export_39': True}, '030900'),
    ('3.19', {'export_319': True}, '031900'),
    ('10.1', {'export_101': True}, '100100'),
    ('10.2', {'export_102': True}, '100200'),
    ('10.3', {'export_103': True}, '100300'),
    ('10.4', {'export_104': True}, '100400'),
    ('5.2', {'export_52': True}, '050200'),
    ('5.4', {'export_54': True}, '050400'),
    ('8.3', {'export_83': True}, '080300'),
    ('14.2', {'export_142': True}, '140200'),
]
for label, flags, code in CASES:
    vals = {'year': YEAR, 'month': MONTH, 'balance_date': BALANCE,
            'opportunity': '07', 'export_71': False,
            'generate_xlsx': False}
    vals.update(flags)
    wizard = env['l10n_pe.ple.export.wizard'].create(vals)
    try:
        wizard.action_export()
    except Exception as exc:
        log(label, False, 'excepción: %s' % exc)
        continue
    name = wizard.file_name
    content = base64.b64decode(wizard.file_data).decode()
    lines = [l for l in content.split('\r\n') if l]
    name_ok = name.startswith('LE%s' % company.vat) and len(name) == 37 \
        and code in name
    struct_ok = all(mixin._ple_check_structure(code, l) for l in lines)
    log(label, name_ok and struct_ok and lines,
        '%s líneas=%d nombre=%s estructura=%s' % (
            name, len(lines), 'ok' if name_ok else 'MAL',
            'ok' if struct_ok else 'MAL'))

print('=== 3. Reportes nativos EE (5.1/5.3/6.1, 1.1/1.2) ===')
try:
    report = env.ref('account_reports.general_ledger_report')
    options = report.with_company(company).get_options({})
    handler = env[report.custom_handler_model_name]
    for label, method in (('5.1', 'l10n_pe_export_ple_51_to_txt'),
                          ('5.3', 'l10n_pe_export_ple_53_to_txt'),
                          ('6.1', 'l10n_pe_export_ple_61_to_txt')):
        try:
            res = getattr(handler, method)(options)
            n_lines = len([l for l in res['file_content'].decode().splitlines() if l])
            log('EE %s' % label, bool(res['file_name']),
                '%s líneas=%d' % (res['file_name'], n_lines))
        except Exception as exc:
            log('EE %s' % label, False, str(exc)[:120])
except Exception as exc:
    log('EE GL', False, str(exc)[:120])
try:
    report = env.ref('account_reports.cash_flow_report')
    options = report.with_company(company).get_options({})
    handler = env[report.custom_handler_model_name]
    for label, method in (('1.1', 'l10n_pe_export_ple_11_to_txt'),
                          ('1.2', 'l10n_pe_export_ple_12_to_txt')):
        try:
            res = getattr(handler, method)(options)
            log('EE %s' % label, bool(res['file_name']), res['file_name'])
        except Exception as exc:
            log('EE %s' % label, False, str(exc)[:120])
except Exception as exc:
    log('EE cash', False, str(exc)[:120])

print('=== 4. Validación del Excel de revisión (formato v18) ===')
import io
import zipfile
from openpyxl import load_workbook
from odoo.addons.al_l10n_pe_ple.models.ple_xlsx import (
    PLE_XLSX_HEADERS, PLE_XLSX_TITLES)

for label, flags, code in CASES:
    vals = {'year': YEAR, 'month': MONTH, 'balance_date': BALANCE,
            'opportunity': '07', 'export_71': False, 'generate_xlsx': True}
    vals.update(flags)
    wizard = env['l10n_pe.ple.export.wizard'].create(vals)
    try:
        wizard.action_export()
        archive = zipfile.ZipFile(
            io.BytesIO(base64.b64decode(wizard.file_data)))
        names = archive.namelist()
        txt_name = next(n for n in names if n.endswith('.txt'))
        xlsx_name = next(n for n in names if n.endswith('.xlsx'))
        txt_lines = [l for l in
                     archive.read(txt_name).decode().split('\r\n') if l]
        book = load_workbook(io.BytesIO(archive.read(xlsx_name)),
                             read_only=False)
        sheet = book[PLE_XLSX_TITLES[code]]         # nombre de hoja exacto
        headers = PLE_XLSX_HEADERS[code]
        # título de compañía en A1
        title_ok = (sheet.cell(1, 1).value or '').startswith(company.name)
        # fila RUC
        ruc_ok = (sheet.cell(2, 1).value == 'RUC'
                  and sheet.cell(2, 2).value == company.partner_id.vat)
        # encabezados en la fila 4, columnas B..; numeración en fila 3
        head_ok = all(sheet.cell(4, i + 2).value == h
                      for i, h in enumerate(headers))
        num_ok = all(sheet.cell(3, i + 2).value == i + 1
                     for i in range(len(headers)))
        # datos: misma cantidad de filas que el TXT y primera fila igual
        data_ok = True
        for r, line in enumerate(txt_lines):
            fields_txt = line.split('|')
            for c, value in enumerate(fields_txt):
                cell = sheet.cell(6 + r, c + 2).value
                if str(cell if cell is not None else '') != value:
                    data_ok = False
                    break
            if not data_ok:
                break
        extra = sheet.cell(6 + len(txt_lines), 2).value
        ok = all([title_ok, ruc_ok, head_ok, num_ok, data_ok, extra is None])
        log('XLS %s' % label, ok,
            '%s filas=%d título=%s ruc=%s cab=%s num=%s datos=%s' % (
                xlsx_name, len(txt_lines),
                'ok' if title_ok else 'MAL', 'ok' if ruc_ok else 'MAL',
                'ok' if head_ok else 'MAL', 'ok' if num_ok else 'MAL',
                'ok' if data_ok and extra is None else 'MAL'))
    except Exception as exc:
        log('XLS %s' % label, False, 'excepción: %s' % str(exc)[:120])

env.cr.commit()
print('=== RESUMEN ===')
for fmt, status, detail in results:
    print('%-8s %-6s %s' % (fmt, status, detail))
fails = [r for r in results if r[1] != 'OK']
print('TOTAL: %d validaciones, %d fallas' % (len(results), len(fails)))
