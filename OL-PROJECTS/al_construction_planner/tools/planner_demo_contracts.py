# -*- coding: utf-8 -*-
"""Datos demo de las fases 5 y 6 (contratas y liquidación semanal) sobre el
plan vigente de «DEMO PLAN MOMEN-35-26».

Requiere haber ejecutado antes ``planner_demo_data.py`` y
``planner_demo_baseline.py`` (plan aprobado). Deja:

- «DEMO PLAN Leandro (instalación)» asignado a la instalación del piso 05
  (W-05): 64 líneas, 8 líneas en su OC de servicio por S/ 941.17, confirmada;
- «DEMO PLAN Armado Gonza» asignado al armado del Dpto 501 (OC en borrador);
- el avance del ejemplo de P-08 (Dpto 501 a 504, del 29/10 al 03/11/2026)
  reportado y validado, y la liquidación de Leandro del 29/10 al 04/11 creada
  por la acción programada del jueves 05/11 (bruto S/ 380.88, neto S/ 342.79);
- avances por validar para P-07: uno de Leandro del 05/11 (liquidación del
  12/11) y el armado de dos módulos de Gonza.

Idempotente (si Leandro ya tiene la instalación asignada no hace nada).
Ejecutar con:
  odoo-bin shell -c cfg/my/pe.cfg -d ol_pe_v19 --no-http < planner_demo_contracts.py
"""
import base64
import io
from datetime import date

from PIL import Image, ImageDraw

from odoo import Command

P = 'DEMO PLAN'
# Como admin (jefatura del planificador, compras): el superusuario no revisa.
env = env(user=env.ref('base.user_admin'))
project = env['project.project'].search([('name', '=', f'{P} MOMEN-35-26')], limit=1)
assert project, 'Ejecute antes planner_demo_data.py'
plan = project._construction_current_plan()
assert plan.state in ('approved', 'in_progress'), 'Ejecute antes planner_demo_baseline.py'
leandro = env['res.partner'].search([('name', '=', f'{P} Leandro (instalación)')], limit=1)
gonza = env['res.partner'].search([('name', '=', f'{P} Armado Gonza')], limit=1)
Task = env['project.task']
floor = Task.search([('project_id', '=', project.id), ('construction_level', '=', 'floor')],
                    limit=1)
apartments = {apt.name: apt for apt in Task.search([
    ('parent_id', '=', floor.id), ('construction_level', '=', 'apartment')])}
spaces = {name: Task.search([('parent_id', '=', apt.id)]) for name, apt in apartments.items()}
act = {a.code.split('-', 1)[1]: a for a in env['construction.labor.activity'].search(
    [('code', '=like', 'DEMO-%')])}


def photo(label):
    """Foto de ejemplo: un rectángulo con el nivel y la actividad."""
    image = Image.new('RGB', (480, 320), (226, 232, 240))
    draw = ImageDraw.Draw(image)
    draw.rectangle([30, 120, 450, 260], fill=(148, 163, 184), outline=(51, 65, 85), width=4)
    draw.text((30, 30), label, fill=(15, 23, 42))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue())


def report(apartment, code, qty, day, module=None):
    line = plan.line_ids.filtered(
        lambda l: l.task_id == (module or spaces[apartment]) and l.activity_id == act[code])
    label = f'{apartment} · {act[code].name} · {qty} {act[code].uom_id.name} · {day}'
    progress = env['construction.task.progress'].create({
        'task_id': line.task_id.id, 'activity_id': act[code].id, 'date': day, 'qty': qty,
        'attachment_ids': [Command.create({'name': f'{line.task_id.name}.png',
                                           'datas': photo(label)})],
    })
    progress.attachment_ids.write({'res_model': progress._name, 'res_id': progress.id})
    return progress


installation = plan.line_ids.filtered(
    lambda l: l.stage == 'installation' and l.resource_type == 'contract')
if installation.partner_id == leandro:
    print('Leandro ya tiene la instalación del piso 05: nada que hacer.')
else:
    print('=== Asignar contrata (W-05) ===')
    wizard = env['construction.plan.contract.wizard'].with_context(
        default_plan_id=plan.id, construction_selection_task_ids=floor.ids,
    ).create({'stage': 'installation', 'partner_id': leandro.id,
              'date_start': date(2026, 10, 26), 'date_end': date(2026, 11, 20)})
    print('Leandro:', len(wizard.line_ids), 'actividades,', wizard.plan_line_count, 'líneas,',
          wizard.amount_total, 'retención', wizard.retention_total)
    wizard.action_assign()
    order = env['purchase.order'].search([
        ('construction_is_service_order', '=', True), ('partner_id', '=', leandro.id),
        ('construction_project_id', '=', project.id)], limit=1)
    order.button_confirm()
    print(order.name, order.state, order.amount_untaxed)
    wizard = env['construction.plan.contract.wizard'].with_context(
        default_plan_id=plan.id, construction_selection_task_ids=apartments['Dpto 501'].ids,
    ).create({'stage': 'assembly', 'partner_id': gonza.id, 'date_start': date(2026, 10, 19)})
    print('Gonza:', len(wizard.line_ids), 'actividades,', wizard.amount_total)
    wizard.action_assign()

    print('=== Avance del ejemplo de P-08 (W-07) ===')
    EXAMPLE = [
        ('INB', [('Dpto 501', 2.12), ('Dpto 502', 2.55), ('Dpto 503', 2.80), ('Dpto 504', 2.67)]),
        ('RGB', [('Dpto 501', 1.60), ('Dpto 502', 2.00), ('Dpto 503', 2.20), ('Dpto 504', 0.22)]),
        ('INA', [('Dpto 501', 2.10), ('Dpto 502', 2.45), ('Dpto 503', 2.72), ('Dpto 504', 0.09)]),
        ('RGA', [('Dpto 501', 1.60), ('Dpto 502', 1.70), ('Dpto 503', 1.80), ('Dpto 504', 0.23)]),
        ('TAP', [('Dpto 501', 4), ('Dpto 502', 3), ('Dpto 503', 2)]),
        ('REC', [('Dpto 501', 2), ('Dpto 502', 1)]),
        ('PIN', [('Dpto 501', 2), ('Dpto 502', 2), ('Dpto 503', 2)]),
        ('PUS', [('Dpto 501', 2), ('Dpto 502', 2), ('Dpto 503', 2)]),
    ]
    days = {'Dpto 501': date(2026, 10, 29), 'Dpto 502': date(2026, 10, 30),
            'Dpto 503': date(2026, 11, 2), 'Dpto 504': date(2026, 11, 3)}
    example = env['construction.task.progress']
    for code, rows in EXAMPLE:
        for apartment, qty in rows:
            example |= report(apartment, code, qty, days[apartment])
    example.action_validate()
    print(len(example), 'avances validados')

    print('=== Liquidación del jueves 05/11 (acción programada) ===')
    settlement = env['construction.contract.settlement']._prepare_settlements(
        date(2026, 11, 5), project)
    print(settlement.name, settlement.period_start, settlement.period_end,
          settlement.payment_date, settlement.amount_gross, settlement.amount_net)
    assert round(settlement.amount_gross, 2) == 380.88, settlement.amount_gross
    assert round(settlement.amount_net, 2) == 342.79, settlement.amount_net
    settlement.action_submit()

    print('=== Avances por validar (P-07) ===')
    report('Dpto 504', 'INA', 2.41, date(2026, 11, 5))
    modules = Task.search([('parent_id', '=', spaces['Dpto 501'].id)], limit=2)
    for module in modules:
        line = plan.line_ids.filtered(
            lambda l: l.task_id == module and l.stage == 'assembly'
            and l.resource_type == 'contract')[:1]
        code = line.activity_id.code.split('-', 1)[1]
        report('Dpto 501', code, line.qty_planned, date(2026, 11, 4), module=module)

env.cr.commit()
print('OK')
