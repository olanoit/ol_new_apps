# -*- coding: utf-8 -*-
"""Datos demo + validación integral de letras de cambio y canje (prefijo DEMO LETRA).

Ejecutar con:  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < account_letter_demo_data.py
"""
from datetime import date

YEAR, MONTH = 2026, 7
company = env.company
results = []


def log(name, ok, detail=''):
    results.append((name, 'OK' if ok else 'FALLA', detail))
    print('  [%s] %-42s %s' % ('OK' if ok else 'XX', name, detail))


def get_or_create(model, domain, vals):
    rec = env[model].search(domain, limit=1)
    return rec or env[model].create(vals)


print('=== 1. Configuración: cuentas, diarios, socios ===')
Account = env['account.account'].with_company(company)
pen = env.ref('base.PEN')
acc_receivable = Account.search([('account_type', '=', 'asset_receivable')], limit=1)
acc_payable = Account.search([('account_type', '=', 'liability_payable')], limit=1)
doc_type_01 = env.ref('l10n_pe.document_type01')

Config = env['l10n_pe.letter.account.config']
for letter_type in ('portfolio', 'billing', 'discount'):
    get_or_create(
        'l10n_pe.letter.account.config',
        [('account_type', '=', 'asset_receivable'), ('letter_type', '=', letter_type),
         ('currency_id', '=', pen.id), ('company_id', '=', company.id)],
        {'account_type': 'asset_receivable', 'letter_type': letter_type,
         'currency_id': pen.id, 'account_id': acc_receivable.id, 'company_id': company.id})
    get_or_create(
        'l10n_pe.letter.account.config',
        [('account_type', '=', 'liability_payable'), ('letter_type', '=', letter_type),
         ('currency_id', '=', pen.id), ('company_id', '=', company.id)],
        {'account_type': 'liability_payable', 'letter_type': letter_type,
         'currency_id': pen.id, 'account_id': acc_payable.id, 'company_id': company.id})
log('cuentas de letras configuradas (6 combinaciones)',
    Config.search_count([]) >= 6, 'total=%d' % Config.search_count([]))

# create_residual() busca por nombre exacto una cuenta "Redondeo" de gasto
# (débito) o de otro ingreso (crédito) para el ajuste de redondeo del canje.
acc_redondeo_gasto = get_or_create('account.account', [('name', '=', 'Redondeo'), ('account_type', '=', 'expense')], {
    'name': 'Redondeo', 'account_type': 'expense', 'code': '659901'})
acc_redondeo_ingreso = get_or_create(
    'account.account', [('name', '=', 'Redondeo'), ('account_type', '=', 'income_other')], {
        'name': 'Redondeo', 'account_type': 'income_other', 'code': '759901'})

j_cobrar = get_or_create('account.journal', [('name', '=', 'Letras por Cobrar')], {
    'name': 'Letras por Cobrar', 'code': 'LETC', 'type': 'general',
    'company_id': company.id, 'currency_id': pen.id})
j_pagar = get_or_create('account.journal', [('name', '=', 'Letras por Pagar')], {
    'name': 'Letras por Pagar', 'code': 'LETP', 'type': 'general',
    'company_id': company.id, 'currency_id': pen.id})
log('diarios de letras (Cobrar/Pagar)', bool(j_cobrar) and bool(j_pagar),
    '%s / %s' % (j_cobrar.code, j_pagar.code))

partner = get_or_create('res.partner', [('name', '=', 'DEMO LETRA Cliente SAC')], {
    'name': 'DEMO LETRA Cliente SAC', 'vat': '20100070970'})
provider = get_or_create('res.partner', [('name', '=', 'DEMO LETRA Proveedor SAC')], {
    'name': 'DEMO LETRA Proveedor SAC', 'vat': '20131312955'})
bank = env['res.bank'].search([], limit=1) or env['res.bank'].create({'name': 'Banco DEMO'})

# Diarios propios sin numeración SUNAT (l10n_latam_use_documents=False) para
# no depender del correlativo real de comprobantes electrónicos del entorno.
sale_journal = get_or_create('account.journal', [('code', '=', 'DLTV')], {
    'name': 'DEMO LETRA Ventas', 'code': 'DLTV', 'type': 'sale',
    'company_id': company.id, 'l10n_latam_use_documents': False})
purchase_journal = get_or_create('account.journal', [('code', '=', 'DLTC')], {
    'name': 'DEMO LETRA Compras', 'code': 'DLTC', 'type': 'purchase',
    'company_id': company.id, 'l10n_latam_use_documents': False})
acc_inc = Account.search([('account_type', '=', 'income')], limit=1)
acc_exp = Account.search([('account_type', '=', 'expense')], limit=1)
tax_sale = env['account.tax'].search(
    [('company_id', '=', company.id), ('type_tax_use', '=', 'sale'), ('amount', '=', 18.0)], limit=1)
tax_purchase = env['account.tax'].search(
    [('company_id', '=', company.id), ('type_tax_use', '=', 'purchase'), ('amount', '=', 18.0)], limit=1)

print('=== 2. Comprobantes originales (factura cliente / proveedor) ===')


def make_invoice(origin, move_type, partner_id, journal_id, account_id, amount, tax, ref=None):
    move = env['account.move'].search(
        [('invoice_origin', '=', origin), ('state', '=', 'posted')], limit=1)
    if move:
        return move
    vals = {
        'move_type': move_type, 'partner_id': partner_id, 'journal_id': journal_id,
        'invoice_origin': origin,
        'invoice_date': date(YEAR, MONTH, 5), 'date': date(YEAR, MONTH, 5),
        'invoice_line_ids': [(0, 0, {
            'name': origin, 'quantity': 1, 'price_unit': amount, 'account_id': account_id,
            'tax_ids': [(6, 0, tax.ids)]})],
    }
    if ref:
        vals['ref'] = ref
    move = env['account.move'].create(vals)
    move.action_post()
    return move


# invoice_2 (1000 + 18% IGV = 1180.00) se reparte entre 3 letras (393.33 c/u)
# para forzar un residual/redondeo natural de 0.01.
invoice_1 = make_invoice('DEMO LETRA venta 1', 'out_invoice', partner.id, sale_journal.id,
                          acc_inc.id, 3000.0, tax_sale)
invoice_2 = make_invoice('DEMO LETRA venta 2', 'out_invoice', partner.id, sale_journal.id,
                          acc_inc.id, 1000.0, tax_sale)
bill_1 = make_invoice('DEMO LETRA compra 1', 'in_invoice', provider.id, purchase_journal.id,
                       acc_exp.id, 2000.0, tax_purchase, ref='F001-DEMOLETRA1')
log('factura cliente 1 publicada (3000)',
    invoice_1.state == 'posted' and invoice_1.amount_residual == invoice_1.amount_total,
    'total=%.2f residual=%.2f' % (invoice_1.amount_total, invoice_1.amount_residual))
log('factura cliente 2 publicada (1000)',
    invoice_2.state == 'posted' and invoice_2.amount_residual == invoice_2.amount_total,
    'total=%.2f' % invoice_2.amount_total)
log('factura proveedor 1 publicada (2000)',
    bill_1.state == 'posted' and bill_1.amount_residual == bill_1.amount_total,
    'total=%.2f' % bill_1.amount_total)


def payment_term_line(move):
    return move.line_ids.filtered(lambda l: l.display_type == 'payment_term')


def add_invoice_line(letter, move, document_type=doc_type_01):
    # account_id normalmente lo llena el onchange de la vista al elegir
    # move_line_id; al crear la línea directo por ORM hay que fijarlo a mano.
    line = payment_term_line(move)
    if move.id not in letter.invoice_line_ids.move_line_id.move_id.ids:
        letter.write({'invoice_line_ids': [(0, 0, {
            'document_type_id': document_type.id,
            'move_line_id': line.id,
            'account_id': line.account_id.id,
            'imp_div': abs(line.amount_residual_currency),
        })]})
    return line


print('=== 3. Canje de letras — cliente (residual por redondeo) ===')
letter_cli = get_or_create(
    'l10n_pe.letter', [('payment_reference', '=', 'DEMO-LETRA-CLI-01')],
    {'partner_id': partner.id, 'type': 'out_invoice', 'journal_id': j_cobrar.id,
     'payment_reference': 'DEMO-LETRA-CLI-01'})
log('canje cliente creado en borrador',
    letter_cli.state == 'draft' and letter_cli.name.startswith('CLC'), letter_cli.name)

add_invoice_line(letter_cli, invoice_2)
letter_cli.invoice_date = date(YEAR, MONTH, 10)
log('línea de factura agregada al canje', len(letter_cli.invoice_line_ids) == 1,
    'imp_div=%.2f' % letter_cli.invoice_line_ids.imp_div)

if letter_cli.state == 'draft':
    letter_cli.action_checked()
log('canje confirmado (checked)', letter_cli.state == 'checked', letter_cli.name)

if not letter_cli.letter_line_ids:
    # 1180.00 (1000 + 18% IGV) / 3 letras = 393.33 c/u -> deja un residual de
    # redondeo natural (393.33*3 = 1179.99, diferencia 0.01).
    letter_cli.write({'number_letter': 3, 'letter_end_date': date(YEAR, MONTH + 1, 10), 'range_date': 30})
    letter_cli.create_letters()
    for i, line in enumerate(letter_cli.letter_line_ids, start=1):
        line.nro_letter = 'LET-CLI-%03d' % i
log('3 letras generadas (393.33 c/u)', len(letter_cli.letter_line_ids) == 3,
    'importes=%s' % letter_cli.letter_line_ids.mapped('imp_div'))

if letter_cli.state == 'checked':
    letter_cli.action_redeemed()
log('canje canjeado (redeemed) + asiento posteado',
    letter_cli.state == 'redeemed' and letter_cli.account_id.state == 'posted',
    letter_cli.account_id.name if letter_cli.account_id else '-')
residual_amount = letter_cli.letter_residual_ids.amount if letter_cli.letter_residual_ids else 0.0
log('residual/redondeo registrado (~0.01)',
    len(letter_cli.letter_residual_ids) == 1 and 0 < abs(residual_amount) < 1,
    'monto=%.2f' % residual_amount)
log('factura original conciliada', invoice_2.payment_state in ('paid', 'in_payment', 'reversed'),
    'payment_state=%s' % invoice_2.payment_state)

print('=== 4. Canje individual (cobranza libre) de una letra ===')
if not letter_cli.canje_move_ids:
    pending_line = letter_cli.letter_line_ids.filtered(lambda l: l.payment_state == 'pending')[:1]
    letter_cli.action_canje_create('billing', date(YEAR, MONTH, 15), pending_line)
    pending_line.write({'bank_id': bank.id, 'code': 'CANJE-CLI-001', 'letter_type': 'billing'})
log('letra en cobranza libre generó asiento y quedó conciliada',
    bool(letter_cli.canje_move_ids) and letter_cli.canje_move_ids.state == 'posted',
    'asientos=%d' % len(letter_cli.canje_move_ids))

print('=== 5. Refinanciación individual ===')
if not letter_cli.refinance_id:
    refinance_letter = env['l10n_pe.letter'].create_refinance(letter_cli, date(YEAR, MONTH, 20))
else:
    refinance_letter = letter_cli.refinance_id
log('refinanciamiento individual creado (hijo en borrador)',
    refinance_letter.is_refinance_children and refinance_letter.state == 'draft'
    and letter_cli.is_refinance_parent,
    refinance_letter.name)
log('refinanciamiento trae el saldo adeudado como línea "99"',
    any(line.document_type_id.code == '99' for line in refinance_letter.invoice_line_ids),
    'líneas=%d' % len(refinance_letter.invoice_line_ids))

print('=== 6. Refinanciación masiva (2 canjes del mismo cliente) ===')
letter_cli_2 = get_or_create(
    'l10n_pe.letter', [('payment_reference', '=', 'DEMO-LETRA-CLI-02')],
    {'partner_id': partner.id, 'type': 'out_invoice', 'journal_id': j_cobrar.id,
     'payment_reference': 'DEMO-LETRA-CLI-02'})
add_invoice_line(letter_cli_2, invoice_1)
letter_cli_2.invoice_date = date(YEAR, MONTH, 10)
if letter_cli_2.state == 'draft':
    letter_cli_2.action_checked()
if not letter_cli_2.letter_line_ids:
    letter_cli_2.write({'number_letter': 1, 'letter_end_date': date(YEAR, MONTH + 1, 10), 'range_date': 30})
    letter_cli_2.create_letters()
    letter_cli_2.letter_line_ids.nro_letter = 'LET-CLI-004'
if letter_cli_2.state == 'checked':
    letter_cli_2.action_redeemed()
log('segundo canje cliente canjeado', letter_cli_2.state == 'redeemed', letter_cli_2.name)

massive_candidates = (letter_cli | letter_cli_2).filtered(
    lambda l: l.state in ('redeemed', 'banked') and not l.is_refinance_parent and not l.is_refinance_children)
if len(massive_candidates) >= 1 and not any(massive_candidates.mapped('is_refinance_parent')):
    massive_refinance = env['l10n_pe.letter'].create_massive_refinance(
        massive_candidates, date(YEAR, MONTH, 25))
    log('refinanciamiento masivo creado', massive_refinance.is_refinance_children,
        'origen=%s' % massive_candidates.mapped('name'))
else:
    log('refinanciamiento masivo creado', False, 'sin candidatos disponibles (ya refinanciados)')

print('=== 7. Canje masivo (2 canjes -> l10n_pe.letter.massive) ===')
letter_cli_3 = get_or_create(
    'l10n_pe.letter', [('payment_reference', '=', 'DEMO-LETRA-CLI-03')],
    {'partner_id': partner.id, 'type': 'out_invoice', 'journal_id': j_cobrar.id,
     'payment_reference': 'DEMO-LETRA-CLI-03'})
invoice_3 = make_invoice('DEMO LETRA venta 3', 'out_invoice', partner.id, sale_journal.id,
                          acc_inc.id, 500.0, tax_sale)
add_invoice_line(letter_cli_3, invoice_3)
letter_cli_3.invoice_date = date(YEAR, MONTH, 10)
if letter_cli_3.state == 'draft':
    letter_cli_3.action_checked()
if not letter_cli_3.letter_line_ids:
    letter_cli_3.write({'number_letter': 1, 'letter_end_date': date(YEAR, MONTH + 1, 10), 'range_date': 30})
    letter_cli_3.create_letters()
    letter_cli_3.letter_line_ids.nro_letter = 'LET-CLI-005'
if letter_cli_3.state == 'checked':
    letter_cli_3.action_redeemed()

multi_candidates = massive_candidates | letter_cli_3
multi_candidates = multi_candidates.filtered(lambda l: l.state in ('redeemed', 'banked'))
if len(multi_candidates) >= 2 and not env['l10n_pe.letter.massive'].search(
        [('letter_invoices_ids', 'in', multi_candidates.mapped('invoice_line_ids').ids)], limit=1):
    # action_multi_redeemed lee los ids desde el contexto ("active_ids"),
    # como lo hace el botón del listado multi-selección.
    massive_letter = env['l10n_pe.letter'].with_context(
        active_ids=multi_candidates.ids).action_multi_redeemed('portfolio')
    log('canje masivo creado (l10n_pe.letter.massive)',
        bool(massive_letter) and massive_letter.is_massive_letter,
        massive_letter.name if massive_letter else '-')
else:
    log('canje masivo creado (l10n_pe.letter.massive)', False, 'sin candidatos nuevos disponibles')

print('=== 8. Flujo proveedor (in_invoice) ===')
letter_prov = get_or_create(
    'l10n_pe.letter', [('payment_reference', '=', 'DEMO-LETRA-PROV-01')],
    {'partner_id': provider.id, 'type': 'in_invoice', 'journal_id': j_pagar.id,
     'payment_reference': 'DEMO-LETRA-PROV-01'})
add_invoice_line(letter_prov, bill_1)
letter_prov.invoice_date = date(YEAR, MONTH, 10)
log('canje proveedor creado y con línea de factura',
    letter_prov.name.startswith('CLP') and len(letter_prov.invoice_line_ids) == 1, letter_prov.name)

if letter_prov.state == 'draft':
    letter_prov.action_checked()
if not letter_prov.letter_line_ids:
    letter_prov.write({'number_letter': 2, 'letter_end_date': date(YEAR, MONTH + 1, 10), 'range_date': 30})
    letter_prov.create_letters()
    for i, line in enumerate(letter_prov.letter_line_ids, start=1):
        line.nro_letter = 'LET-PROV-%03d' % i
if letter_prov.state == 'checked':
    letter_prov.action_redeemed()
log('canje proveedor canjeado + asiento posteado',
    letter_prov.state == 'redeemed' and letter_prov.account_id.state == 'posted',
    letter_prov.account_id.name if letter_prov.account_id else '-')
log('factura de proveedor conciliada', bill_1.payment_state in ('paid', 'in_payment', 'reversed'),
    'payment_state=%s' % bill_1.payment_state)

print('=== 9. Vinculación de asientos por referencia ===')
unlinked = env['l10n_pe.letter'].create({
    'partner_id': partner.id, 'type': 'out_invoice', 'journal_id': j_cobrar.id,
    'payment_reference': 'DEMO-LETRA-CLI-04',
})
manual_move = env['account.move'].create({
    'journal_id': j_cobrar.id, 'ref': unlinked.name, 'date': date(YEAR, MONTH, 28),
    'line_ids': [
        (0, 0, {'account_id': acc_receivable.id, 'debit': 100.0, 'credit': 0.0, 'partner_id': partner.id}),
        (0, 0, {'account_id': acc_receivable.id, 'debit': 0.0, 'credit': 100.0, 'partner_id': partner.id}),
    ],
})
manual_move.action_post()
unlinked.invoice_date = date(YEAR, MONTH, 28)
unlinked.state = 'redeemed'  # simula un canje ya canjeado sin asiento vinculado (p.ej. importado)
unlinked.action_link_account_move_by_ref()
log('asiento vinculado por referencia', unlinked.account_id == manual_move, unlinked.account_id.name)

env.cr.commit()
print('=== RESUMEN ===')
for name, status, detail in results:
    print('%-52s %-6s %s' % (name, status, detail))
fails = [r for r in results if r[1] != 'OK']
print('TOTAL: %d validaciones, %d fallas' % (len(results), len(fails)))
