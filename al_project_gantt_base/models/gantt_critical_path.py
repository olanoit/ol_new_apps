# -*- coding: utf-8 -*-
"""Ruta crítica calculada en el servidor (CPM).

La edición MIT de dhtmlxGantt **no** trae ruta crítica (no es un candado de
licencia: el código no está en el paquete), así que se calcula aquí con el
método del camino crítico clásico —pasada hacia delante y hacia atrás sobre el
grafo de dependencias fin-comienzo— y se devuelve como dos datos por tarea:
``slack_hours`` (holgura total) y ``critical``.

Solo entran las tareas con fechas y sin hijos: las tareas contenedoras heredan
la marca de sus descendientes, como en cualquier herramienta de planificación.
"""
import logging
from datetime import datetime, timedelta

from odoo import api, models

_logger = logging.getLogger(__name__)

#: Holgura por debajo de la cual una tarea se considera crítica.
CRITICAL_TOLERANCE = timedelta(hours=1)


class GanttCriticalPath(models.AbstractModel):
    _inherit = 'al.gantt.data'

    @api.model
    def _apply_critical_path(self, tasks, links):
        """Añade ``slack_hours`` y ``critical`` a las tareas (las muta).

        :return: resumen para ``meta`` (tareas críticas, fin del plan).
        """
        parents = {task['parent_id'] for task in tasks if task['parent_id']}
        nodes = {
            task['id']: task
            for task in tasks
            if task['start'] and task['end'] and task['id'] not in parents
        }
        for task in tasks:
            task['slack_hours'] = None
            task['critical'] = False
        if not nodes:
            return {'computed': False, 'critical_count': 0, 'project_finish': None}

        starts = {task_id: self._from_iso(task['start']) for task_id, task in nodes.items()}
        ends = {task_id: self._from_iso(task['end']) for task_id, task in nodes.items()}
        durations = {task_id: ends[task_id] - starts[task_id] for task_id in nodes}

        predecessors = {task_id: [] for task_id in nodes}
        successors = {task_id: [] for task_id in nodes}
        for link in links:
            source, target = link['source'], link['target']
            if source in nodes and target in nodes:
                predecessors[target].append(source)
                successors[source].append(target)

        order = self._topological_order(nodes, predecessors, successors)
        if order is None:
            _logger.warning("Gantt: dependencias cíclicas; no se calcula la ruta crítica")
            return {'computed': False, 'critical_count': 0, 'project_finish': None}

        # Pasada hacia delante: fecha más temprana en que puede terminar cada tarea.
        earliest_finish = {}
        for task_id in order:
            earliest_start = starts[task_id]
            for predecessor in predecessors[task_id]:
                earliest_start = max(earliest_start, earliest_finish[predecessor])
            earliest_finish[task_id] = earliest_start + durations[task_id]

        project_finish = max(earliest_finish.values())

        # Pasada hacia atrás: fecha más tardía sin retrasar el plan.
        latest_finish = {}
        for task_id in reversed(order):
            if successors[task_id]:
                latest_finish[task_id] = min(
                    latest_finish[successor] - durations[successor]
                    for successor in successors[task_id]
                )
            else:
                latest_finish[task_id] = project_finish

        critical_count = 0
        for task_id, task in nodes.items():
            slack = latest_finish[task_id] - earliest_finish[task_id]
            task['slack_hours'] = round(slack.total_seconds() / 3600.0, 2)
            task['critical'] = slack <= CRITICAL_TOLERANCE
            if task['critical']:
                critical_count += 1

        self._propagate_critical_to_parents(tasks)
        return {
            'computed': True,
            'critical_count': critical_count,
            'project_finish': self._iso(project_finish),
        }

    @api.model
    def _propagate_critical_to_parents(self, tasks):
        """Una tarea contenedora es crítica si lo es alguna de sus hijas."""
        by_id = {task['id']: task for task in tasks}
        for task in tasks:
            if not task['critical']:
                continue
            parent_id = task['parent_id']
            guard = 0
            while parent_id and parent_id in by_id and guard < 50:
                by_id[parent_id]['critical'] = True
                parent_id = by_id[parent_id]['parent_id']
                guard += 1

    @api.model
    def _topological_order(self, nodes, predecessors, successors):
        """Orden topológico (Kahn). ``None`` si el grafo tiene ciclos."""
        pending = {task_id: len(predecessors[task_id]) for task_id in nodes}
        queue = [task_id for task_id, count in pending.items() if not count]
        order = []
        while queue:
            task_id = queue.pop(0)
            order.append(task_id)
            for successor in successors[task_id]:
                pending[successor] -= 1
                if not pending[successor]:
                    queue.append(successor)
        return order if len(order) == len(nodes) else None

    @api.model
    def _from_iso(self, value):
        """Inverso de ``_iso``: cadena ISO en UTC -> datetime naive."""
        return datetime.fromisoformat(str(value).replace('Z', ''))
