"""Escenarios de anticipos y descuentos: genera el XML UBL de Perú y lo valida.

Se ejecuta con ``odoo-bin shell`` sobre una base con l10n_pe_edi y sale; todo
ocurre en una transacción que se deshace al final (no deja datos)::

    odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < docs/anticipos/escenarios_xml.py

Para cada escenario imprime los incumplimientos según ``tests/sunat_rules.py``
del módulo y
guarda el XML en ``docs/anticipos/xml/<escenario>.xml`` para revisarlo.
"""
import sys
from pathlib import Path

ROOT = Path('/home/och/odoo/ce19/myodoo/ol_new_apps/docs/anticipos')
# El validador vive en las pruebas del módulo: una sola fuente.
sys.path.insert(0, str(ROOT.parents[1] / 'OL-INVOICING' / 'al_l10n_pe_edi_downpayment_discount' / 'tests'))
from sunat_rules import validar  # noqa: E402

OUT = ROOT / 'xml'
OUT.mkdir(exist_ok=True)
env = env  # noqa: F821 (lo inyecta odoo-bin shell)
company = env.ref('base.main_company')
env = env(context=dict(env.context, allowed_company_ids=[company.id], tracking_disable=True))
ChartRef = env['account.chart.template'].with_company(company).ref
Edi = env['account.edi.xml.ubl_pe']
pen = env.ref('base.PEN')
usd = env.ref('base.USD')

igv = ChartRef('sale_tax_igv_18')
exo = ChartRef('sale_tax_exo')
ina = ChartRef('sale_tax_ina')
# Diario de facturas con serie F (el primero de venta puede tener otra secuencia).
JOURNAL = env['account.journal'].search([('company_id', '=', company.id), ('type', '=', 'sale'),
                                          ('code', '=', 'F001')], limit=1)
# IGV 18 % con precio incluido (la base no lo trae): copia del IGV estándar.
igv_incl = igv.copy({'name': 'IGV 18% incluido (prueba)', 'price_include_override': 'tax_included'})


def partner(ruc=True):
    vals = {'name': 'Cliente prueba anticipos', 'company_id': company.id,
            'country_id': env.ref('base.pe').id, 'street': 'Av. Prueba 123'}
    if ruc:
        vals.update(vat='20100070970', l10n_latam_identification_type_id=env.ref('l10n_pe.it_RUC').id)
    else:
        vals.update(vat='46027897', l10n_latam_identification_type_id=env.ref('l10n_pe.it_DNI').id)
    return env['res.partner'].create(vals)


def product(name, price, tax):
    return env['product.product'].create({
        'name': name, 'list_price': price, 'type': 'service', 'invoice_policy': 'order',
        'taxes_id': [(6, 0, tax.ids)], 'company_id': company.id})


def sale(cust, lines, currency=pen):
    pricelist = env['product.pricelist'].create({'name': f'PL {currency.name}', 'currency_id': currency.id})
    order = env['sale.order'].create({
        'partner_id': cust.id, 'company_id': company.id, 'pricelist_id': pricelist.id,
        'journal_id': JOURNAL.id,
        'order_line': [(0, 0, {'product_id': p.id, 'product_uom_qty': q, 'price_unit': pu,
                               'discount': d, 'tax_ids': [(6, 0, t.ids)]})
                       for p, q, pu, d, t in lines]})
    order.action_confirm()
    return order


def advance(order, method, amount):
    wiz = env['sale.advance.payment.inv'].with_context(
        active_model='sale.order', active_ids=order.ids, active_id=order.id).create({
            'advance_payment_method': method,
            'amount' if method == 'percentage' else 'fixed_amount': amount})
    wiz.create_invoices()
    return order.invoice_ids.sorted('id')[-1]


def final(order):
    wiz = env['sale.advance.payment.inv'].with_context(
        active_model='sale.order', active_ids=order.ids, active_id=order.id).create({
            'advance_payment_method': 'delivered'})
    wiz.create_invoices()
    return order.invoice_ids.sorted('id')[-1]


def post(move, boleta=False):
    if boleta:
        move.l10n_latam_document_type_id = env.ref('l10n_pe.document_type02')
    move.action_post()
    return move


def check(name, move):
    xml, errors = Edi._export_invoice(move)
    (OUT / f'{name}.xml').write_bytes(xml)
    issues = validar(xml)
    estado = 'OK' if not issues else f'{len(issues)} incumplimiento(s)'
    print(f'\n=== {name}: {move.name} total={move.amount_total} {move.currency_id.name} → {estado}')
    for code, msg in issues:
        print(f'   [{code}] {msg}')
    if errors:
        print('   exportador:', errors)
    return issues


resultados = {}
try:
    cli, cli_dni = partner(), partner(ruc=False)
    p_a = product('Servicio A', 1000.0, igv)
    p_b = product('Servicio B', 333.33, igv)
    p_x = product('Servicio exonerado', 500.0, exo)
    p_i = product('Servicio inafecto', 300.0, ina)

    # E1: un anticipo fijo (factura) y factura final que lo deduce
    o = sale(cli, [(p_a, 1, 1000.0, 0, igv)])
    post(advance(o, 'fixed', 118.0))
    resultados['E1_un_anticipo'] = check('E1_un_anticipo', post(final(o)))

    # E2: dos anticipos (porcentaje y fijo) + final
    o = sale(cli, [(p_a, 2, 1000.0, 0, igv)])
    a1 = post(advance(o, 'percentage', 10))
    a2 = post(advance(o, 'fixed', 236.0))
    resultados['E2_anticipo'] = check('E2_anticipo_documento', a1)
    resultados['E2_dos_anticipos'] = check('E2_dos_anticipos', post(final(o)))

    # E3: anticipo + descuento de línea + línea con céntimos
    o = sale(cli, [(p_a, 3, 1000.0, 10, igv), (p_b, 7, 333.33, 0, igv)])
    post(advance(o, 'percentage', 30))
    resultados['E3_anticipo_desc_linea'] = check('E3_anticipo_desc_linea', post(final(o)))

    # E4: descuento global (línea negativa) sin anticipo
    inv = env['account.move'].create({
        'move_type': 'out_invoice', 'partner_id': cli.id, 'company_id': company.id,
        'journal_id': JOURNAL.id,
        'invoice_line_ids': [
            (0, 0, {'product_id': p_a.id, 'quantity': 2, 'price_unit': 1000.0, 'tax_ids': [(6, 0, igv.ids)]}),
            (0, 0, {'name': 'Descuento global', 'quantity': 1, 'price_unit': -200.0, 'tax_ids': [(6, 0, igv.ids)]}),
        ]})
    resultados['E4_descuento_global'] = check('E4_descuento_global', post(inv))

    # E5: anticipo + descuento global en la factura final
    o = sale(cli, [(p_a, 1, 1000.0, 0, igv)])
    post(advance(o, 'fixed', 236.0))
    f = final(o)
    f.write({'invoice_line_ids': [(0, 0, {'name': 'Descuento global', 'quantity': 1,
                                          'price_unit': -100.0, 'tax_ids': [(6, 0, igv.ids)]})]})
    resultados['E5_anticipo_y_desc_global'] = check('E5_anticipo_y_desc_global', post(f))

    # E6: precios con IGV incluido y céntimos
    if igv_incl:
        o = sale(cli, [(p_b, 3, 99.99, 0, igv_incl), (p_a, 1, 1180.0, 0, igv_incl)])
        post(advance(o, 'percentage', 33))
        resultados['E6_igv_incluido'] = check('E6_igv_incluido', post(final(o)))

    # E7: en dólares
    o = sale(cli, [(p_a, 1, 1000.0, 0, igv)], currency=usd)
    post(advance(o, 'fixed', 118.0))
    resultados['E7_usd'] = check('E7_usd', post(final(o)))

    # E8: boletas (cliente con DNI)
    o = sale(cli_dni, [(p_a, 1, 500.0, 0, igv)])
    post(advance(o, 'fixed', 118.0), boleta=True)
    resultados['E8_boleta'] = check('E8_boleta', post(final(o), boleta=True))

    # E9: mixto gravado + exonerado con anticipo
    o = sale(cli, [(p_a, 1, 1000.0, 0, igv), (p_x, 1, 500.0, 0, exo)])
    post(advance(o, 'percentage', 20))
    resultados['E9_mixto_exonerado'] = check('E9_mixto_exonerado', post(final(o)))

    # E11: gravado + inafecto con anticipo
    o = sale(cli, [(p_a, 1, 1000.0, 0, igv), (p_i, 1, 300.0, 0, ina)])
    post(advance(o, 'percentage', 50))
    resultados['E11_mixto_inafecto'] = check('E11_mixto_inafecto', post(final(o)))

    # E10: nota de crédito de una factura final con anticipo
    o = sale(cli, [(p_a, 1, 1000.0, 0, igv)])
    post(advance(o, 'fixed', 118.0))
    f = post(final(o))
    rev = env['account.move.reversal'].with_context(active_model='account.move', active_ids=f.ids).create({
        'reason': 'Anulación', 'journal_id': f.journal_id.id, 'l10n_pe_edi_refund_reason': '01'})
    nc = env['account.move'].browse(rev.refund_moves()['res_id'])
    try:
        with env.cr.savepoint():
            resultados['E10_nota_credito'] = check('E10_nota_credito', post(nc))
    except Exception as e:  # noqa: BLE001 - se informa como hallazgo
        print(f'\n=== E10_nota_credito: no se puede publicar → {str(e).splitlines()[-1]}')
        resultados['E10_nota_credito'] = [('PUBLICAR', str(e).splitlines()[-1])]

    def factura(lines, name):
        inv = env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': cli.id, 'company_id': company.id,
            'journal_id': JOURNAL.id,
            'invoice_line_ids': [(0, 0, {'name': n, 'product_id': prod.id if prod else False, 'quantity': q,
                                         'price_unit': pu, 'tax_ids': [(6, 0, tx.ids)]})
                                 for n, prod, q, pu, tx in lines]})
        return post(inv)

    def nota_credito(name, inv):
        rev = env['account.move.reversal'].with_context(active_model='account.move', active_ids=inv.ids).create({
            'reason': 'Anulación', 'journal_id': inv.journal_id.id, 'l10n_pe_edi_refund_reason': '01'})
        nc = env['account.move'].browse(rev.refund_moves()['res_id'])
        try:
            with env.cr.savepoint():
                resultados[name] = check(name, post(nc))
        except Exception as e:  # noqa: BLE001
            print(f'\n=== {name}: no se puede publicar → {str(e).splitlines()[-1]}')
            resultados[name] = [('PUBLICAR', str(e).splitlines()[-1])]

    # E12: nota de crédito de una factura con descuento global
    inv = factura([('Servicio A', p_a, 2, 1000.0, igv), ('Descuento global', False, 1, -200.0, igv)], 'E12')
    nota_credito('E12_nc_descuento_global', inv)

    # E13: descuento global sobre una venta exonerada
    resultados['E13_desc_exonerado'] = check('E13_desc_exonerado', factura(
        [('Servicio exonerado', p_x, 2, 500.0, exo), ('Descuento global', False, 1, -100.0, exo)], 'E13'))

    # E14: descuento global en una venta mixta (un descuento por tipo de afectación)
    resultados['E14_desc_mixto'] = check('E14_desc_mixto', factura(
        [('Servicio A', p_a, 1, 1000.0, igv), ('Servicio exonerado', p_x, 1, 500.0, exo),
         ('Descuento gravado', False, 1, -100.0, igv), ('Descuento exonerado', False, 1, -50.0, exo)], 'E14'))

    # E15: descuento global con IGV incluido y céntimos
    resultados['E15_desc_incluido'] = check('E15_desc_incluido', factura(
        [('Servicio B', p_b, 3, 33.33, igv_incl), ('Servicio B', p_b, 7, 19.99, igv_incl),
         ('Descuento global', False, 1, -10.01, igv_incl)], 'E15'))
    # E16: nota de crédito de una factura con descuento de línea (%)
    inv = env['account.move'].create({
        'move_type': 'out_invoice', 'partner_id': cli.id, 'company_id': company.id, 'journal_id': JOURNAL.id,
        'invoice_line_ids': [(0, 0, {'product_id': p_a.id, 'quantity': 3, 'price_unit': 1000.0,
                                     'discount': 10, 'tax_ids': [(6, 0, igv.ids)]})]})
    nota_credito('E16_nc_desc_linea', post(inv))
finally:
    env.cr.rollback()
    print('\nResumen:')
    for k, v in resultados.items():
        print(f'  {k:32} {"OK" if not v else ", ".join(sorted({c for c, _ in v}))}')
