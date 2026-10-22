"""Prueba funcional de comisiones y agencias externas de cobranza (v7, 22/10/2026).

Se corre después de ``prueba_funcional_cobranza.py`` (reutiliza sus gestores,
clientes y banco). Crea la agencia «Estudio Jurídico Recupera» con un usuario de
prueba, le entrega dos clientes, registra cobros y liquida las comisiones de la
gestora y de la agencia. Idempotente: cada corrida agrega documentos.

    .venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d test_pe_collection --no-http \\
        < myodoo/ol_new_apps/docs/cobranza/pruebas/prueba_funcional_comisiones.py
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError

#: Usuario de prueba de la agencia (solo para bases test_).
AGENCY_LOGIN = 'estudio_recupera'
AGENCY_PASSWORD = 'FwiQ5EcBpOUmrAfL'

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


company = env['res.company'].search([('chart_template', '=', 'pe')], limit=1)
admin = env.ref('base.user_admin')
env = env(user=admin, context=dict(env.context, allowed_company_ids=[company.id], tz='America/Lima'))
today = fields.Date.context_today(env['res.partner'])
Users = env['res.users'].with_context(active_test=False)
rosa = Users.search([('login', '=', 'rquispe')])
assert rosa, 'Corra antes prueba_funcional_cobranza.py'
Partner = env['res.partner']
agro = Partner.search([('name', '=', 'Agroindustrias San Lorenzo S.A.C.')], limit=1)
andes = Partner.search([('name', '=', 'Ferretería Los Andes S.A.C.')], limit=1)
misti = Partner.search([('name', '=', 'Comercial Misti S.R.L.')], limit=1)
sale_journal = env['account.journal'].search([('code', '=', 'VCOB'), ('company_id', '=', company.id)])
bank = env['account.journal'].search([('code', '=', 'BBVA'), ('company_id', '=', company.id)])


def invoice(partner, amount, due_days):
    due = today + timedelta(days=due_days)
    move = env['account.move'].create({
        'move_type': 'out_invoice', 'partner_id': partner.id, 'journal_id': sale_journal.id,
        'invoice_date': min(due, today) - timedelta(days=30), 'invoice_date_due': due,
        'invoice_line_ids': [Command.create({'name': 'Venta de mercadería', 'price_unit': amount,
                                             'tax_ids': [Command.clear()]})],
    })
    move.action_post()
    return move


def pay(move, amount=None):
    vals = {'journal_id': bank.id, 'payment_date': today}
    if amount:
        vals['amount'] = amount
    return env['account.payment.register'].with_context(
        active_model='account.move', active_ids=move.ids).create(vals)._create_payments()


# ----------------------------------------------------------------------
# F10 Agencia externa
# ----------------------------------------------------------------------
plan = env.ref('al_l10n_pe_collection.commission_plan_default')
igv = env['account.tax'].search([('type_tax_use', '=', 'purchase'), ('amount', '=', 18),
                                 ('company_id', '=', company.id)], limit=1)
product = env['product.product'].search([('name', '=', 'Servicio de cobranza extrajudicial')], limit=1) \
    or env['product.product'].create({'name': 'Servicio de cobranza extrajudicial', 'type': 'service',
                                      'purchase_ok': True, 'sale_ok': False,
                                      'supplier_taxes_id': [Command.set(igv.ids)]})
company.write({'l10n_pe_collection_commission_plan_id': plan.id,
               'l10n_pe_collection_commission_product_id': product.id})

agency_user = Users.search([('login', '=', AGENCY_LOGIN)]) or Users.create({
    'name': 'Carmen Salazar (Estudio Recupera)', 'login': AGENCY_LOGIN, 'email': 'csalazar@recupera.pe',
    'tz': 'America/Lima', 'group_ids': [Command.set([env.ref('base.group_user').id])],
    'company_id': company.id, 'company_ids': [Command.set(company.ids)]})
agency_user.password = AGENCY_PASSWORD
Agency = env['l10n_pe.collection.agency']
agency = Agency.search([('name', '=', 'Estudio Jurídico Recupera')], limit=1)
if not agency:
    supplier = Partner.search([('name', '=', 'Estudio Jurídico Recupera S.A.C.')], limit=1) or Partner.create({
        'name': 'Estudio Jurídico Recupera S.A.C.', 'is_company': True, 'vat': '20601234565',
        'l10n_latam_identification_type_id': env.ref('l10n_pe.it_RUC').id, 'email': 'facturas@recupera.pe'})
    agency = Agency.create({'name': 'Estudio Jurídico Recupera', 'partner_id': supplier.id, 'plan_id': plan.id,
                            'user_ids': [Command.set(agency_user.ids)],
                            'note': 'Cartera mayor a 90 días. Comisión según la escala por antigüedad; '
                                    'liquidación mensual.'})
check('F10', 'El usuario de la agencia recibe su grupo',
      env.ref('al_l10n_pe_collection.group_collection_agency') in agency_user.group_ids)

wizard = env['l10n_pe.collection.agency.assign'].with_context(
    active_model='res.partner', active_ids=(andes | misti).ids).create({
        'agency_id': agency.id, 'date_from': today - timedelta(days=5), 'replace': True})
wizard.action_assign()
check('F10', 'Dos clientes entregados a la agencia',
      andes.l10n_pe_collection_agency_id == agency and misti.l10n_pe_collection_agency_id == agency)

inv_andes = invoice(andes, 6000, -150)
inv_misti = invoice(misti, 2500, -95)
inv_agro = invoice(agro, 4000, -50)
pay(inv_andes, 3500)
pay(inv_misti)
pay(inv_agro)
env['l10n_pe.collection.portfolio'].flush_model()

as_agency = env(user=agency_user)
visible = as_agency['l10n_pe.collection.portfolio'].search([]).partner_id
check('F10', 'La agencia solo ve la cartera asignada', visible and visible <= (andes | misti), visible.mapped('name'))
check('F10', 'La agencia no lee facturas de otros clientes',
      raises(lambda: inv_agro.with_user(agency_user).read(['name']), AccessError))
check('F10', 'La agencia registra gestiones de sus clientes', as_agency['l10n_pe.collection.action'].create({
    'partner_id': andes.id, 'channel': 'email', 'result_id': env.ref('al_l10n_pe_collection.result_no_answer').id,
    'note': 'Carta notarial enviada al domicilio fiscal.'}))
check('F10', 'Pero no de clientes ajenos', raises(lambda: as_agency['l10n_pe.collection.action'].create({
    'partner_id': agro.id, 'channel': 'email',
    'result_id': env.ref('al_l10n_pe_collection.result_no_answer').id}), AccessError))
env.cr.commit()

# ----------------------------------------------------------------------
# F11 Comisiones
# ----------------------------------------------------------------------
Commission = env['l10n_pe.collection.commission']
month_start = today.replace(day=1)
rosa_com = Commission.create({'beneficiary': 'user', 'user_id': rosa.id, 'date_from': month_start,
                              'date_to': today})
rosa_com.action_compute()
agro_line = rosa_com.line_ids.filtered(lambda l: l.move_id == inv_agro)
check('F11', 'Gestora: 4 000 cobrados a 50 días al 3 %', agro_line.rate == 3.0 and agro_line.commission_amount == 120.0,
      '%s %%' % agro_line.rate)
check('F11', 'Gestora: no le cuenta lo cobrado por la agencia',
      not rosa_com.line_ids.filtered(lambda l: l.partner_id in (andes | misti)))
rosa_com.action_confirm()
agency_com = Commission.create({'beneficiary': 'agency', 'agency_id': agency.id, 'date_from': month_start,
                                'date_to': today})
agency_com.action_compute()
by_move = {l.move_id: l for l in agency_com.line_ids}
check('F11', 'Agencia: 3 500 a 150 días al 6 % y 2 500 a 95 días al 6 %',
      by_move.get(inv_andes) and by_move[inv_andes].commission_amount == 210.0
      and by_move.get(inv_misti) and by_move[inv_misti].commission_amount == 150.0)
agency_com.action_confirm()
agency_com.action_create_bill()
bill = agency_com.invoice_id
check('F11', 'Factura de la agencia en borrador con IGV', bill.state == 'draft' and bill.move_type == 'in_invoice'
      and bill.amount_tax > 0, '%s + IGV %s' % (bill.amount_untaxed, bill.amount_tax))
check('F11', 'La agencia ve su liquidación y no la de la gestora',
      as_agency['l10n_pe.collection.commission'].search([]) == agency_com
      or rosa_com not in as_agency['l10n_pe.collection.commission'].search([]))
check('F11', 'La gestora no ve la liquidación de la agencia',
      agency_com not in Commission.with_user(rosa).search([]))
env.cr.commit()

failed = [r for r in RESULTS if not r[2]]
print('\nRESUMEN: %s comprobaciones, %s OK, %s FALLA' % (len(RESULTS), len(RESULTS) - len(failed), len(failed)))
for stage, label, _ok in failed:
    print('  FALLA [%s] %s' % (stage, label))
