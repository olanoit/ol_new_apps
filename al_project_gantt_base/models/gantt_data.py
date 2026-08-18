# -*- coding: utf-8 -*-
"""Capa de datos única de la suite Gantt.

Este servicio es el **único** punto de acceso a datos: las interfaces
(``al_project_gantt_backend``, ``al_project_gantt_website``) no consultan el ORM
por su cuenta. El formato de salida es **neutral** respecto de la librería de
renderizado; la traducción al formato de dhtmlxGantt la hace el adaptador
JavaScript (``static/src/js/gantt_adapter.js``).

Seguridad: todas las lecturas se hacen con el usuario real (**sin** ``sudo()``),
de modo que las reglas de registro nativas de ``project`` — privacidad por
seguidores, portal, multicompañía — se aplican tal cual, sin duplicarlas.
"""
import logging
from datetime import timedelta

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError
from odoo.addons.project.models.project_task import CLOSED_STATES

_logger = logging.getLogger(__name__)

#: Grupo mínimo para leer datos del Gantt.
GROUP_GANTT_USER = 'al_project_gantt_base.group_gantt_user'

#: Límite de tareas por consulta (evita traer un portafolio entero por error).
TASK_LIMIT_PARAM = 'al_gantt.task_limit'
DEFAULT_TASK_LIMIT = 2000
MAX_TASK_LIMIT = 20000

#: Tope de personas ofrecidas en el formulario para asignar una tarea.
ASSIGNABLE_USER_LIMIT = 500

#: Versión del contrato de datos. Súbela si cambia la forma de la respuesta.
#: 2: se añaden `filters` (valores disponibles) y `applied_filters` (eco).
#: 3: se añaden `baselines`, `calendar` y los extras de `meta` (edición, CPM).
#: 4: campos de tarea para el formulario (prioridad, etiquetas, cliente,
#:    actividades) y opciones de etapas/prioridades/etiquetas en `filters`.
#: 5: `filters.assignable_users` — todas las personas asignables, aparte de
#:    las que ya tienen tareas (`filters.users`, que alimenta el filtro).
CONTRACT_VERSION = 5


class GanttData(models.AbstractModel):
    _name = 'al.gantt.data'
    _description = 'Gantt — servicio de datos'

    # ------------------------------------------------------------------
    # Seguridad
    # ------------------------------------------------------------------
    @api.model
    def _check_gantt_access(self):
        """Usuario interno con el grupo del Gantt. Punto de extensión."""
        user = self.env.user
        if user.share:
            raise AccessError(_("El Gantt de proyectos solo está disponible para usuarios internos."))
        if not user.has_group(GROUP_GANTT_USER):
            raise AccessError(_("No tiene permiso para consultar el Gantt de proyectos."))

    # ------------------------------------------------------------------
    # Opciones y dominios
    # ------------------------------------------------------------------
    @api.model
    def _get_task_limit(self, options):
        limit = (options or {}).get('limit')
        if not limit:
            raw = self.env['ir.config_parameter'].sudo().get_param(TASK_LIMIT_PARAM)
            try:
                limit = int(raw) if raw else DEFAULT_TASK_LIMIT
            except (TypeError, ValueError):
                _logger.warning("%s no es entero; se usa %s", TASK_LIMIT_PARAM, DEFAULT_TASK_LIMIT)
                limit = DEFAULT_TASK_LIMIT
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            raise UserError(_("El límite de tareas debe ser un número entero."))
        if limit <= 0:
            limit = DEFAULT_TASK_LIMIT
        return min(limit, MAX_TASK_LIMIT)

    @api.model
    def _get_project_domain(self, project_ids=None, options=None):
        domain = [('is_template', '=', False)]
        if project_ids:
            domain.append(('id', 'in', list(project_ids)))
        return domain

    @api.model
    def _get_task_domain(self, project_ids, field_map, options, with_date_range=True):
        """Dominio de tareas. Punto de extensión para filtros adicionales.

        ``with_date_range=False`` omite el filtro por rango de fechas: se usa
        para contar las tareas sin fecha, a las que ese filtro no puede aplicar.
        """
        options = options or {}
        domain = [('project_id', 'in', list(project_ids))]

        states = options.get('states')
        if states:
            domain.append(('state', 'in', list(states)))

        user_ids = options.get('user_ids')
        if user_ids:
            domain.append(('user_ids', 'in', list(user_ids)))

        if not with_date_range:
            return domain

        date_from = options.get('date_from')
        date_to = options.get('date_to')
        start_field = field_map['date_start']
        end_field = field_map['date_end']
        # Una tarea entra en el rango si se solapa con él, no solo si empieza
        # dentro. Sin campo de inicio, el solapamiento se evalúa sobre el fin.
        if date_to and (start_field or end_field):
            domain.append(((start_field or end_field), '<=', date_to))
        if date_from and end_field:
            domain.append((end_field, '>=', date_from))
        return domain

    # ------------------------------------------------------------------
    # Utilidades de serialización
    # ------------------------------------------------------------------
    @api.model
    def _iso(self, value):
        """Datetime del ORM (naive UTC) -> cadena ISO 8601 en UTC."""
        if not value:
            return None
        return value.isoformat(sep='T', timespec='seconds') + 'Z'

    @api.model
    def _m2o(self, value):
        """``search_read`` devuelve m2o como ``(id, nombre)``; normaliza a par."""
        if not value:
            return (None, None)
        if isinstance(value, (list, tuple)):
            return (value[0], value[1] if len(value) > 1 else None)
        if isinstance(value, int):
            return (value, None)
        return (None, None)

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------
    @api.model
    def get_data(self, project_ids=None, options=None):
        """Devuelve el conjunto de datos del Gantt ya normalizado.

        :param project_ids: ids de ``project.project``; ``None`` = todos los
            visibles para el usuario.
        :param options: ``date_from``, ``date_to``, ``user_ids``, ``states``,
            ``include_undated``, ``limit``.
        :rtype: dict
        """
        self._check_gantt_access()
        options = dict(options or {})

        field_map = self.env['al.gantt.field.map'].get_map()
        projects = self._read_projects(project_ids, options)
        accessible_ids = [project['id'] for project in projects]

        if not accessible_ids:
            return self._empty_payload(field_map, projects)

        tasks, meta = self._read_tasks(accessible_ids, field_map, options)
        task_ids = {task['id'] for task in tasks}
        links = self._read_links(tasks, task_ids)  # consume 'depend_on_ids' de cada tarea

        # Extras «pro», solo si se piden: cuestan una pasada extra sobre los
        # datos ya leídos, no consultas nuevas (salvo la línea base).
        meta['critical_path'] = (
            self._apply_critical_path(tasks, links)
            if options.get('critical_path') else {'computed': False}
        )
        meta['baseline'] = (
            self._apply_baseline(tasks, options['baseline_id'])
            if options.get('baseline_id') else {'applied': False}
        )

        payload = {
            'contract_version': CONTRACT_VERSION,
            'field_map': field_map,
            'projects': projects,
            'tasks': tasks,
            'links': links,
            'milestones': self._read_milestones(accessible_ids),
            'colors': {
                'states': self.env['al.gantt.state.color'].get_color_map(),
                'fallback': self.env['al.gantt.state.color'].get_fallback(),
            },
            'filters': self._read_filter_options(accessible_ids),
            'applied_filters': self._get_applied_filters(options),
            'baselines': self._read_baselines(accessible_ids),
            'calendar': self._read_calendar(accessible_ids),
            'meta': meta,
        }
        return payload

    @api.model
    def _empty_payload(self, field_map, projects):
        return {
            'contract_version': CONTRACT_VERSION,
            'field_map': field_map,
            'projects': projects,
            'tasks': [],
            'links': [],
            'milestones': [],
            'colors': {
                'states': self.env['al.gantt.state.color'].get_color_map(),
                'fallback': self.env['al.gantt.state.color'].get_fallback(),
            },
            'filters': self._read_filter_options([]),
            'applied_filters': self._get_applied_filters(None),
            'baselines': [],
            'calendar': self._read_calendar([]),
            'meta': {
                'count': 0, 'total': 0, 'limit': self._get_task_limit(None),
                'truncated': False, 'undated_count': 0,
                'tz': self.env.user.tz or 'UTC', 'editable': False,
                'can_create': False, 'can_reschedule_chain': False,
            },
        }

    # ------------------------------------------------------------------
    # Opciones de filtrado
    # ------------------------------------------------------------------
    @api.model
    def _read_filter_options(self, project_ids):
        """Valores disponibles para los desplegables de la interfaz.

        Se calculan en el servidor para que las dos UIs pinten lo mismo sin
        hardcodear estados ni consultar el ORM por su cuenta.

        Hay **dos listas de personas** a propósito:

        * ``users``: las que ya tienen tareas en los proyectos consultados. Es
          lo útil para *filtrar* — ofrecer gente sin tareas solo da resultados
          vacíos.
        * ``assignable_users``: todas las que se pueden asignar, con el mismo
          dominio que el campo ``user_ids`` de la tarea
          (``share = False`` y ``active = True``). Es lo que necesita el
          *formulario* para poder asignar a alguien nuevo.
        """
        states = [
            {'value': value, 'label': label}
            for value, label in self.env['project.task']._fields['state']._description_selection(self.env)
        ]
        priorities = [
            {'value': value, 'label': label}
            for value, label in self.env['project.task']._fields['priority']._description_selection(self.env)
        ]
        stages = self.env['project.task.type'].search_read(
            [('project_ids', 'in', list(project_ids))] if project_ids else [],
            ['id', 'name'], order='sequence, id',
        ) if project_ids else []
        tags = self.env['project.tags'].search_read([], ['id', 'name'], order='name', limit=200)

        # Mismo dominio que el campo user_ids de project.task. Sin sudo: las
        # reglas de res.users acotan a las compañías del usuario, que es
        # exactamente a quién puede asignar.
        assignable = self.env['res.users'].search_read(
            [('share', '=', False), ('active', '=', True)],
            ['id', 'name'], order='name', limit=ASSIGNABLE_USER_LIMIT,
        )

        users = []
        if project_ids:
            groups = self.env['project.task']._read_group(
                [('project_id', 'in', list(project_ids)), ('user_ids', '!=', False)],
                groupby=['user_ids'],
                aggregates=['__count'],
            )
            users = [
                {'id': user.id, 'name': user.display_name, 'task_count': count}
                for user, count in groups if user
            ]
            users.sort(key=lambda item: item['name'] or '')
        return {
            'states': states,
            'users': users,
            'assignable_users': [{'id': user['id'], 'name': user['name']} for user in assignable],
            'priorities': priorities,
            'stages': [{'id': stage['id'], 'name': stage['name']} for stage in stages],
            'tags': [{'id': tag['id'], 'name': tag['name']} for tag in tags],
        }

    @api.model
    def _get_applied_filters(self, options):
        """Eco de los filtros aplicados, para que la interfaz pueda repintarse."""
        options = options or {}
        return {
            'date_from': options.get('date_from') or None,
            'date_to': options.get('date_to') or None,
            'user_ids': list(options.get('user_ids') or []),
            'states': list(options.get('states') or []),
            'include_undated': bool(options.get('include_undated')),
        }

    # ------------------------------------------------------------------
    # Proyectos
    # ------------------------------------------------------------------
    @api.model
    def _read_projects(self, project_ids, options):
        domain = self._get_project_domain(project_ids, options)
        records = self.env['project.project'].search_read(
            domain,
            ['id', 'name', 'date_start', 'date', 'company_id'],
            order='name',
        )
        counts = {}
        if records:
            groups = self.env['project.task']._read_group(
                [('project_id', 'in', [record['id'] for record in records])],
                groupby=['project_id'],
                aggregates=['__count'],
            )
            counts = {project.id: count for project, count in groups}

        projects = []
        for record in records:
            company_id, company_name = self._m2o(record.get('company_id'))
            projects.append({
                'id': record['id'],
                'name': record['name'],
                'date_start': record['date_start'].isoformat() if record.get('date_start') else None,
                'date_end': record['date'].isoformat() if record.get('date') else None,
                'company_id': company_id,
                'company_name': company_name,
                'task_count': counts.get(record['id'], 0),
            })
        return projects

    # ------------------------------------------------------------------
    # Tareas
    # ------------------------------------------------------------------
    @api.model
    def _get_task_fields(self, field_map):
        """Lista explícita de campos a leer (sin ``fields=None``, que traería todo)."""
        field_names = [
            'id', 'name', 'project_id', 'parent_id', 'state', 'stage_id',
            'user_ids', 'allocated_hours', 'depend_on_ids', 'milestone_id',
            'sequence', 'priority', 'tag_ids', 'partner_id',
            'activity_state', 'activity_summary', 'activity_type_icon',
        ]
        for key in ('date_start', 'date_end', 'progress'):
            if field_map[key] and field_map[key] not in field_names:
                field_names.append(field_map[key])
        return field_names

    @api.model
    def _read_tasks(self, project_ids, field_map, options):
        Task = self.env['project.task']
        limit = self._get_task_limit(options)
        domain = self._get_task_domain(project_ids, field_map, options)
        include_undated = bool(options.get('include_undated'))
        end_field = field_map['date_end']

        # Las tareas sin fecha de fin se cuentan siempre, incluso cuando quedan
        # fuera del resultado: la interfaz debe poder avisar de que existen.
        undated_domain = self._get_task_domain(
            project_ids, field_map, options, with_date_range=False,
        )
        if end_field:
            undated_domain = undated_domain + [(end_field, '=', False)]
        undated_total = Task.search_count(undated_domain)

        if not include_undated:
            if end_field:
                domain = domain + [(end_field, '!=', False)]
            else:
                # Sin campo de fin (mode='none') no hay barra posible: nada que
                # dibujar salvo que se pidan explícitamente las tareas sin fecha.
                return [], {
                    'count': 0, 'total': Task.search_count(domain), 'limit': limit,
                    'truncated': False, 'undated_count': undated_total,
                    'tz': self.env.user.tz or 'UTC', 'editable': False,
                    'can_create': False, 'can_reschedule_chain': False,
                    'can_edit_progress': False,
                }

        total = Task.search_count(domain)
        order = f"project_id, {field_map['date_start'] or end_field or 'sequence'}, sequence, id"
        records = Task.search_read(
            domain, self._get_task_fields(field_map), limit=limit, order=order,
        )

        # Permiso real de escritura, resuelto en bloque (una consulta) en vez de
        # tarea por tarea: es lo que decide si la barra se puede arrastrar.
        editable_ids = set(Task.browse([record['id'] for record in records])
                           ._filtered_access('write').ids)
        user_names = self._read_user_names(records)
        duration = timedelta(hours=self.env['al.gantt.field.map'].get_default_duration_hours())
        colors = self.env['al.gantt.state.color'].get_color_map()
        fallback = self.env['al.gantt.state.color'].get_fallback()
        present_ids = {record['id'] for record in records}

        tasks = []
        for record in records:
            start_raw = record.get(field_map['date_start']) if field_map['date_start'] else None
            end_raw = record.get(end_field) if end_field else None
            start_inferred = False
            if end_raw and not start_raw:
                start_raw = end_raw - duration
                start_inferred = True

            progress, progress_derived = self._compute_progress(record, field_map)
            stage_id, stage_name = self._m2o(record.get('stage_id'))
            parent_id, _parent_name = self._m2o(record.get('parent_id'))
            project_id, project_name = self._m2o(record.get('project_id'))
            milestone_id, milestone_name = self._m2o(record.get('milestone_id'))
            partner_id, partner_name = self._m2o(record.get('partner_id'))
            color = colors.get(record['state'], fallback)

            tasks.append({
                'id': record['id'],
                'name': record['name'],
                'project_id': project_id,
                'project_name': project_name,
                # Si el padre quedó fuera del conjunto (filtro o límite), la
                # tarea se emite como raíz para no perderla en el árbol.
                'parent_id': parent_id if parent_id in present_ids else None,
                'orphaned': bool(parent_id) and parent_id not in present_ids,
                'start': self._iso(start_raw),
                'end': self._iso(end_raw),
                'start_is_inferred': start_inferred,
                'undated': not end_raw,
                'is_milestone': bool(start_raw and end_raw and start_raw == end_raw),
                'progress': progress,
                'progress_is_derived': progress_derived,
                'state': record['state'],
                'stage_id': stage_id,
                'stage_name': stage_name,
                'milestone_id': milestone_id,
                'milestone_name': milestone_name,
                'color': color['color'],
                'text_color': color['text_color'],
                'user_ids': [
                    {'id': user_id, 'name': user_names.get(user_id, '')}
                    for user_id in record.get('user_ids', [])
                ],
                'allocated_hours': record.get('allocated_hours', 0.0),
                'priority': record.get('priority') or '0',
                'tag_ids': record.get('tag_ids', []),
                'partner_id': partner_id,
                'partner_name': partner_name,
                # Actividades pendientes (mail.activity): estado, resumen e icono.
                'activity_state': record.get('activity_state') or False,
                'activity_summary': record.get('activity_summary') or '',
                'activity_icon': record.get('activity_type_icon') or '',
                'depend_on_ids': record.get('depend_on_ids', []),
                'editable': record['id'] in editable_ids,
            })

        meta = {
            'count': len(tasks),
            'total': total,
            'limit': limit,
            'truncated': total > len(tasks),
            'undated_count': undated_total,
            'tz': self.env.user.tz or 'UTC',
            # La edición se decide por tarea (`editable`); estas banderas solo
            # dicen si la interfaz debe ofrecer las herramientas de edición.
            'editable': bool(editable_ids),
            'can_create': Task.has_access('create'),
            'can_reschedule_chain': bool(field_map['date_start'] and field_map['date_end']),
            # El avance solo se puede editar si existe el campo real; si es
            # derivado del estado, el formulario no debe ofrecerlo.
            'can_edit_progress': bool(field_map['progress']),
        }
        return tasks, meta

    @api.model
    def _read_user_names(self, records):
        """Nombres de los responsables en una sola consulta (sin N+1)."""
        user_ids = {user_id for record in records for user_id in record.get('user_ids', [])}
        if not user_ids:
            return {}
        # active_test=False: un responsable dado de baja sigue figurando en sus
        # tareas y debe mostrarse con nombre, no en blanco.
        rows = self.env['res.users'].sudo().with_context(active_test=False).search_read(
            [('id', 'in', list(user_ids))], ['id', 'name'],
        )
        # sudo() acotado y justificado: solo se lee el nombre de usuarios que ya
        # figuran como responsables de tareas que el usuario puede ver; sin él,
        # un empleado sin acceso a res.users vería el Gantt sin responsables.
        return {row['id']: row['name'] for row in rows}

    @api.model
    def _compute_progress(self, record, field_map):
        """Avance real si el campo existe (``hr_timesheet``); si no, derivado."""
        if field_map['progress']:
            return record.get(field_map['progress']) or 0.0, False
        return (100.0 if record['state'] in CLOSED_STATES else 0.0), True

    # ------------------------------------------------------------------
    # Dependencias e hitos
    # ------------------------------------------------------------------
    @api.model
    def _read_links(self, tasks, task_ids):
        """Dependencias derivadas de ``depend_on_ids`` (fin-comienzo).

        Solo se emiten enlaces cuyos dos extremos están en el conjunto leído;
        el M2M nativo no guarda tipo ni retraso, así que todas son FS.
        """
        links = []
        for task in tasks:
            for source_id in task.pop('depend_on_ids', []):
                if source_id in task_ids:
                    links.append({
                        'id': f"{source_id}-{task['id']}",
                        'source': source_id,
                        'target': task['id'],
                        'type': 'FS',
                    })
        return links

    @api.model
    def _read_milestones(self, project_ids):
        records = self.env['project.milestone'].search_read(
            [('project_id', 'in', list(project_ids))],
            ['id', 'name', 'project_id', 'deadline', 'is_reached'],
            order='deadline',
        )
        milestones = []
        for record in records:
            project_id, project_name = self._m2o(record.get('project_id'))
            milestones.append({
                'id': record['id'],
                'name': record['name'],
                'project_id': project_id,
                'project_name': project_name,
                'date': record['deadline'].isoformat() if record.get('deadline') else None,
                'is_reached': record['is_reached'],
            })
        return milestones
