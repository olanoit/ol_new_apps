# -*- coding: utf-8 -*-
"""Prueba de flujo completo: retención de IGV y detracción SPOT.

Los tests unitarios de cada módulo trabajan sobre datos de laboratorio y
comprueban piezas sueltas. Esto recorre los dos ciclos **de punta a
punta** sobre una base real —factura, publicación, reparto del asiento,
pago, constancia y comprobante electrónico— y comprueba además el cruce
entre ambos regímenes, que es donde más fácil se cuelan los errores: una
operación sujeta a detracción está exceptuada de retención.

    cd /home/och/odoo/ce19
    .venv/bin/python3 odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19_qa --no-http \
        < myodoo/ol_new_apps/docs/validacion/pruebas/flujo_retencion_detraccion.py

Escribe en la base durante la ejecución y termina en **rollback**: no
deja rastro. Aun así, conviene lanzarlo sobre el clon y no sobre la base
de trabajo.

Cada paso imprime OK / AVISO / FALLA:

* **FALLA**: el flujo no produce el resultado que manda la norma.
* **AVISO**: falta configuración para ejercitar ese tramo; el script la
  siembra al vuelo para poder seguir, y lo dice.
"""
import traceback

from odoo import Command, fields
from odoo.tools import float_compare

RESULTS = []
CURRENT = ['general']
OK, WARN, FAIL = 'OK', 'AVISO', 'FALLA'


def escenario(name):
    CURRENT[0] = name
    print('\n' + '=' * 72)
    print('  %s' % name)
    print('=' * 72)


def record(level, title, detail=''):
    RESULTS.append((CURRENT[0], level, title, detail))
    icon = {OK: '  OK  ', WARN: ' AVISO', FAIL: ' FALLA'}[level]
    print('%s  %s%s' % (icon, title, ' — %s' % detail if detail else ''))


def check(condition, title, detail=''):
    record(OK if condition else FAIL, title, detail)
    return bool(condition)


def aviso(title, detail=''):
    record(WARN, title, detail)


def igual(valor, esperado, title, decimales=2):
    ok = float_compare(valor, esperado, precision_digits=decimales) == 0
    record(OK if ok else FAIL, title,
           'esperado %s, obtenido %s' % (esperado, valor))
    return ok


def guard(fn):
    try:
        fn()
    except Exception as exc:                      # noqa: BLE001
        record(FAIL, '%s lanzó una excepción' % fn.__name__,
               '%s: %s' % (type(exc).__name__, exc))
        traceback.print_exc(limit=4)


# ======================================================================
#  Preparación: compañía peruana, diario, cuentas, impuestos
# ======================================================================
company = env['res.company'].search(
    [('partner_id.country_id.code', '=', 'PE')], limit=1) or env.company
env = env(context=dict(env.context, allowed_company_ids=[company.id]))
env.cr.execute('SELECT 1')                        # despierta el cursor

print('Base de datos : %s' % env.cr.dbname)
print('Compañía      : %s (%s)' % (company.name, company.vat or 'sin RUC'))

Move = env['account.move'].with_company(company)
Account = env['account.account'].with_company(company)
Tax = env['account.tax'].with_company(company)


def cuenta(code, name, account_type, reconcile=False):
    acc = Account.search([('code', '=', code)], limit=1)
    if not acc:
        acc = Account.create({
            'code': code, 'name': name, 'account_type': account_type,
            'reconcile': reconcile, 'company_ids': [Command.link(company.id)]})
    return acc


journal_purchase = env['account.journal'].search(
    [('company_id', '=', company.id), ('type', '=', 'purchase')], limit=1)
journal_bank = env['account.journal'].search(
    [('company_id', '=', company.id), ('type', '=', 'bank')], limit=1)
tax_igv = Tax.search([('company_id', '=', company.id),
                      ('type_tax_use', '=', 'purchase'),
                      ('amount', '=', 18.0)], limit=1)
account_exp = Account.search([('account_type', '=', 'expense')], limit=1)

check(bool(journal_purchase), 'Diario de compras disponible',
      journal_purchase.name if journal_purchase else 'ninguno')
check(bool(journal_bank), 'Diario de banco disponible',
      journal_bank.name if journal_bank else 'ninguno')
check(bool(tax_igv), 'IGV 18 % de compras disponible',
      tax_igv.name if tax_igv else 'ninguno')

# --- configuración del agente de retención ---------------------------
if not company.l10n_pe_retention_tax_id:
    aviso('Impuesto de retención sin configurar', 'se crea al vuelo')
    acc_ret = cuenta('40114', 'IGV Retenciones por pagar (flujo)',
                     'liability_current', reconcile=True)
    seq = env['ir.sequence'].create({
        'name': 'Retención IGV (flujo)', 'implementation': 'no_gap',
        'prefix': 'R001-', 'padding': 8, 'company_id': company.id})
    tax_ret = Tax.create({
        'name': 'Retención IGV 3 % (flujo)', 'amount': -3.0,
        'amount_type': 'percent', 'type_tax_use': 'purchase',
        'is_withholding_tax_on_payment': True,
        'withholding_sequence_id': seq.id, 'company_id': company.id})
    tax_ret.invoice_repartition_line_ids.filtered(
        lambda l: l.repartition_type == 'tax').account_id = acc_ret
    tax_ret.refund_repartition_line_ids.filtered(
        lambda l: l.repartition_type == 'tax').account_id = acc_ret
else:
    tax_ret = company.l10n_pe_retention_tax_id

acc_pendiente = cuenta('104901', 'Pagos pendientes (flujo)',
                       'asset_current', reconcile=True)
company.write({
    'l10n_pe_retention_agent': True,
    'l10n_pe_retention_rate': 3.0,
    'l10n_pe_retention_min_amount': 700.0,
    'l10n_pe_retention_tax_id': tax_ret.id,
    'l10n_pe_retention_outstanding_account_id': acc_pendiente.id,
})

# Odoo 19 solo genera el asiento del pago si el método de pago tiene
# cuenta de pagos pendientes; sin ella el pago se queda en «in_process»
# sin apuntes y la retención nunca llega al mayor.
metodo = journal_bank.outbound_payment_method_line_ids[:1]
if metodo and not metodo.payment_account_id:
    aviso('El método de pago del diario de banco no tiene cuenta de '
          'pagos pendientes', 'se siembra %s para poder seguir'
          % acc_pendiente.code)
    metodo.payment_account_id = acc_pendiente
check(bool(tax_ret.withholding_sequence_id),
      'Serie de la constancia de retención',
      tax_ret.withholding_sequence_id.prefix or 'sin secuencia')

# --- configuración del reparto de la detracción ----------------------
if not company.l10n_pe_detraction_payable_account_id:
    aviso('Cuenta de detracciones por pagar sin configurar',
          'se crea al vuelo')
    # el módulo restringe por dominio a liability_payable / asset_receivable
    company.l10n_pe_detraction_payable_account_id = cuenta(
        '42121', 'Detracciones por pagar (flujo)', 'liability_payable',
        reconcile=True)
if not company.l10n_pe_detraction_receivable_account_id:
    company.l10n_pe_detraction_receivable_account_id = cuenta(
        '12121', 'Detracciones por cobrar (flujo)', 'asset_receivable',
        reconcile=True)
company.l10n_pe_detraction_split = True

# --- terceros --------------------------------------------------------
tipo_ruc = env['l10n_latam.identification.type'].search(
    [('l10n_pe_vat_code', '=', '6')], limit=1)
pe = env.ref('base.pe')


def proveedor(name, vat, **extra):
    vals = {'name': name, 'vat': vat, 'country_id': pe.id,
            'is_company': True, 'company_type': 'company'}
    if tipo_ruc:
        vals['l10n_latam_identification_type_id'] = tipo_ruc.id
    vals.update(extra)
    return env['res.partner'].with_company(company).create(vals)


prov_normal = proveedor('FLUJO Proveedor Normal SAC', '20512528458')
prov_agente = proveedor('FLUJO Proveedor Agente SAC', '20100128056',
                        is_retention_agent=True)
prov_bueno = proveedor('FLUJO Buen Contribuyente SAC', '20100017491',
                       is_good_taxpayer=True)


SERIE = [0]


def factura(monto, partner=None, producto=None, doc_type=None, post=True):
    """Factura de proveedor de `monto` + IGV.

    En una factura de proveedor la localización exige el número del
    documento (l10n_latam_document_number, con numeración manual), y ha
    de ser distinto en cada una: Odoo rechaza el duplicado por tercero.
    """
    SERIE[0] += 1
    line = {'name': 'Servicio de prueba', 'quantity': 1,
            'price_unit': monto, 'account_id': account_exp.id,
            'tax_ids': [Command.set(tax_igv.ids)]}
    if producto:
        line['product_id'] = producto.id
    vals = {
        'move_type': 'in_invoice',
        'partner_id': (partner or prov_normal).id,
        'ref': 'F001-%08d' % SERIE[0],
        'l10n_latam_document_number': 'F001-%08d' % SERIE[0],
        'invoice_date': fields.Date.context_today(Move),
        'date': fields.Date.context_today(Move),
        'journal_id': journal_purchase.id,
        'invoice_line_ids': [Command.create(line)],
    }
    if doc_type:
        vals['l10n_latam_document_type_id'] = doc_type.id
    move = Move.create(vals)
    if post:
        move.action_post()
    return move


# ======================================================================
#  A · Retención de IGV: ciclo completo
# ======================================================================
def escenario_retencion_completo():
    escenario('A · Retención de IGV — factura, pago, constancia y CRE')
    bill = factura(1000.0)

    check(bill.l10n_pe_retention_applies,
          'La retención aplica a una factura de S/ 1 180',
          'base %s > mínimo %s' % (bill.amount_total,
                                   company.l10n_pe_retention_min_amount))
    igual(bill.l10n_pe_retention_amount, 35.40,
          'Estimación de la retención (3 % de 1 180)')
    igual(bill.amount_total, 1180.0,
          'El total de la factura NO cambia al inyectar el impuesto')

    lineas_ret = bill.invoice_line_ids.filtered(
        lambda l: tax_ret in l.tax_ids)
    check(bool(lineas_ret),
          'El impuesto de retención queda inyectado en la línea',
          '%s línea(s)' % len(lineas_ret))

    # --- pago con retención ------------------------------------------
    wizard = env['account.payment.register'].with_company(company).with_context(
        active_model='account.move', active_ids=bill.ids).create({
            'journal_id': journal_bank.id,
            'payment_date': fields.Date.context_today(Move)})
    igual(sum(wizard.withholding_line_ids.mapped('amount')), 35.40,
          'El asistente de pago propone retener 35.40')
    igual(wizard.withholding_net_amount, 1144.60,
          'Neto a pagar al proveedor (1 180 − 35.40)')

    payments = wizard._create_payments()
    payment = payments[0]
    check(payment.state in ('paid', 'in_process'),
          'El pago se emite', 'estado %s' % payment.state)
    # En el marco nativo «amount» es el bruto aplicado a la factura: la
    # retención se descuenta dentro del asiento, no del importe del pago.
    igual(payment.amount, 1180.0,
          'El pago se registra por el bruto de la factura')

    ret_lines = payment._l10n_pe_retention_lines()
    check(bool(ret_lines), 'El pago lleva línea de retención',
          '%s línea(s)' % len(ret_lines))
    check(bool(payment.l10n_pe_retention_number),
          'Se numera la constancia al emitir el pago',
          payment.l10n_pe_retention_number or 'sin número')
    check((payment.l10n_pe_retention_number or '').startswith('R001-'),
          'La constancia sigue la serie R001-########',
          payment.l10n_pe_retention_number or '')

    # --- asiento contable --------------------------------------------
    if not check(bool(payment.move_id), 'El pago genera asiento contable',
                 payment.move_id.name or 'sin asiento'):
        return
    check(payment.move_id.state == 'posted', 'El asiento del pago se publica',
          payment.move_id.state)

    acc_ret = tax_ret.invoice_repartition_line_ids.filtered(
        lambda l: l.repartition_type == 'tax').account_id
    apuntes = payment.move_id.line_ids.filtered(
        lambda l: l.account_id in acc_ret)
    igual(sum(apuntes.mapped('credit')) - sum(apuntes.mapped('debit')), 35.40,
          'La retención se abona en la cuenta 4011x')

    salida = payment.move_id.line_ids.filtered(
        lambda l: l.account_id == payment.outstanding_account_id)
    igual(sum(salida.mapped('credit')) - sum(salida.mapped('debit')), 1144.60,
          'Por tesorería solo salen 1 144.60')
    igual(sum(payment.move_id.line_ids.mapped('balance')), 0.0,
          'El asiento del pago cuadra')

    # --- la factura queda saldada ------------------------------------
    igual(bill.amount_residual, 0.0,
          'La factura queda saldada: 1 144.60 pagados + 35.40 retenidos')
    check(bill.payment_state in ('paid', 'in_payment'),
          'La factura consta como pagada', bill.payment_state)

    # --- comprobante de retención electrónico ------------------------
    try:
        payment.action_l10n_pe_generate_cre_xml()
        adj = env['ir.attachment'].search(
            [('res_model', '=', 'account.payment'), ('res_id', '=', payment.id)],
            limit=1)
        contenido = (adj.raw or b'').decode('utf-8', 'ignore')
        check(bool(adj), 'Se genera el XML del comprobante de retención',
              adj.name if adj else 'sin adjunto')
        check('35.40' in contenido or '35.4' in contenido,
              'El XML lleva el importe retenido')
        check(str(bill.amount_total) in contenido or '1180' in contenido,
              'El XML referencia el documento de origen')
    except Exception as exc:                       # noqa: BLE001
        record(FAIL, 'La generación del CRE falla', str(exc))


# ======================================================================
#  B · Las cinco excepciones al régimen de retenciones
# ======================================================================
def escenario_excepciones():
    escenario('B · Retención — las excepciones de la R.S. 037-2002')

    bajo = factura(500.0, post=False)              # 590 <= 700
    check(not bajo.l10n_pe_retention_applies,
          'No retiene por debajo del mínimo de S/ 700',
          'total %s' % bajo.amount_total)

    entre_agentes = factura(1000.0, partner=prov_agente, post=False)
    check(not entre_agentes.l10n_pe_retention_applies,
          'No retiene entre agentes de retención')

    buen_contrib = factura(1000.0, partner=prov_bueno, post=False)
    check(not buen_contrib.l10n_pe_retention_applies,
          'No retiene a un buen contribuyente')

    boleta = env['l10n_latam.document.type'].search(
        [('code', '=', '03'), ('country_id', '=', pe.id)], limit=1)
    if boleta:
        bol = factura(1000.0, doc_type=boleta, post=False)
        check(not bol.l10n_pe_retention_applies,
              'No retiene en boleta (sin crédito fiscal)')
    else:
        aviso('No hay tipo de documento «03» para probar la boleta')

    venta = Move.create({
        'move_type': 'out_invoice', 'partner_id': prov_normal.id,
        'invoice_date': fields.Date.context_today(Move),
        'invoice_line_ids': [Command.create({
            'name': 'Venta', 'quantity': 1, 'price_unit': 1000.0,
            'account_id': account_exp.id})]})
    check(not venta.l10n_pe_retention_applies,
          'No retiene en una factura de cliente')


# ======================================================================
#  C · Detracción SPOT: cálculo, reparto del asiento y depósito
# ======================================================================
def escenario_detraccion():
    escenario('C · Detracción SPOT — cálculo, asiento y depósito')

    dtype = env['l10n_pe.detraction.type'].search(
        [('percentage', '>', 0)], order='percentage desc', limit=1)
    if not check(bool(dtype), 'Catálogo 54 de detracciones cargado',
                 '%s tipos' % env['l10n_pe.detraction.type'].search_count([])):
        return
    record(OK, 'Tipo de detracción usado en la prueba',
           '%s — %s %% (mínimo %s)' % (dtype.code, dtype.percentage,
                                       dtype.min_amount))

    producto = env['product.product'].with_company(company).create({
        'name': 'FLUJO Servicio con detracción',
        'type': 'service',
        'l10n_pe_detraction_type_id': dtype.id})

    bill = factura(2000.0, producto=producto, post=False)
    check(bill.l10n_pe_detraction_applies,
          'La detracción aplica al servicio del catálogo',
          'total %s' % bill.amount_total)
    igual(bill.l10n_pe_detraction_percent, dtype.percentage,
          'Se toma el porcentaje del tipo de detracción')

    esperado = round(bill.amount_total * dtype.percentage / 100.0)
    igual(bill.l10n_pe_detraction_amount, esperado,
          'El depósito se redondea a soles enteros')
    igual(bill.l10n_pe_detraction_net,
          bill.amount_total - bill.l10n_pe_detraction_amount,
          'Neto = total − detracción')

    # --- reparto dentro del propio asiento ---------------------------
    bill.action_post()
    cuenta_det = company.l10n_pe_detraction_payable_account_id
    terminos = bill.line_ids.filtered(
        lambda l: l.display_type == 'payment_term')
    lineas_det = terminos.filtered(lambda l: l.account_id == cuenta_det)
    lineas_prov = terminos - lineas_det

    check(bool(lineas_det),
          'El asiento separa la detracción en su propia línea',
          '%s línea(s) en %s' % (
              len(lineas_det), cuenta_det.with_company(company).code))
    igual(abs(sum(lineas_det.mapped('balance'))),
          bill.l10n_pe_detraction_amount,
          'La línea de detracción lleva el importe del depósito')
    igual(abs(sum(lineas_prov.mapped('balance'))),
          bill.l10n_pe_detraction_net,
          'La línea del proveedor lleva solo el neto')
    igual(sum(bill.line_ids.mapped('balance')), 0.0,
          'El asiento cuadra tras el reparto')
    check(len(bill.line_ids.filtered(
        lambda l: l.display_type == 'payment_term')) == 2,
        'No se crea un segundo asiento: el reparto va dentro de la factura')

    # --- depósito en el Banco de la Nación ---------------------------
    wizard = env['l10n_pe.detraction.deposit.wizard'].with_company(
        company).create({
            'move_id': bill.id,
            'journal_id': journal_bank.id,
            'payment_date': fields.Date.context_today(Move),
            'constancy_number': '000-2026-999999'})
    igual(wizard.amount, bill.l10n_pe_detraction_amount,
          'El asistente propone el importe exacto del depósito')
    wizard.action_confirm()

    check(bill.l10n_pe_detraction_number == '000-2026-999999',
          'La constancia del depósito queda guardada en la factura',
          bill.l10n_pe_detraction_number or 'sin número')
    check(bool(bill.l10n_pe_detraction_date),
          'La fecha del depósito queda guardada',
          str(bill.l10n_pe_detraction_date))

    pagos = env['account.payment'].search(
        [('company_id', '=', company.id),
         ('partner_id', '=', prov_normal.id)], order='id desc', limit=3)
    deposito = pagos.filtered(
        lambda p: float_compare(p.amount, bill.l10n_pe_detraction_amount,
                                precision_digits=2) == 0)
    check(bool(deposito), 'Se registra el pago del depósito',
          '%s por %s' % (deposito[:1].name, deposito[:1].amount)
          if deposito else 'ninguno')

    residual = bill.amount_residual
    igual(residual, bill.l10n_pe_detraction_net,
          'Tras depositar, al proveedor se le sigue debiendo el neto')


# ======================================================================
#  D · El cruce: una operación con detracción no sufre retención
# ======================================================================
def escenario_cruce():
    escenario('D · Cruce — detracción y retención son excluyentes')

    dtype = env['l10n_pe.detraction.type'].search(
        [('percentage', '>', 0)], order='percentage desc', limit=1)
    if not dtype:
        aviso('Sin catálogo de detracciones, no se puede probar el cruce')
        return

    producto = env['product.product'].with_company(company).create({
        'name': 'FLUJO Servicio SPOT para el cruce',
        'type': 'service',
        'l10n_pe_detraction_type_id': dtype.id})
    bill = factura(2000.0, producto=producto, post=False)

    check(bill.l10n_pe_detraction_applies,
          'La factura está sujeta a detracción')
    check(not bill.l10n_pe_retention_applies,
          'Y por eso NO se le aplica retención',
          'retención estimada %s' % bill.l10n_pe_retention_amount)
    igual(bill.l10n_pe_retention_amount, 0.0,
          'La retención estimada es cero')

    # y al revés: el mismo importe sin producto sujeto a SPOT sí retiene
    normal = factura(2000.0, post=False)
    check(normal.l10n_pe_retention_applies,
          'El mismo importe sin SPOT sí sufre retención',
          'estimada %s' % normal.l10n_pe_retention_amount)


# ======================================================================
for fn in (escenario_retencion_completo, escenario_excepciones,
           escenario_detraccion, escenario_cruce):
    guard(fn)

# ----------------------------------------------------------------------
print('\n' + '=' * 72)
print('  RESUMEN')
print('=' * 72)
n_ok = sum(1 for r in RESULTS if r[1] == OK)
n_warn = sum(1 for r in RESULTS if r[1] == WARN)
n_fail = sum(1 for r in RESULTS if r[1] == FAIL)
print('OK: %s   AVISO: %s   FALLA: %s   (total %s)'
      % (n_ok, n_warn, n_fail, len(RESULTS)))
if n_fail:
    print('\nFallas:')
    for mod, level, title, detail in RESULTS:
        if level == FAIL:
            print('  - [%s] %s — %s' % (mod, title, detail))
if n_warn:
    print('\nAvisos:')
    for mod, level, title, detail in RESULTS:
        if level == WARN:
            print('  - [%s] %s — %s' % (mod, title, detail))

env.cr.rollback()
print('\nRollback hecho: la base queda como estaba.')
