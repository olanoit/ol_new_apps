# -*- coding: utf-8 -*-
"""Feriado o descanso laborado unas pocas horas (D.Leg. 713, art. 9).

«El trabajo efectuado en los días feriados no laborables sin descanso
sustitutorio dará lugar al pago de la retribución correspondiente por la
labor efectuada, con una sobretasa de 100 %»: se paga por las horas
trabajadas, no por el día completo. Además (criterio SUNAFIL), el turno
que empieza en un día laborable y termina en el feriado no es feriado
laborado.
"""
from datetime import date, datetime, timedelta

from odoo.tests.common import TransactionCase, tagged


def _lima(day, hour, minute=0):
    """Hora de Lima (UTC−5) → datetime UTC ingenuo, como se guarda."""
    return datetime(day.year, day.month, day.day, hour, minute) \
        + timedelta(hours=5)


@tagged('post_install', '-at_install', 'al_hr_pe_attendance')
class TestWorkedHolidayHours(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'PE Feriado Laborado SAC',
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.env.user.company_ids |= cls.company
        cls.env.user.group_ids |= cls.env.ref(
            'hr_payroll.group_hr_payroll_manager')
        cls.env['hr.main.parameter'].create({
            'company_id': cls.company.id, 'rmv': 1130.0})
        cls.Tareaje = cls.env['hr.tareaje.manager']
        cls.structure = cls.env.ref('al_hr_pe.base_structure')
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Diurno feriado', 'company_id': cls.company.id,
            'hours_per_day': 8.0,
            'attendance_ids': [(5, 0, 0)] + [
                (0, 0, {'dayofweek': str(dia),
                        'hour_from': 8.0, 'hour_to': 16.0,
                        'day_period': 'morning'})
                for dia in range(0, 5)],
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Trabajador feriado',
            'company_id': cls.company.id,
            'tz': 'America/Lima',
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'wage': 3000.0,
            'structure_type_id': cls.structure.type_id.id,
            'resource_calendar_id': cls.calendar.id,
        })
        # Miércoles 4 de marzo de 2026: feriado.
        cls.holiday_day = date(2026, 3, 4)
        holiday = cls.env['pe.public.holiday'].create({
            'name': 'Feriado de prueba', 'date': cls.holiday_day})
        cls.holiday = holiday

    def _holiday_on(self, calendar):
        leave = self.env['resource.calendar.leaves'].create({
            'name': 'Feriado de prueba',
            'calendar_id': calendar.id,
            'company_id': self.company.id,
            'date_from': _lima(self.holiday_day, 0),
            'date_to': _lima(self.holiday_day, 23, 59),
            'pe_public_holiday_id': self.holiday.id,
        })
        leave.write({'date_from': _lima(self.holiday_day, 0),
                     'date_to': _lima(self.holiday_day, 23, 59)})

    def _attendance(self, day, hour_in, hour_out, out_day=None):
        return self.env['hr.attendance'].with_context(
            skip_time_rules=True).create({
                'employee_id': self.employee.id,
                'check_in': _lima(day, hour_in),
                'check_out': _lima(out_day or day, hour_out),
            })

    def _generate(self, start, end):
        tareaje = self.Tareaje.create({
            'name': 'Feriado', 'date_start': start, 'date_end': end,
            'company_id': self.company.id})
        tareaje.action_generate()
        return tareaje, tareaje.tareaje_line_ids.filtered(
            lambda l: l.employee_id == self.employee)

    @staticmethod
    def _day(line, day):
        return line.attendance_line_ids.filtered(lambda d: d.fecha == day)

    # ------------------------------------------------------------------
    # Clasificación del día
    # ------------------------------------------------------------------
    def test_classify_counts_the_worked_hours(self):
        """Feriado trabajado 2 h: FER con 2 h (antes, solo el día); la
        jornada completa da sus 8 h y el exceso sigue en HE100."""
        res = self.Tareaje._classify_day(
            8.0, 10.0, sched_in=8.0, sched_out=16.0, day_kind='feriado')
        self.assertAlmostEqual(res['fer'], 1.0, places=2)
        self.assertAlmostEqual(res['hfer'], 2.0, places=2)
        self.assertAlmostEqual(res['he100'], 0.0, places=2)
        res = self.Tareaje._classify_day(
            8.0, 18.0, sched_in=8.0, sched_out=16.0, day_kind='feriado')
        self.assertAlmostEqual(res['hfer'], 8.0, places=2)
        self.assertAlmostEqual(res['he100'], 2.0, places=2)
        # Descanso sin turno: hasta la jornada legal de 8 h; sin HE el
        # exceso tampoco se paga como FER.
        res = self.Tareaje._classify_day(
            8.0, 17.0, day_kind='descanso', compute_overtime=False)
        self.assertAlmostEqual(res['hfer'], 8.0, places=2)
        self.assertAlmostEqual(res['he100'], 0.0, places=2)

    # ------------------------------------------------------------------
    # De la marcación a la boleta
    # ------------------------------------------------------------------
    def _slip(self):
        slip = self.env['hr.payslip'].create({
            'name': 'Boleta feriado',
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 3, 1),
            'date_to': date(2026, 3, 31),
        })
        slip.compute_sheet()
        return slip

    @staticmethod
    def _fer_line(slip):
        return slip.worked_days_line_ids.filtered(lambda l: l.code == 'FER')

    def test_holiday_worked_two_hours_pays_two_hours(self):
        """2 h en el feriado: la boleta paga 2 h × valor hora × 2, no el
        día completo doble (antes, 200 con un sueldo de 3 000)."""
        self._holiday_on(self.calendar)
        for offset in (2, 3, 5, 6):
            self._attendance(date(2026, 3, offset), 8, 16)
        self._attendance(self.holiday_day, 8, 10)
        tareaje, line = self._generate(date(2026, 3, 2), date(2026, 3, 6))
        day = self._day(line, self.holiday_day)
        self.assertEqual(day.state, 'feriado_trab')
        self.assertAlmostEqual(day.fer, 1.0, places=2)
        self.assertAlmostEqual(day.hfer, 2.0, places=2)
        self.assertAlmostEqual(line.hfer, 2.0, places=2)
        tareaje.action_close()
        slip = self._slip()
        fer = self._fer_line(slip)
        self.assertAlmostEqual(sum(fer.mapped('number_of_hours')), 2.0, places=2)
        total = slip.line_ids.filtered(lambda l: l.code == 'FER').total
        self.assertAlmostEqual(total, round(3000.0 / 30 / 8 * 2 * 2, 2))

    def test_holiday_worked_full_day_pays_as_before(self):
        """La jornada completa en el feriado paga lo mismo que antes: el
        día doble."""
        self._holiday_on(self.calendar)
        self._attendance(self.holiday_day, 8, 16)
        tareaje, line = self._generate(self.holiday_day, self.holiday_day)
        self.assertAlmostEqual(line.hfer, 8.0, places=2)
        tareaje.action_close()
        slip = self._slip()
        total = slip.line_ids.filtered(lambda l: l.code == 'FER').total
        self.assertAlmostEqual(total, 3000.0 / 30 * 2)

    def test_night_shift_ending_on_the_holiday_is_not_holiday_work(self):
        """Turno del martes 22:00 al miércoles feriado 06:00: es el turno
        del martes, laborable; el feriado no se laboró (criterio SUNAFIL)."""
        night = self.env['resource.calendar'].create({
            'name': 'Nocturno feriado', 'company_id': self.company.id,
            'attendance_ids': [(5, 0, 0)] + [
                (0, 0, {'dayofweek': str(dia), 'hour_from': 22.0,
                        'hour_to': 24.0, 'day_period': 'afternoon'})
                for dia in range(0, 5)] + [
                (0, 0, {'dayofweek': str(dia), 'hour_from': 0.0,
                        'hour_to': 6.0, 'day_period': 'morning'})
                for dia in range(1, 6)],
        })
        self.employee.version_id.resource_calendar_id = night
        self._holiday_on(night)
        tuesday = date(2026, 3, 3)
        self._attendance(tuesday, 22, 6, out_day=self.holiday_day)
        _tareaje, line = self._generate(tuesday, self.holiday_day)
        shift = self._day(line, tuesday)
        self.assertEqual(shift.state, 'ok')
        self.assertAlmostEqual(shift.dlab + shift.dlabn, 1.0, places=2)
        self.assertAlmostEqual(shift.fer, 0.0, places=2)
        holiday = self._day(line, self.holiday_day)
        self.assertEqual(holiday.state, 'feriado')
        self.assertAlmostEqual(holiday.fer, 0.0, places=2)
        self.assertAlmostEqual(line.fer, 0.0, places=2)
        self.assertAlmostEqual(line.hfer, 0.0, places=2)
