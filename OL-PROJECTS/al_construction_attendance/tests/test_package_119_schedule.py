# -*- coding: utf-8 -*-
"""Paquete 1.19, M119-03: jornales y turnos con el horario de obra (lunes a
viernes de 8:00 a 17:00 con refrigerio y sábado de 8:00 a 13:00).

* Un jornalero que marca de 8:00 a 13:00 un sábado suma 0.625 jornal y cuesta
  0.625 del jornal, aunque los jornales se redondeen a día completo.
* «Asignar cuadrilla» crea turnos de lunes a viernes de 8:00 a 17:00 y sábado
  de 8:00 a 13:00, y propone 5.625 jornales por semana."""
from datetime import datetime, timedelta

import pytz

from odoo import Command
from odoo.tests import tagged

from odoo.addons.al_construction_planner.tests.test_package_119_schedule import site_calendar

from .test_crew_v18 import MONDAY, TestCrewDays

SATURDAY = MONDAY + timedelta(days=5)


@tagged('post_install', '-at_install')
class TestPackage119Schedule(TestCrewDays):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.tz = 'America/Lima'
        cls.calendar = site_calendar(cls.env, cls.company)

    def _sede(self):
        return self.project.construction_hr_site_ids[:1] or self.env[
            'l10n_pe.hr.construction.site'].create({
                'name': 'Sede 1.19 (test)', 'project_id': self.project.id,
                'company_id': self.company.id})

    def _mark(self, employee, day, hour_from, hour_to):
        """Marcación en hora de Lima (UTC-5)."""
        base = datetime.combine(day, datetime.min.time())
        return self.env['hr.attendance'].create({
            'employee_id': employee.id, 'l10n_pe_construction_site_id': self._sede().id,
            'check_in': base + timedelta(hours=hour_from + 5),
            'check_out': base + timedelta(hours=hour_to + 5)})

    def _executed(self, day):
        return self.env['construction.crew.day'].search([
            ('project_id', '=', self.project.id), ('kind', '=', 'executed'), ('date', '=', day)])

    def test_saturday_is_0625_jornal(self):
        self.company.construction_site_calendar_id = self.calendar
        self.assertEqual(self.company.construction_crew_hours_per_day, 8.0)
        operario = self.crew[0]
        self._mark(operario, SATURDAY, 8, 13)
        self._mark(operario, MONDAY, 8, 17)  # 9 h con refrigerio marcado: 1 jornal
        saturday = self._executed(SATURDAY)
        self.assertAlmostEqual(saturday.days, 0.625)
        self.assertAlmostEqual(saturday.amount, round(0.625 * self._wage('operario', SATURDAY), 2))
        self.assertAlmostEqual(self._executed(MONDAY).days, 1.0)

    def test_saturday_without_schedule_rounds_as_today(self):
        self.company.construction_site_calendar_id = False
        self._mark(self.crew[0], SATURDAY, 8, 13)
        self.assertAlmostEqual(self._executed(SATURDAY).days, 1.0)

    def test_crew_shifts_follow_the_schedule(self):
        self.company.construction_site_calendar_id = self.calendar
        wizard = self.env['construction.plan.crew.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=self.space_501.ids,
        ).create({'time_mode': 'days', 'weeks': 1, 'date_start': MONDAY,
                  'member_ids': [Command.create({'resource_id': self.crew[0].resource_id.id,
                                                 'role_id': self.roles['operario'].id})]})
        self.assertAlmostEqual(wizard.days_per_week, 5.625)
        self.assertAlmostEqual(wizard.days_total, 5.625)
        self.assertEqual(len(wizard.line_ids), 6)
        action = wizard.action_assign()
        slots = self.env['planning.slot'].search(action['domain'], order='start_datetime')
        lima = pytz.timezone('America/Lima')
        local = [(pytz.utc.localize(slot.start_datetime).astimezone(lima),
                  pytz.utc.localize(slot.end_datetime).astimezone(lima), slot.allocated_hours)
                 for slot in slots]
        self.assertEqual([(start.weekday(), start.hour, end.hour, hours)
                          for start, end, hours in local],
                         [(0, 8, 17, 8.0), (1, 8, 17, 8.0), (2, 8, 17, 8.0), (3, 8, 17, 8.0),
                          (4, 8, 17, 8.0), (5, 8, 13, 5.0)])
        planned = self.env['construction.crew.day'].search([
            ('project_id', '=', self.project.id), ('kind', '=', 'planned')])
        self.assertAlmostEqual(sum(planned.mapped('days')), 5.625)

    def test_crew_without_schedule_keeps_the_weekly_shift(self):
        self.company.construction_site_calendar_id = False
        wizard = self._wizard([(self.crew[0], 'operario')])
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertFalse(wizard.line_ids.date)
