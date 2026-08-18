# -*- coding: utf-8 -*-
"""Mapeo de campos de ``project.task`` hacia los conceptos del Gantt.

Odoo no ofrece un juego de fechas único para las tareas:

* ``date_deadline`` (fecha de fin) existe siempre, en ``project``.
* ``planned_date_begin`` (fecha de inicio) **solo** existe si está instalado
  ``project_enterprise``; la restricción SQL de ese módulo es
  ``planned_date_begin <= date_deadline``, es decir, el fin planificado sigue
  siendo ``date_deadline`` (no hay ``planned_date_end`` en Odoo 19).
* ``progress`` **solo** existe si está instalado ``hr_timesheet``.
* ``project.task`` **no** tiene ``date_start`` en Odoo 19 (sí lo tiene
  ``project.project``). ``date_end`` sí existe, pero es la fecha *real* de
  cierre, no la planificada: no se autodetecta como fin, aunque se acepta si se
  configura explícitamente.

Este modelo resuelve el mapeo por introspección del registro y lo deja
sobreescribible mediante el parámetro de sistema ``al_gantt.field_map``.
"""
import json
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

#: Parámetro de sistema que sobreescribe la detección automática (JSON).
CONFIG_PARAM = 'al_gantt.field_map'

#: Candidatos por concepto, en orden de preferencia.
CANDIDATES = {
    'date_start': ('planned_date_begin', 'date_start'),
    'date_end': ('date_deadline', 'planned_date_end'),
    'progress': ('progress',),
}

#: Duración por defecto (horas) de la barra cuando solo se conoce el fin.
DEFAULT_DURATION_PARAM = 'al_gantt.default_duration_hours'
DEFAULT_DURATION_HOURS = 8.0


class GanttFieldMap(models.AbstractModel):
    """Servicio de mapeo de campos. Punto de extensión: heredar y ampliar
    :meth:`_get_candidates` o :meth:`get_map` para otros modelos/instalaciones.
    """
    _name = 'al.gantt.field.map'
    _description = 'Gantt — mapeo de campos'

    @api.model
    def _get_candidates(self):
        return {key: tuple(values) for key, values in CANDIDATES.items()}

    @api.model
    def _get_model_fields(self, model_name='project.task'):
        return self.env[model_name]._fields

    @api.model
    def _detect(self, model_name='project.task'):
        """Detección automática por introspección del registro."""
        fields_ = self._get_model_fields(model_name)
        detected = {}
        for key, candidates in self._get_candidates().items():
            detected[key] = next((name for name in candidates if name in fields_), None)
        return detected

    @api.model
    def _get_override(self):
        """Sobreescritura manual vía parámetro de sistema (JSON)."""
        raw = self.env['ir.config_parameter'].sudo().get_param(CONFIG_PARAM)
        if not raw:
            return {}
        try:
            override = json.loads(raw)
        except ValueError:
            _logger.warning("%s no es JSON válido; se ignora: %r", CONFIG_PARAM, raw)
            return {}
        if not isinstance(override, dict):
            _logger.warning("%s debe ser un objeto JSON; se ignora: %r", CONFIG_PARAM, raw)
            return {}
        return override

    @api.model
    def get_map(self, model_name='project.task'):
        """Devuelve el mapeo efectivo.

        :return: ``{'date_start', 'date_end', 'progress', 'source', 'mode'}``
            donde ``source`` es ``auto`` o ``config``, y ``mode`` describe qué
            se puede dibujar: ``planned`` (inicio y fin), ``deadline_only``
            (solo fin, la barra se calcula hacia atrás) o ``none``.
        """
        detected = self._detect(model_name)
        override = self._get_override()
        model_fields = self._get_model_fields(model_name)
        source = 'auto'

        for key in detected:
            if key not in override:
                continue
            value = override[key]
            if value in (None, False, ''):
                detected[key] = None
                source = 'config'
            elif value in model_fields:
                detected[key] = value
                source = 'config'
            else:
                _logger.warning(
                    "%s: el campo %r no existe en %s; se mantiene la detección automática (%r)",
                    CONFIG_PARAM, value, model_name, detected[key],
                )

        if detected['date_end']:
            mode = 'planned' if detected['date_start'] else 'deadline_only'
        else:
            mode = 'none'

        return {
            'date_start': detected['date_start'],
            'date_end': detected['date_end'],
            'progress': detected['progress'],
            'source': source,
            'mode': mode,
        }

    @api.model
    def get_default_duration_hours(self):
        """Duración de la barra cuando la tarea solo tiene fecha de fin."""
        raw = self.env['ir.config_parameter'].sudo().get_param(DEFAULT_DURATION_PARAM)
        try:
            value = float(raw) if raw else DEFAULT_DURATION_HOURS
        except (TypeError, ValueError):
            _logger.warning("%s no es numérico; se usa %s", DEFAULT_DURATION_PARAM, DEFAULT_DURATION_HOURS)
            return DEFAULT_DURATION_HOURS
        return value if value > 0 else DEFAULT_DURATION_HOURS
