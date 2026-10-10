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
etapas; ``'tasks'``: las tareas de la obra) y ``construction_stage`` (solo
esa etapa)."""
from datetime import timedelta

from odoo import api, fields, models

from .common import DRIVER_TYPES, UNIT_STATES
from .construction_plan_tree import LINE_FIELD

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
        return {
            'rows': rows if rows in ('stages', 'tasks') else 'stages',
            'stage': options.get('construction_stage') or False,
            'plan_id': options.get('construction_plan_id') or False,
        }

    @api.model
    def _get_task_domain(self, project_ids, field_map, options, with_date_range=True):
        domain = super()._get_task_domain(project_ids, field_map, options, with_date_range)
        schedule = self._construction_options(options)
        if schedule and schedule['rows'] == 'stages':
            # Las barras son las etapas: los módulos no se listan.
            domain = domain + [('construction_level', 'in', ('floor', 'apartment', 'space'))]
        return domain

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
            'stage': schedule['stage'],
            'stage_labels': stage_labels,
        }
        payload['construction_stages'] = []
        payload['construction_stage_links'] = []
        if not plan:
            return
        tasks = payload['tasks']
        info = self._construction_task_info(tasks, plan, schedule['stage'])
        for task in tasks:
            task['construction'] = info.get(task['id'], {})
        if schedule['rows'] == 'stages':
            self._construction_stage_rows(payload, plan, schedule['stage'], stage_labels)

    @api.model
    def _construction_task_info(self, tasks, plan, stage):
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
            if stage:
                domain.append(('stage', '=', stage))
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
        return result

    @api.model
    def _construction_stage_rows(self, payload, plan, stage, stage_labels):
        Stage = self.env['construction.space.stage']
        space_ids = [task['id'] for task in payload['tasks']
                     if task.get('construction', {}).get('level') == 'space']
        domain = [('space_task_id', 'in', space_ids)]
        if stage:
            domain.append(('stage', '=', stage))
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
        payload['construction_stage_links'] = links
        # Los ambientes, departamentos y pisos sin fechas toman las de sus
        # etapas: no cuentan como «sin fecha» en el aviso de la interfaz.
        covered = self._construction_covered_tasks(payload['tasks'], set(by_space))
        meta = payload['meta']
        meta['undated_count'] = max(0, meta.get('undated_count', 0) - len(
            [task for task in payload['tasks'] if task['undated'] and task['id'] in covered]))

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
        """Carga semanal del cronograma (P-15): monto de contratas y personal
        propio por contrata (o cuadrilla) y etapa, repartido en partes iguales
        entre los días hábiles (lunes a viernes) de la etapa de cada ambiente
        y sumado por semana calendario (desde el lunes).

        :returns: ``{'weeks': [lunes ISO], 'rows': [{label, stage, values,
            total}], 'totals': [...], 'total': n}``
        """
        self.ensure_one()
        self.check_access('read')
        Line = self.env['construction.resource.plan.line']
        Stage = self.env['construction.space.stage']
        stage_domain = [('project_id', '=', self.project_id.id)]
        line_domain = [('plan_id', '=', self.id), ('resource_type', 'in', DRIVER_TYPES),
                       ('space_task_id', '!=', False), ('stage', '!=', False)]
        if stage:
            stage_domain.append(('stage', '=', stage))
            line_domain.append(('stage', '=', stage))
        dates = {(record.space_task_id.id, record.stage): (record.date_start, record.date_end)
                 for record in Stage.search(stage_domain)}
        stage_labels = dict(Stage._fields['stage']._description_selection(self.env))
        unassigned = self.env._('Sin asignar')
        rows = {}
        for space, line_stage, partner, role, amount in Line._read_group(
                line_domain, ['space_task_id', 'stage', 'partner_id', 'role_id'],
                ['amount_planned:sum']):
            period = dates.get((space.id, line_stage))
            if not period or not amount:
                continue
            days = [period[0] + timedelta(days=offset)
                    for offset in range((period[1] - period[0]).days + 1)]
            workdays = [day for day in days if day.weekday() < 5] or days[:1]
            name = partner.display_name if partner else role.display_name if role else unassigned
            row = rows.setdefault((name, line_stage), {})
            share = amount / len(workdays)
            for day in workdays:
                week = day - timedelta(days=day.weekday())
                row[week] = row.get(week, 0.0) + share
        weeks = sorted({week for values in rows.values() for week in values})
        if weeks:
            # Semanas seguidas, aunque alguna no tenga montos.
            weeks = [weeks[0] + timedelta(days=7 * index)
                     for index in range((weeks[-1] - weeks[0]).days // 7 + 1)]
        order = {key: index for index, key in enumerate(stage_labels)}
        result_rows = []
        for (name, line_stage), values in sorted(
                rows.items(), key=lambda item: (order.get(item[0][1], 9), item[0][0])):
            amounts = [round(values.get(week, 0.0), 2) for week in weeks]
            result_rows.append({
                'label': name, 'stage': line_stage,
                'stage_label': stage_labels.get(line_stage, ''),
                'unassigned': name == unassigned,
                'values': amounts, 'total': round(sum(values.values()), 2),
            })
        totals = [round(sum(row['values'][index] for row in result_rows), 2)
                  for index in range(len(weeks))]
        return {
            'weeks': [fields.Date.to_string(week) for week in weeks],
            'rows': result_rows,
            'totals': totals,
            'total': round(sum(row['total'] for row in result_rows), 2),
        }
