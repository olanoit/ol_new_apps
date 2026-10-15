# -*- coding: utf-8 -*-
"""Datos demo de la fase 7 (control y personal propio) sobre el plan vigente
de «DEMO PLAN MOMEN-35-26».

Requiere haber ejecutado antes ``planner_demo_data.py``,
``planner_demo_baseline.py`` y ``planner_demo_contracts.py``. Deja (todo
ficticio):

- la actividad «DEMO PLAN Instalación con personal propio» en horas, con el
  rol «DEMO PLAN Instalador propio», y dos obreros con costo hora S/ 9.50;
- una línea de personal propio de 16 h a S/ 12.00 en las cocinas de los
  Dpto 501 y 502 (instalación), agregada al plan vigente como si viniera de
  la generación;
- la cuadrilla asignada (W-06) a la cocina del Dpto 501: dos obreros, dos
  semanas desde el 29/10/2026 y 4 h por semana cada uno (4 turnos, 16 h);
- 6 h registradas por un obrero en la hoja de horas de un módulo de esa
  cocina (ejecutado, real y comprometido de la línea).

Idempotente (si la actividad ya tiene líneas en el plan no hace nada).
Ejecutar con:
  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < planner_demo_control.py
"""
from datetime import date

from odoo import Command

P = 'DEMO PLAN'
env = env(user=env.ref('base.user_admin'))
project = env['project.project'].search([('name', '=', f'{P} MOMEN-35-26')], limit=1)
assert project, 'Ejecute antes planner_demo_data.py'
plan = project._construction_current_plan()
assert plan.state in ('approved', 'in_progress'), 'Ejecute antes planner_demo_baseline.py'
company = plan.company_id
hour = env.ref('uom.product_uom_hour')
Task = env['project.task']

role = env['planning.role'].search([('name', '=', f'{P} Instalador propio')], limit=1) \
    or env['planning.role'].create({'name': f'{P} Instalador propio'})
activity = env['construction.labor.activity'].search([('code', '=', 'DEMO-PPI')], limit=1) \
    or env['construction.labor.activity'].create({
        'code': 'DEMO-PPI', 'name': f'{P} Instalación con personal propio',
        'stage': 'installation', 'uom_id': hour.id, 'default_price': 12.0,
        'role_id': role.id, 'productivity_source': 'estimated'})
employees = env['hr.employee']
for name in ('Obrero propio 1', 'Obrero propio 2'):
    employees |= env['hr.employee'].search([('name', '=', f'{P} {name}')], limit=1) \
        or env['hr.employee'].create({'name': f'{P} {name}', 'hourly_cost': 9.5,
                                      'company_id': company.id})

if not plan.line_ids.filtered(lambda l: l.activity_id == activity):
    spaces = Task.search([('project_id', '=', project.id), ('construction_level', '=', 'space'),
                          ('parent_id.name', 'in', ('Dpto 501', 'Dpto 502'))])
    # La línea se agrega al plan vigente como si viniera de la generación
    # (proceso interno, no una edición del plan aprobado).
    env['construction.resource.plan.line'].with_context(construction_plan_force=True).create([{
        'plan_id': plan.id, 'task_id': space.id, 'resource_type': 'labor',
        'stage': 'installation', 'activity_id': activity.id, 'role_id': role.id,
        'product_uom_id': hour.id, 'qty_planned': 16.0, 'price_unit_planned': 12.0,
        'source': 'generated',
    } for space in spaces])
    space_501 = spaces.filtered(lambda s: s.parent_id.name == 'Dpto 501')
    wizard = env['construction.plan.crew.wizard'].with_context(
        default_plan_id=plan.id, construction_selection_task_ids=space_501.ids,
    ).create({'role_id': role.id, 'resource_ids': [Command.set(employees.resource_id.ids)],
              'date_start': date(2026, 10, 29), 'weeks': 2, 'hours_per_week': 4.0})
    wizard.action_assign()
    module = Task.search([('parent_id', '=', space_501.id)], limit=1)
    if not project.account_id:
        project._create_analytic_account()
    env['account.analytic.line'].create({
        'name': 'Instalación cocina Dpto 501', 'project_id': project.id,
        'task_id': module.id, 'employee_id': employees[0].id, 'unit_amount': 6.0,
        'date': date(2026, 10, 30)})
    line = plan.line_ids.filtered(lambda l: l.activity_id == activity and l.task_id == space_501)
    print('Personal propio Dpto 501: ejecutado %s h, real %s, comprometido %s, estado %s' % (
        line.qty_executed, line.amount_actual, line.amount_committed, line.line_state))

plan.line_ids._refresh_control()
print('Control del plan: planificado %s, comprometido %s, real %s' % (
    plan.amount_total, sum(plan.line_ids.mapped('amount_committed')),
    sum(plan.line_ids.mapped('amount_actual'))))
env.cr.commit()
