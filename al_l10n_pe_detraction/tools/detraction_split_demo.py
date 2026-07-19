# -*- coding: utf-8 -*-
"""Prueba del reparto de la detracción en el asiento (ciclo de vida).

Ejecutar con:  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < detraction_split_demo.py

Activa la opción «Separar detracción en el asiento», crea facturas «DEMO
SPLIT» de cliente y proveedor y las somete al ciclo publicar → borrador →
cambiar monto → republicar, verificando en cada publicación que el asiento
quede balanceado y el reparto recalculado (sin líneas duplicadas ni
obsoletas)."""
from datetime import date

YEAR, MONTH_DAY = 2026, (7, 15)
company = env.company
results = []


def log(name, ok, detail=''):
    results.append((name, 'OK' if ok else 'FALLA', detail))
    print('  [%s] %-38s %s' % ('OK' if ok else 'XX', name, detail))


def get_or_create(model, domain, vals):
    rec = env[model].search(domain, limit=1)
    return rec or env[model].create(vals)


# --- Configuración: opción + cuentas ------------------------------------
Account = env['account.account'].with_company(company)
acc_det_ar = get_or_create('account.account', [('code', '=', '121901')], {
    'code': '121901', 'name': 'Detracciones por cobrar (DEMO)',
    'account_type': 'asset_receivable', 'reconcile': True})
acc_det_ap = get_or_create('account.account', [('code', '=', '424901')], {
    'code': '424901', 'name': 'Detracciones por pagar (DEMO)',
    'account_type': 'liability_payable', 'reconcile': True})
company.write({
    'l10n_pe_detraction_split': True,
    'l10n_pe_detraction_receivable_account_id': acc_det_ar.id,
    'l10n_pe_detraction_payable_account_id': acc_det_ap.id,
})
log('configuración split', company.l10n_pe_detraction_split,
    'cuentas %s / %s' % (acc_det_ar.code, acc_det_ap.code))

acc_inc = Account.search([('account_type', '=', 'income')], limit=1)
acc_exp = Account.search([('account_type', '=', 'expense')], limit=1)
tax_s = env['account.tax'].search([('company_id', '=', company.id),
                                   ('type_tax_use', '=', 'sale'),
                                   ('amount', '=', 18.0)], limit=1)
tax_p = env['account.tax'].search([('company_id', '=', company.id),
                                   ('type_tax_use', '=', 'purchase'),
                                   ('amount', '=', 18.0)], limit=1)
j_sale = env['account.journal'].search([('code', '=', 'DPSV')], limit=1)
j_purchase = env['account.journal'].search([('code', '=', 'DPSC')], limit=1)
partner = get_or_create('res.partner', [('name', '=', 'DEMO SPLIT SAC')], {
    'name': 'DEMO SPLIT SAC', 'vat': '20131312955'})
service = env['product.product'].search(
    [('default_code', '=', 'DEMO-SPOT2-SERV')], limit=1)


def make_invoice(tag, move_type, price):
    origin = 'DEMO SPLIT %s' % tag
    old = env['account.move'].search([('invoice_origin', '=', origin)])
    if old:
        old.filtered(lambda m: m.state == 'posted').button_draft()
        old.button_cancel()
    journal = j_sale if move_type == 'out_invoice' else j_purchase
    tax = tax_s if move_type == 'out_invoice' else tax_p
    account = acc_inc if move_type == 'out_invoice' else acc_exp
    return env['account.move'].create({
        'move_type': move_type, 'partner_id': partner.id,
        'journal_id': journal.id, 'invoice_origin': origin,
        'invoice_date': date(YEAR, *MONTH_DAY),
        'date': date(YEAR, *MONTH_DAY),
        'ref': 'F00S-00000%s1' % tag[:2] if move_type == 'in_invoice' else False,
        'invoice_line_ids': [(0, 0, {
            'name': service.name, 'product_id': service.id,
            'quantity': 1.0, 'price_unit': price,
            'account_id': account.id,
            'tax_ids': [(6, 0, tax.ids)]})]})


def check_entry(label, move, det_account, expect_det):
    """Balance del asiento + reparto correcto tras cada publicación."""
    balanced = abs(sum(move.line_ids.mapped('balance'))) < 0.005
    term_lines = move.line_ids.filtered(
        lambda l: l.display_type == 'payment_term')
    det_lines = term_lines.filtered(lambda l: l.account_id == det_account)
    total = abs(move.amount_total_signed)
    if expect_det:
        det = move.l10n_pe_detraction_amount
        ok = (balanced and len(term_lines) == 2 and len(det_lines) == 1
              and abs(abs(det_lines.balance) - det) < 0.005
              and abs(abs((term_lines - det_lines).balance)
                      - (total - det)) < 0.005
              and abs(move.amount_residual - total) < 0.005)
        detail = 'total=%.2f det=%.2f neto=%.2f balance=%s' % (
            total, abs(det_lines.balance) if det_lines else 0,
            abs((term_lines - det_lines).balance) if det_lines else 0,
            'ok' if balanced else 'MAL')
    else:
        ok = (balanced and len(term_lines) == 1 and not det_lines
              and abs(move.amount_residual - total) < 0.005)
        detail = 'total=%.2f sin reparto balance=%s' % (
            total, 'ok' if balanced else 'MAL')
    log(label, ok, detail)


print('=== Cliente: publicar → borrador → cambiar monto → republicar ===')
inv = make_invoice('cli', 'out_invoice', 1000.0)     # 1180, det 142
inv.action_post()
check_entry('venta 1180 publicada', inv, acc_det_ar, True)

inv.button_draft()
inv.invoice_line_ids.write({'price_unit': 2000.0})   # 2360, det 283
inv.action_post()
check_entry('venta editada a 2360 republicada', inv, acc_det_ar, True)

inv.button_draft()
inv.invoice_line_ids.write({'price_unit': 500.0})    # 590 <= 700: no aplica
inv.action_post()
check_entry('venta reducida a 590 (sin detracción)', inv, acc_det_ar, False)

inv.button_draft()
inv.invoice_line_ids.write({'price_unit': 3000.0})   # 3540, det 425
inv.action_post()
check_entry('venta ampliada a 3540 republicada', inv, acc_det_ar, True)

inv.button_draft()
inv.action_post()                                    # re-post sin editar
check_entry('re-publicación sin cambios', inv, acc_det_ar, True)

print('=== Proveedor: mismo ciclo ===')
bill = make_invoice('pro', 'in_invoice', 3000.0)     # 3540, det 425
bill.action_post()
check_entry('compra 3540 publicada', bill, acc_det_ap, True)

bill.button_draft()
bill.invoice_line_ids.write({'price_unit': 1500.0})  # 1770, det 212
bill.action_post()
check_entry('compra editada a 1770 republicada', bill, acc_det_ap, True)

bill.button_draft()
bill.action_post()
check_entry('compra re-publicada sin cambios', bill, acc_det_ap, True)

env.cr.commit()
print('=== RESUMEN ===')
for name, status, detail in results:
    print('%-40s %-6s %s' % (name, status, detail))
fails = [r for r in results if r[1] != 'OK']
print('TOTAL: %d validaciones, %d fallas' % (len(results), len(fails)))
