"""Batería de comprobantes electrónicos de una botica contra SUNAT beta.

Requiere la base configurada con ``configurar_cpe_beta.py`` (compañía de
prueba, certificado de prueba, series F001/B001 y la caja «Botica
Principal»). Cada caso se emite como lo haría un usuario (asistentes de nota
de crédito, nota de débito y anulación; ventas de caja) y se envía a SUNAT
beta; al final imprime una tabla con el código y la descripción del CDR.

Uso (dentro del contenedor): odoo shell ... -d <base> < pruebas_cpe_beta.py

Un comprobante rechazado se corrige y se reenvía con el mismo número:
``button_draft()``, corregir, ``action_post()`` y enviar (Odoo no reintenta
un rechazo sin regenerar el XML).

Nada de esto tiene valor tributario: SUNAT beta valida el XML con las
mismas reglas que producción, pero no registra los comprobantes. Las pruebas
de producción (certificado, usuario SOL u OSE reales) las hace el usuario.
"""
import base64
import io
import re
import time
import traceback
import zipfile

from odoo import Command, fields

env = env(user=env.ref('base.user_admin').id)
company = env.company
assert company.l10n_pe_edi_test_env, 'Solo para el entorno de prueba de SUNAT'

Move = env['account.move']
Journal = env['account.journal']
Product = env['product.template']
Tax = env['account.tax']
factura_journal = Journal.search([('company_id', '=', company.id), ('code', '=', 'FAC')], limit=1)
boleta_journal = Journal.search([('company_id', '=', company.id), ('code', '=', 'BOL')], limit=1)
doc_factura = env.ref('l10n_pe.document_type01')
doc_boleta = env.ref('l10n_pe.document_type02')


def tax(code, amount_type='percent'):
    return Tax.search([('company_id', '=', company.id), ('type_tax_use', '=', 'sale'),
                       ('l10n_pe_edi_tax_code', '=', code), ('amount_type', '=', amount_type)], limit=1)


igv, exo, ina = tax('1000'), tax('9997'), tax('9998')
free_group = tax('9996', 'group')
icbper = Tax.search([('company_id', '=', company.id), ('l10n_pe_edi_tax_code', '=', '7152')], limit=1)
if not icbper:
    # Impuesto al consumo de bolsas de plástico: S/ 0,50 por bolsa desde 2023.
    icbper = Tax.create({
        'name': 'ICBPER', 'amount_type': 'fixed', 'amount': 0.5, 'type_tax_use': 'sale',
        'l10n_pe_edi_tax_code': '7152', 'l10n_pe_edi_unece_category': 'S',
        'tax_group_id': env['account.chart.template'].ref('tax_group_icbper').id,
        'company_id': company.id,
    })
bag = Product.search([('name', '=', 'Bolsa plástica mediana')], limit=1)
if not bag:
    bag = Product.create({'name': 'Bolsa plástica mediana', 'type': 'consu', 'list_price': 0.10,
                          'available_in_pos': True, 'taxes_id': [Command.set((igv | icbper).ids)]})
bag = bag.product_variant_id


def product(name):
    return Product.search([('name', '=', name)], limit=1).product_variant_id


para = product('Paracetamol 500 mg tableta')
amox = product('Amoxicilina 500 mg cápsula')
metf = product('Metformina 850 mg tableta')
lora = product('Loratadina 10 mg tableta')
insulin = product('Insulina humana NPH 100 UI/mL frasco 10 mL')
syrup = product('Jarabe para la tos 120 mL')
partner = env['res.partner']
lucia = partner.search([('vat', '=', '44556677')], limit=1)
dist = partner.search([('vat', '=', '20512528458')], limit=1)
final = partner.search([('vat', '=', '00000000')], limit=1)


def presentation(variant, factor):
    return variant.product_tmpl_id.pharmacy_presentation_ids.filtered(lambda p: p.factor == factor)


def line(variant, quantity, price=None, taxes=None, **extra):
    values = {'product_id': variant.id, 'quantity': quantity,
              'price_unit': variant.lst_price if price is None else price}
    if taxes is not None:
        values['tax_ids'] = [Command.set(taxes.ids)]
    values.update(extra)
    return Command.create(values)


def invoice(journal, document, customer, lines, **values):
    move = Move.create({'move_type': 'out_invoice', 'journal_id': journal.id, 'partner_id': customer.id,
                        'l10n_latam_document_type_id': document.id, 'invoice_line_ids': lines, **values})
    move.action_post()
    return move


def send(move, rounds=1):
    env.cr.commit()
    for _round in range(rounds):
        move.action_process_edi_web_services()
        env.cr.commit()
        if move.edi_state in ('sent', 'cancelled') and not move.edi_document_ids.filtered('error'):
            break
        time.sleep(5)
    return move


def cdr(move):
    """Código, descripción y observaciones del último CDR del comprobante."""
    attachments = env['ir.attachment'].search(
        [('res_model', '=', 'account.move'), ('res_id', '=', move.id), ('name', 'ilike', 'CDR')],
        order='id desc', limit=1)
    if not attachments:
        return '', ''
    raw = base64.b64decode(attachments.datas)
    if raw[:2] == b'PK':
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            raw = b''.join(archive.read(name) for name in archive.namelist() if name.lower().endswith('.xml'))
    text = raw.decode('utf-8', 'ignore')
    code = re.search(r'<cbc:ResponseCode[^>]*>([^<]*)<', text)
    description = re.search(r'<cbc:Description[^>]*>([^<]*)<', text)
    notes = re.findall(r'<cbc:Note[^>]*>([^<]*)<', text)
    return (code.group(1) if code else ''), ' '.join(
        filter(None, [description.group(1) if description else ''] + notes))


results = []


def record(case, move, expected='sent'):
    errors = ' | '.join((d.error or '') for d in move.edi_document_ids if d.error)
    errors = re.sub(r'<[^>]+>', ' ', errors)
    code, description = cdr(move)
    ok = move.edi_state == expected and not errors
    results.append((case, move.name, move.l10n_latam_document_type_id.code, move.currency_id.name,
                    round(move.amount_total, 2), move.edi_state, code, (description or errors)[:220], ok))


def run(case, function):
    try:
        function()
    except Exception as error:
        env.cr.rollback()
        results.append((case, '', '', '', 0, 'excepción', '', ('%s' % error)[:220], False))
        traceback.print_exc()


# ----------------------------------------------------------------------
# Facturas (F001)
# ----------------------------------------------------------------------
def factura_credito():
    # Las cuotas deben vencer después de la emisión (regla 3267): un plazo
    # con una parte «ahora» (30 % ahora, el resto a 60 días) es rechazado.
    term = env['account.payment.term'].search([('name', '=', 'Crédito 30 y 60 días')], limit=1)
    if not term:
        term = env['account.payment.term'].create({'name': 'Crédito 30 y 60 días', 'line_ids': [
            Command.create({'value': 'percent', 'value_amount': 50, 'nb_days': 30}),
            Command.create({'value': 'percent', 'value_amount': 50, 'nb_days': 60})]})
    move = invoice(factura_journal, doc_factura, dist, [line(syrup, 10), line(amox, 100)],
                   invoice_payment_term_id=term.id)
    record('F1 Factura al crédito en 2 cuotas', send(move))


def factura_descuento_linea():
    move = invoice(factura_journal, doc_factura, dist, [line(syrup, 12, discount=10), line(lora, 70, discount=5)])
    record('F2 Factura con descuento por línea (convenio)', send(move))


def factura_descuento_global():
    move = invoice(factura_journal, doc_factura, dist, [
        line(syrup, 10), line(insulin, 2),
        Command.create({'name': 'Descuento por volumen', 'quantity': 1, 'price_unit': -15.0,
                        'tax_ids': [Command.set(igv.ids)]}),
    ])
    record('F3 Factura con descuento global', send(move))


def factura_dolares():
    move = invoice(factura_journal, doc_factura, dist, [line(syrup, 20, price=5.40)],
                   currency_id=env.ref('base.USD').id)
    record('F4 Factura en dólares', send(move))


def factura_gratuita():
    # Venta con una muestra médica: leyenda 1002 e ítem con «18% Libre Final».
    # Requiere al_l10n_pe_edi_downpayment_discount v5 (el nativo rechaza 3294).
    move = invoice(factura_journal, doc_factura, dist, [
        line(syrup, 5),
        line(lora, 30, taxes=free_group, name='Loratadina 10 mg tableta (muestra médica)'),
    ], l10n_pe_edi_legend='1002')
    record('F5 Factura con muestra médica gratuita', send(move))


def factura_mixta():
    move = invoice(factura_journal, doc_factura, dist, [
        line(syrup, 3), line(metf, 60), line(insulin, 1),
        line(lora, 10, taxes=ina, name='Loratadina 10 mg tableta (inafecta, prueba)'),
    ])
    record('F6 Factura gravada, exonerada e inafecta', send(move))


def factura_icbper():
    move = invoice(factura_journal, doc_factura, dist, [line(syrup, 2), line(bag, 2)])
    record('F7 Factura con bolsa plástica (ICBPER)', send(move))


def factura_100_gratuita():
    move = invoice(factura_journal, doc_factura, dist, [
        line(lora, 30, taxes=free_group, name='Loratadina 10 mg tableta (muestra médica)')],
        l10n_pe_edi_legend='1002')
    record('F8 Factura 100 % gratuita (leyenda 1002)', send(move))


# ----------------------------------------------------------------------
# Boletas (B001)
# ----------------------------------------------------------------------
def boleta_consumidor_final():
    move = invoice(boleta_journal, doc_boleta, final, [line(para, 20)])
    record('B1 Boleta a consumidor final (menos de S/ 700)', send(move))


def boleta_mayor_700():
    move = invoice(boleta_journal, doc_boleta, lucia, [line(insulin, 13)])
    record('B2 Boleta de más de S/ 700 con DNI', send(move))


# ----------------------------------------------------------------------
# Notas de crédito y débito (asistentes de Odoo)
# ----------------------------------------------------------------------
def reverse(origin, reason, code, partial=False):
    wizard = env['account.move.reversal'].with_context(
        active_model='account.move', active_ids=origin.ids).create({
            'reason': reason, 'l10n_pe_edi_refund_reason': code,
            'journal_id': origin.journal_id.id, 'date': fields.Date.context_today(origin)})
    action = wizard.refund_moves()
    refund = Move.browse(action['res_id'])
    if partial:
        partial(refund)
    refund.action_post()
    return refund


def nc_anulacion():
    origin = send(invoice(factura_journal, doc_factura, dist, [line(syrup, 4)]))
    record('N0 Factura de origen de la NC total', origin)
    record('N1 NC por anulación de la operación (01)', send(reverse(origin, 'Anulación de la operación', '01')))


def nc_devolucion_parcial():
    origin = send(invoice(factura_journal, doc_factura, dist, [line(syrup, 10), line(amox, 100)]))
    record('N2 Factura de origen de la devolución', origin)

    def keep_two_syrups(refund):
        refund.invoice_line_ids.filtered(lambda l: l.product_id == amox).unlink()
        refund.invoice_line_ids.filtered(lambda l: l.product_id == syrup).quantity = 2
    record('N3 NC por devolución parcial (07)',
           send(reverse(origin, 'Devolución de 2 frascos', '07', keep_two_syrups)))


def nc_descuento():
    origin = send(invoice(factura_journal, doc_factura, dist, [line(syrup, 10)]))
    record('N4 Factura de origen del descuento', origin)

    def discount(refund):
        refund.invoice_line_ids = [Command.clear(), Command.create({
            'name': 'Descuento por pronto pago', 'quantity': 1, 'price_unit': 10.0,
            'tax_ids': [Command.set(igv.ids)]})]
    record('N5 NC por descuento global (04)', send(reverse(origin, 'Descuento por pronto pago', '04', discount)))


def nc_boleta():
    origin = send(invoice(boleta_journal, doc_boleta, lucia, [line(para, 30)]))
    record('N6 Boleta de origen', origin)
    record('N7 NC de boleta (BC01)', send(reverse(origin, 'Error en el producto', '01')))


def nd_intereses():
    origin = send(invoice(factura_journal, doc_factura, dist, [line(syrup, 10)]))
    record('D0 Factura de origen de la ND', origin)
    wizard = env['account.debit.note'].with_context(
        active_model='account.move', active_ids=origin.ids).create({
            'reason': 'Intereses por pago tardío', 'l10n_pe_edi_charge_reason': '01',
            'journal_id': origin.journal_id.id})
    debit = Move.browse(wizard.create_debit()['res_id'])
    debit.invoice_line_ids = [Command.clear(), Command.create({
        'name': 'Intereses moratorios', 'quantity': 1, 'price_unit': 5.0, 'tax_ids': [Command.set(igv.ids)]})]
    debit.action_post()
    record('D1 ND por intereses moratorios (01)', send(debit))


# ----------------------------------------------------------------------
# Comunicación de baja
# ----------------------------------------------------------------------
def cancel(move, reason):
    move.l10n_pe_edi_cancel_reason = reason
    move.button_cancel_posted_moves()
    return send(move, rounds=6)


def baja_factura():
    origin = send(invoice(factura_journal, doc_factura, dist, [line(syrup, 1)]))
    record('A0 Factura que se da de baja', origin)
    record('A1 Comunicación de baja de factura', cancel(origin, 'Error en el monto'), 'cancelled')


def baja_boleta():
    # Odoo no envía bajas de boletas (resumen diario): se anulan con una
    # nota de crédito (caso N7). Se comprueba que lo impida.
    origin = send(invoice(boleta_journal, doc_boleta, lucia, [line(para, 10)]))
    record('A2 Boleta que se intenta dar de baja', origin)
    origin.l10n_pe_edi_cancel_reason = 'Error en el cliente'
    try:
        origin.button_cancel_posted_moves()
    except Exception as error:
        env.cr.rollback()
        results.append(('A3 Baja de boleta: Odoo exige nota de crédito', origin.name, '03', 'PEN',
                        origin.amount_total, origin.edi_state, '', str(error)[:200], True))
        return
    results.append(('A3 Baja de boleta: se esperaba que Odoo la impidiera', origin.name, '03', 'PEN',
                    origin.amount_total, origin.edi_state, '', '', False))


# ----------------------------------------------------------------------
# Caja (al_l10n_pe_edi_pos)
# ----------------------------------------------------------------------
config = env['pos.config'].search([('name', '=', 'Botica Principal')], limit=1)


def session():
    if not config.current_session_id:
        config.open_ui()
    current = config.current_session_id
    if current.state == 'opening_control':
        current.set_opening_control(0, '')
    return current


def pos_order(customer, doc_type, items, refund_of=None):
    """``items``: (variante, cantidad en unidades, precio por unidad, presentación)."""
    pos_session = session()
    lines, untaxed, total = [], 0.0, 0.0
    for variant, qty, price, pres in items:
        taxes = variant.taxes_id
        computed = taxes.compute_all(price, quantity=qty, product=variant, partner=customer)
        untaxed += computed['total_excluded']
        total += computed['total_included']
        values = {'product_id': variant.id, 'qty': qty, 'price_unit': price,
                  'tax_ids': [Command.set(taxes.ids)], 'price_subtotal': computed['total_excluded'],
                  'price_subtotal_incl': computed['total_included']}
        if pres:
            values['pharmacy_presentation_id'] = pres.id
        if variant.tracking == 'lot':
            lot = env['stock.lot'].search([('product_id', '=', variant.id),
                                           ('pharmacy_state', '=', 'available')], limit=1)
            values['pack_lot_ids'] = [Command.create({'lot_name': lot.name})]
        lines.append(Command.create(values))
    order = env['pos.order'].create({
        'session_id': pos_session.id, 'partner_id': customer.id, 'lines': lines, 'to_invoice': True,
        'l10n_pe_doc_type': doc_type, 'amount_tax': total - untaxed, 'amount_total': total,
        'amount_paid': total, 'amount_return': 0,
    })
    cash = config.payment_method_ids.filtered('is_cash_count')[:1] or config.payment_method_ids[:1]
    env['pos.payment'].create({'pos_order_id': order.id, 'payment_method_id': cash.id, 'amount': total})
    order.action_pos_order_paid()
    order.action_pos_order_invoice()
    return order


def caja_factura():
    box = presentation(para, 100)
    order = pos_order(dist, 'factura', [(para, 100, box.price / 100, box), (syrup, 1, syrup.lst_price, None)])
    record('C1 Factura desde la caja (Caja x 100)', send(order.account_move))


def caja_bolsa():
    order = pos_order(lucia, 'boleta', [(lora, 10, lora.lst_price, None), (bag, 1, bag.lst_price, None)])
    record('C2 Boleta desde la caja con bolsa (ICBPER)', send(order.account_move))


def caja_devolucion():
    order = pos_order(lucia, 'boleta', [(syrup, 2, syrup.lst_price, None)])
    record('C3 Boleta de caja que se devuelve', send(order.account_move))
    refund = env['pos.order'].browse(order.refund()['res_id'])
    refund.l10n_pe_edi_refund_reason = '07'
    cash = config.payment_method_ids.filtered('is_cash_count')[:1] or config.payment_method_ids[:1]
    env['pos.payment'].create({'pos_order_id': refund.id, 'payment_method_id': cash.id,
                               'amount': refund.amount_total})
    refund.amount_paid = refund.amount_total
    refund.to_invoice = True
    refund.action_pos_order_paid()
    refund.action_pos_order_invoice()
    record('C4 NC por devolución en la caja', send(refund.account_move))


for case, function in [
    ('F1', factura_credito), ('F2', factura_descuento_linea), ('F3', factura_descuento_global),
    ('F4', factura_dolares), ('F5', factura_gratuita), ('F6', factura_mixta), ('F7', factura_icbper),
    ('F8', factura_100_gratuita),
    ('B1', boleta_consumidor_final), ('B2', boleta_mayor_700),
    ('N1', nc_anulacion), ('N3', nc_devolucion_parcial), ('N5', nc_descuento), ('N7', nc_boleta),
    ('D1', nd_intereses), ('A1', baja_factura), ('A3', baja_boleta),
    ('C1', caja_factura), ('C2', caja_bolsa), ('C4', caja_devolucion),
]:
    run(case, function)
    env.cr.commit()

for row in results:
    print('RESULT', ' ; '.join(str(value) for value in row))
print('RESULT total %s, aceptados %s' % (len(results), sum(1 for row in results if row[-1])))
