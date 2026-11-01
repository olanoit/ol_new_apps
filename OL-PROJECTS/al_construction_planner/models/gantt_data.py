# -*- coding: utf-8 -*-
"""Cronograma con recursos (P-15): herencia de la capa de datos del Gantt.

Sin tocar los archivos del Gantt. Solo actúa si la interfaz lo pide con la
opción ``construction_schedule`` (el Gantt de proyectos sigue igual):

* cada tarea con nivel de obra trae, en ``construction``, el monto
  planificado, el avance valorizado, la contrata, el estado del módulo y sus
  alertas (líneas excedidas);
* ``construction_stages`` y ``construction_stage_links``: las etapas de cada
  ambiente (``construction.space.stage``) como filas hijas del ambiente, con
  los vínculos Producción → Armado → Instalación → Acabado.

Opciones: ``construction_plan_id`` (plan; por defecto el vigente de la obra),
``construction_rows`` (``'stages'``: pisos, departamentos y ambientes con sus
etapas; ``'tasks'``: las tareas de la obra) y ``construction_stages`` (solo
esas etapas; una etapa padre son sus sub etapas).

Las etapas padre del catálogo (v1.8, M18-02) son barras resumen de cada
ambiente (``construction_stage_groups``) con sus sub etapas como hijas."""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError

from .common import DRIVER_TYPES, UNIT_STATES, can_see_amounts
from .construction_plan_tree import LINE_FIELD
from .construction_space_current_stage import SCHEDULE_RANK

#: Días antes del inicio en que una etapa sin contrata ni cuadrilla es alerta.
UNASSIGNED_ALERT_DAYS = 14


class GanttData(models.AbstractModel):
    _inherit = 'al.gantt.data'

    @api.model
    def _construction_options(self, options):
        options = options or {}
        if not options.get('construction_schedule'):
            return None
        rows = options.get('construction_rows') or 'stages'
        # Filtro de etapas (v1.8, M18-02): varias etapas a la vez; una etapa
        # padre son todas sus sub etapas. ``construction_stage`` (una sola)
        # sigue valiendo.
        stages = list(options.get('construction_stages') or [])
        if options.get('construction_stage'):
            stages.append(options['construction_stage'])
        return {
            'rows': rows if rows in ('stages', 'tasks') else 'stages',
            'stages': self.env['construction.stage']._leaf_codes(stages),
            'plan_id': options.get('construction_plan_id') or False,
            # Filtros de la etapa actual (paquete 1.15, M115-04).
            'current_stages': list(options.get('construction_current_stages') or []),
            'only_late': bool(options.get('construction_only_late')),
        }

    @api.model
    def _get_task_domain(self, project_ids, field_map, options, with_date_range=True):
        domain = super()._get_task_domain(project_ids, field_map, options, with_date_range)
        schedule = self._construction_options(options)
        if schedule and schedule['rows'] == 'stages':
            # Las barras son las etapas: los módulos no se listan.
            domain = domain + [('construction_level', 'in', ('group', 'floor', 'apartment', 'space'))]
        if schedule and (schedule['current_stages'] or schedule['only_late']):
            domain = domain + [('id', 'in', self._construction_current_filter_ids(
                project_ids, schedule))]
        return domain

    @api.model
    def _construction_current_filter_ids(self, project_ids, schedule):
        """Ambientes que pasan los filtros de la etapa actual y sus
        ancestros (para que el árbol se siga leyendo)."""
        Task = self.env['project.task']
        domain = [('construction_current_stage', '!=', False)]
        if project_ids:
            domain.append(('project_id', 'in', list(project_ids)))
        if schedule['current_stages']:
            domain.append(('construction_current_stage', 'in', schedule['current_stages']))
        if schedule['only_late']:
            domain.append(('construction_stage_schedule', 'in', ['late', 'risk']))
        ids = set()
        for task in Task.search(domain):
            node = task
            while node and node.id not in ids:
                ids.add(node.id)
                node = node.parent_id
        return list(ids)

    @api.model
    def get_data(self, project_ids=None, options=None):
        schedule = self._construction_options(options)
        if not schedule:
            return super().get_data(project_ids, options)
        options = dict(options)
        if schedule['rows'] == 'stages':
            # Pisos, departamentos y ambientes no suelen tener fechas: su barra
            # es el resumen de sus etapas.
            options['include_undated'] = True
        payload = super().get_data(project_ids, options)
        self._construction_enrich(payload, schedule)
        # Visibilidad de montos (v1.8, M18-10): sin el grupo, el cronograma
        # muestra fechas, contratas y avance, sin el monto planificado.
        show_amounts = can_see_amounts(self.env)
        payload['construction']['show_amounts'] = show_amounts
        if not show_amounts:
            for item in payload['tasks']:
                if item.get('construction'):
                    item['construction']['amount'] = False
            for row in payload['construction_stages'] + payload['construction_stage_groups']:
                row['amount'] = False
        return payload

    # ------------------------------------------------------------------
    # Enriquecido
    # ------------------------------------------------------------------
    @api.model
    def _construction_plan(self, payload, schedule):
        Plan = self.env['construction.resource.plan']
        if schedule['plan_id']:
            plan = Plan.browse(int(schedule['plan_id'])).exists()
            if plan and plan.project_id.id in [p['id'] for p in payload['projects']]:
                return plan
        projects = self.env['project.project'].browse([p['id'] for p in payload['projects']])
        for project in projects:
            plan = project._construction_current_plan()
            if plan:
                return plan
        return Plan

    @api.model
    def _construction_enrich(self, payload, schedule):
        plan = self._construction_plan(payload, schedule)
        stage_labels = dict(self.env['construction.space.stage']._fields['stage']
                            ._description_selection(self.env))
        payload['construction'] = {
            'plan_id': plan.id or False,
            'plan_name': plan.display_name or '',
            'rows': schedule['rows'],
            'stages': schedule['stages'],
            'stage_labels': stage_labels,
            'stage_tree': self.env['construction.stage']._get_tree(),
            'stage_colors': {stage.code: stage.color for stage in
                             self.env['construction.stage'].search([]) if stage.color},
        }
        payload['construction_stages'] = []
        payload['construction_stage_groups'] = []
        payload['construction_stage_links'] = []
        # Estados del ambiente para la etapa actual (M115-04): sin los de
        # mobiliario si la obra no los usa.
        has_states = bool(plan.project_id._construction_space_state_labels()) if plan else False
        payload['construction']['space_states'] = [
            state for state in self.env['project.task']._construction_space_states()
            if has_states or not state['is_state']]
        if not plan:
            return
        tasks = payload['tasks']
        info = self._construction_task_info(tasks, plan, schedule['stages'])
        for task in tasks:
            task['construction'] = info.get(task['id'], {})
        self._construction_current_stage_info(tasks, payload['construction']['space_states'])
        if schedule['rows'] == 'stages':
            self._construction_stage_rows(payload, plan, schedule['stages'], stage_labels)

    @api.model
    def _construction_task_info(self, tasks, plan, stages):
        """{tarea: {level, amount, progress, partners, unit_state, alerts}}
        con un _read_group por nivel (sin una consulta por tarea)."""
        Task = self.env['project.task']
        Line = self.env['construction.resource.plan.line']
        Plan = self.env['construction.resource.plan']
        records = Task.browse([task['id'] for task in tasks])
        unit_labels = dict(UNIT_STATES)
        result = {}
        for level, field in LINE_FIELD.items():
            level_tasks = records.filtered(lambda t, level=level: t.construction_level == level)
            if not level_tasks:
                continue
            domain = [('plan_id', '=', plan.id), (field, 'in', level_tasks.ids)]
            if stages:
                domain.append(('stage', 'in', stages))
            amounts = {task.id: amount for task, amount in Line._read_group(
                domain, [field], ['amount_planned:sum'])}
            partners = {}
            for task, partner in Line._read_group(
                    domain + [('resource_type', 'in', DRIVER_TYPES), ('partner_id', '!=', False)],
                    [field, 'partner_id']):
                partners.setdefault(task.id, []).append(partner.display_name)
            exceeded = {task.id: count for task, count in Line._read_group(
                domain + [('line_state', '=', 'exceeded')], [field], ['__count'])}
            progress = Plan._progress_amounts(domain, field)
            for task in level_tasks:
                alerts = []
                if exceeded.get(task.id):
                    alerts.append(self.env._('%s líneas excedidas', exceeded[task.id]))
                result[task.id] = {
                    'level': level,
                    'amount': round(amounts.get(task.id, 0.0), 2),
                    'progress': round(Plan._progress_ratio(progress, task.id) * 100, 1),
                    'partners': ', '.join(sorted(partners.get(task.id, []))),
                    'unit_state': unit_labels.get(task.construction_unit_state, '')
                    if level == 'module' else '',
                    'alerts': alerts,
                }
        # Agrupadores (torre, disciplina, área): lo de su ruta (v1.7, M17-01).
        for task in records.filtered(lambda t: t.construction_level == 'group'):
            domain = [('plan_id', '=', plan.id),
                      ('task_path', '=like', '%s%%' % task.construction_path)]
            if stages:
                domain.append(('stage', 'in', stages))
            amount = sum(Line.search(domain).mapped('amount_planned'))
            progress = Plan._progress_amounts(domain)
            result[task.id] = {
                'level': 'group', 'amount': round(amount, 2),
                'progress': round(Plan._progress_ratio(progress, False) * 100, 1),
                'partners': '', 'unit_state': '', 'alerts': [],
            }
        return result

    @api.model
    def _construction_current_stage_info(self, tasks, states):
        """Etapa actual y plazo (M115-04) en ``construction.current`` de
        cada ambiente; en sus ancestros, cuántos ambientes hay en cada estado
        (``current_counts``) y el peor plazo (``worst``)."""
        Task = self.env['project.task']
        by_code = {state['code']: state for state in states}
        parents = {task['id']: task['parent_id'] for task in tasks}
        by_id = {task['id']: task for task in tasks}
        records = Task.browse(list(by_id)).filtered('construction_current_stage')
        labels = dict(Task._fields['construction_stage_schedule']._description_selection(self.env))
        for record in records:
            state = by_code.get(record.construction_current_stage, {})
            schedule = record.construction_stage_schedule
            item = by_id[record.id].setdefault('construction', {})
            item['current'] = {
                'code': record.construction_current_stage,
                'label': state.get('label') or record.construction_current_stage,
                'color': state.get('color') or '#3d85c6',
                'is_state': state.get('is_state', False),
                'pct': record.construction_current_stage_progress,
                'schedule': schedule or '',
                'schedule_name': labels.get(schedule, ''),
                'schedule_label': record.construction_stage_schedule_label or '',
            }
            node, seen = parents.get(record.id), set()
            while node and node in by_id and node not in seen:
                seen.add(node)
                parent = by_id[node].setdefault('construction', {})
                counts = parent.setdefault('current_counts', {})
                counts[record.construction_current_stage] = \
                    counts.get(record.construction_current_stage, 0) + 1
                worst = parent.get('worst')
                if schedule and (not worst or SCHEDULE_RANK[schedule] > SCHEDULE_RANK[worst['state']]):
                    parent['worst'] = {'state': schedule, 'name': labels.get(schedule, ''), 'count': 1}
                elif worst and schedule == worst['state']:
                    worst['count'] += 1
                node = parents.get(node)

    @api.model
    def _construction_stage_rows(self, payload, plan, stages_filter, stage_labels):
        Stage = self.env['construction.space.stage']
        space_ids = [task['id'] for task in payload['tasks']
                     if task.get('construction', {}).get('level') == 'space']
        domain = [('space_task_id', 'in', space_ids)]
        if stages_filter:
            domain.append(('stage', 'in', stages_filter))
        stages = Stage.search(domain)
        resources = Stage._resources_by_stage(stages)
        progress = Stage._progress_by_stage(stages)
        editable = Stage.has_access('write') and plan.state not in ('closed', 'cancel', 'replaced')
        today = fields.Date.context_today(self)
        rows, by_space = [], {}
        for record in stages:
            key = (record.space_task_id.id, record.stage)
            item = resources.get(key, {})
            partner, role = item.get('partner'), item.get('role')
            alerts = []
            unassigned = bool(item.get('drivers')) and not partner and not role
            if unassigned and record.date_start - today <= timedelta(days=UNASSIGNED_ALERT_DAYS) \
                    and record.date_end >= today:
                alerts.append(self.env._('Empieza pronto sin contrata ni cuadrilla'))
            dependencies = record.dependency_ids
            if dependencies:
                alerts.append(self.env._('Bloqueada por %s', ', '.join(dependencies.mapped('name'))))
            rows.append({
                'id': record.id,
                'space_task_id': record.space_task_id.id,
                'stage': record.stage,
                'name': stage_labels.get(record.stage, record.stage),
                'start': fields.Date.to_string(record.date_start),
                'end': fields.Date.to_string(record.date_end),
                'partner_name': partner.display_name if partner else '',
                'role_name': role.display_name if role else '',
                'amount': round(item.get('amount', 0.0), 2),
                'progress': round(progress.get(key, 0.0) * 100, 1),
                'unassigned': unassigned,
                'blocked': bool(dependencies),
                'alerts': alerts,
                'editable': editable,
            })
            by_space.setdefault(record.space_task_id.id, []).append(record)
        links = []
        for space_stages in by_space.values():
            ordered = sorted(space_stages, key=lambda s: s.sequence)
            for previous, current in zip(ordered, ordered[1:]):
                links.append({'id': f'sl{current.id}', 'source': previous.id,
                              'target': current.id, 'type': 'FS'})
        payload['construction_stages'] = rows
        payload['construction_stage_groups'] = self._construction_stage_groups(rows)
        payload['construction_stage_links'] = links
        # Los ambientes, departamentos y pisos sin fechas toman las de sus
        # etapas: no cuentan como «sin fecha» en el aviso de la interfaz.
        covered = self._construction_covered_tasks(payload['tasks'], set(by_space))
        meta = payload['meta']
        meta['undated_count'] = max(0, meta.get('undated_count', 0) - len(
            [task for task in payload['tasks'] if task['undated'] and task['id'] in covered]))

    @api.model
    def _construction_stage_groups(self, rows):
        """Barras resumen de las etapas padre (v1.8, M18-02): una por ambiente
        y etapa padre con sub etapas en el cronograma, con su monto y su
        avance ponderado por monto. Cada fila de etapa recibe ``group_key``
        (la barra de la que cuelga) y cada resumen ``parent_key`` si su etapa
        padre también tiene padre."""
        Stage = self.env['construction.stage']
        catalog = {stage.code: stage for stage in Stage.with_context(active_test=False).search(
            [('code', 'in', list({row['stage'] for row in rows}))])}
        groups = {}
        for row in rows:
            stage = catalog.get(row['stage'])
            child_key = None
            node = stage.parent_id if stage else Stage
            while node:
                key = 'g%s_%s' % (row['space_task_id'], node.id)
                group = groups.setdefault(key, {
                    'key': key, 'space_task_id': row['space_task_id'], 'stage': node.code,
                    'name': node._label(), 'sequence': node._tree_key(), 'amount': 0.0,
                    'weighted': 0.0, 'stages': [], 'parent_key': False,
                })
                group['amount'] += row['amount']
                group['weighted'] += row['amount'] * row['progress']
                group['stages'].append(row['stage'])
                if child_key:
                    groups[child_key]['parent_key'] = key
                else:
                    row['group_key'] = key
                child_key = key
                node = node.parent_id
        result = []
        for group in sorted(groups.values(), key=lambda g: (g['space_task_id'], g['sequence'])):
            weighted = group.pop('weighted')
            group.pop('sequence')
            group['progress'] = round(weighted / group['amount'], 1) if group['amount'] else 0.0
            group['amount'] = round(group['amount'], 2)
            result.append(group)
        return result

    @api.model
    def _construction_covered_tasks(self, tasks, space_ids):
        """Tareas con alguna etapa en su descendencia (ambientes con etapas y
        sus ancestros dentro del conjunto leído)."""
        parents = {task['id']: task['parent_id'] for task in tasks}
        covered = set()
        for space_id in space_ids:
            node = space_id
            while node and node not in covered:
                covered.add(node)
                node = parents.get(node)
        return covered


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def get_schedule_load(self, stage=False):
        """Carga semanal del cronograma (P-15; paquete 1.15, M115-06, con
        M116-07): monto de contratas y personal propio por etapa y por quién
        lo hace, planificado y ejecutado, por semana de la obra.

        * Planificado: el monto de cada línea repartido en partes iguales
          entre los días hábiles de la etapa del ambiente (calendario y
          feriados de la compañía, ``_construction_is_site_day``).
        * Ejecutado: los avances validados (sin retrabajos) por la semana de
          su fecha de ejecución.
        * Semanas: las de la obra (``_construction_period``), las mismas de
          la liquidación (CR-10).

        :returns: ``{'weeks': [inicio ISO], 'week_ends': [fin ISO],
            'current_week': índice o -1, 'rows': [...], 'groups': [...],
            'totals': [...], 'executed_totals': [...], 'diff': [...],
            'total', 'plan_to_date', 'executed_total', 'pct', 'thresholds'}``.
            Cada fila: ``label, stage, stage_label, unassigned, values
            (planificado), executed, total, plan_to_date, executed_total,
            pct``. Cada grupo (etapa) trae lo mismo con ``color`` y las filas
            de la etapa en ``rows``.
        """
        self.ensure_one()
        if not can_see_amounts(self.env):
            raise AccessError(self.env._(
                'La carga semanal está en soles: solo la ve el grupo «Planificación de obra: '
                've montos».'))
        self.check_access('read')
        Line = self.env['construction.resource.plan.line']
        Stage = self.env['construction.space.stage']
        Progress = self.env['construction.task.progress']
        project = self.project_id
        company = project.company_id or self.company_id or self.env.company
        stage_domain = [('project_id', '=', project.id)]
        line_domain = [('plan_id', '=', self.id), ('resource_type', 'in', DRIVER_TYPES),
                       ('space_task_id', '!=', False), ('stage', '!=', False)]
        # Una etapa, varias o una etapa padre (sus sub etapas: M18-02).
        stages = self.env['construction.stage']._leaf_codes(
            [stage] if isinstance(stage, str) else stage or [])
        if stages:
            stage_domain.append(('stage', 'in', stages))
            line_domain.append(('stage', 'in', stages))
        dates = {(record.space_task_id.id, record.stage): (record.date_start, record.date_end)
                 for record in Stage.search(stage_domain)}
        stage_labels = dict(Stage._fields['stage']._description_selection(self.env))
        unassigned = self.env._('Por asignar')
        extra = Line._weekly_load_groupby()

        def week_of(day):
            return project._construction_period(day)[0]

        site_days = {}

        def is_site_day(day):
            if day not in site_days:
                site_days[day] = company._construction_is_site_day(day)
            return site_days[day]

        planned, executed = {}, {}
        # Quién ejecuta: la contrata o, con el puente de cuadrillas, el rol.
        groupby = ['space_task_id', 'stage', 'partner_id'] + extra
        for space, line_stage, *resources, amount in Line._read_group(
                line_domain, groupby, ['amount_planned:sum']):
            period = dates.get((space.id, line_stage))
            if not period or not amount:
                continue
            days = [period[0] + timedelta(days=offset)
                    for offset in range((period[1] - period[0]).days + 1)]
            workdays = [day for day in days if is_site_day(day)] or days[:1]
            who = next((record for record in resources if record), None)
            row = planned.setdefault((who.display_name if who else unassigned, line_stage), {})
            share = amount / len(workdays)
            for day in workdays:
                week = week_of(day)
                row[week] = row.get(week, 0.0) + share
        # Lo ejecutado: avances validados de esas líneas, con la contrata que
        # los ejecutó (el avance la guarda) o el rol de la línea.
        for line, partner, day, amount in Progress._read_group(
                [('state', '=', 'validated'), ('is_rework', '=', False),
                 ('plan_line_id', 'any', line_domain)],
                ['plan_line_id', 'partner_id', 'date:day'], ['amount:sum']):
            if not amount or not day:
                continue
            who = partner or next((line[field] for field in extra if line[field]), None)
            row = executed.setdefault((who.display_name if who else unassigned, line.stage), {})
            week = week_of(fields.Date.to_date(day))
            row[week] = row.get(week, 0.0) + amount
        today = fields.Date.context_today(self)
        current = week_of(today)
        weeks = sorted({week for values in list(planned.values()) + list(executed.values())
                        for week in values})
        if weeks:
            # Semanas seguidas, aunque alguna no tenga montos.
            weeks = [weeks[0] + timedelta(days=7 * index)
                     for index in range((weeks[-1] - weeks[0]).days // 7 + 1)]
        to_date = [week <= current for week in weeks]

        def measure(plan_values, done_values):
            plan_list = [round(plan_values.get(week, 0.0), 2) for week in weeks]
            done_list = [round(done_values.get(week, 0.0), 2) for week in weeks]
            plan_to_date = sum(value for value, past in zip(plan_list, to_date) if past)
            done_total = sum(done_list)
            return {
                'values': plan_list, 'executed': done_list,
                'total': round(sum(plan_values.values()), 2),
                'plan_to_date': round(plan_to_date, 2),
                'executed_total': round(done_total, 2),
                'pct': round(100.0 * done_total / plan_to_date, 1) if plan_to_date else False,
            }

        order = {key: index for index, key in enumerate(stage_labels)}
        colors = {record.code: record.color for record in self.env['construction.stage'].with_context(
            active_test=False).search([])}
        keys = sorted(set(planned) | set(executed),
                      key=lambda key: (order.get(key[1], 9999), key[0] == unassigned, key[0]))
        result_rows, groups = [], {}
        for name, line_stage in keys:
            row = dict(measure(planned.get((name, line_stage), {}),
                               executed.get((name, line_stage), {})),
                       label=name, stage=line_stage,
                       stage_label=stage_labels.get(line_stage, ''),
                       unassigned=name == unassigned)
            result_rows.append(row)
            groups.setdefault(line_stage, []).append(row)

        def add(rows, key):
            return [round(sum(row[key][index] for row in rows), 2) for index in range(len(weeks))]

        result_groups = []
        for line_stage, rows in groups.items():
            plan_values = dict(zip(weeks, add(rows, 'values')))
            done_values = dict(zip(weeks, add(rows, 'executed')))
            group = measure(plan_values, done_values)
            group.update(stage=line_stage, stage_label=stage_labels.get(line_stage, ''),
                         color=colors.get(line_stage) or '#3d85c6', rows=rows)
            result_groups.append(group)
        totals = measure(dict(zip(weeks, add(result_rows, 'values'))),
                         dict(zip(weeks, add(result_rows, 'executed'))))
        return {
            'weeks': [fields.Date.to_string(week) for week in weeks],
            'week_ends': [fields.Date.to_string(week + timedelta(days=6)) for week in weeks],
            'current_week': weeks.index(current) if current in weeks else -1,
            'rows': result_rows,
            'groups': result_groups,
            'totals': totals['values'],
            'executed_totals': totals['executed'],
            'diff': [round(done - plan, 2) if past else False for plan, done, past in zip(
                totals['values'], totals['executed'], to_date)],
            'total': totals['total'],
            'plan_to_date': totals['plan_to_date'],
            'executed_total': totals['executed_total'],
            'pct': totals['pct'],
            'thresholds': {'green': company.construction_load_green_pct,
                           'amber': company.construction_load_amber_pct},
        }
