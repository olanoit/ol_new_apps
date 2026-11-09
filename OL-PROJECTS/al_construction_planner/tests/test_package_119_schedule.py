# -*- coding: utf-8 -*-
"""Horario de obra (paquete 1.19, M119-03): el planificador lee un horario de
trabajo nativo de lunes a viernes de 8:00 a 17:00 con una hora de refrigerio y
sábado de 8:00 a 13:00 (45 h). Sin horario, todo sigue como antes."""
from datetime import date, datetime

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

MONDAY = date(2026, 11, 2)


def site_calendar(env, company=False, name='Obra L-V 8-17, sáb 8-13 (test)'):
    """El horario del requerimiento, con el refrigerio de 12:00 a 13:00."""
    lines = []
    for day in range(5):
        lines += [
            (0, 0, {'name': 'Mañana %s' % day, 'dayofweek': str(day), 'hour_from': 8,
                    'hour_to': 12, 'day_period': 'morning'}),
            (0, 0, {'name': 'Refrigerio %s' % day, 'dayofweek': str(day), 'hour_from': 12,
                    'hour_to': 13, 'day_period': 'lunch'}),
            (0, 0, {'name': 'Tarde %s' % day, 'dayofweek': str(day), 'hour_from': 13,
                    'hour_to': 17, 'day_period': 'afternoon'}),
        ]
    lines.append((0, 0, {'name': 'Sábado', 'dayofweek': '5', 'hour_from': 8, 'hour_to': 13,
                         'day_period': 'morning'}))
    return env['resource.calendar'].create({
        'name': name, 'company_id': company and company.id, 'tz': 'America/Lima',
        'attendance_ids': [(5, 0, 0)] + lines})


@tagged('post_install', '-at_install')
class TestSiteSchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.resource_calendar_id = cls.env['resource.calendar'].create({
            'name': 'Lunes a viernes (test 1.19)', 'company_id': cls.company.id,
            'tz': 'America/Lima',
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'name': 'Día %s' % day, 'dayofweek': str(day), 'hour_from': 8, 'hour_to': 17,
                'day_period': 'full_day'}) for day in range(5)]})
        cls.company.construction_site_calendar_id = False
        cls.company.construction_workday_hours = 8.0
        # Sin horario de los feriados de Perú en el plazo de prueba: noviembre.
        cls.calendar = site_calendar(cls.env)

    def test_empty_keeps_today(self):
        company = self.company
        self.assertEqual(company._construction_site_weekdays(), {0, 1, 2, 3, 4})
        self.assertEqual(company._construction_full_day_hours(), 8.0)
        self.assertEqual(company._construction_day_factor(MONDAY + (date(2026, 11, 7) - MONDAY)),
                         0.0)
        self.assertEqual(company._construction_day_factor(MONDAY), 1.0)
        self.assertFalse(company._construction_is_short_day(date(2026, 11, 7)))
        self.assertIsNone(company._construction_day_window(MONDAY))
        company.construction_workday_hours = 9.0
        self.assertEqual(company.construction_workday_hours, 9.0)

    def test_derived_figures(self):
        company = self.company
        company.construction_site_calendar_id = self.calendar
        self.assertEqual(company.construction_site_week_hours, 45.0)
        self.assertEqual(company.construction_site_full_day_hours, 8.0)
        self.assertEqual(company.construction_site_week_days, 5.625)
        self.assertEqual(company.construction_site_work_days, 6)
        self.assertEqual(company.construction_workday_hours, 8.0)
        self.assertEqual(company._construction_site_weekdays(), {0, 1, 2, 3, 4, 5})
        saturday = date(2026, 11, 7)
        self.assertEqual(company._construction_day_factor(saturday), 0.625)
        self.assertEqual(company._construction_day_factor(date(2026, 11, 8)), 0.0)
        self.assertTrue(company._construction_is_short_day(saturday))
        self.assertFalse(company._construction_is_short_day(MONDAY))
        self.assertEqual(company._construction_day_window(saturday), (8.0, 13.0, 5.0))
        self.assertEqual(company._construction_day_window(MONDAY), (8.0, 17.0, 8.0))
        # Una jornada más larga en el horario cambia la jornada completa y las
        # horas de la jornada del APU.
        self.calendar.attendance_ids.filtered(
            lambda a: a.dayofweek == '0' and a.day_period == 'afternoon').hour_to = 18
        self.assertEqual(company.construction_workday_hours, 9.0)

    def test_equivalent_days_and_holiday(self):
        """Ejemplo de Vicente: 30 días calendario desde un lunes son 22 días
        de lunes a viernes y 4 sábados de 5 h: 24.5 días equivalentes. Un
        feriado del horario resta 1."""
        company = self.company
        company.construction_site_calendar_id = self.calendar
        end = date(2026, 12, 1)
        self.assertEqual(company._construction_equivalent_days(MONDAY, end), 24.5)
        self.env['resource.calendar.leaves'].create({
            'name': 'Feriado de obra (test)', 'calendar_id': self.calendar.id,
            'date_from': datetime(2026, 11, 18, 13, 0), 'date_to': datetime(2026, 11, 18, 22, 0)})
        self.env.cr.cache.pop('al_construction_holidays', None)
        self.env.cr.cache.pop('al_construction_site_holidays', None)
        self.assertEqual(company._construction_equivalent_days(MONDAY, end), 23.5)
        self.assertEqual(company._construction_site_hours(date(2026, 11, 18)), 0.0)
        self.assertFalse(company._construction_is_site_day(date(2026, 11, 18)))

    def test_calendar_without_company_holidays(self):
        """Un horario sin compañía también aporta sus feriados."""
        company = self.company
        calendar = site_calendar(self.env, name='Obra sin compañía (test)')
        calendar.company_id = False
        company.construction_site_calendar_id = calendar
        self.env['resource.calendar.leaves'].create({
            'name': 'Feriado (test)', 'calendar_id': calendar.id,
            'date_from': datetime(2026, 11, 11, 13, 0), 'date_to': datetime(2026, 11, 11, 22, 0)})
        self.env.cr.cache.pop('al_construction_holidays', None)
        self.env.cr.cache.pop('al_construction_site_holidays', None)
        self.assertTrue(company._construction_is_holiday(date(2026, 11, 11)))
        self.assertEqual(company._construction_day_factor(date(2026, 11, 11)), 0.0)

    def test_settings_show_figures(self):
        self.company.construction_site_calendar_id = self.calendar
        settings = self.env['res.config.settings'].create({})
        self.assertEqual(settings.construction_site_calendar_id, self.calendar)
        self.assertEqual(settings.construction_site_week_hours, 45.0)
        self.assertEqual(settings.construction_site_full_day_hours, 8.0)
        self.assertEqual(settings.construction_site_week_days, 5.625)
