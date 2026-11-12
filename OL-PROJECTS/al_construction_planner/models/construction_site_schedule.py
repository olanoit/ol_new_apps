# -*- coding: utf-8 -*-
"""Horario de obra (paquete 1.19, M119-03).

Un parámetro de la compañía apunta a un horario de trabajo nativo
(``resource.calendar``) que el planificador solo lee: no lo asigna a contratos
ni a la compañía, y la nómina no cambia. De él salen las horas de cada día, la
jornada completa (el día más largo), las horas y los jornales por semana y los
días equivalentes de un plazo (un sábado de 5 h con jornada de 8 h vale 0.625).

Con el campo vacío, todo se calcula como antes: «Horas de la jornada», los
días hábiles del horario de la compañía y los parámetros de cada puente.
"""
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models
from odoo.tools.float_utils import float_compare, float_round

# Precisión de los jornales y de los días equivalentes.
DAY_DIGITS = 4


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_site_calendar_id = fields.Many2one(
        'resource.calendar', string='Horario de obra',
        domain="[('company_id', 'in', (False, id))]",
        help='Horario de trabajo (Empleados › Configuración › Horarios de trabajo) con los días, '
             'las horas y los feriados de la obra. El planificador solo lo lee: no se asigna a '
             'contratos ni a la compañía. Vacío: las horas de la jornada y los días hábiles del '
             'horario de la compañía.')
    construction_site_week_hours = fields.Float(
        string='Horas por semana', compute='_compute_construction_site_figures', digits=(16, 2))
    construction_site_full_day_hours = fields.Float(
        string='Jornada completa', compute='_compute_construction_site_figures', digits=(16, 2),
        help='Horas del día más largo del horario de obra: una persona-día.')
    construction_site_week_days = fields.Float(
        string='Jornales por persona y semana', compute='_compute_construction_site_figures',
        digits=(16, 3), help='Horas por semana ÷ jornada completa.')
    construction_site_work_days = fields.Integer(
        string='Días con horario por semana', compute='_compute_construction_site_figures')

    @api.depends('construction_site_calendar_id.attendance_ids.hour_from',
                 'construction_site_calendar_id.attendance_ids.hour_to',
                 'construction_site_calendar_id.attendance_ids.day_period',
                 'construction_site_calendar_id.attendance_ids.dayofweek',
                 'construction_workday_hours', 'resource_calendar_id')
    def _compute_construction_site_figures(self):
        for company in self:
            hours = company._construction_weekday_hours()
            full = company._construction_full_day_hours()
            week = sum(hours.values())
            company.construction_site_week_hours = week
            company.construction_site_full_day_hours = full
            company.construction_site_week_days = float_round(
                week / full, precision_digits=3) if full else 0.0
            company.construction_site_work_days = len([h for h in hours.values() if h > 0])

    # ------------------------------------------------------------------
    # Lectura del horario
    # ------------------------------------------------------------------
    def _construction_calendar_attendances(self, week_type=None):
        """Franjas de trabajo del horario de obra (sin refrigerio ni secciones).
        En un horario de dos semanas, las de ``week_type`` (o la primera)."""
        self.ensure_one()
        # sudo: con hr_work_entry, _is_work_period() lee el tipo de entrada de
        # trabajo de la franja, campo reservado a RR. HH.; el planificador solo
        # necesita saber qué franjas son de trabajo.
        calendar_sudo = self.construction_site_calendar_id.sudo()
        attendances = calendar_sudo.attendance_ids.filtered(lambda a: a._is_work_period())
        if calendar_sudo.two_weeks_calendar:
            wanted = week_type if week_type is not None else '0'
            attendances = attendances.filtered(lambda a: a.week_type == wanted)
        return attendances.sudo(False)

    def _construction_weekday_hours(self, week_type=None):
        """{día de la semana (0 = lunes): horas}. Sin horario de obra, la
        jornada completa en los días hábiles del horario de la compañía."""
        self.ensure_one()
        if not self.construction_site_calendar_id:
            full = self.construction_workday_hours or 8.0
            return {weekday: full for weekday in self._construction_site_weekdays()}
        hours = defaultdict(float)
        for attendance in self._construction_calendar_attendances(week_type):
            hours[int(attendance.dayofweek)] += attendance.hour_to - attendance.hour_from
        return {weekday: value for weekday, value in hours.items() if value > 0}

    def _construction_full_day_hours(self):
        """Horas de una persona-día: el día más largo del horario de obra o,
        sin horario, «Horas de la jornada»."""
        self.ensure_one()
        if self.construction_site_calendar_id:
            hours = self._construction_weekday_hours()
            if hours:
                return max(hours.values())
        return self.construction_workday_hours or 8.0

    def _construction_week_type(self, day):
        self.ensure_one()
        if not self.construction_site_calendar_id.two_weeks_calendar:
            return None
        return str(self.env['resource.calendar.attendance'].get_week_type(day))

    def _construction_site_hours(self, day):
        """Horas de trabajo del horario de obra en ``day``: 0 en un feriado o
        en un día sin horario."""
        self.ensure_one()
        if self._construction_is_holiday(day):
            return 0.0
        hours = self._construction_weekday_hours(self._construction_week_type(day))
        return hours.get(day.weekday(), 0.0)

    def _construction_day_factor(self, day):
        """Días equivalentes de ``day``: sus horas ÷ la jornada completa (lunes
        a viernes 1, un sábado de 5 h 0.625, domingo y feriado 0)."""
        self.ensure_one()
        full = self._construction_full_day_hours()
        if not full:
            return 0.0
        return float_round(self._construction_site_hours(day) / full,
                           precision_digits=DAY_DIGITS)

    def _construction_equivalent_days(self, start, end):
        """Días equivalentes entre ``start`` y ``end``, ambos incluidos."""
        self.ensure_one()
        total, day = 0.0, start
        while start and end and day <= end:
            total += self._construction_day_factor(day)
            day += timedelta(days=1)
        return float_round(total, precision_digits=DAY_DIGITS)

    def _construction_is_short_day(self, day):
        """Día con horario y con menos horas que la jornada completa (el
        sábado de 5 h): sus jornales no se redondean (decisión del 09-nov)."""
        self.ensure_one()
        if not self.construction_site_calendar_id:
            return False
        hours = self._construction_weekday_hours(self._construction_week_type(day)).get(
            day.weekday(), 0.0)
        return hours > 0 and float_compare(
            hours, self._construction_full_day_hours(), precision_digits=2) < 0

    def _construction_day_window(self, day):
        """(hora de inicio, hora de fin, horas) del horario de obra en ``day``
        en hora local, de la primera entrada a la última salida; ``None`` sin
        horario, en un feriado o en un día sin horario."""
        self.ensure_one()
        if not self.construction_site_calendar_id or self._construction_is_holiday(day):
            return None
        attendances = self._construction_calendar_attendances(
            self._construction_week_type(day)).filtered(
            lambda a: int(a.dayofweek) == day.weekday())
        if not attendances:
            return None
        hours = sum(a.hour_to - a.hour_from for a in attendances)
        return min(attendances.mapped('hour_from')), max(attendances.mapped('hour_to')), hours

    # ------------------------------------------------------------------
    # Días hábiles de la obra: con horario de obra, sus días
    # ------------------------------------------------------------------
    def _construction_site_weekdays(self):
        self.ensure_one()
        if self.construction_site_calendar_id:
            weekdays = {int(a.dayofweek) for a in self._construction_calendar_attendances()}
            if weekdays:
                return weekdays
        return super()._construction_site_weekdays()

    def _construction_holidays(self, year):
        """Con horario de obra, también sus feriados (ausencias globales del
        horario, aunque sea de otra compañía o de ninguna)."""
        days = super()._construction_holidays(year)
        calendar = self.construction_site_calendar_id
        if not calendar:
            return days
        cache = self.env.cr.cache.setdefault('al_construction_site_holidays', {})
        key = (self.id, calendar.id, year)
        if key not in cache:
            extra = set()
            # sudo: los feriados del horario son de RR. HH.; solo se leen.
            for leave in calendar.sudo().global_leave_ids:
                day = fields.Datetime.context_timestamp(
                    self.with_context(tz=calendar.tz or 'UTC'), leave.date_from).date()
                stop = fields.Datetime.context_timestamp(
                    self.with_context(tz=calendar.tz or 'UTC'), leave.date_to).date()
                while day <= stop:
                    if day.year == year:
                        extra.add(day)
                    day += timedelta(days=1)
            cache[key] = extra
        return days | cache[key]
