"""Prueba funcional de Cobranza y Recaudación bancaria (v3/v4, 22/10/2026).

Recorre los flujos completos con datos realistas en la compañía peruana de una
base de pruebas y deja los datos para revisarlos en la interfaz. Idempotente:
los datos maestros se reutilizan si ya existen; cada corrida agrega documentos.

    .venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d test_pe_collection --no-http \\
        < myodoo/ol_new_apps/docs/cobranza/pruebas/prueba_funcional_cobranza.py

Imprime OK/FALLA por comprobación y confirma la transacción por etapas: el shell
hace rollback al salir.
"""
import base64
from datetime import datetime, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError

RESULTS = []


def check(stage, label, condition, detail=''):
    RESULTS.append((stage, label, bool(condition)))
    print('%s  [%s] %s %s' % ('OK   ' if condition else 'FALLA', stage, label, detail))


def raises(func, *exceptions):
    try:
        with env.cr.savepoint():
            func()
    except exceptions:
        return True
    return False


def ruc(base):
    """RUC válido (dígito verificador de SUNAT) a partir de 10 dígitos."""
    weights = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    digit = 11 - sum(int(d) * w for d, w in zip(base, weights)) % 11
    return base + str({10: 0, 11: 1}.get(digit, digit))


# ----------------------------------------------------------------------
# Compañía y usuarios
# ----------------------------------------------------------------------
company = env['res.company'].search([('chart_template', '=', 'pe')], limit=1)
admin = env.ref('base.user_admin')
admin.write({'company_ids': [Command.link(company.id)], 'company_id': company.id})
env = env(user=admin, context=dict(env.context, allowed_company_ids=[company.id], tz='America/Lima'))
today = fields.Date.context_today(env['res.partner'])
print('Compañía:', company.name, '· hoy', today)

group_user = env.ref('al_l10n_pe_collection.group_collection_user')
group_manager = env.ref('al_l10n_pe_collection.group_collection_manager')
group_sale = env.ref('sales_team.group_sale_salesman')


def user(login, name):
    found = env['res.users'].with_context(active_test=False).search([('login', '=', login)])
    if found:
        return found
    return env['res.users'].create({
        'name': name, 'login': login, 'email': '%s@cobranza.pe' % login, 'tz': 'America/Lima',
        'group_ids': [Command.set([group_user.id, group_sale.id])],
        'company_id': company.id, 'company_ids': [Command.set(company.ids)],
    })


rosa = user('rquispe', 'Rosa Quispe Mamani')
luis = user('lmendoza', 'Luis Mendoza Torres')
admin.group_ids = [Command.link(group_manager.id)]

company.write({
    'l10n_pe_collection_hold_days': 60, 'l10n_pe_collection_interest_rate': 12.0,
    'l10n_pe_collection_uit': 5500.0, 'l10n_pe_collection_bureau_wait_days': 7,
})
Journal = env['account.journal']
sale_journal = Journal.search([('code', '=', 'VCOB'), ('company_id', '=', company.id)]) or Journal.create({
    'name': 'Ventas cobranza (prueba)', 'code': 'VCOB', 'type': 'sale', 'company_id': company.id,
    'l10n_latam_use_documents': False})
bank = Journal.search([('code', '=', 'BBVA'), ('company_id', '=', company.id)])
if not bank:
    bank = Journal.create({'name': 'BBVA recaudadora', 'code': 'BBVA', 'type': 'bank', 'company_id': company.id})
    outstanding = env['account.account'].create({
        'name': 'Cobros por identificar BBVA', 'code': '104199', 'account_type': 'asset_current',
        'reconcile': True})
    (bank.inbound_payment_method_line_ids | bank.outbound_payment_method_line_ids).payment_account_id = outstanding
misc = Journal.search([('code', '=', 'PROV'), ('company_id', '=', company.id)]) or Journal.create({
    'name': 'Provisiones', 'code': 'PROV', 'type': 'general', 'company_id': company.id})
company.l10n_pe_collection_provision_journal_id = misc

Zone = env['l10n_pe.collection.zone']
lima = Zone.search([('name', '=', 'Lima Norte')]) or Zone.create({'name': 'Lima Norte', 'user_id': rosa.id})
sur = Zone.search([('name', '=', 'Arequipa')]) or Zone.create({'name': 'Arequipa', 'user_id': luis.id})

it_ruc, it_dni = env.ref('l10n_pe.it_RUC'), env.ref('l10n_pe.it_DNI')
CUSTOMERS = [
    ('Agroindustrias San Lorenzo S.A.C.', ruc('2060123451'), it_ruc, rosa, lima),
    ('Distribuidora El Sol E.I.R.L.', ruc('2060234562'), it_ruc, rosa, lima),
    ('Ferretería Los Andes S.A.C.', ruc('2045678913'), it_ruc, luis, sur),
    ('Comercial Misti S.R.L.', ruc('2049876544'), it_ruc, luis, sur),
    ('Juana Huamán Rojas', '45871236', it_dni, rosa, lima),
]
partners = {}
for name, vat, id_type, collector, zone in CUSTOMERS:
    partner = env['res.partner'].search([('name', '=', name)], limit=1) or env['res.partner'].create({
        'name': name, 'vat': vat, 'l10n_latam_identification_type_id': id_type.id,
        'is_company': id_type == it_ruc, 'email': '%s@clientes.pe' % vat, 'phone': '+51 1 %s' % vat[-7:]})
    partner.with_company(company).write({'followup_responsible_id': collector.id,
                                         'l10n_pe_collection_zone_id': zone.id})
    partners[name] = partner
agro, sol, andes, misti, juana = partners.values()
env.cr.commit()


def invoice(partner, amount, due_days, label='Venta de mercadería'):
    due = today + timedelta(days=due_days)
    move = env['account.move'].create({
        'move_type': 'out_invoice', 'partner_id': partner.id, 'journal_id': sale_journal.id,
        'invoice_date': min(due, today) - timedelta(days=30), 'invoice_date_due': due,
        'invoice_line_ids': [Command.create({'name': label, 'price_unit': amount, 'tax_ids': [Command.clear()]})],
    })
    move.action_post()
    return move


def receivable(move):
    return move.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')


def pay(move, amount=None, day=None):
    vals = {'journal_id': bank.id, 'payment_date': day or today}
    if amount:
        vals['amount'] = amount
    return env['account.payment.register'].with_context(
        active_model='account.move', active_ids=move.ids).create(vals)._create_payments()


# ----------------------------------------------------------------------
# F1 Cartera
# ----------------------------------------------------------------------
inv_agro_old = invoice(agro, 8500, -75)
inv_agro_new = invoice(agro, 3200, 12)
inv_sol = invoice(sol, 1800, -20)
inv_andes = invoice(andes, 12400, -400)
inv_misti = invoice(misti, 950, -45)
inv_juana = invoice(juana, 640, -10)
Portfolio = env['l10n_pe.collection.portfolio']
Portfolio.flush_model()
rows = Portfolio.search([('move_id', 'in', (inv_agro_old | inv_andes).ids)])
row_agro = rows.filtered(lambda r: r.move_id == inv_agro_old)
check('F1', 'Cartera con gestor, zona y tramo', row_agro.user_id == rosa and row_agro.zone_id == lima
      and row_agro.bucket_id.name == '61 a 90 días', row_agro.bucket_id.name)
check('F1', 'Gestora solo ve su cartera', not Portfolio.with_user(rosa).search(
    [('move_id', '=', inv_andes.id)]))
env.cr.commit()

# ----------------------------------------------------------------------
# F2 Gestiones, compromisos y art. 62
# ----------------------------------------------------------------------
Action = env['l10n_pe.collection.action']
promise_result = env.ref('al_l10n_pe_collection.result_promise')
no_answer = env.ref('al_l10n_pe_collection.result_no_answer')
action = Action.with_user(rosa).create({
    'partner_id': agro.id, 'channel': 'call', 'result_id': promise_result.id,
    'date': datetime.combine(today, datetime.min.time()) + timedelta(hours=15),  # 10:00 en Lima
    'promise_date': today + timedelta(days=5), 'promise_amount': 8500,
    'line_ids': [Command.set(receivable(inv_agro_old).ids)], 'note': 'Pagará el viernes por transferencia.'})
check('F2', 'La gestora registra la llamada y el compromiso', action.promise_id.state == 'pending')
night = datetime.combine(today, datetime.min.time()) + timedelta(hours=26)  # 21:00 en Lima
check('F2', 'Llamada a consumidor a las 21:00: rechazada (art. 62)', raises(lambda: Action.with_user(rosa).create({
    'partner_id': juana.id, 'channel': 'call', 'result_id': no_answer.id, 'date': night}), ValidationError))
check('F2', 'Correo a consumidor a las 21:00: permitido', Action.with_user(rosa).create({
    'partner_id': juana.id, 'channel': 'email', 'result_id': no_answer.id, 'date': night}))
broken = env['l10n_pe.collection.promise'].create({
    'partner_id': misti.id, 'user_id': luis.id, 'date': today - timedelta(days=10), 'amount': 950,
    'line_ids': [Command.set(receivable(inv_misti).ids)]})
broken._l10n_pe_evaluate()
check('F2', 'Compromiso vencido sin pago: incumplido con actividad', broken.state == 'broken' and broken.activity_ids)
env.cr.commit()

# ----------------------------------------------------------------------
# F3 Reclamos
# ----------------------------------------------------------------------
dispute = env['l10n_pe.collection.dispute'].with_user(rosa).create({
    'partner_id': sol.id, 'reason_id': env.ref('al_l10n_pe_collection.dispute_reason_quantity').id,
    'line_ids': [Command.set(receivable(inv_sol).ids)], 'description': 'Faltaron 10 cajas en la entrega.'})
check('F3', 'Reclamo saca la factura del seguimiento', receivable(inv_sol).no_followup)
Portfolio.flush_model()
check('F3', 'Cartera la marca en disputa', Portfolio.search([('move_id', '=', inv_sol.id)]).in_dispute)
dispute.resolution = 'Se emite nota de crédito por las 10 cajas.'
dispute.action_resolve_customer()
check('F3', 'Cerrado a favor del cliente: vuelve al seguimiento', not receivable(inv_sol).no_followup)
check('F3', 'Ofrece la nota de crédito', dispute.action_credit_note()['res_model'] == 'account.move.reversal')
env.cr.commit()

# ----------------------------------------------------------------------
# F4 Calificación, bloqueo y ventas
# ----------------------------------------------------------------------
# Una corrida anterior pudo dejarlo liberado: se reinicia para probar el bloqueo automático.
andes.with_company(company).sudo().write({'l10n_pe_collection_hold': False, 'l10n_pe_collection_hold_until': False})
env['res.partner']._cron_l10n_pe_collection_rating()
andes_c = andes.with_company(company)
check('F4', 'Ferretería Los Andes (400 días) calificada D y bloqueada',
      andes_c.l10n_pe_collection_rating == 'D' and andes_c.l10n_pe_collection_hold == 'auto',
      '%s/%s' % (andes_c.l10n_pe_collection_rating, andes_c.l10n_pe_collection_hold))
check('F4', 'Cliente al día sin bloqueo', not sol.with_company(company).l10n_pe_collection_hold)
product = env['product.product'].search([('sale_ok', '=', True)], limit=1) or env['product.product'].create(
    {'name': 'Cemento Portland tipo I', 'list_price': 32.5})
order = env['sale.order'].with_user(luis).create({
    'partner_id': andes.id, 'company_id': company.id,
    'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': 100})]})
check('F4', 'Pedido de cliente bloqueado: aviso y no confirma', order.l10n_pe_collection_hold_warning
      and raises(order.action_confirm, UserError))
andes.action_l10n_pe_collection_release()
order.invalidate_recordset(['l10n_pe_collection_hold_warning'])
order.action_confirm()
check('F4', 'Liberado por el administrador: el pedido se confirma', order.state == 'sale')
env.cr.commit()

# ----------------------------------------------------------------------
# F5 Intereses moratorios
# ----------------------------------------------------------------------
statement = misti._l10n_pe_collection_statement_values(company)
check('F5', 'Estado de cuenta con interés moratorio (12 % TEA, 45 días)', statement['interest'] > 0,
      '%.2f' % statement['interest'])
wizard = env['l10n_pe.collection.interest.wizard'].create({'partner_ids': [Command.set(misti.ids)]})
note = env['account.move'].browse(wizard.action_create().get('res_id'))
check('F5', 'Nota de débito por intereses en borrador', note.state == 'draft' and note.debit_origin_id == inv_misti,
      '%.2f' % note.amount_total)
env.cr.commit()

# ----------------------------------------------------------------------
# F6 Provisión, recuperación, castigo y expediente
# ----------------------------------------------------------------------
Action.with_user(luis).create({
    'partner_id': andes.id, 'channel': 'letter', 'result_id': no_answer.id,
    'note': 'Carta de requerimiento entregada en el local de la Av. Ejército.'})
provision = env['l10n_pe.collection.provision'].create({'journal_id': misc.id})
provision.action_load()
line = provision.line_ids.filtered(lambda l: l.move_id == inv_andes)
check('F6', 'Propone la deuda de más de 12 meses con su gestión', line.selected and line.action_count >= 1)
provision.line_ids.filtered(lambda l: l.move_id != inv_andes).selected = False
provision.action_post()
check('F6', 'Asiento 68711 / 1911 contabilizado', provision.move_id.state == 'posted', provision.move_id.name)
pay(inv_andes, amount=2400)
provision.action_recover()
check('F6', 'Recuperación registrada (7551)', abs(line.recovered_amount - 2400) < 0.01)
html = env['ir.actions.report']._render_qweb_html('al_l10n_pe_collection.report_collection_file', andes.ids)[0]
check('F6', 'Expediente de cobranza con la carta', b'Carta de requerimiento' in html)
line.action_write_off()
check('F6', 'Castigo hasta 3 UIT concilia la factura', receivable(inv_andes).reconciled)
env.cr.commit()

# ----------------------------------------------------------------------
# F7 Centrales de riesgo
# ----------------------------------------------------------------------
bureau = env['l10n_pe.collection.bureau'].create({
    'partner_id': agro.id, 'user_id': rosa.id, 'bureau': 'equifax',
    'line_ids': [Command.set(receivable(inv_agro_old).ids)]})
bureau.action_send_notice()
check('F7', 'Aviso previo enviado', bureau.state == 'notified')
check('F7', 'No reporta antes del plazo', raises(bureau.action_report, UserError))
bureau.date_notice = today - timedelta(days=8)
bureau.action_report()
pay(inv_agro_old)
bureau._cron_collection_bureau()
check('F7', 'Pagada la deuda: por retirar con actividad', bureau.state == 'to_withdraw' and bureau.activity_ids)
env.cr.commit()

# ----------------------------------------------------------------------
# F8 Recaudación bancaria BBVA
# ----------------------------------------------------------------------
agreement = env['l10n_pe.bank.collection.agreement'].search([('name', '=', 'BBVA soles')]) or \
    env['l10n_pe.bank.collection.agreement'].create({
        'name': 'BBVA soles', 'journal_id': bank.id, 'service_code': '001', 'account_number': '001102410100001250',
        'debtors_layout_id': env.ref('al_l10n_pe_bank_collection.layout_bbva_debtors').id,
        'response_layout_id': env.ref('al_l10n_pe_bank_collection.layout_bbva_response').id})
batch = env['l10n_pe.bank.collection.batch'].create({
    'agreement_id': agreement.id, 'partner_ids': [Command.set((sol | misti | juana).ids)]})
batch.action_load()
batch.action_generate()
lines = base64.b64decode(batch.file).decode('ascii').split('\r\n')
check('F8', 'Archivo BBVA de 360 bytes con encabezado y totales',
      all(len(x) == 360 for x in lines) and lines[0][:2] == '01' and lines[-1][:2] == '03', batch.filename)
day = today.strftime('%Y%m%d')
operation = datetime.now().strftime('%H%M%S')  # único por corrida: el banco no repite operaciones
detail = ('02' + 'COMERCIAL MISTI SRL'.ljust(30) + misti.vat + inv_misti.name.replace('/', ' ').ljust(37)
          + '%015d' % 95000 + '%015d' % 95000 + '0' * 15 + '0241' + operation + day + '01' + '06')
content = '\r\n'.join(x.ljust(152) for x in (
    '01' + company.vat + '001' + 'PEN' + day + '001102410100001250', detail,
    '03' + '000000001' + '%015d' % 95000 + '%015d' % 95000 + '0' * 15)).encode('ascii')
response = env['l10n_pe.bank.collection.response'].create({
    'agreement_id': agreement.id, 'file': base64.b64encode(content), 'filename': 'recaudos_bbva.txt'})
response.action_import()
check('F8', 'Respuesta identifica cliente y documento', response.line_ids.state == 'matched'
      and response.line_ids.partner_id == misti)
response.action_process()
check('F8', 'Pago creado y factura pagada', inv_misti.payment_state in ('paid', 'in_payment'))
again = env['l10n_pe.bank.collection.response'].create({
    'agreement_id': agreement.id, 'file': base64.b64encode(content), 'filename': 'recaudos_bbva.txt'})
again.action_import()
check('F8', 'El mismo archivo otra vez: operación ya procesada', again.line_ids.state == 'duplicate')
env.cr.commit()

# ----------------------------------------------------------------------
# F9 Seguridad y crons
# ----------------------------------------------------------------------
check('F9', 'Gestor no ve compromisos de otro gestor', not env['l10n_pe.collection.promise'].with_user(rosa).search(
    [('partner_id', '=', misti.id)]))
check('F9', 'Gestor sin acceso a provisiones', raises(
    lambda: env['l10n_pe.collection.provision'].with_user(rosa).search([]), AccessError))
check('F9', 'Gestor no libera bloqueos', raises(lambda: andes.with_user(luis).action_l10n_pe_collection_release(),
                                                UserError))
env['l10n_pe.collection.promise']._cron_collection_promises()
env['l10n_pe.collection.dashboard']._cron_collection_digest()
check('F9', 'Crons de compromisos, resumen, calificación y centrales sin error', True)
env.cr.commit()

failed = [r for r in RESULTS if not r[2]]
print('\nRESUMEN: %s comprobaciones, %s OK, %s FALLA' % (len(RESULTS), len(RESULTS) - len(failed), len(failed)))
for stage, label, _ok in failed:
    print('  FALLA [%s] %s' % (stage, label))
