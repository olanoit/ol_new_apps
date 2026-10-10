# -*- coding: utf-8 -*-
"""Datos demo de la fase 3 (línea base) sobre el plan «DEMO PLAN MOMEN-35-26».

Requiere haber ejecutado antes ``planner_demo_data.py``. Deja:

- dos reglas de aprobación del plan (jefatura y, sobre S/ 100 000, gerencia de
  operaciones), como las del archivo demo del módulo;
- tres compras confirmadas de la melamina blanca (base de W-12);
- la versión 1 aprobada, con su presupuesto analítico (la melamina RH, sin
  etapa en el maestro, se asigna a Producción antes de pedir la aprobación);
- la versión 2 en borrador («Nueva versión»), con el costo de la melamina
  blanca aplicado por ponderado de 6 meses y una línea nueva sin etapa ni costo
  (rejilla de ventilación) que impide aprobarla.

Idempotente. Ejecutar con:
  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < planner_demo_baseline.py
"""
from datetime import timedelta

from odoo import fields

P = 'DEMO PLAN'
# Como admin (jefatura del planificador): el superusuario no es revisor.
env = env(user=env.ref('base.user_admin'))
Plan = env['construction.resource.plan']
project = env['project.project'].search([('name', '=', f'{P} MOMEN-35-26')], limit=1)
assert project, 'Ejecute antes planner_demo_data.py'
unit = env.ref('uom.product_uom_unit')


def get_or_create(model, domain, vals):
    return env[model].search(domain, limit=1) or env[model].create(vals)


print('=== Reglas de aprobación del plan ===')
plan_model = env['ir.model']._get('construction.resource.plan')
get_or_create('tier.definition', [('name', '=', f'{P} · Nivel 1: jefatura de proyectos')], {
    'name': f'{P} · Nivel 1: jefatura de proyectos', 'model_id': plan_model.id,
    'review_type': 'group',
    'reviewer_group_id': env.ref('al_construction_planner.group_planner_manager').id,
    'definition_domain': '[]', 'sequence': 20, 'approve_sequence': True, 'has_comment': True})
get_or_create('tier.definition', [('name', '=', f'{P} · Nivel 2: gerencia (más de S/ 100 000)')], {
    'name': f'{P} · Nivel 2: gerencia (más de S/ 100 000)', 'model_id': plan_model.id,
    'review_type': 'group',
    'reviewer_group_id': env.ref(
        'al_construction_material_request.group_construction_operations_manager').id,
    'definition_domain': "[('amount_total', '>', 100000)]", 'sequence': 10,
    'approve_sequence': True})

print('=== Compras de la melamina blanca (base de W-12) ===')
white = env['product.product'].search([('name', '=', f'{P} Melamina MDP blanco fantasía')], limit=1)
assert white, 'No está la melamina blanca del demo'
vendor = get_or_create('res.partner', [('name', '=', f'{P} Maderera (proveedor)')], {
    'name': f'{P} Maderera (proveedor)', 'is_company': True})
today = fields.Date.context_today(env.user)
for ref, days, qty, price in [('W12-1', 150, 20, 118.50), ('W12-2', 75, 35, 122.00),
                              ('W12-3', 20, 15, 124.90)]:
    if env['purchase.order'].search_count([('partner_ref', '=', f'{P} {ref}')]):
        continue
    order = env['purchase.order'].create({
        'partner_id': vendor.id, 'partner_ref': f'{P} {ref}',
        'order_line': [(0, 0, {'product_id': white.id, 'product_qty': qty, 'price_unit': price})]})
    order.button_confirm()
    order.date_approve = fields.Datetime.to_datetime(today - timedelta(days=days))

print('=== Versión 1: aprobada ===')
plan_v1 = Plan.search([('project_id', '=', project.id), ('version', '=', 1)], limit=1)
if plan_v1.state == 'draft':
    unstaged = plan_v1.line_ids.filtered(lambda l: not l.stage)
    if unstaged:
        unstaged.write({'stage': 'production'})
        plan_v1.message_post(body='La melamina RH no tiene etapa en el maestro: se corta en '
                                  'Producción, como la blanca (demo).')
    plan_v1.action_request_approval()
if plan_v1.state == 'to_approve':
    # validate_tier() abriría el asistente de comentario (has_comment).
    plan_v1._validate_tier()
print('v1:', plan_v1.display_name, plan_v1.state, plan_v1.budget_analytic_id.display_name)

print('=== Versión 2: en borrador ===')
REASON = ('La melamina blanca se compra por debajo del costo del maestro (ponderado de '
          '6 meses) y falta la rejilla de ventilación, que el maestro no tenía.')
plan_v2 = Plan.search([('project_id', '=', project.id), ('parent_id', '=', plan_v1.id)], limit=1)
if not plan_v2 and plan_v1.state in ('approved', 'in_progress'):
    wizard = env['construction.plan.replan.wizard'].create({
        'plan_id': plan_v1.id, 'mode': 'all',
        'reason': REASON})
    plan_v2 = Plan.browse(wizard.action_create_version()['res_id'])
    price = env['construction.plan.price.wizard'].create({
        'plan_id': plan_v2.id, 'product_id': white.id, 'basis': 'weighted_6m'})
    price.price_unit = round(price.price_weighted_6m, 2)
    price.action_apply()
    grille = get_or_create('product.product', [('name', '=', f'{P} Rejilla de ventilación')], {
        'name': f'{P} Rejilla de ventilación', 'default_code': '62011239', 'type': 'consu',
        'uom_id': unit.id})
    space = plan_v2.line_ids.filtered(lambda l: l.task_level == 'space')[:1].task_id
    env['construction.resource.plan.line'].create({
        'plan_id': plan_v2.id, 'task_id': space.id, 'resource_type': 'material',
        'product_id': grille.id, 'product_uom_id': unit.id, 'qty_planned': 2})
print('v2:', plan_v2.display_name, plan_v2.state, plan_v2.amount_total)
env.cr.commit()
