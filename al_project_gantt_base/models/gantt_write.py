# -*- coding: utf-8 -*-
"""Capa de escritura del Gantt.

Extiende ``al.gantt.data`` con un único punto de entrada, ``apply_changes``,
que recibe el *changeset* que produce la interfaz y lo traduce a operaciones del
ORM. Igual que en la lectura, **no se usa** ``sudo()``: cada operación se
comprueba contra los permisos reales del usuario sobre esa tarea, de modo que
mandan la ACL y las ``ir.rule`` nativas de ``project``.

Formato del *changeset*::

    {
      "tasks": {
        "update": [{"id": 12, "start": "...Z", "end": "...Z", "name": "...",
                     "progress": 40.0, "parent_id": 8}],
        "create": [{"temp_id": "tmp1", "project_id": 5, "name": "...",
                     "start": "...Z", "end": "...Z", "parent_id": 8}],
        "delete": [13, 14]
      },
      "links": {
        "create": [{"source": 1, "target": 2}],
        "delete": [{"source": 1, "target": 2}]
      },
      "reschedule_chain": true
    }
"""
import logging
from datetime import datetime, timezone

from markupsafe import escape

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

#: Tope de tareas desplazadas por una sola reprogramación en cadena.
MAX_CHAIN_MOVES = 500

#: Campos de tarea que la interfaz puede escribir directamente.
WRITABLE_TASK_FIELDS = ('name', 'parent_id', 'priority')


class GanttWrite(models.AbstractModel):
    _inherit = 'al.gantt.data'

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    @api.model
    def _parse_datetime(self, value, label):
        """Cadena ISO (UTC) del cliente -> datetime naive UTC del ORM."""
        if not value:
            return False
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        text = str(value).strip().replace('Z', '+00:00').replace(' ', 'T', 1)
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            raise UserError(_("Fecha no válida en %(label)s: %(value)s",
                              label=label, value=value))
        if parsed.tzinfo is not None:
            # El ORM guarda datetimes naive en UTC.
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    @api.model
    def _check_writable(self, tasks, operation='write'):
        """Permiso real sobre cada tarea; sin esto no se toca nada."""
        if not tasks:
            return
        allowed = tasks._filtered_access(operation)
        forbidden = tasks - allowed
        if forbidden:
            raise AccessError(_(
                "No tiene permiso para modificar estas tareas: %s",
                ", ".join(forbidden.mapped('display_name')),
            ))

    @api.model
    def _require_date_fields(self, field_map):
        if not field_map['date_end']:
            raise UserError(_(
                "No se pueden guardar fechas: la instalación no tiene un campo "
                "de fecha de fin configurado para las tareas."
            ))
        if not field_map['date_start']:
            raise UserError(_(
                "No se pueden mover las barras: la instalación no tiene un campo "
                "de fecha de inicio (lo aporta el módulo de planificación de "
                "proyectos). Solo se puede editar la fecha límite."
            ))

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------
    @api.model
    def apply_changes(self, changeset=None):
        """Aplica el changeset y devuelve el resultado de cada operación."""
        self._check_gantt_access()
        changeset = dict(changeset or {})
        field_map = self.env['al.gantt.field.map'].get_map()

        tasks_changes = changeset.get('tasks') or {}
        links_changes = changeset.get('links') or {}

        result = {
            'ok': True,
            'created': {},
            'updated': [],
            'deleted': [],
            'links_created': [],
            'links_deleted': [],
            'rescheduled': [],
            'warnings': [],
        }

        created = self._apply_task_creates(tasks_changes.get('create') or [], field_map, result)
        result['created'] = created

        moved = self._apply_task_updates(tasks_changes.get('update') or [], field_map, result)

        self._apply_task_deletes(tasks_changes.get('delete') or [], result)
        self._apply_link_changes(links_changes, result)

        if changeset.get('reschedule_chain') and moved:
            self._reschedule_successors(moved, field_map, result)

        return result

    # ------------------------------------------------------------------
    # Tareas
    # ------------------------------------------------------------------
    @api.model
    def _values_from_payload(self, values, field_map, for_create=False):
        """Traduce un elemento del changeset a valores del ORM."""
        orm_values = {}

        if 'name' in values:
            name = (values.get('name') or '').strip()
            if not name:
                raise UserError(_("El nombre de la tarea no puede quedar vacío."))
            orm_values['name'] = name

        has_start = 'start' in values
        has_end = 'end' in values
        if has_start or has_end:
            self._require_date_fields(field_map)
        start = self._parse_datetime(values.get('start'), _("fecha de inicio")) if has_start else None
        end = self._parse_datetime(values.get('end'), _("fecha de fin")) if has_end else None
        if start and end and start > end:
            raise UserError(_("La fecha de inicio no puede ser posterior a la de fin."))
        if has_start:
            orm_values[field_map['date_start']] = start
        if has_end:
            orm_values[field_map['date_end']] = end

        if 'progress' in values and field_map['progress']:
            # El avance solo se guarda si el campo existe de verdad (hr_timesheet);
            # si no, es un valor derivado del estado y no tiene dónde escribirse.
            orm_values[field_map['progress']] = max(0.0, min(100.0, float(values['progress'] or 0.0)))

        if 'parent_id' in values:
            orm_values['parent_id'] = values['parent_id'] or False

        if 'user_ids' in values:
            orm_values['user_ids'] = [(6, 0, [int(user_id) for user_id in values['user_ids'] or []])]

        if 'tag_ids' in values:
            orm_values['tag_ids'] = [(6, 0, [int(tag_id) for tag_id in values['tag_ids'] or []])]

        if 'stage_id' in values:
            orm_values['stage_id'] = int(values['stage_id']) if values['stage_id'] else False

        if 'partner_id' in values:
            orm_values['partner_id'] = int(values['partner_id']) if values['partner_id'] else False

        if 'description' in values:
            # El campo es HTML; el formulario del diagrama envía texto plano.
            text = (values.get('description') or '').strip()
            orm_values['description'] = f"<p>{escape(text)}</p>" if text else False

        if 'allocated_hours' in values:
            orm_values['allocated_hours'] = float(values['allocated_hours'] or 0.0)

        if for_create:
            if not values.get('project_id'):
                raise UserError(_("Toda tarea nueva necesita un proyecto."))
            orm_values['project_id'] = values['project_id']
            orm_values.setdefault('name', _("Tarea nueva"))

        for field in WRITABLE_TASK_FIELDS:
            if field in values and field not in orm_values:
                orm_values[field] = values[field]
        return orm_values

    @api.model
    def _apply_task_creates(self, creates, field_map, result):
        if not creates:
            return {}
        Task = self.env['project.task']
        Task.check_access('create')

        temp_ids = []
        values_list = []
        for item in creates:
            temp_ids.append(item.get('temp_id') or item.get('id'))
            values_list.append(self._values_from_payload(item, field_map, for_create=True))

        records = Task.create(values_list)
        # `create` respeta ACL, pero no las ir.rule de escritura: se comprueba
        # que las tareas creadas sean realmente accesibles para este usuario.
        self._check_writable(records, 'write')
        return {str(temp_id): record.id for temp_id, record in zip(temp_ids, records) if temp_id}

    @api.model
    def _apply_task_updates(self, updates, field_map, result):
        """Devuelve las tareas cuyas fechas se movieron (para la cadena)."""
        if not updates:
            return self.env['project.task']
        Task = self.env['project.task']
        task_ids = [item['id'] for item in updates if item.get('id')]
        tasks = Task.browse(task_ids).exists()
        self._check_writable(tasks, 'write')

        moved_ids = []
        for item in updates:
            if not item.get('id'):
                continue
            task = Task.browse(item['id'])
            if not task.exists():
                result['warnings'].append(_("Una tarea ya no existe y se omitió."))
                continue
            values = self._values_from_payload(item, field_map)
            if not values:
                continue
            task.write(values)
            result['updated'].append(task.id)
            if field_map['date_end'] in values or (field_map['date_start'] or '') in values:
                moved_ids.append(task.id)
        return Task.browse(moved_ids)

    @api.model
    def _apply_task_deletes(self, deletes, result):
        if not deletes:
            return
        tasks = self.env['project.task'].browse([int(task_id) for task_id in deletes]).exists()
        self._check_writable(tasks, 'unlink')
        deleted_ids = tasks.ids
        tasks.unlink()
        result['deleted'].extend(deleted_ids)

    # ------------------------------------------------------------------
    # Dependencias
    # ------------------------------------------------------------------
    @api.model
    def _apply_link_changes(self, links_changes, result):
        Task = self.env['project.task']
        for link in links_changes.get('create') or []:
            source_id, target_id = int(link['source']), int(link['target'])
            target = Task.browse(target_id).exists()
            source = Task.browse(source_id).exists()
            if not target or not source:
                result['warnings'].append(_("Se omitió una dependencia con tareas inexistentes."))
                continue
            self._check_writable(target, 'write')
            if source in target.depend_on_ids:
                continue
            # La detección de ciclos la hace la restricción nativa de project.
            target.write({'depend_on_ids': [(4, source.id)]})
            result['links_created'].append({'source': source.id, 'target': target.id, 'type': 'FS'})

        for link in links_changes.get('delete') or []:
            source_id, target_id = int(link['source']), int(link['target'])
            target = Task.browse(target_id).exists()
            if not target:
                continue
            self._check_writable(target, 'write')
            target.write({'depend_on_ids': [(3, source_id)]})
            result['links_deleted'].append({'source': source_id, 'target': target_id})

    # ------------------------------------------------------------------
    # Reprogramación en cadena
    # ------------------------------------------------------------------
    @api.model
    def _reschedule_successors(self, moved_tasks, field_map, result):
        """Empuja las tareas dependientes para respetar el fin-comienzo.

        Política (documentada, porque la librería MIT no trae *auto-scheduling*):
        una sucesora nunca empieza antes de que termine su predecesora; si se
        solapa, se desplaza **manteniendo su duración**. No se adelanta nada:
        mover una tarea hacia atrás no comprime el plan.
        """
        start_field, end_field = field_map['date_start'], field_map['date_end']
        if not start_field or not end_field:
            return

        pending = list(moved_tasks)
        moves = 0
        visited = set()

        while pending:
            task = pending.pop(0)
            task_end = task[end_field]
            if not task_end:
                continue
            for successor in task.dependent_ids:
                if moves >= MAX_CHAIN_MOVES:
                    result['warnings'].append(_(
                        "La reprogramación en cadena se detuvo tras %s movimientos.",
                        MAX_CHAIN_MOVES,
                    ))
                    return
                successor_start = successor[start_field]
                successor_end = successor[end_field]
                if not successor_start or not successor_end:
                    continue
                if successor_start >= task_end:
                    continue  # no hay solapamiento: nada que empujar
                if not successor.has_access('write'):
                    result['warnings'].append(_(
                        "«%s» se solapa con su predecesora pero no tiene permiso "
                        "para moverla.", successor.display_name,
                    ))
                    continue
                duration = successor_end - successor_start
                new_start = task_end
                new_end = new_start + duration
                successor.write({start_field: new_start, end_field: new_end})
                moves += 1
                result['rescheduled'].append({
                    'id': successor.id,
                    'start': self._iso(new_start),
                    'end': self._iso(new_end),
                })
                key = successor.id
                if key not in visited:
                    visited.add(key)
                    pending.append(successor)
