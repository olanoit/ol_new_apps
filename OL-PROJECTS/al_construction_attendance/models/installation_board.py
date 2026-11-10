# -*- coding: utf-8 -*-
"""Tablero de control semanal de la etapa de instalación (paquete 1.19,
M119-05).

Una vista por obra, centrada en los pisos: qué pisos tenían que terminar cada
sub etapa en el período, cuáles terminaron, cuáles van atrasados y cómo va la
mano de obra frente al presupuesto del avance (M119-02).

* Columnas: las sub etapas del perfil de la obra. «Instalación» son las que
  llevan presupuesto de mano de obra (catálogo de etapas); «Producción», las
  demás de producción o de campo (no las de control).
* % de un piso en una sub etapa: cantidad validada ÷ cantidad planificada de
  sus líneas de contrata y personal propio (o producción) en el plan vigente.
* Semana programada: la del fin de la sub etapa en los ambientes del piso en
  el Cronograma (``construction.space.stage``); semana en que terminó: la del
  avance que llevó el piso al 100 %.
* Mano de obra: soles reales frente al presupuesto del avance (con «Ve
  montos») o persona-días, de las sub etapas con presupuesto.

Todo se calcula al pedirlo, con los permisos del usuario sobre la obra; los
avances y la marcación se leen con sudo solo para sumar.
"""
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError

STATUS_DONE, STATUS_LATE, STATUS_CURRENT, STATUS_PENDING = 'done', 'late', 'current', 'pending'
# Corrección 3 del 1.19: un piso sin orden de fabricación en una sub etapa de
# producción no cuenta como atrasado.
STATUS_NO_ORDER = 'no_order'
COMPLETE = 0.9999


def _monday(day):
    return day - timedelta(days=day.weekday())


class ConstructionInstallationBoard(models.AbstractModel):
    _name = 'construction.installation.board'
    _description = 'Control semanal de instalación'

    # ------------------------------------------------------------------
    # Acceso
    # ------------------------------------------------------------------
    @api.model
    def _check_board_access(self, project):
        user = self.env.user
        allowed = user.has_group('al_construction_planner.group_planner_user') \
            or user.has_group('al_construction_planner.group_planner_project_head')
        if not allowed or not user.has_group(
                'al_construction_planner.group_planner_feature_control'):
            raise AccessError(self.env._('No tiene acceso al control semanal de instalación.'))
        project.check_access('read')

    @api.model
    def get_projects(self):
        """Obras con plan vigente a las que el usuario tiene acceso."""
        projects = self.env['project.project'].search(
            [('is_construction_site', '=', True)], order='name')
        return [{'id': project.id, 'name': project.display_name} for project in projects]

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    @api.model
    def get_data(self, project_id, week_from=None, week_to=None, production=False,
                 installation=True):
        """Tablero de ``project_id`` para las semanas ``week_from`` a
        ``week_to`` (números de semana de la obra; por defecto, la última
        cerrada)."""
        project = self.env['project.project'].browse(project_id).exists()
        if not project:
            return {'empty': True}
        self._check_board_access(project)
        show_amounts = self.env.user.has_group('al_construction_planner.group_planner_amounts')
        today = fields.Date.context_today(self)
        stages = self.env['construction.stage']._offered_stages(project).filtered(
            lambda s: s.kind != 'control')
        install_stages = stages.filtered('labor_budget')
        production_stages = stages - install_stages
        if not installation and not production:
            installation = True
        shown = (production_stages if production else self.env['construction.stage']) | (
            install_stages if installation else self.env['construction.stage'])
        shown = stages.filtered(lambda s: s in shown)
        # sudo: el tablero suma avances, líneas y fechas del Cronograma de una
        # obra que el usuario puede leer (se comprobó arriba).
        project_sudo = project.sudo()
        plan = project_sudo.construction_current_plan_id
        space_stages = self.env['construction.space.stage'].sudo().search(
            [('project_id', '=', project.id), ('stage', 'in', shown.mapped('code'))])
        first_dates = space_stages.mapped('date_start')
        if not first_dates or not plan:
            return {'empty': True, 'project': project.display_name}
        origin = _monday(min(first_dates))
        last_date = max(space_stages.mapped('date_end') + [today])

        def week_of(day):
            return (_monday(day) - origin).days // 7 + 1 if day else 0

        def monday_of(number):
            return origin + timedelta(days=7 * (number - 1))

        current_week = week_of(today)
        last_week = week_of(last_date)
        closed = max(current_week - 1, 1)
        week_to = int(week_to or closed)
        week_from = int(week_from or week_to)
        if week_from > week_to:
            week_to = week_from
        period_end = monday_of(week_to) + timedelta(days=6)

        floors = project_sudo.task_ids.filtered(lambda t: t.construction_level == 'floor')
        floors = floors.sorted(lambda t: (t.sequence, t.id), reverse=True)
        lines = plan.line_ids.filtered(
            lambda l: l.stage in shown.mapped('code') and l.floor_task_id in floors
            and l.resource_type in ('contract', 'labor', 'production'))
        progress = self.env['construction.task.progress'].sudo().search([
            ('plan_line_id', 'in', lines.ids), ('state', '=', 'validated'),
            ('is_rework', '=', False), ('date', '<=', period_end)], order='date, id')
        done_by_line = defaultdict(list)
        for record in progress:
            done_by_line[record.plan_line_id.id].append((record.date, record.qty_weighted))
        lines_by_cell = defaultdict(lambda: self.env['construction.resource.plan.line'])
        for line in lines:
            lines_by_cell[(line.floor_task_id.id, line.stage)] |= line
        sched_by_cell = defaultdict(list)
        for record in space_stages:
            sched_by_cell[(record.floor_task_id.id, record.stage)].append(record.date_end)
        budgets = {budget.stage: budget for budget in project_sudo.construction_labor_budget_ids}
        controls = self.env['construction.labor.weekly.control'].sudo().search(
            [('project_id', '=', project.id)])

        # Corrección 3 del 1.19: la producción avanza con las órdenes de
        # fabricación (si el puente de Fabricación está instalado).
        production = self._production_progress(project, shown & production_stages,
                                               period_end)
        cells = {}
        for floor in floors:
            for stage in shown:
                key = (floor.id, stage.code)
                source = production.get(key, {}) if production is not None \
                    and stage in production_stages else None
                cells[key] = self._cell(
                    floor, stage, lines_by_cell[key], done_by_line, sched_by_cell.get(key),
                    week_of, monday_of, today, week_to, current_week, budgets.get(stage.code),
                    show_amounts, source)
        self._budget_status(cells, controls, week_from, week_to, monday_of, show_amounts,
                            budgets)
        # Indicadores.
        counted = [c for c in cells.values() if c['status'] != STATUS_NO_ORDER]
        in_period = [c for c in counted if c['sched_week']
                     and week_from <= c['sched_week'] <= week_to]
        to_date = [c for c in counted if c['sched_week'] and c['sched_week'] <= week_to]
        late = [c for c in cells.values() if c['status'] == STATUS_LATE]
        install_codes = set(install_stages.mapped('code'))
        labor = self._labor_indicator(controls, week_from, week_to, monday_of, show_amounts,
                                      install_codes)
        per_stage = []
        for stage in shown:
            stage_cells = [c for c in to_date if c['stage'] == stage.code]
            per_stage.append({'stage': stage._label(),
                              'done': sum(1 for c in stage_cells if c['status'] == STATUS_DONE),
                              'total': len(stage_cells)})
        curves = []
        for stage in shown:
            stage_cells = [c for c in counted if c['stage'] == stage.code]
            points = []
            for number in range(1, last_week + 1):
                points.append({
                    'week': number,
                    'planned': sum(1 for c in stage_cells
                                   if c['sched_week'] and c['sched_week'] <= number),
                    'real': sum(1 for c in stage_cells
                                if c['finish_week'] and c['finish_week'] <= number
                                and number <= week_to),
                })
            curves.append({'stage': stage._label(), 'points': points})
        weeks = [{'number': number, 'monday': monday_of(number).strftime('%d/%m'),
                  'saturday': (monday_of(number) + timedelta(days=5)).strftime('%d/%m'),
                  'state': 'closed' if number < current_week else (
                      'current' if number == current_week else 'future')}
                 for number in range(1, max(last_week, current_week) + 1)]
        return {
            'empty': False,
            'project': project.display_name, 'project_id': project.id,
            'show_amounts': show_amounts,
            'title': (self.env._('Control semanal de producción e instalación') if production
                      else self.env._('Control semanal de instalación')),
            'production': bool(production), 'installation': bool(installation),
            'has_production': bool(production_stages),
            'week_from': week_from, 'week_to': week_to, 'current_week': current_week,
            'closed_week': closed, 'weeks': weeks,
            'period_label': self._period_label(week_from, week_to, monday_of),
            'stages': [{'code': stage.code, 'label': stage._label(),
                        'installation': stage in install_stages} for stage in shown],
            'floors': [{'id': floor.id, 'name': floor.name,
                        'cells': [cells[(floor.id, stage.code)] for stage in shown]}
                       for floor in floors],
            'indicators': {
                'period': {'done': sum(1 for c in in_period if c['status'] == STATUS_DONE),
                           'total': len(in_period)},
                'late': {'count': len(late), 'items': [
                    {'floor': c['floor'], 'stage': c['stage_label'], 'pct': c['pct']}
                    for c in late]},
                'finished': {'done': sum(1 for c in to_date if c['status'] == STATUS_DONE),
                             'total': len(to_date), 'per_stage': per_stage},
                'labor': labor,
            },
            'curves': curves,
        }

    def _period_label(self, week_from, week_to, monday_of):
        start = monday_of(week_from)
        end = monday_of(week_to) + timedelta(days=5)
        weeks = (self.env._('Semana %s', week_from) if week_from == week_to
                 else self.env._('Semanas %(a)s a %(b)s', a=week_from, b=week_to))
        return '%s · %s al %s' % (weeks, start.strftime('%d/%m'), end.strftime('%d/%m'))

    @api.model
    def _production_progress(self, project, stages, period_end):
        """Avance de las sub etapas de producción por piso desde las órdenes de
        fabricación (corrección 3 del 1.19): ``{(piso, sub etapa): {'planned',
        'done', 'spaces': {ambiente: (cantidad, hecho)}, 'finish',
        'productions', 'plants'}}``. Lo producido se reparte entre los
        ambientes de la orden en su orden (por piso). ``None`` sin el puente de
        Fabricación."""
        if not stages or 'mrp.production' not in self.env \
                or 'construction_space_task_ids' not in self.env['mrp.production']._fields:
            return None
        codes = set(stages.mapped('code'))
        # sudo: el tablero suma órdenes de una obra que el usuario puede leer.
        productions_sudo = self.env['mrp.production'].sudo().search([
            ('construction_plan_id.project_id', '=', project.id), ('state', '!=', 'cancel')])
        result = {}
        for production in productions_sudo:
            order_codes = set(production._construction_order_stages()) & codes
            # El orden de la orden: el de «Producir» (piso y ambiente).
            spaces = production.construction_space_task_ids.sorted(
                lambda t: (t.construction_floor_task_id.id, t.id))
            if not order_codes or not spaces or not production.product_qty:
                continue
            moves = production.move_finished_ids.filtered(
                lambda m: m.state == 'done' and m.product_id == production.product_id
                and m.date and m.date.date() <= period_end)
            produced = sum(moves.mapped('quantity'))
            last = max(moves.mapped('date')).date() if moves else None
            per_space = production.product_qty / len(spaces)
            remaining = produced
            plant = production.picking_type_id.warehouse_id.name or production.company_id.name
            for space in spaces:
                take = min(per_space, max(remaining, 0.0))
                remaining -= take
                for code in order_codes:
                    entry = result.setdefault((space.construction_floor_task_id.id, code), {
                        'planned': 0.0, 'done': 0.0, 'spaces': {}, 'finish': None,
                        'productions': [], 'plants': []})
                    entry['planned'] += per_space
                    entry['done'] += take
                    entry['spaces'][space] = (per_space, take)
                    if production.id not in [p['id'] for p in entry['productions']]:
                        entry['productions'].append({'id': production.id,
                                                     'name': production.name})
                    if plant and plant not in entry['plants']:
                        entry['plants'].append(plant)
                    if last and take >= per_space * COMPLETE:
                        entry['finish'] = max(entry['finish'] or last, last)
        return result

    def _cell(self, floor, stage, lines, done_by_line, sched_dates, week_of, monday_of, today,
              week_to, current_week, budget, show_amounts, production=None):
        if production is not None:
            return self._production_cell(floor, stage, production, sched_dates, week_of,
                                         monday_of, week_to, current_week)
        planned = sum(lines.mapped('qty_planned'))
        events = sorted((day, qty) for line in lines for day, qty in done_by_line[line.id])
        done, finish = 0.0, None
        for day, qty in events:
            done += qty
            if planned and finish is None and done >= planned * COMPLETE:
                finish = day
        pct = min(done / planned, 1.0) if planned else 0.0
        sched = max(sched_dates) if sched_dates else None
        sched_week = week_of(sched) if sched else 0
        finish_week = week_of(finish) if finish else 0
        if planned and pct >= COMPLETE:
            status = STATUS_DONE
        elif sched_week and sched_week < week_to:
            status = STATUS_LATE
        elif sched_week and sched_week == week_to:
            status = STATUS_CURRENT if week_to >= current_week else STATUS_LATE
        else:
            status = STATUS_PENDING
        partners = lines.filtered(lambda l: l.resource_type == 'contract').partner_id
        executor = ', '.join(partners.mapped('name')) if partners else (
            self.env._('Cuadrilla propia') if lines.filtered(
                lambda l: l.resource_type == 'labor') else self.env._('Planta'))
        # Ambientes del piso (cocinas): hecho, pendiente o falta.
        spaces = []
        by_space = defaultdict(lambda: [0.0, 0.0])
        for line in lines:
            space = line.space_task_id
            if not space:
                continue
            by_space[space][0] += line.qty_planned
            by_space[space][1] += sum(qty for _day, qty in done_by_line[line.id])
        for space, (space_planned, space_done) in sorted(
                by_space.items(), key=lambda item: item[0].display_name or ''):
            state = 'done' if space_planned and space_done >= space_planned * COMPLETE else (
                'pending' if not space_done else 'partial')
            spaces.append({
                'id': space.id, 'apartment': space.construction_apartment_task_id.name or '',
                'name': space.name, 'typology': space.construction_typology_id.code or '',
                'qty': round(space_planned, 2), 'state': state})
        return {
            'floor': floor.name, 'floor_id': floor.id, 'stage': stage.code,
            'stage_label': stage._label(), 'pct': round(pct * 100),
            'planned': round(planned, 2), 'done': round(done, 2),
            'sched_week': sched_week,
            'sched_dates': ('%s al %s' % (monday_of(sched_week).strftime('%d/%m'),
                                          (monday_of(sched_week) + timedelta(days=5))
                                          .strftime('%d/%m')) if sched_week else ''),
            'finish_week': finish_week,
            'delay_weeks': max(finish_week - sched_week, 0) if finish_week and sched_week
            else (max(week_to - sched_week, 0) if status == STATUS_LATE else 0),
            'status': status, 'executor': executor,
            'spaces': spaces, 'spaces_done': sum(1 for s in spaces if s['state'] == 'done'),
            'line_ids': lines.ids, 'has_budget': bool(budget),
            'budget': {'state': 'none'},
        }

    def _production_cell(self, floor, stage, source, sched_dates, week_of, monday_of, week_to,
                         current_week):
        """Celda de producción: lo producido de las órdenes del piso; sin
        orden, «Sin orden» (no cuenta como atrasada)."""
        planned, done = source.get('planned', 0.0), source.get('done', 0.0)
        pct = min(done / planned, 1.0) if planned else 0.0
        sched = max(sched_dates) if sched_dates else None
        sched_week = week_of(sched) if sched else 0
        complete = bool(planned) and done >= planned * COMPLETE
        finish = source.get('finish') if complete else None
        finish_week = week_of(finish) if finish else 0
        if not source:
            status = STATUS_NO_ORDER
        elif complete:
            status = STATUS_DONE
        elif sched_week and sched_week < week_to:
            status = STATUS_LATE
        elif sched_week and sched_week == week_to:
            status = STATUS_CURRENT if week_to >= current_week else STATUS_LATE
        else:
            status = STATUS_PENDING
        spaces = []
        for space, (space_planned, space_done) in sorted(
                (source.get('spaces') or {}).items(),
                key=lambda item: item[0].construction_apartment_task_id.name or ''):
            state = 'done' if space_done >= space_planned * COMPLETE else (
                'partial' if space_done else 'pending')
            spaces.append({
                'id': space.id, 'apartment': space.construction_apartment_task_id.name or '',
                'name': space.name, 'typology': space.construction_typology_id.code or '',
                'qty': round(space_planned, 2), 'state': state})
        return {
            'floor': floor.name, 'floor_id': floor.id, 'stage': stage.code,
            'stage_label': stage._label(), 'pct': round(pct * 100),
            'planned': round(planned, 2), 'done': round(done, 2), 'sched_week': sched_week,
            'sched_dates': ('%s al %s' % (monday_of(sched_week).strftime('%d/%m'),
                                          (monday_of(sched_week) + timedelta(days=5))
                                          .strftime('%d/%m')) if sched_week else ''),
            'finish_week': finish_week,
            'delay_weeks': max(finish_week - sched_week, 0) if finish_week and sched_week
            else (max(week_to - sched_week, 0) if status == STATUS_LATE else 0),
            'status': status,
            'executor': ', '.join(source.get('plants') or []) or self.env._('Planta'),
            'productions': source.get('productions') or [],
            'spaces': spaces, 'spaces_done': sum(1 for s in spaces if s['state'] == 'done'),
            'line_ids': [], 'has_budget': False, 'budget': {'state': 'none'},
        }

    def _budget_status(self, cells, controls, week_from, week_to, monday_of, show_amounts,
                       budgets):
        """Semáforo de presupuesto por celda: el presupuesto del avance del
        piso frente a lo real repartido por su avance en la semana."""
        start, end = monday_of(week_from), monday_of(week_to)
        rows = controls.filtered(lambda r: start <= r.week_start <= end)
        for (floor_id, stage_code), cell in cells.items():
            budget = budgets.get(stage_code)
            if not budget or not cell['planned']:
                continue
            stage_rows = rows.filtered(lambda r, code=stage_code: r.budget_id.stage == code)
            stage_progress = sum(stage_rows.mapped('progress'))
            share = (cell['done'] / stage_progress) if stage_progress else 0.0
            share = min(share, 1.0)
            real_pd = sum(stage_rows.mapped('person_days_real')) * share
            budget_pd = sum(stage_rows.mapped('progress_person_days')) * share
            real_amount = sum(stage_rows.mapped('amount_real')) * share
            budget_amount = sum(stage_rows.mapped('progress_amount')) * share
            band = (budget.band or 0.0) / 100.0
            by_amount = budget.mode == 'own' and show_amounts
            real, base = (real_amount, budget_amount) if by_amount else (real_pd, budget_pd)
            deviation = (real / base - 1) if base else 0.0
            state = 'none' if not base else (
                'inside' if deviation <= 0 else ('band' if deviation <= band else 'outside'))
            cell['budget'] = {
                'state': state, 'deviation': round(deviation * 100, 1),
                'unit': 'amount' if by_amount else 'person_days',
                'real': round(real, 2), 'base': round(base, 2),
                'budget_total': round(budget.amount if show_amounts else
                                      budget.person_days_budget, 2),
            }

    def _labor_indicator(self, controls, week_from, week_to, monday_of, show_amounts,
                         install_codes):
        start, end = monday_of(week_from), monday_of(week_to)
        rows = controls.filtered(lambda r: start <= r.week_start <= end
                                 and r.budget_id.stage in install_codes)
        if not rows:
            return {'empty': True}
        if show_amounts:
            real, base = sum(rows.mapped('amount_real')), sum(rows.mapped('progress_amount'))
        else:
            real = sum(rows.mapped('person_days_real'))
            base = sum(rows.mapped('progress_person_days'))
        return {
            'empty': False, 'unit': 'amount' if show_amounts else 'person_days',
            'real': round(real, 2), 'base': round(base, 2),
            'deviation': round((real / base - 1) * 100, 1) if base else 0.0,
        }


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def action_open_installation_board(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client', 'tag': 'al_construction_installation_board',
            'name': self.env._('Control semanal de instalación'),
            'params': {'project_id': self.id},
        }
