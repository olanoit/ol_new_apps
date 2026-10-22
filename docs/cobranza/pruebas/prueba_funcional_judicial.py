"""Prueba funcional de cobranza judicial (v8, 22/10/2026).

Se corre después de ``prueba_funcional_comisiones.py``: demanda a Ferretería
Los Andes (en el Estudio Jurídico Recupera) con actuaciones, plazos y gastos, y
comprueba el seguimiento, la provisión y el acceso del estudio.

    .venv/bin/python odoo-bin shell -c cfg/my/pe.cfg -d test_pe_collection --no-http \\
        < myodoo/ol_new_apps/docs/cobranza/pruebas/prueba_funcional_judicial.py
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError

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
luis = Users.search([('login', '=', 'lmendoza')])
agency_user = Users.search([('login', '=', 'estudio_recupera')])
assert agency_user, 'Corra antes prueba_funcional_comisiones.py'
andes = env['res.partner'].search([('name', '=', 'Ferretería Los Andes S.A.C.')], limit=1)
agro = env['res.partner'].search([('name', '=', 'Agroindustrias San Lorenzo S.A.C.')], limit=1)
agency = env['l10n_pe.collection.agency'].search([('name', '=', 'Estudio Jurídico Recupera')], limit=1)
sale_journal = env['account.journal'].search([('code', '=', 'VCOB'), ('company_id', '=', company.id)])

due = today - timedelta(days=120)
invoice = env['account.move'].create({
    'move_type': 'out_invoice', 'partner_id': andes.id, 'journal_id': sale_journal.id,
    'invoice_date': due - timedelta(days=30), 'invoice_date_due': due,
    'invoice_line_ids': [Command.create({'name': 'Fierro corrugado 1/2" x 9 m', 'quantity': 400, 'price_unit': 45,
                                         'tax_ids': [Command.clear()]})],
})
invoice.action_post()
receivable = invoice.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')

Lawsuit = env['l10n_pe.collection.lawsuit']
lawsuit = Lawsuit.create({
    'partner_id': andes.id, 'user_id': luis.id, 'agency_id': agency.id, 'lawyer': 'Dra. Carmen Salazar',
    'process_type': 'execution', 'court': '2.º Juzgado Civil Comercial de Lima',
    'line_ids': [Command.set(receivable.ids)],
    'note': 'Factura negociable conformada: título ejecutivo. El deudor tiene un local en Arequipa (SUNARP).'})
as_agency = lawsuit.with_user(agency_user)
as_agency.write({'file_number': '04512-%s-0-1817-JR-CO-02' % today.year, 'event_ids': [
    Command.create({'date': today - timedelta(days=3), 'event_type': 'filing', 'name': 'Demanda ejecutiva presentada'}),
    Command.create({'date': today, 'event_type': 'resolution', 'name': 'Mandato ejecutivo y embargo en forma de inscripción',
                    'date_deadline': today + timedelta(days=10)}),
], 'cost_ids': [
    Command.create({'name': 'Tasa judicial por ofrecimiento de pruebas', 'amount': 165.0}),
    Command.create({'name': 'Cédulas de notificación', 'amount': 42.0}),
]})
as_agency.action_file()
check('F12', 'El estudio registra el expediente, actuaciones y gastos', lawsuit.state == 'filed'
      and len(lawsuit.event_ids) == 2 and lawsuit.amount_costs == 207.0)
check('F12', 'Petitorio congelado al presentar la demanda', lawsuit.amount_claimed == 18000.0, lawsuit.amount_claimed)
check('F12', 'La factura sale del seguimiento automático', receivable.no_followup and receivable.l10n_pe_collection_in_lawsuit)
check('F12', 'El plazo queda agendado al responsable',
      lawsuit.activity_ids.user_id == luis and lawsuit.next_deadline == today + timedelta(days=10))
other = Lawsuit.search([('partner_id', '!=', andes.id)], limit=1) or Lawsuit.create({
    'partner_id': agro.id, 'court': 'Juzgado de Paz Letrado de Lima', 'process_type': 'summary',
    'line_ids': [Command.set(env['account.move.line'].search([
        ('partner_id', '=', agro.id), ('account_id.account_type', '=', 'asset_receivable'),
        ('balance', '>', 0)], limit=1).ids)]})
check('F12', 'El estudio no ve procesos de otros', raises(lambda: other.with_user(agency_user).read(['name']), AccessError))
provision = env['l10n_pe.collection.provision'].create({'journal_id': company.l10n_pe_collection_provision_journal_id.id})
provision.action_load()
line = provision.line_ids.filtered(lambda l: l.move_id == invoice)
check('F12', 'Provisión: la demanda sustenta una deuda de 4 meses', line.judicial and line.selected and line.supported)
provision.unlink()
lawsuit.action_admit()
env.cr.commit()

failed = [r for r in RESULTS if not r[2]]
print('\nRESUMEN: %s comprobaciones, %s OK, %s FALLA' % (len(RESULTS), len(RESULTS) - len(failed), len(failed)))
for stage, label, _ok in failed:
    print('  FALLA [%s] %s' % (stage, label))
