# -*- coding: utf-8 -*-
"""Datos demo de la fase 4 (asignaciones y compras) sobre el plan vigente de
«DEMO PLAN MOMEN-35-26».

Requiere haber ejecutado antes ``planner_demo_data.py`` y
``planner_demo_baseline.py``. Deja:

- una compra masiva con analítica de la obra (W-02) de los materiales de
  producción del piso 05;
- un requerimiento de obra (W-03) del piso 05, agrupado por piso, con los
  materiales de instalación y acabado, aprobado;
- un segundo requerimiento del Dpto 501 que excede el plan, justificado y en
  aprobación con la revisión adicional de la jefatura (W-10);
- una orden de fabricación (W-04) del Dpto 502 en borrador.

Idempotente (si el plan ya tiene asignaciones no hace nada). Ejecutar con:
  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < planner_demo_supply.py
"""
P = 'DEMO PLAN'
# Como admin (jefatura del planificador, compras y requerimientos).
env = env(user=env.ref('base.user_admin'))
project = env['project.project'].search([('name', '=', f'{P} MOMEN-35-26')], limit=1)
assert project, 'Ejecute antes planner_demo_data.py'
plan = env['construction.resource.plan'].search([
    ('project_id', '=', project.id), ('state', 'in', ('approved', 'in_progress'))], limit=1)
assert plan, 'Ejecute antes planner_demo_baseline.py (plan aprobado)'
Task = env['project.task']
floor = Task.search([('project_id', '=', project.id), ('construction_level', '=', 'floor')],
                    limit=1)
apartments = Task.search([('parent_id', '=', floor.id), ('construction_level', '=', 'apartment')],
                         order='name')
project.message_subscribe(partner_ids=env.user.partner_id.ids)

if plan.allocation_ids:
    print('El plan ya tiene asignaciones: nada que hacer.')
else:
    ctx = {'default_plan_id': plan.id, 'construction_selection_task_ids': floor.ids}

    def stages(**on):
        return {f'stage_{s}': on.get(s, False)
                for s in ('production', 'assembly', 'installation', 'finishing')}

    print('=== Compra masiva (W-02) ===')
    wizard = env['construction.plan.purchase.wizard'].with_context(**ctx).create(
        dict(stages(production=True), mode='project'))
    request = env['purchase.request'].browse(wizard.action_create()['res_id'])
    print(request.name, len(request.line_ids), 'productos')

    print('=== Requerimiento de obra del piso (W-03) ===')
    wizard = env['construction.plan.request.wizard'].with_context(**ctx).create(
        dict(stages(installation=True, finishing=True), group_by='floor'))
    material_request = env['construction.material.request'].browse(
        wizard.action_create()['res_id'])
    result = material_request.action_request_approval()
    print(material_request.name, material_request.state, material_request.construction_exceed_state)

    print('=== Requerimiento que excede el plan (W-10) ===')
    screw_line = plan.line_ids.filtered(
        lambda l: l.stage == 'installation' and l.product_id
        and l.space_task_id.parent_id == apartments[0])[:1]
    exceeded = env['construction.material.request'].create({
        'project_id': project.id,
        'task_id': apartments[0].id,
        'line_ids': [(0, 0, {'product_id': screw_line.product_id.id, 'product_qty': 20})],
    })
    action = exceeded.action_request_approval()
    if isinstance(action, dict) and action.get('res_model') == 'construction.plan.exceed.wizard':
        exceed = env['construction.plan.exceed.wizard'].browse(action['res_id'])
        exceed.reason = 'Reposición por piezas dañadas en el traslado.'
        exceed.action_confirm()
    print(exceeded.name, exceeded.state, exceeded.construction_exceed_state)

    print('=== Orden de fabricación (W-04) ===')
    wizard = env['construction.plan.production.wizard'].with_context(
        default_plan_id=plan.id, construction_selection_task_ids=apartments[1:2].ids,
    ).create({'group_by': 'selection'})
    production = env['mrp.production'].browse(wizard.action_create()['res_id'])
    print(production.name, production.product_qty, production.state)

env.cr.commit()
print('Plan', plan.display_name, plan.state, len(plan.allocation_ids), 'asignaciones')
