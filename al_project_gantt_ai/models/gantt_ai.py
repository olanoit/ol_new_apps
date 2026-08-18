# -*- coding: utf-8 -*-
"""Asistente de IA del Gantt.

Punto de entrada único: ``al.gantt.ai.ask()``. Recibe la pregunta y los ids de
las tareas que el usuario está viendo, arma un **resumen** del cronograma, lo
manda al proveedor y devuelve la respuesta más una lista de **propuestas de
cambio ya validadas**.

Tres reglas que no se negocian:

1. **La IA no escribe.** Este modelo no llama nunca a ``apply_changes``. Las
   propuestas viajan al cliente, el usuario marca las que quiere y la
   escritura pasa por ``project.project.apply_gantt_changes()``, que comprueba
   los permisos de cada tarea igual que al arrastrar una barra.
2. **Solo se manda lo que se ve, resumido.** Las tareas se releen desde el ORM
   *con el usuario real* y acotadas a los ids que envía el cliente: si alguien
   manipula la petición, las reglas de registro de ``project`` recortan el
   resultado. De cada tarea salen nombre, fechas, estado, avance, dependencias
   y —si se activa— las personas asignadas. Nada más.
3. **La salida del modelo es entrada no confiable.** Todo lo que devuelve pasa
   por ``_normalize_proposal``: ids que no están en el contexto, fechas mal
   formadas o valores fuera de rango se descartan con un aviso.
"""
import logging
from datetime import datetime, timezone

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services import ai_provider

_logger = logging.getLogger(__name__)

PARAM_PREFIX = 'al_gantt_ai.'

#: Valores por defecto de la configuración (parámetros del sistema).
DEFAULTS = {
    'provider': 'anthropic',
    'effort': 'medium',
    'max_tokens': 8000,
    'timeout': 90,
    'context_limit': 200,
    'share_assignees': True,
}

#: Topes de la petición del cliente.
MAX_QUESTION_CHARS = 2000
MAX_HISTORY_TURNS = 10
MAX_HISTORY_CHARS = 4000

#: Campos que el asistente puede proponer cambiar.
PROPOSABLE_FIELDS = ('start', 'end', 'progress', 'name', 'user_ids')

#: Personas asignables que se listan en el prompt (para poder reasignar).
ASSIGNABLE_IN_PROMPT = 100


class GanttAi(models.AbstractModel):
    _name = 'al.gantt.ai'
    _description = 'Gantt — asistente de IA'

    # ------------------------------------------------------------------
    # Configuración
    # ------------------------------------------------------------------
    @api.model
    def _get_param(self, key, default=None):
        # sudo() acotado: los parámetros del sistema no son legibles por un
        # empleado normal, y la clave nunca sale de este proceso.
        value = self.env['ir.config_parameter'].sudo().get_param(PARAM_PREFIX + key)
        return value if value not in (None, '', False) else default

    @api.model
    def _get_int_param(self, key):
        raw = self._get_param(key)
        try:
            return int(raw) if raw else DEFAULTS[key]
        except (TypeError, ValueError):
            _logger.warning("%s%s no es un entero; se usa %s", PARAM_PREFIX, key, DEFAULTS[key])
            return DEFAULTS[key]

    @api.model
    def _get_config(self):
        """Configuración efectiva, con la clave incluida. No se expone al cliente."""
        provider = self._get_param('provider', DEFAULTS['provider'])
        return {
            'provider': provider,
            'api_key': self._get_param('api_key'),
            'model': self._get_param('model', ai_provider.DEFAULT_MODEL.get(provider)),
            'base_url': self._get_param('base_url'),
            'effort': self._get_param('effort', DEFAULTS['effort']),
            'max_tokens': self._get_int_param('max_tokens'),
            'timeout': self._get_int_param('timeout'),
            'context_limit': self._get_int_param('context_limit'),
            'share_assignees': self._get_param(
                'share_assignees', str(DEFAULTS['share_assignees'])
            ) not in ('False', 'false', '0'),
        }

    @api.model
    def get_status(self):
        """Lo que el cliente necesita saber para decidir si pinta el panel.

        Nunca devuelve la clave ni la URL: solo si está listo y con qué modelo.
        """
        self.env['al.gantt.data']._check_gantt_access()
        config = self._get_config()
        return {
            'enabled': bool(config['api_key'] and config['model']),
            'provider': config['provider'],
            'model': config['model'],
            'share_assignees': config['share_assignees'],
            'context_limit': config['context_limit'],
        }

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------
    @api.model
    def ask(self, payload=None):
        """Responde una pregunta sobre el cronograma visible.

        :param dict payload: ``question`` (str), ``task_ids`` (list[int]),
            ``project_ids`` (list[int], solo informativo), ``history``
            (list[{role, content}]).
        :returns: ``{'answer', 'proposals', 'warnings', 'usage', 'context'}``
        """
        self.env['al.gantt.data']._check_gantt_access()
        payload = dict(payload or {})

        question = (payload.get('question') or '').strip()
        if not question:
            raise UserError(_("Escriba una pregunta."))
        if len(question) > MAX_QUESTION_CHARS:
            raise UserError(_(
                "La pregunta es demasiado larga (%(length)s caracteres, máximo %(max)s).",
                length=len(question), max=MAX_QUESTION_CHARS,
            ))

        config = self._get_config()
        if not config['api_key']:
            raise UserError(_(
                "El asistente de IA no está configurado. Un administrador debe indicar "
                "la clave de API en Ajustes ▸ Gantt IA."
            ))
        if not config['model']:
            raise UserError(_("Falta indicar el modelo de IA en Ajustes ▸ Gantt IA."))

        context = self._build_context(payload.get('task_ids') or [], config)
        if not context['tasks']:
            raise UserError(_(
                "No hay tareas visibles que enviar al asistente. Seleccione un proyecto "
                "con tareas antes de preguntar."
            ))

        messages = self._build_messages(payload.get('history') or [], question)
        answer, raw_proposal, usage = ai_provider.call_provider(
            self.env, config, self._build_system_prompt(context, config), messages,
        )

        proposals, warnings = self._normalize_proposal(raw_proposal, context)
        if not answer and not proposals:
            answer = _("El asistente no devolvió ninguna respuesta.")

        return {
            'answer': answer,
            'summary': (raw_proposal or {}).get('summary') or '',
            'proposals': proposals,
            'warnings': warnings + context['warnings'],
            'usage': usage,
            'context': {
                'task_count': len(context['tasks']),
                'truncated': context['truncated'],
            },
        }

    # ------------------------------------------------------------------
    # Contexto: lo que se manda al proveedor
    # ------------------------------------------------------------------
    @api.model
    def _build_context(self, task_ids, config):
        """Resumen de las tareas visibles, releídas con los permisos del usuario."""
        warnings = []
        try:
            requested = [int(task_id) for task_id in task_ids]
        except (TypeError, ValueError):
            raise UserError(_("La lista de tareas no es válida."))

        limit = config['context_limit']
        truncated = len(requested) > limit
        if truncated:
            requested = requested[:limit]
            warnings.append(_(
                "Se enviaron las primeras %(limit)s tareas de las %(total)s visibles; "
                "filtre el diagrama para preguntar por el resto.",
                limit=limit, total=len(task_ids),
            ))

        field_map = self.env['al.gantt.field.map'].get_map()
        Task = self.env['project.task']
        # Sin sudo, y acotado a los ids pedidos: si el cliente inventa ids, las
        # reglas de registro de `project` los dejan fuera del resultado.
        records = Task.search(
            [('id', 'in', requested)],
            order='project_id, %s, id' % (field_map['date_start'] or field_map['date_end'] or 'sequence'),
        )
        if len(records) < len(requested):
            warnings.append(_("Algunas tareas ya no son accesibles y no se enviaron."))

        present_ids = set(records.ids)
        data = self.env['al.gantt.data']
        state_labels = dict(
            Task._fields['state']._description_selection(self.env)
        )

        tasks = []
        for record in records:
            start = record[field_map['date_start']] if field_map['date_start'] else False
            end = record[field_map['date_end']] if field_map['date_end'] else False
            progress = (
                record[field_map['progress']] if field_map['progress']
                else (100.0 if record.state in ('1_done', '1_canceled') else 0.0)
            )
            entry = {
                'id': record.id,
                'name': record.name,
                'project': record.project_id.display_name or '',
                'start': data._iso(start),
                'end': data._iso(end),
                'state': state_labels.get(record.state, record.state),
                'progress': round(progress or 0.0, 1),
                'depends_on': [
                    dependency.id for dependency in record.depend_on_ids
                    if dependency.id in present_ids
                ],
                'editable': record.has_access('write'),
            }
            if config['share_assignees']:
                entry['assignees'] = record.user_ids.mapped('name')
            tasks.append(entry)

        return {
            'tasks': tasks,
            'by_id': {task['id']: task for task in tasks},
            'truncated': truncated,
            'warnings': warnings,
            # Solo hacen falta para que el modelo pueda proponer reasignaciones,
            # y cada nombre cuesta tokens en todas las preguntas: se recorta.
            # El dominio no se duplica aquí; sale del módulo base.
            'assignable_users': (
                self.env['al.gantt.data']._read_filter_options([])
                ['assignable_users'][:ASSIGNABLE_IN_PROMPT]
                if config['share_assignees'] else []
            ),
        }

    @api.model
    def _build_system_prompt(self, context, config):
        """Instrucciones + datos. El contexto va en el sistema, no en el turno.

        Así el historial de la conversación queda limpio y el prefijo estable
        (instrucciones + tareas) es el mismo entre preguntas de una sesión.
        """
        today = fields.Date.context_today(self)
        lines = [
            "Eres un asistente de planificación integrado en un diagrama de Gantt de "
            "Odoo. Respondes en el idioma de la persona y con frases cortas.",
            "",
            "Qué puedes hacer:",
            "- Responder preguntas sobre el cronograma que aparece más abajo: "
            "solapamientos, retrasos, carga por persona, orden de dependencias, huecos.",
            "- Proponer cambios concretos llamando a la herramienta "
            "`%s`. Tus propuestas NO se aplican solas: la persona las revisa una a una "
            "y decide. Dilo así si te preguntan." % ai_provider.TOOL_NAME,
            "",
            "Reglas:",
            "- Usa únicamente las tareas listadas. Si te preguntan por algo que no está, "
            "dilo en vez de inventarlo.",
            "- Propón cambios solo sobre tareas con `editable: true`.",
            "- Las fechas se escriben en ISO 8601 UTC (2026-09-01T13:00:00Z).",
            "- Al mover una tarea, mantén su duración salvo que se pida lo contrario.",
            "- Cada propuesta lleva un `reason` de una frase.",
            "- Si la pregunta es solo informativa, responde en texto y no llames a la "
            "herramienta.",
            "",
            "Hoy es %s. Todas las fechas del contexto están en UTC." % today.isoformat(),
            "",
            "Tareas visibles (%s):" % len(context['tasks']),
        ]
        for task in context['tasks']:
            lines.append(self._format_task_line(task))

        if context['assignable_users']:
            lines.append("")
            lines.append("Personas asignables (id: nombre):")
            lines.append(", ".join(
                "%s: %s" % (user['id'], user['name']) for user in context['assignable_users']
            ))

        if context['truncated']:
            lines.append("")
            lines.append("Aviso: la lista está recortada; hay más tareas fuera del contexto.")

        return "\n".join(lines)

    @api.model
    def _format_task_line(self, task):
        """Una línea por tarea: legible para el modelo y barata en tokens."""
        parts = [
            "#%s %s" % (task['id'], task['name']),
            "proyecto=%s" % task['project'],
            "inicio=%s" % (task['start'] or '—'),
            "fin=%s" % (task['end'] or '—'),
            "estado=%s" % task['state'],
            "avance=%s%%" % task['progress'],
        ]
        if task.get('assignees'):
            parts.append("asignadas=%s" % ", ".join(task['assignees']))
        if task['depends_on']:
            parts.append("depende_de=%s" % ",".join(str(dep) for dep in task['depends_on']))
        if not task['editable']:
            parts.append("editable=false")
        return "- " + " | ".join(parts)

    @api.model
    def _build_messages(self, history, question):
        """Historial normalizado + la pregunta nueva."""
        messages = []
        for turn in list(history)[-MAX_HISTORY_TURNS:]:
            role = (turn or {}).get('role')
            content = ((turn or {}).get('content') or '').strip()
            if role not in ('user', 'assistant') or not content:
                continue
            messages.append({'role': role, 'content': content[:MAX_HISTORY_CHARS]})
        # Los dos proveedores exigen que el primer turno sea del usuario.
        while messages and messages[0]['role'] != 'user':
            messages.pop(0)
        messages.append({'role': 'user', 'content': question})
        return messages

    # ------------------------------------------------------------------
    # Validación de la salida del modelo
    # ------------------------------------------------------------------
    @api.model
    def _normalize_proposal(self, raw, context):
        """Convierte la propuesta cruda en cambios aplicables (o los descarta).

        Devuelve ``(proposals, warnings)``. Cada propuesta lleva ``values``,
        que es exactamente un elemento de ``tasks.update`` del changeset del
        módulo base: el cliente no compone nada, solo reenvía.
        """
        if not raw or not isinstance(raw, dict):
            return [], []

        proposals, warnings = [], []
        for index, change in enumerate(raw.get('changes') or []):
            if not isinstance(change, dict):
                continue
            task = context['by_id'].get(self._as_int(change.get('task_id')))
            if not task:
                warnings.append(_(
                    "Se descartó una propuesta sobre una tarea que no está en la vista."
                ))
                continue
            if not task['editable']:
                warnings.append(_(
                    "Se descartó una propuesta sobre «%s»: no tiene permiso para modificarla.",
                    task['name'],
                ))
                continue

            values, labels = self._normalize_change(change, task, warnings)
            if not values:
                continue
            proposals.append({
                'key': 'p%s' % index,
                'task_id': task['id'],
                'task_name': task['name'],
                'reason': (change.get('reason') or '').strip(),
                'labels': labels,
                'values': dict(values, id=task['id']),
            })
        return proposals, warnings

    @api.model
    def _normalize_change(self, change, task, warnings):
        """Valida campo a campo. Lo que no encaja se ignora, no se corrige."""
        values, labels = {}, []

        start = self._as_datetime(change.get('start'))
        end = self._as_datetime(change.get('end'))
        if change.get('start') and not start:
            warnings.append(_("Fecha de inicio no válida en la propuesta sobre «%s».", task['name']))
        if change.get('end') and not end:
            warnings.append(_("Fecha de fin no válida en la propuesta sobre «%s».", task['name']))

        # Si solo se propone un extremo, el otro se toma del valor actual para
        # poder comprobar que el intervalo sigue teniendo sentido.
        effective_start = start or self._as_datetime(task['start'])
        effective_end = end or self._as_datetime(task['end'])
        if effective_start and effective_end and effective_start > effective_end:
            warnings.append(_(
                "Se descartaron las fechas propuestas para «%s»: el inicio queda después del fin.",
                task['name'],
            ))
            start = end = None

        if start:
            values['start'] = self._to_iso(start)
            labels.append(_("Inicio: %(old)s → %(new)s",
                            old=self._short(task['start']), new=self._short(values['start'])))
        if end:
            values['end'] = self._to_iso(end)
            labels.append(_("Fin: %(old)s → %(new)s",
                            old=self._short(task['end']), new=self._short(values['end'])))

        if change.get('progress') is not None:
            progress = self._as_float(change.get('progress'))
            if progress is None:
                warnings.append(_("Avance no válido en la propuesta sobre «%s».", task['name']))
            else:
                progress = max(0.0, min(100.0, progress))
                values['progress'] = progress
                labels.append(_("Avance: %(old)s%% → %(new)s%%",
                                old=task['progress'], new=round(progress, 1)))

        name = (change.get('name') or '').strip()
        if name and name != task['name']:
            values['name'] = name[:255]
            labels.append(_("Nombre: «%(old)s» → «%(new)s»", old=task['name'], new=values['name']))

        if change.get('user_ids') is not None:
            user_ids = [
                user_id for user_id in
                (self._as_int(value) for value in change.get('user_ids') or [])
                if user_id
            ]
            allowed = self.env['res.users'].search([
                ('id', 'in', user_ids), ('share', '=', False), ('active', '=', True),
            ])
            if len(allowed) != len(set(user_ids)):
                warnings.append(_(
                    "Se ignoraron personas inexistentes en la propuesta sobre «%s».", task['name'],
                ))
            if allowed:
                values['user_ids'] = allowed.ids
                labels.append(_("Asignar a: %s", ", ".join(allowed.mapped('name'))))

        return values, labels

    # ------------------------------------------------------------------
    # Conversiones tolerantes (la entrada viene de un modelo, no de un formulario)
    # ------------------------------------------------------------------
    @api.model
    def _as_int(self, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @api.model
    def _as_float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @api.model
    def _as_datetime(self, value):
        if not value:
            return None
        text = str(value).strip().replace('Z', '+00:00').replace(' ', 'T', 1)
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    @api.model
    def _to_iso(self, value):
        return value.isoformat(sep='T', timespec='seconds') + 'Z'

    @api.model
    def _short(self, iso_value):
        """Fecha corta para las etiquetas de la interfaz, en la zona del usuario.

        El contexto que ve el modelo va en UTC, pero estas etiquetas las lee una
        persona junto a la rejilla del diagrama, que muestra hora local: si no se
        convierten, la misma tarea aparece con dos horas distintas en pantalla.
        """
        parsed = self._as_datetime(iso_value)
        if not parsed:
            return '—'
        return fields.Datetime.context_timestamp(self, parsed).strftime('%d/%m/%Y %H:%M')
