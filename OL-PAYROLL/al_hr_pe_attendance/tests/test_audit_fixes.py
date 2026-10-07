# -*- coding: utf-8 -*-
"""Regresiones de la auditoría del tareaje y del monitor.

* Turno nocturno: la boleta recibe el día completo en DLAB.
* Descanso o feriado trabajado: conserva el descanso (DOM) y suma FER.
* Marcación sin salida: marcación incompleta, no falta.
* Feriados en la zona horaria local (no en UTC).
* Dos tareajes aplicados que se solapan no se pueden aplicar a la vez.
* Monitor: el documento de identidad es de RR. HH. y el usuario de
  Planning solo ve sus filas.
"""
from datetime import date, datetime

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'al_hr_pe_attendance')
class TestTareajeAuditFixes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Tareaje = cls.env['hr.tareaje.manager']
        Param = cls.env['hr.main.parameter']
        cls.param = Param.search(
            [('company_id', '=', cls.env.company.id)], limit=1) \
            or Param.create({'company_id': cls.env.company.id})
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Diurno auditoría',
            'tz': 'America/Lima',
            'attendance_ids': [(5, 0, 0)] + [
                (0, 0, {'name': 'Día %s' % dia, 'dayofweek': str(dia),
                        'hour_from': 8.0, 'hour_to': 16.0,
                        'day_period': 'morning'})
                for dia in range(0, 5)
            ],
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Trabajador auditoría',
            'tz': 'America/Lima',
            'resource_calendar_id': cls.calendar.id,
        })

    def _tareaje(self, name, start, end):
        return self.Tareaje.create({
            'name': name, 'date_start': start, 'date_end': end})

    # ------------------------------------------------------------------
    # Volcado a la boleta
    # ------------------------------------------------------------------
    def test_night_shift_goes_whole_to_dlab(self):
        """Un turno 22-06 cuenta como día laborado completo en DLAB."""
        totals = {'dlab': 0.0, 'dlabn': 1.0, 'htd': 0.0, 'htn': 8.0}
        assignments = self.env['hr.payslip']._l10n_pe_tareaje_assignments(
            totals)
        self.assertEqual(assignments['dlab'], (1.0, 8.0))
        # La nocturnidad no suma días (sería doble conteo del día).
        self.assertEqual(assignments['noct'], (0.0, 8.0))

    def test_mixed_shift_sums_both_parts(self):
        totals = {'dlab': 0.5, 'dlabn': 0.5, 'htd': 4.0, 'htn': 4.0}
        assignments = self.env['hr.payslip']._l10n_pe_tareaje_assignments(
            totals)
        self.assertEqual(assignments['dlab'], (1.0, 8.0))

    # ------------------------------------------------------------------
    # Descanso y feriado trabajados
    # ------------------------------------------------------------------
    def test_worked_rest_day_keeps_rest(self):
        """D.Leg. 713: el descanso se paga y la labor se suma aparte."""
        for kind in ('descanso', 'feriado'):
            with self.subTest(dia=kind):
                res = self.Tareaje._classify_day(
                    8.0, 16.0, sched_in=8.0, sched_out=16.0, day_kind=kind)
                self.assertAlmostEqual(res['dom'], 1.0, places=2)
                self.assertAlmostEqual(res['fer'], 1.0, places=2)
                self.assertAlmostEqual(res['fal'], 0.0, places=2)

    # ------------------------------------------------------------------
    # Marcación sin salida
    # ------------------------------------------------------------------
    def test_missing_check_out_is_incomplete(self):
        """Quien olvidó marcar la salida no queda como falta."""
        # Lunes 06/07/2026, 08:00 en Lima = 13:00 UTC; sin salida.
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2026, 7, 6, 13, 0, 0),
        })
        tareaje = self._tareaje(
            'Sin salida', date(2026, 7, 6), date(2026, 7, 6))
        marks = tareaje._get_marks_by_employee_day()
        self.assertIn(self.employee, marks)
        self.assertIsNone(marks[self.employee][date(2026, 7, 6)][1])

        tareaje.action_generate()
        line = tareaje.tareaje_line_ids.filtered(
            lambda l: l.employee_id == self.employee)
        self.assertAlmostEqual(line.incos, 1.0, places=2)
        self.assertAlmostEqual(line.fal, 0.0, places=2)
        self.assertEqual(line.attendance_line_ids.state, 'incompleto')

    # ------------------------------------------------------------------
    # Feriados en hora local
    # ------------------------------------------------------------------
    def _global_leave(self, date_from, date_to, holiday=True):
        vals = {
            'name': 'Feriado de prueba',
            'calendar_id': self.calendar.id,
            'company_id': self.env.company.id,
            'date_from': date_from,
            'date_to': date_to,
        }
        if holiday and 'pe.public.holiday' in self.env:
            vals['pe_public_holiday_id'] = self.env['pe.public.holiday'] \
                .create({'name': 'Feriado de prueba',
                         'date': date_from.date()}).id
        leave = self.env['resource.calendar.leaves'].create(vals)
        # hr_holidays reinterpreta en el create las fechas de un descanso
        # global como si vinieran en el huso del USUARIO; se fijan en UTC
        # con un write, igual que hace al_hr_pe_public_holidays.
        leave.write({'date_from': date_from, 'date_to': date_to})
        return leave

    def test_holiday_uses_local_date(self):
        """Un feriado de 00:00 a 23:59 en Lima no marca el día siguiente."""
        # 28/07 00:00-23:59:59 America/Lima en UTC.
        self._global_leave(datetime(2026, 7, 28, 5, 0, 0),
                           datetime(2026, 7, 29, 4, 59, 59))
        tareaje = self._tareaje(
            'Feriado local', date(2026, 7, 27), date(2026, 7, 30))
        holidays = tareaje._get_public_holidays()
        self.assertEqual(holidays[self.calendar.id], {date(2026, 7, 28)})

    def test_closure_and_half_day_are_not_holidays(self):
        """Un cierre de la compañía (descanso global sin feriado) y un
        medio feriado no convierten el día en feriado con sobretasa."""
        if 'pe.public.holiday' not in self.env:
            self.skipTest('sin feriados PE no hay cómo distinguir un cierre')
        self._global_leave(datetime(2026, 8, 3, 5, 0, 0),
                           datetime(2026, 8, 4, 4, 59, 59), holiday=False)
        self._global_leave(datetime(2026, 8, 5, 5, 0, 0),
                           datetime(2026, 8, 5, 18, 0, 0))
        tareaje = self._tareaje(
            'Cierre', date(2026, 8, 3), date(2026, 8, 7))
        self.assertFalse(tareaje._get_public_holidays()[self.calendar.id])

    # ------------------------------------------------------------------
    # Tareajes solapados
    # ------------------------------------------------------------------
    def test_overlapping_done_tareajes_are_rejected(self):
        first = self._tareaje(
            'Primero', date(2026, 8, 1), date(2026, 8, 31))
        second = self._tareaje(
            'Segundo', date(2026, 8, 15), date(2026, 9, 15))
        for tareaje in first | second:
            self.env['hr.tareaje.manager.line'].create({
                'tareaje_id': tareaje.id,
                'employee_id': self.employee.id,
                'dlab': 10.0,
            })
        first.set_close()
        with self.assertRaises(UserError):
            second.set_close()
        # Con el primero reabierto, el segundo sí se puede aplicar.
        first.set_reopen()
        second.set_close()
        self.assertEqual(second.state, 'done')

    def test_non_overlapping_tareajes_can_be_applied(self):
        first = self._tareaje(
            'Agosto', date(2026, 8, 1), date(2026, 8, 31))
        second = self._tareaje(
            'Setiembre', date(2026, 9, 1), date(2026, 9, 30))
        for tareaje in first | second:
            self.env['hr.tareaje.manager.line'].create({
                'tareaje_id': tareaje.id,
                'employee_id': self.employee.id,
            })
        (first | second).set_close()
        self.assertEqual(set((first | second).mapped('state')), {'done'})

    # ------------------------------------------------------------------
    # Privacidad
    # ------------------------------------------------------------------
    def test_overtime_flag_is_private(self):
        field = self.env['hr.version']._fields['l10n_pe_is_overtime']
        self.assertEqual(field.groups, 'hr.group_hr_user')

    def test_monitor_hides_identity_and_limits_planning_user(self):
        Monitor = self.env['l10n_pe.hr.attendance.monitor']
        for fname in ('identification_id', 'identification_type_id'):
            self.assertEqual(Monitor._fields[fname].groups,
                             'hr.group_hr_user')
        rule = self.env.ref(
            'al_hr_pe_attendance.'
            'l10n_pe_hr_attendance_monitor_planning_user_rule')
        self.assertEqual(rule.domain_force, "[('user_id', '=', user.id)]")
        self.assertIn(self.env.ref('planning.group_planning_user'),
                      rule.groups)
        # La vista SQL expone el usuario del trabajador para la regla.
        self.assertIn('user_id', Monitor._fields)
        Monitor.search([], limit=1)  # la vista se consulta sin error
