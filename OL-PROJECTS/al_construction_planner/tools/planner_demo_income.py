# -*- coding: utf-8 -*-
"""Datos demo de la fase 10 (ruta del ingreso) sobre «DEMO PLAN
MOMEN-35-26».

Requiere haber ejecutado antes ``planner_demo_data.py``,
``planner_demo_baseline.py`` y ``planner_demo_contracts.py``. Deja (todo
ficticio):

- la orden de venta del contrato con la partida «Cocinas» (cantidad 1, más
  IGV) para «DEMO PLAN Inmobiliaria MOMEN», confirmada y
  enlazada a la obra, con la obra del 12/10 al 18/12/2026 y su calendario de
  ingresos (cada 2 semanas, 2 + 5 + 2 días, cobro a 30 días, fondo de
  garantía 5 % al cierre) y los días hábiles del ingreso de lunes a viernes
  en Ajustes. El demo solo tiene el piso 05: el precio de la
  partida guarda la proporción de MOMEN (S/ 159,231.23 por S/ 170,764.10
  planificados);
- las entregas semanales del 22/10, 29/10 y 05/11 preparadas por la acción
  programada (días de liquidación 29/10, 05/11 y 12/11) y confirmadas;
- la valorización 1 con corte el 11/11: enviada, observada («dos cocinas del
  piso 05 con puertas por regular»), reenviada, confirmada por el cliente con
  su acta y facturada (factura publicada, no enviada a SUNAT).

Idempotente (si la obra ya tiene orden de venta del contrato no hace nada).
Ejecutar con:
  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < planner_demo_income.py
"""
import base64
from datetime import date

from odoo import Command

P = 'DEMO PLAN'
# Como admin (jefatura del planificador e ingresos).
env = env(user=env.ref('base.user_admin'))
project = env['project.project'].search([('name', '=', f'{P} MOMEN-35-26')], limit=1)
assert project, 'Ejecute antes planner_demo_data.py'
plan = project._construction_current_plan()
company = plan.company_id or project.company_id or env.company
env = env(context=dict(env.context, allowed_company_ids=company.ids))
project = project.with_env(env)
admin = env.user
for group in ('al_construction_planner.group_planner_manager',
              'al_construction_planner.group_planner_revenue'):
    if not admin.has_group(group):
        admin.group_ids = [Command.link(env.ref(group).id)]

if project.construction_sale_order_id:
    print('La obra ya tiene orden de venta del contrato:', project.construction_sale_order_id.name)
else:
    print('=== Contrato y calendario de ingresos (P-21) ===')
    # Días hábiles del ingreso de lunes a viernes (la obra puede trabajar
    # los sábados; el cliente y la administración, no).
    if not company.construction_income_calendar_id:
        calendar = env['resource.calendar'].search([
            ('name', '=', 'Días hábiles del ingreso (lunes a viernes)'),
            ('company_id', '=', company.id)], limit=1) or env['resource.calendar'].create({
                'name': 'Días hábiles del ingreso (lunes a viernes)',
                'company_id': company.id, 'tz': 'America/Lima',
                'attendance_ids': [Command.clear()] + [Command.create({
                    'name': name, 'dayofweek': str(day), 'hour_from': 8, 'hour_to': 17,
                    'day_period': 'full_day'}) for day, name in enumerate(
                        ('Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'))]})
        company.construction_income_calendar_id = calendar
    customer_vals = {'name': f'{P} Inmobiliaria MOMEN', 'is_company': True,
                     'vat': '20557912879', 'company_id': False}
    ruc = env.ref('l10n_pe.it_RUC', raise_if_not_found=False)
    if ruc:
        customer_vals['l10n_latam_identification_type_id'] = ruc.id
    customer = env['res.partner'].search([('name', '=', customer_vals['name'])], limit=1) \
        or env['res.partner'].create(customer_vals)
    product = env['product.product'].search([('name', '=', f'{P} Cocinas')], limit=1)
    if not product:
        vals = {'name': f'{P} Cocinas', 'type': 'service', 'invoice_policy': 'delivery',
                'default_code': 'DEMO-PARTIDA-COC'}
        if 'service_type' in env['product.template']._fields:
            vals['service_type'] = 'manual'
        product = env['product.product'].create(vals)
    tax = env['account.tax'].search([
        *env['account.tax']._check_company_domain(company),
        ('type_tax_use', '=', 'sale'), ('amount_type', '=', 'percent'), ('amount', '=', 18.0),
        ('price_include', '=', False)], limit=1)
    # Precio de la partida: el demo solo tiene el piso 05, así que la
    # partida vale lo mismo que en MOMEN respecto de su plan (159,231.23 de
    # 170,764.10 planificados).
    price = company.currency_id.round(plan.amount_total * 159231.23 / 170764.10)
    order = env['sale.order'].create({
        'partner_id': customer.id,
        'company_id': company.id,
        'date_order': date(2026, 10, 9),
        'client_order_ref': 'Contrato MOMEN-35-26 (demo)',
        'order_line': [Command.create({
            'product_id': product.id, 'name': 'Cocinas', 'product_uom_qty': 1,
            'price_unit': price, 'tax_ids': [Command.set(tax.ids)]})],
    })
    order.action_confirm()
    project.write({
        'partner_id': customer.id,
        'date_start': date(2026, 10, 12),
        'date': date(2026, 12, 18),
        'construction_sale_order_id': order.id,
        'construction_valuation_every': 2,
        'construction_valuation_unit': 'week',
        'construction_valuation_submit_days': 2,
        'construction_client_confirm_days': 5,
        'construction_invoice_days': 2,
        'construction_collection_days': 30,
        'construction_advance_pct': 0.0,
        'construction_advance_amortization_pct': 0.0,
        'construction_guarantee_pct': 5.0,
        'construction_guarantee_release': 'close',
    })
    print(order.name, order.amount_untaxed, project._construction_valuation_cutoffs())

    print('=== Entregas semanales (P-19) ===')
    Delivery = env['construction.weekly.delivery']
    for today in (date(2026, 10, 29), date(2026, 11, 5), date(2026, 11, 12)):
        delivery = Delivery._prepare_deliveries(today=today, projects=project)
        delivery.action_confirm()
        print(delivery.name, delivery.period_start, delivery.period_end,
              [round(p * 100, 2) for p in delivery.line_ids.mapped('progress_end')],
              delivery.revenue_amount, delivery.cost_amount, delivery.margin_amount)

    print('=== Valorización 1 (P-20) ===')
    wizard = env['construction.valuation.prepare.wizard'].create({
        'project_id': project.id, 'cutoff_date': date(2026, 11, 11)})
    valuation = env['construction.valuation'].browse(wizard.action_create()['res_id'])
    valuation.action_send()
    env['construction.reason.wizard'].with_context(
        active_model='construction.valuation', active_ids=valuation.ids,
        construction_reason_action='observe').create({
            'reason': 'Dos cocinas del piso 05 con puertas por regular.'}).action_confirm()
    valuation.message_post(body='Observación levantada con fotos de las puertas reguladas.')
    valuation.action_send()
    act = base64.b64encode(
        'Acta de conformidad de la valorización 1 (documento de ejemplo).'.encode())
    confirm = env['construction.valuation.confirm.wizard'].with_context(
        default_valuation_id=valuation.id).create({
            'confirm_date': date(2026, 11, 18),
            'confirm_name': 'Ing. Rosa Quispe (demo)',
            'confirm_role': 'Residente de obra del cliente',
            'attachment_ids': [Command.create({'name': 'Acta de conformidad VAL 1.txt',
                                               'datas': act, 'mimetype': 'text/plain'})],
        })
    confirm.action_confirm()
    valuation.action_create_invoice()
    invoice = valuation.invoice_id
    invoice.invoice_date = date(2026, 11, 20)
    invoice.action_post()
    print(valuation.name, valuation.state, valuation.amount_delivered,
          valuation.amount_confirmed, valuation.amount_guarantee, valuation.amount_net,
          invoice.name, invoice.amount_untaxed, invoice.invoice_line_ids.mapped('quantity'))

env.cr.commit()
print('OK')
