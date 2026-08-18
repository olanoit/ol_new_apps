# -*- coding: utf-8 -*-
"""Días no laborables, para sombrearlos en el diagrama.

Se leen del `resource.calendar` que ya usa el proyecto (el de su compañía), sin
inventar un calendario propio: los días con jornada configurada son laborables y
el resto no, y los descansos globales del calendario (feriados) se envían como
rangos.

**Solo afecta al dibujo.** La reprogramación en cadena sigue trabajando en
tiempo natural: convertirla a días hábiles exigiría recalcular duraciones con el
calendario, y eso cambiaría las fechas que el usuario ya tiene guardadas.
"""
from datetime import timedelta

from odoo import api, models

#: Ventana de feriados que se envía al cliente alrededor de hoy.
HOLIDAY_WINDOW_DAYS = 730


class GanttCalendar(models.AbstractModel):
    _inherit = 'al.gantt.data'

    @api.model
    def _read_calendar(self, project_ids):
        """``{working_days: [0..6], holidays: [{start, end, name}]}``.

        Si los proyectos usan calendarios distintos se toma el del primero y se
        avisa en `mixed`: sombrear dos calendarios a la vez sería engañoso.
        """
        projects = self.env['project.project'].browse(list(project_ids or []))
        calendars = projects.mapped('resource_calendar_id')
        calendar = calendars[:1] or self.env.company.resource_calendar_id
        if not calendar:
            return {'working_days': [0, 1, 2, 3, 4], 'holidays': [], 'mixed': False,
                    'calendar_name': None}

        working_days = sorted({
            int(day) for day in calendar.attendance_ids.mapped('dayofweek') if day is not False
        })
        today = self.env.cr.now()
        leaves = self.env['resource.calendar.leaves'].search_read(
            [
                ('calendar_id', '=', calendar.id),
                ('resource_id', '=', False),
                ('date_to', '>=', today - timedelta(days=HOLIDAY_WINDOW_DAYS)),
                ('date_from', '<=', today + timedelta(days=HOLIDAY_WINDOW_DAYS)),
            ],
            ['name', 'date_from', 'date_to'],
        )
        return {
            'working_days': working_days or [0, 1, 2, 3, 4],
            'holidays': [{
                'name': leave['name'],
                'start': self._iso(leave['date_from']),
                'end': self._iso(leave['date_to']),
            } for leave in leaves],
            'mixed': len(calendars) > 1,
            'calendar_name': calendar.name,
        }
