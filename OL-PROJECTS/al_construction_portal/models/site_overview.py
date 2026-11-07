# -*- coding: utf-8 -*-
"""La obra en el portal del residente (paquete 6, entrega 3: CR-58 y CR-54).

* Resumen (U17): avance físico real validado frente al programado a hoy,
  partidas atrasadas, avances por validar, pedidos abiertos y personal de
  hoy; curva de avance (programado y real) y avance por especialidad. El
  avance real y los montos son los del tablero de obra del escritorio
  (``construction_board_*``). Montos solo si la compañía lo permite.
* Semana (U18): partidas que inician y que terminan esta semana; avisa las
  que inician sin contrata ni cuadrilla y las que terminan con poco avance.
* Tareas (U19): partidas en columnas que calcula Odoo con las fechas del plan
  y el avance validado (solo lectura).
* Gantt (U20): barras por partida con el avance como relleno, hitos y línea
  de hoy.

Las fechas de cada partida son las de las etapas de su ambiente
(``construction.space.stage``), las mismas del Cronograma del planificador;
los hitos salen del lector del Gantt de proyectos. El programado a una fecha
reparte el monto de cada línea del plan entre los días hábiles de la obra de
su etapa."""
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models

from odoo.addons.al_construction_planner.models.common import DRIVER_TYPES

from .portal_service import _split_task

COMPLETE = 0.9999
#: Puntos de la curva de avance (semanas), como máximo.
CURVE_POINTS = 40


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_portal_show_amounts = fields.Boolean(
        string='El residente del portal ve montos',
        help='Muestra en la pestaña Obra del portal el planificado, comprometido, real y saldo '
             'del plan, como el tablero de obra del escritorio. Desactivado, solo avances.')
    construction_portal_risk_pct = fields.Integer(
        string='Partida en riesgo al terminar con menos de (%)', default=70,
        help='En la semana de la obra, una partida que termina con menos avance validado que '
             'este porcentaje sale «en riesgo».')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_portal_show_amounts = fields.Boolean(
        related='company_id.construction_portal_show_amounts', readonly=False)
    construction_portal_risk_pct = fields.Integer(
        related='company_id.construction_portal_risk_pct', readonly=False)


class ConstructionPortalService(models.AbstractModel):
    _inherit = 'construction.portal.service'

    @api.model
    def sync(self, project_id):
        data = super().sync(project_id)
        if 'resident' not in data:
            return data
        project, _members = self._project(project_id)
        today = fields.Date.context_today(self)
        data['site'] = self._site_overview(project, today, data)
        return data

    # ------------------------------------------------------------------
    # Datos de las partidas
    # ------------------------------------------------------------------
    def _site_windows(self, plan, lines):
        """{línea: (inicio, fin)}: las fechas de la etapa del ambiente de la
        línea; sin etapa, la fecha de necesidad."""
        # sudo: las etapas de los ambientes de la obra del residente.
        stages = self.env['construction.space.stage'].sudo().search([
            ('space_task_id', 'in', lines.space_task_id.ids)])
        by_key = {(s.space_task_id.id, s.stage): (s.date_start, s.date_end) for s in stages}
        by_space = defaultdict(list)
        for stage in stages:
            by_space[stage.space_task_id.id].append((stage.date_start, stage.date_end))
        windows = {}
        for line in lines:
            window = by_key.get((line.space_task_id.id, line.stage))
            if not window and by_space.get(line.space_task_id.id):
                spans = by_space[line.space_task_id.id]
                window = (min(s for s, _e in spans), max(e for _s, e in spans))
            if not window and line.date_needed:
                window = (line.date_needed, line.date_needed)
            if window:
                windows[line] = window
        return windows

    def _expected_fraction(self, company, window, day, cache):
        """Parte de la línea programada hasta ``day`` por días hábiles de la
        obra (lo mismo que ``_construction_count_site_days``, con al menos un
        día). ``cache`` guarda el acumulado de días hábiles por fecha: cada
        día se consulta una sola vez aunque la obra tenga cientos de líneas."""
        start, end = window
        if day < start:
            return 0.0
        if day >= end:
            return 1.0

        site_days = cache.setdefault('days', {})

        def is_site_day(date):
            if date not in site_days:
                site_days[date] = 1 if company._construction_is_site_day(date) else 0
            return site_days[date]

        def cumulative(date):
            # Días hábiles desde el origen de la tabla hasta ``date`` inclusive;
            # con una fecha anterior al origen, la tabla se rehace desde ella.
            if 'origin' not in cache or date <= cache['origin']:
                old_end = cache['origin'] + timedelta(days=len(cache['counts']) - 1) \
                    if 'origin' in cache else date
                cache['origin'] = date - timedelta(days=1)
                cache['counts'] = [0]
                day = cache['origin']
                while day < old_end:
                    day += timedelta(days=1)
                    cache['counts'].append(cache['counts'][-1] + is_site_day(day))
            origin, counts = cache['origin'], cache['counts']
            index = (date - origin).days
            while len(counts) <= index:
                counts.append(counts[-1] + is_site_day(origin + timedelta(days=len(counts))))
            return counts[index]

        def count(first, last):
            # Primero la fecha menor: si rehace la tabla, el acumulado de la
            # mayor ya sale del mismo origen.
            before = cumulative(first - timedelta(days=1))
            return max(cumulative(last) - before, 1)

        return min(1.0, count(start, day) / (count(start, end) or 1))

    def _site_tasks(self, project, plan, today):
        """Las partidas del plan vigente con sus fechas, avance, contrata o
        cuadrilla y la columna del tablero."""
        Line = self.env['construction.resource.plan.line'].sudo()
        lines = Line.search([('plan_id', '=', plan.id), ('resource_type', 'in', DRIVER_TYPES),
                             ('task_id', '!=', False), ('line_state', '!=', 'cancel')])
        windows = self._site_windows(plan, lines)
        amounts = plan.sudo()._progress_amounts([('plan_id', '=', plan.id)], 'task_id')
        company = project.company_id or self.env.company
        week_start, week_end = project._construction_period(today)
        slots = defaultdict(list)
        if 'planning.slot' in self.env and 'construction_task_id' in self.env['planning.slot']._fields:
            # sudo: los turnos de la cuadrilla en las partidas de la obra.
            for slot in self.env['planning.slot'].sudo().search([
                    ('construction_task_id', 'in', lines.task_id.ids)]):
                slots[slot.construction_task_id.id].append(
                    (slot.start_datetime.date(), slot.end_datetime.date()))
        by_task = defaultdict(lambda: self.env['construction.resource.plan.line'].sudo())
        for line in lines:
            by_task[line.task_id] |= line
        cache = {}
        rows = []
        for task, task_lines in by_task.items():
            spans = [windows[l] for l in task_lines if l in windows]
            start = min((s for s, _e in spans), default=False)
            end = max((e for _s, e in spans), default=False)
            executed, planned = amounts.get(task.id, (0.0, 0.0))
            progress = min(executed / planned, 1.0) if planned else 0.0
            expected = 0.0
            if planned:
                expected = sum(l.amount_planned * self._expected_fraction(
                    company, windows[l], today, cache) for l in task_lines if l in windows) / planned
            contract = task_lines.filtered(lambda l: l.resource_type == 'contract')
            labor = task_lines.filtered(lambda l: l.resource_type == 'labor')
            partners = contract.partner_id.commercial_partner_id
            has_crew = any(s <= (end or s) and e >= (start or e) for s, e in slots[task.id])
            unassigned = (bool(contract) and not partners) or (bool(labor) and not has_crew
                                                               and not contract)
            done = progress >= COMPLETE
            late = bool(end) and today > end and not done
            if done:
                column = 'done'
            elif start and start > today:
                column = 'todo'
            elif end and week_start <= end <= week_end:
                column = 'ending'
            else:
                column = 'doing'
            code, name = _split_task(task)
            root = task
            while root.parent_id:
                root = root.parent_id
            rows.append({
                'id': task.id, 'task_code': code, 'task_name': name,
                'parent_label': ' '.join(_split_task(task.parent_id)).strip()
                if task.parent_id else '',
                'specialty': ' '.join(_split_task(root)).strip() if root != task else '',
                'start': fields.Date.to_string(start) if start else '',
                'end': fields.Date.to_string(end) if end else '',
                'progress': round(progress, 4), 'expected': round(min(expected, 1.0), 4),
                'late': late, 'late_days': (today - end).days if late else 0,
                'column': column, 'partners': partners.mapped('name'),
                'own_staff': bool(labor), 'has_crew': has_crew, 'unassigned': unassigned,
                'plan_line_ids': task_lines.ids,
                '_planned': planned, '_executed': executed, '_lines': task_lines,
            })
        rows.sort(key=lambda r: (r['start'] or '9999', r['task_code'], r['id']))
        return rows, windows

    # ------------------------------------------------------------------
    # Resumen, semana, tareas y Gantt
    # ------------------------------------------------------------------
    def _site_overview(self, project, today, data):
        plan = project._construction_current_plan()
        project_sudo = project.sudo()
        company = project.company_id or self.env.company
        week_start, week_end = project._construction_period(today)
        base = {'as_of': data.get('synced_at'), 'today': fields.Date.to_string(today),
                'week_start': fields.Date.to_string(week_start),
                'week_end': fields.Date.to_string(week_end), 'has_plan': bool(plan)}
        if not plan:
            return dict(base, summary={}, curve=[], specialties=[], tasks=[], milestones=[],
                        week={'starting': [], 'ending': [], 'next_starting': []})
        rows, windows = self._site_tasks(project, plan, today)
        total_planned = sum(r['_planned'] for r in rows)
        cache = {}

        def programmed(day):
            if not total_planned:
                return 0.0
            return sum(line.amount_planned * self._expected_fraction(company, window, day, cache)
                       for line, window in windows.items()) / total_planned

        # Resumen: los números del tablero del escritorio.
        requests = self.env['construction.material.request'].sudo().search_count([
            ('project_id', '=', project.id), ('state', 'in', ('to_approve', 'approved',
                                                              'in_progress'))])
        # Personal de hoy: la asistencia propia en la sede y el personal de
        # contrata de los partes del día.
        # sudo: los partes del día de la obra del residente.
        contract_staff = sum(self.env['construction.daily.report.staff'].sudo().search([
            ('report_id.project_id', '=', project.id), ('report_id.date', '=', today),
            ('report_id.kind', '=', 'member'), ('source', '=', 'contract')]).mapped('count'))
        staff = ((data.get('daily') or {}).get('own_today') or 0) + contract_staff
        summary = {
            'real': round(project_sudo.construction_board_progress, 4),
            'programmed': round(programmed(today), 4),
            'late': len([r for r in rows if r['late']]),
            'to_validate': project_sudo.construction_progress_to_validate_count,
            'open_requests': requests,
            'staff_today': staff,
            'amounts': {
                'planned': project_sudo.construction_board_planned,
                'committed': project_sudo.construction_board_committed,
                'actual': project_sudo.construction_board_actual,
                'remaining': project_sudo.construction_board_remaining,
            } if company.construction_portal_show_amounts else False,
        }
        # Curva de avance por semanas de la obra (U17).
        start = min((w[0] for w in windows.values()), default=plan.date_start) or today
        end = max((w[1] for w in windows.values()), default=plan.date_end) or today
        validated = defaultdict(float)
        # sudo: lo validado de la obra, por fecha de ejecución.
        for day, amount in self.env['construction.task.progress'].sudo()._read_group(
                [('plan_line_id.plan_id', '=', plan.id), ('state', '=', 'validated'),
                 ('is_rework', '=', False)], ['date:day'], ['amount:sum']):
            validated[day] += amount or 0.0
        planned_total = sum(r['_planned'] for r in rows) or 0.0
        weeks, day = [], project._construction_period(start)[1]
        step = max(1, ((end - start).days // 7 + 1) // CURVE_POINTS + 1)
        while day <= end + timedelta(days=6 * step):
            weeks.append(day)
            day += timedelta(days=7 * step)
            if len(weeks) > CURVE_POINTS + 2:
                break
        curve = []
        for week in weeks:
            real = None
            if week <= today + timedelta(days=6):
                done = sum(a for d, a in validated.items() if d and d <= week)
                real = round(min(done / planned_total, 1.0), 4) if planned_total else 0.0
            curve.append({'week': fields.Date.to_string(week),
                          'programmed': round(programmed(week), 4), 'real': real})
        # Avance por especialidad.
        groups = defaultdict(lambda: [0.0, 0.0, 0.0])
        for r in rows:
            key = r['specialty'] or r['parent_label'] or project.display_name
            groups[key][0] += r['_executed']
            groups[key][1] += r['_planned']
            groups[key][2] += r['expected'] * r['_planned']
        specialties = [{'name': name, 'real': round(e / p, 4) if p else 0.0,
                        'programmed': round(x / p, 4) if p else 0.0}
                       for name, (e, p, x) in sorted(groups.items())]
        # Semana (U18): inician y terminan esta semana.
        risk = (company.construction_portal_risk_pct or 70) / 100.0
        ws, we = fields.Date.to_string(week_start), fields.Date.to_string(week_end)
        starting = [dict(self._public_row(r), warning=self.env._(
            'Inicia sin contrata ni cuadrilla') if r['unassigned'] else '')
            for r in rows if r['start'] and ws <= r['start'] <= we]
        ending = [dict(self._public_row(r), warning=self.env._(
            'En riesgo: %s %% de avance', round(100 * r['progress']))
            if r['progress'] < risk and r['column'] != 'done' else '')
            for r in rows if r['end'] and ws <= r['end'] <= we]
        # La semana siguiente (CR-54, punto 1): lo que inicia, con su aviso.
        ns = fields.Date.to_string(week_end + timedelta(days=1))
        ne = fields.Date.to_string(week_end + timedelta(days=7))
        next_starting = [dict(self._public_row(r), warning=self.env._(
            'Inicia sin contrata ni cuadrilla') if r['unassigned'] else '')
            for r in rows if r['start'] and ns <= r['start'] <= ne]
        # sudo: los hitos del Gantt de proyectos de la obra.
        milestones = self.env['al.gantt.data'].sudo()._read_milestones([project.id]) \
            if 'al.gantt.data' in self.env else []
        return dict(base, summary=summary, curve=curve, specialties=specialties,
                    tasks=[self._public_row(r) for r in rows],
                    week={'starting': starting, 'ending': ending, 'next_starting': next_starting},
                    milestones=[{'name': m['name'], 'date': m['date'],
                                 'reached': m['is_reached']} for m in milestones if m['date']],
                    start=fields.Date.to_string(start), end=fields.Date.to_string(end))

    @staticmethod
    def _public_row(row):
        return {key: value for key, value in row.items() if not key.startswith('_')}
