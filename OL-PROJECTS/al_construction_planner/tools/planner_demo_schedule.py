# -*- coding: utf-8 -*-
"""Datos demo de la fase 11 (cronograma valorizado e inicio) sobre «DEMO
PLAN MOMEN-35-26».

Requiere haber ejecutado antes los scripts de las fases 1 a 10 (al menos
``planner_demo_data.py``, ``planner_demo_baseline.py``,
``planner_demo_contracts.py`` y ``planner_demo_income.py``). Deja:

- la administradora como supervisora de la obra demo (su inicio muestra los
  avances por validar de la obra);
- el cobro de la factura de la valorización 1 conciliado el 21/12/2026
  (asiento de banco contra la cuenta por cobrar, como la conciliación del
  extracto), para ver el cobro real en el cronograma;
- el cronograma valorizado calculado (plan y real).

Idempotente. Ejecutar con:
  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < planner_demo_schedule.py
"""
from datetime import date

from odoo import Command

P = 'DEMO PLAN'
env = env(user=env.ref('base.user_admin'))
project = env['project.project'].search([('name', '=', f'{P} MOMEN-35-26')], limit=1)
assert project, 'Ejecute antes planner_demo_data.py'
plan = project._construction_current_plan()
company = plan.company_id or project.company_id or env.company
env = env(context=dict(env.context, allowed_company_ids=company.ids))
project = project.with_env(env)

admin = env.ref('base.user_admin')
if admin not in project.construction_supervisor_ids:
    project.construction_supervisor_ids = [Command.link(admin.id)]

valuation = env['construction.valuation'].search(
    [('project_id', '=', project.id), ('invoice_id', '!=', False)], order='cutoff_date', limit=1)
invoice = valuation.invoice_id
if invoice and invoice.state == 'posted' and invoice.payment_state not in ('paid', 'in_payment'):
    receivable = invoice.line_ids.filtered(
        lambda l: l.account_id.account_type == 'asset_receivable')
    journal = env['account.journal'].search([
        *env['account.journal']._check_company_domain(company), ('type', '=', 'bank')], limit=1)
    entry = env['account.move'].create({
        'move_type': 'entry', 'journal_id': journal.id, 'date': date(2026, 12, 21),
        'ref': f'{P} cobro {invoice.name}',
        'line_ids': [
            Command.create({'account_id': journal.default_account_id.id,
                            'debit': invoice.amount_residual,
                            'partner_id': invoice.commercial_partner_id.id,
                            'name': f'Cobro {invoice.name}'}),
            Command.create({'account_id': receivable.account_id.id,
                            'credit': invoice.amount_residual,
                            'partner_id': invoice.commercial_partner_id.id,
                            'name': f'Cobro {invoice.name}'}),
        ]})
    entry.action_post()
    (receivable | entry.line_ids.filtered(
        lambda l: l.account_id == receivable.account_id)).reconcile()
    print('Cobro', entry.name, invoice.name, invoice.payment_state)

Report = env['construction.schedule.report'].with_company(company)
rows = Report._construction_refresh(project)
data = Report.get_schedule(project.id, refresh=False)
for scenario in ('plan', 'real'):
    totals = data['totals'][scenario]
    print(scenario, 'costo', totals['cost'], 'ingreso', totals['revenue'],
          'margen', totals['margin'], 'cobrado', totals['collection_total'])
print(len(rows), 'filas')

env.cr.commit()
print('OK')
