# -*- coding: utf-8 -*-
"""Obra de aceptación del tablero de control semanal (correcciones del
paquete 1.19, «Datos de aceptación»): «ZZ TABLERO PRUEBA», con los datos del
prototipo aprobado.

* 20 pisos con 8 departamentos (n01 a n08), tipologías C01 a C08 y sus ML.
* Programa de 2 pisos por semana desde la semana 3 (2.1); 2.2 una semana
  después, 2.3 dos; 1.1 dos semanas antes y 1.2 una; los pisos 01 y 20 en la
  semana 12. La semana 1 es la del 24-nov-2025.
* Avances, atrasos y costos del prototipo (``LATE`` y ``FACTOR``), validados
  hasta la semana 8.
* Contrata A en los pisos pares y B en los impares (2.1), C en 2.2 y
  cuadrilla propia en 2.3; 1.1 y 1.2 con órdenes de fabricación.
* Presupuesto de mano de obra de 2.1, 2.2 y 2.3, marcaciones y jornales; la
  semana 8 se calibra para el criterio de mano de obra (−0.2 %) y el del piso
  13 · 2.1 (persona-días +2.0 %).

Lo usa la prueba ``TestBoardAcceptanceData``. Para cargarlo en una base de
desarrollo (con su permiso)::

    from odoo.addons.al_construction_attendance.tests.board_acceptance_data import load
    load(env)
    env.cr.commit()
"""
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from odoo.exceptions import UserError

NAME = 'ZZ TABLERO PRUEBA'
ORIGIN = date(2025, 11, 24)
LAST = 8
FLOORS = range(1, 21)
ML = [4.48, 5.07, 5.54, 5.48, 5.15, 5.69, 5.79, 4.03]
MODULES = [9, 9, 11, 10, 8, 10, 10, 9]
OFFSET = {'production': -2, 'assembly': -1, 'installation': 0, 'finishing': 1, 'cleaning': 2}
# % del piso en la sub etapa al cierre de una semana (sin entrada: termina en
# su semana programada).
LATE = {
    'production': {15: {7: 80}},
    'assembly': {13: {7: 50}, 15: {8: 30}},
    'installation': {6: {5: 60}, 7: {5: 55}, 13: {8: 70}},
    'finishing': {7: {6: 40}, 11: {8: 60}},
    'cleaning': {7: {7: 50}, 9: {8: 80}},
}
# Costo real ÷ presupuesto del avance de cada piso.
FACTOR = {
    'production': {15: 1.04, 9: 1.12},
    'assembly': {13: 1.25, 7: 1.15},
    'installation': {2: 2.0, 4: 1.9, 6: 1.5, 13: 1.02},
    'cleaning': {6: 1.8, 7: 1.6},
}
PRODUCTIVITY = {'installation': 6.98, 'finishing': 2.72, 'cleaning': 13.97}
RATE = {'installation': 18.0, 'finishing': 7.13}
WAGE = 120.0
MATERIAL = {'production': 191.0, 'assembly': 6.2}   # por ML y por módulo
LABOR_TARGET = -0.002                                 # mano de obra, semana 8


def base_week(floor):
    return 12 if floor in (1, 20) else 3 + (floor - 2) // 2


def planned_week(floor, stage):
    return base_week(floor) + OFFSET[stage]


def finish_week(floor, stage):
    late = LATE[stage].get(floor)
    if not late:
        week = planned_week(floor, stage)
        return week if week <= LAST else None
    week = max(late) + 1
    return week if week <= LAST else None


def monday(week):
    return ORIGIN + timedelta(days=7 * (week - 1))


def steps(floor, stage):
    """[(semana, cocinas hechas acumuladas)] hasta la semana 8."""
    late = LATE[stage].get(floor, {})
    result = [(week, round(pct * 8 / 100)) for week, pct in sorted(late.items())
              if week <= LAST]
    done = finish_week(floor, stage)
    if done:
        result.append((done, 8))
    return result


def final_pct(floor, stage):
    if finish_week(floor, stage):
        return 100
    late = LATE[stage].get(floor, {})
    weeks = [week for week in late if week <= LAST]
    return late[max(weeks)] if weeks else 0


def _noon(day):
    """Mediodía UTC: el mismo día en Lima."""
    return datetime.combine(day, time(17, 0))


def load(env):
    """Carga la obra; si ya existe, no hace nada y la devuelve."""
    Project = env['project.project']
    project = Project.search([('name', '=', NAME)], limit=1)
    if project:
        return project
    reference = Project.search([('name', 'ilike', 'ZZMOMENP-26')], limit=1)
    company = reference.company_id or env.company
    project = Project.create({
        'name': NAME, 'is_construction_site': True, 'company_id': company.id,
        'construction_profile_id': reference.construction_profile_id.id or False,
        'date_start': ORIGIN,
    })
    Partner = env['res.partner']
    partner_a = Partner.create({'name': 'Contrata A', 'is_company': True})
    partner_b = Partner.create({'name': 'Contrata B', 'is_company': True})
    partner_c = Partner.create({'name': 'Contrata C', 'is_company': True})
    uom_ml = env['uom.uom'].search([('name', '=', 'ML')], limit=1) or \
        env['uom.uom'].search([('name', '=ilike', 'ml')], limit=1) or env.ref('uom.product_uom_meter')
    uom_unit = env.ref('uom.product_uom_unit')
    Activity = env['construction.labor.activity']

    def activity(code, name, stage, uom):
        return Activity.create({'code': code, 'name': name, 'stage': stage, 'uom_id': uom.id,
                                'company_id': company.id})

    act = {
        'installation': activity('ZZTB-INS', 'Instalación de cocinas (tablero)',
                                 'installation', uom_ml),
        'finishing': activity('ZZTB-ACA', 'Acabado de cocinas (tablero)', 'finishing', uom_unit),
        'cleaning': activity('ZZTB-LIM', 'Limpieza de cocinas (tablero)', 'cleaning', uom_ml),
    }
    typologies = [env['construction.typology'].create({
        'code': 'C0%s' % (index + 1), 'name': 'Cocina C0%s (tablero)' % (index + 1),
        'project_id': project.id, 'company_id': company.id}) for index in range(8)]

    Task = env['project.task']

    def task(name, level, parent=None, **values):
        return Task.create(dict({'name': name, 'project_id': project.id,
                                 'construction_level': level,
                                 'parent_id': parent.id if parent else False}, **values))

    spaces = {}
    for floor in FLOORS:
        floor_task = task('Piso %02d' % floor, 'floor')
        for index in range(8):
            apartment = task(str(floor * 100 + index + 1), 'apartment', floor_task)
            spaces[(floor, index)] = task('Cocina', 'space', apartment,
                                          construction_typology_id=typologies[index].id)

    # Productos de las órdenes de fabricación y sus materiales.
    Product = env['product.product']
    board_material = Product.create({'name': 'Tablero (ZZ tablero)', 'type': 'consu',
                                     'standard_price': 1.0})
    hardware = Product.create({'name': 'Herrajes (ZZ tablero)', 'type': 'consu',
                               'standard_price': 1.0})
    made = {}
    for stage, component in (('production', board_material), ('assembly', hardware)):
        product = Product.create({'name': 'Módulos %s (ZZ tablero)' % stage, 'type': 'consu'})
        bom = env['mrp.bom'].create({
            'product_tmpl_id': product.product_tmpl_id.id, 'product_qty': 1.0,
            'bom_line_ids': [(0, 0, {'product_id': component.id, 'product_qty': 1.0,
                                     'construction_consumption_stage': stage})]})
        made[stage] = (product, bom, component)

    # Plan.
    plan = env['construction.resource.plan'].create({'project_id': project.id})
    Line = env['construction.resource.plan.line'].with_context(construction_plan_force=True)
    lines = defaultdict(list)
    line_values = []
    for (floor, index), space in spaces.items():
        ml = ML[index]
        installer = partner_a if floor % 2 == 0 else partner_b
        line_values += [
            {'plan_id': plan.id, 'task_id': space.id, 'resource_type': 'contract',
             'activity_id': act['installation'].id, 'stage': 'installation',
             'partner_id': installer.id, 'qty_planned': ml,
             'price_unit_planned': RATE['installation'], 'product_uom_id': uom_ml.id},
            {'plan_id': plan.id, 'task_id': space.id, 'resource_type': 'contract',
             'activity_id': act['finishing'].id, 'stage': 'finishing',
             'partner_id': partner_c.id, 'qty_planned': 1.0,
             'price_unit_planned': RATE['finishing'], 'product_uom_id': uom_unit.id},
            {'plan_id': plan.id, 'task_id': space.id, 'resource_type': 'labor',
             'activity_id': act['cleaning'].id, 'stage': 'cleaning', 'qty_planned': ml,
             'price_unit_planned': WAGE / PRODUCTIVITY['cleaning'],
             'product_uom_id': uom_ml.id},
            {'plan_id': plan.id, 'task_id': space.id, 'resource_type': 'material',
             'product_id': board_material.id, 'stage': 'production',
             'qty_planned': ml * MATERIAL['production'], 'price_unit_planned': 1.0,
             'product_uom_id': board_material.uom_id.id},
            {'plan_id': plan.id, 'task_id': space.id, 'resource_type': 'material',
             'product_id': hardware.id, 'stage': 'assembly',
             'qty_planned': MODULES[index] * MATERIAL['assembly'], 'price_unit_planned': 1.0,
             'product_uom_id': hardware.uom_id.id},
        ]
    for line in Line.create(line_values):
        floor = int(line.task_id.parent_id.parent_id.name[-2:])
        index = int(line.task_id.parent_id.name) % 100 - 1
        lines[(floor, line.stage)].append((index, line))

    # Cronograma: el fin de cada sub etapa en su semana programada.
    stage_values = []
    for (floor, index), space in spaces.items():
        for stage in OFFSET:
            week = planned_week(floor, stage)
            stage_values.append({'space_task_id': space.id, 'stage': stage,
                                 'date_start': monday(week),
                                 'date_end': monday(week) + timedelta(days=4)})
    env['construction.space.stage'].create(stage_values)

    plan.action_request_approval()
    if plan.state != 'approved':
        # Datos de prueba: se aprueba sin las revisiones de la compañía.
        plan.sudo().review_ids.write({'status': 'approved', 'done_by': env.user.id})
        plan.invalidate_recordset(['review_ids', 'validation_status', 'need_validation'])
        if plan.state != 'approved':
            # Con la app Aprobaciones, la solicitud abierta se cancela y el plan
            # se aprueba como si la hubieran concedido.
            if hasattr(plan, '_construction_cancel_open_approvals'):
                plan.sudo()._construction_cancel_open_approvals()
            plan.sudo().with_context(construction_approval_granted=True)._write_approved()

    # Avances validados de las contratas y la cuadrilla propia.
    photo = env['ir.attachment'].create({'name': 'avance.png', 'datas': b'eA=='})
    Progress = env['construction.task.progress']
    for floor in FLOORS:
        for stage in ('installation', 'finishing', 'cleaning'):
            ordered = sorted(lines[(floor, stage)], key=lambda item: item[0])
            previous = 0
            for week, count in steps(floor, stage):
                for _index, line in ordered[previous:count]:
                    record = Progress.create({
                        'task_id': line.task_id.id, 'activity_id': line.activity_id.id,
                        'plan_line_id': line.id, 'date': monday(week) + timedelta(days=2),
                        'qty': line.qty_planned, 'attachment_ids': [(6, 0, photo.ids)]})
                    record.sudo().write({'state': 'validated'})
                previous = max(previous, count)

    # Órdenes de fabricación de 1.1 y 1.2, una por piso, con lo producido y lo
    # consumido al cierre de la semana 8.
    for floor in FLOORS:
        floor_spaces = [spaces[(floor, index)] for index in range(8)]
        for stage, (product, bom, component) in made.items():
            quantity = float(sum(MODULES))
            production = env['mrp.production'].create({
                'product_id': product.id, 'product_qty': quantity,
                'product_uom_id': product.uom_id.id, 'bom_id': bom.id,
                'construction_plan_id': plan.id,
                'construction_space_task_ids': [(6, 0, [s.id for s in floor_spaces])]})
            pct = final_pct(floor, stage)
            if not pct:
                continue
            week = finish_week(floor, stage) or max(
                w for w in LATE[stage][floor] if w <= LAST)
            when = _noon(monday(week) + timedelta(days=3))
            finished = production.move_finished_ids.filtered(
                lambda m: m.product_id == product)[:1]
            finished.sudo().write({'quantity': quantity * pct / 100.0, 'state': 'done',
                                   'date': when})
            if stage == 'production':
                planned = sum(ML) * MATERIAL['production']
            else:
                planned = sum(MODULES) * MATERIAL['assembly']
            consumed = planned * pct / 100.0 * FACTOR[stage].get(floor, 1.0)
            raw = production.move_raw_ids.filtered(lambda m: m.product_id == component)[:1]
            raw.sudo().write({'quantity': consumed, 'state': 'done', 'date': when})

    # Presupuesto de mano de obra de 2.1, 2.2 y 2.3.
    stages = {stage.code: stage for stage in env['construction.stage'].search(
        [('code', 'in', list(PRODUCTIVITY))])}
    budgets = {}
    for stage, productivity in PRODUCTIVITY.items():
        weeks = [planned_week(floor, stage) for floor in FLOORS]
        quantity = sum(ML) * len(FLOORS) if stage != 'finishing' else 8.0 * len(FLOORS)
        budgets[stage] = env['construction.labor.budget'].create({
            'project_id': project.id, 'stage_id': stages[stage].id,
            'mode': 'own' if stage == 'cleaning' else 'contract',
            'daily_wage': WAGE if stage == 'cleaning' else 0.0,
            'date_start': monday(min(weeks)),
            'date_end': monday(max(weeks)) + timedelta(days=4),
            'line_ids': [(0, 0, {'activity_id': act[stage].id, 'quantity': quantity,
                                 'productivity': productivity,
                                 'rate': RATE.get(stage, 0.0)})],
        })

    # Marcaciones de las contratas y jornales de la cuadrilla propia: lo que
    # justifica su avance, por el factor de exceso de cada piso.
    Control = env['construction.labor.weekly.control']
    Control._construction_refresh(project)
    site = project.sudo().construction_hr_site_ids[:1] or \
        env['l10n_pe.hr.construction.site'].sudo().create({
            'name': project.name, 'company_id': company.id, 'project_id': project.id,
            'site_kind': 'site', 'radius_m': 200, 'date_start': ORIGIN})
    full_day = company._construction_full_day_hours() or 8.0
    weights = _week_weights(lines, partner_a, partner_b, partner_c)
    workers = {}

    def mark(partner, week, person_days):
        hours = person_days * full_day
        per_day = hours / 5.0
        count = max(1, math.ceil(per_day / 8.0))
        while len(workers.setdefault(partner.id, [])) < count:
            number = len(workers[partner.id]) + 1
            workers[partner.id].append(env['construction.contractor.worker'].sudo().create({
                'name': '%s · persona %s' % (partner.name, number),
                'document_number': 'ZZTB%s%02d' % (partner.id, number),
                'partner_id': partner.id, 'company_id': company.id}))
        values = []
        for offset in range(5):
            day = monday(week) + timedelta(days=offset)
            for worker in workers[partner.id][:count]:
                start = datetime.combine(day, time(13, 0))
                values.append({'worker_id': worker.id, 'site_id': site.id, 'check_in': start,
                               'check_out': start + timedelta(hours=per_day / count)})
        env['construction.contractor.attendance'].sudo().create(values)

    rows = Control.search([('project_id', '=', project.id)])
    for row in rows.filtered(lambda r: r.mode == 'contract' and r.progress_person_days):
        week = (row.week_start - ORIGIN).days // 7 + 1
        weight = weights.get((row.partner_id.id, row.budget_id.stage, week), 1.0)
        mark(row.partner_id, week, row.progress_person_days * weight)
    own_lines = {floor: lines[(floor, 'cleaning')][0][1] for floor in FLOORS}
    Day = env['construction.crew.day'].sudo()

    def crew(week, days):
        floor = next((f for f in FLOORS if any(w == week for w, _c in steps(f, 'cleaning'))),
                     FLOORS[0])
        Day.create({'kind': 'executed', 'project_id': project.id, 'company_id': company.id,
                    'plan_line_id': own_lines[floor].id, 'date': monday(week) + timedelta(days=2),
                    'days': days})

    for row in rows.filtered(lambda r: r.mode == 'own' and r.progress_person_days):
        week = (row.week_start - ORIGIN).days // 7 + 1
        if week == LAST:
            continue
        crew(week, row.progress_person_days * weights.get((0, 'cleaning', week), 1.0))
    Control._construction_refresh(project)
    # Semana 8: los jornales que dejan la mano de obra en −0.2 % (soles).
    week_rows = Control.search([('project_id', '=', project.id),
                                ('week_start', '=', monday(LAST))])
    contract = sum(week_rows.filtered(lambda r: r.mode == 'contract').mapped('amount_real'))
    own_advance = sum(week_rows.filtered(lambda r: r.mode == 'own').mapped('progress_amount'))
    own_real = (contract + own_advance) * (1 + LABOR_TARGET) - contract
    if own_real > 0:
        crew(LAST, own_real / WAGE)
    Control._construction_refresh(project)
    return project


def _week_weights(lines, partner_a, partner_b, partner_c):
    """Factor de exceso de cada contrata (o de la cuadrilla, 0) por semana: el
    de los pisos que avanzó esa semana, pesado por lo que avanzó."""
    partner_of = {'installation': lambda floor: (partner_a if floor % 2 == 0 else partner_b).id,
                  'finishing': lambda floor: partner_c.id, 'cleaning': lambda floor: 0}
    sums = defaultdict(lambda: [0.0, 0.0])
    for stage in ('installation', 'finishing', 'cleaning'):
        for floor in FLOORS:
            previous = 0
            ordered = sorted(lines[(floor, stage)], key=lambda item: item[0])
            for week, count in steps(floor, stage):
                qty = sum(line.qty_planned for _i, line in ordered[previous:count])
                previous = max(previous, count)
                key = (partner_of[stage](floor), stage, week)
                sums[key][0] += qty * FACTOR.get(stage, {}).get(floor, 1.0)
                sums[key][1] += qty
    return {key: value[0] / value[1] for key, value in sums.items() if value[1]}


def check_absent(env):
    if env['project.project'].search_count([('name', '=', NAME)]):
        raise UserError('La obra %s ya existe.' % NAME)
