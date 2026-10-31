# -*- coding: utf-8 -*-
"""Revisión del tareaje en Odoo 20 (31/10/2026).

Cada test reproduce un hallazgo de la revisión (#1, #2…) y falla con el
código anterior a su corrección.
"""
from datetime import date, datetime, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


def _lima(day, hour, minute=0):
    """Hora de Lima (UTC−5) → datetime UTC ingenuo, como se guarda."""
    return datetime(day.year, day.month, day.day, hour, minute) \
        + timedelta(hours=5)


@tagged('post_install', '-at_install', 'al_hr_pe_attendance')
class TestReviewTareaje(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Tareaje = cls.env['hr.tareaje.manager']
        Param = cls.env['hr.main.parameter']
        cls.param = Param.search(
            [('company_id', '=', cls.env.company.id)], limit=1) \
            or Param.create({'company_id': cls.env.company.id})
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Diurno revisión',
            'attendance_ids': [(5, 0, 0)] + [
                (0, 0, {'dayofweek': str(dia),
                        'hour_from': 8.0, 'hour_to': 16.0,
                        'day_period': 'morning'})
                for dia in range(0, 5)],
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Trabajador revisión',
            'tz': 'America/Lima',
            'resource_calendar_id': cls.calendar.id,
        })

    def _attendance(self, day, hour_in, hour_out, **vals):
        return self.env['hr.attendance'].with_context(
            skip_time_rules=True).create(dict({
                'employee_id': self.employee.id,
                'check_in': _lima(day, int(hour_in), round(hour_in % 1 * 60)),
                'check_out': _lima(day, int(hour_out),
                                   round(hour_out % 1 * 60)),
            }, **vals))

    def _generate(self, start, end, employee=None):
        tareaje = self.Tareaje.create({
            'name': 'Revisión', 'date_start': start, 'date_end': end})
        tareaje.action_generate()
        employee = employee or self.employee
        return tareaje, tareaje.tareaje_line_ids.filtered(
            lambda l: l.employee_id == employee)

    @staticmethod
    def _day(line, day):
        return line.attendance_line_ids.filtered(lambda d: d.fecha == day)

    # ------------------------------------------------------------------
    # #1 Asistencias que no son trabajo real (Odoo 20)
    # ------------------------------------------------------------------
    def test_01_technical_refused_and_deficit_are_not_work(self):
        """La asistencia técnica del cron de ausencias, la rechazada y la
        salida de déficit de una regla de tiempo no son días trabajados."""
        monday, tuesday, wednesday, thursday = (
            date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4),
            date(2026, 3, 5))
        self._attendance(monday, 8.0, 16.0)
        # Cron de absence_management: 00:00:00 → 00:00:01, técnica.
        self.env['hr.attendance'].with_context(skip_time_rules=True).create({
            'employee_id': self.employee.id,
            'check_in': _lima(tuesday, 0),
            'check_out': _lima(tuesday, 0).replace(second=1),
            'in_mode': 'technical', 'out_mode': 'technical',
            'state': 'validated',
        })
        refused = self._attendance(wednesday, 8.0, 16.0)
        refused.action_refuse()
        rule = self.env['hr.time.rule'].create({
            'name': 'Déficit revisión',
            'threshold_operator': 'less_than',
            # Ningún empleado: la regla no debe evaluarse sola.
            'employee_domain': "[('id', '=', 0)]",
            'work_entry_type_id':
                self.env.company.attendance_work_entry_type_id.id,
        })
        self._attendance(thursday, 8.0, 16.0, time_rule_id=rule.id)

        _tareaje, line = self._generate(monday, thursday)
        self.assertEqual(self._day(line, monday).state, 'ok')
        for day in (tuesday, wednesday, thursday):
            with self.subTest(day=day):
                self.assertEqual(self._day(line, day).state, 'falta')
        self.assertAlmostEqual(line.dlab, 1.0, places=2)
        self.assertAlmostEqual(line.fal, 3.0, places=2)

    def test_01_monitor_ignores_technical_attendance(self):
        """El monitor no cuenta la asistencia técnica como marcación."""
        tuesday = date(2026, 3, 3)
        self.env['hr.attendance'].with_context(skip_time_rules=True).create({
            'employee_id': self.employee.id,
            'check_in': _lima(tuesday, 0),
            'check_out': _lima(tuesday, 0).replace(second=1),
            'in_mode': 'technical', 'out_mode': 'technical',
            'state': 'validated',
        })
        self._published_slot(tuesday)
        self.env.flush_all()
        row = self.env['l10n_pe.hr.attendance.monitor'].search([
            ('employee_id', '=', self.employee.id), ('fecha', '=', tuesday)])
        self.assertEqual(row.state, 'no_ok')
        self.assertEqual(row.marc_count, 0)

    def _published_slot(self, day):
        slot = self.env['planning.slot'].create({
            'resource_ids': [(6, 0, self.employee.resource_id.ids)],
            'start_datetime': _lima(day, 8),
            'end_datetime': _lima(day, 16),
        })
        slot.write({'state': '2_published'})
        return slot

    # ------------------------------------------------------------------
    # #10 Feriados en el monitor
    # ------------------------------------------------------------------
    def test_10_monitor_sees_calendar_holidays(self):
        """Los feriados PE se aplican al calendario (con calendar_id): el
        monitor los mostraba como falta."""
        holiday_day = date(2026, 3, 4)
        holiday = self.env['pe.public.holiday'].create({
            'name': 'Feriado revisión', 'date': holiday_day})
        leave = self.env['resource.calendar.leaves'].create({
            'name': 'Feriado revisión',
            'calendar_id': self.calendar.id,
            'company_id': self.env.company.id,
            'date_from': _lima(holiday_day, 0),
            'date_to': _lima(holiday_day, 23, 59),
            'pe_public_holiday_id': holiday.id,
        })
        leave.write({'date_from': _lima(holiday_day, 0),
                     'date_to': _lima(holiday_day, 23, 59)})
        self._published_slot(holiday_day)
        self.env.flush_all()
        row = self.env['l10n_pe.hr.attendance.monitor'].search([
            ('employee_id', '=', self.employee.id),
            ('fecha', '=', holiday_day)])
        self.assertEqual(row.state, 'feriado')

    # ------------------------------------------------------------------
    # #4 Días fuera del contrato
    # ------------------------------------------------------------------
    def test_04_days_outside_contract_are_neither_absence_nor_rest(self):
        """Ingreso el 16: los días anteriores no son faltas ni descansos."""
        self.employee.version_id.contract_date_start = date(2026, 3, 16)
        self._attendance(date(2026, 3, 16), 8.0, 16.0)
        _tareaje, line = self._generate(date(2026, 3, 1), date(2026, 3, 31))
        self.assertEqual(self._day(line, date(2026, 3, 2)).state,
                         'fuera_contrato')
        self.assertEqual(self._day(line, date(2026, 3, 1)).state,
                         'fuera_contrato')
        # Del 16 al 31: 12 laborables (1 asistido + 11 faltas) y 4
        # descansos. Antes, 11 faltas y 4 descansos más del 1 al 15.
        self.assertAlmostEqual(line.dlab, 1.0, places=2)
        self.assertAlmostEqual(line.fal, 11.0, places=2)
        self.assertAlmostEqual(line.dom, 4.0, places=2)

    # ------------------------------------------------------------------
    # #5 Marca de duración cero
    # ------------------------------------------------------------------
    def test_05_zero_duration_mark_is_incomplete(self):
        """Entrada = salida no son 24 h trabajadas."""
        monday = date(2026, 3, 2)
        self._attendance(monday, 8.0, 8.0)
        _tareaje, line = self._generate(monday, monday)
        day = self._day(line, monday)
        self.assertEqual(day.state, 'incompleto')
        self.assertAlmostEqual(day.worked_hours, 0.0, places=2)
        self.assertAlmostEqual(line.he35, 0.0, places=2)
        self.assertAlmostEqual(line.he25, 0.0, places=2)

    # ------------------------------------------------------------------
    # #6 Turno nocturno con ingreso después de medianoche
    # ------------------------------------------------------------------
    def test_06_late_entry_after_midnight_belongs_to_the_night_shift(self):
        """Turno del lunes 22:00-06:00; entra el martes a las 00:10: es el
        turno del lunes (con tardanza), no una falta el lunes."""
        night = self.env['resource.calendar'].create({
            'name': 'Nocturno revisión',
            'attendance_ids': [(5, 0, 0)] + [
                (0, 0, {'dayofweek': str(dia), 'hour_from': 22.0,
                        'hour_to': 24.0, 'day_period': 'afternoon'})
                for dia in range(0, 5)] + [
                (0, 0, {'dayofweek': str(dia), 'hour_from': 0.0,
                        'hour_to': 6.0, 'day_period': 'morning'})
                for dia in range(1, 6)],
        })
        self.employee.version_id.resource_calendar_id = night
        monday, tuesday = date(2026, 3, 2), date(2026, 3, 3)
        self._attendance(tuesday, 0 + 10 / 60.0, 6.0)
        _tareaje, line = self._generate(monday, tuesday)
        day = self._day(line, monday)
        self.assertEqual(day.state, 'ok')
        self.assertAlmostEqual(day.dlab + day.dlabn, 1.0, places=2)
        self.assertGreater(day.tar, 0.0)
        self.assertAlmostEqual(day.fal, 0.0, places=2)

    # ------------------------------------------------------------------
    # #7 Marcación incompleta
    # ------------------------------------------------------------------
    def test_07_close_blocked_with_incomplete_days(self):
        monday = date(2026, 3, 2)
        self.env['hr.attendance'].create({
            'employee_id': self.employee.id, 'check_in': _lima(monday, 8)})
        tareaje, line = self._generate(monday, monday)
        with self.assertRaises(UserError):
            tareaje.action_close()
        # Corregido el día, se aplica.
        self._day(line, monday).write({'state': 'ok', 'dlab': 1.0})
        tareaje.action_close()
        self.assertEqual(tareaje.state, 'done')

    # ------------------------------------------------------------------
    # #13 Registro de asistencia = tareaje
    # ------------------------------------------------------------------
    def test_13_register_uses_tolerance_and_overtime_switch(self):
        """Con 15 min de tolerancia, 10 min tarde y 30 min después de la
        salida: el tareaje da 0,5 h de HE (desde las 16:00); el registro
        daba 0,33 h (desde las 16:10)."""
        self.employee.version_id.l10n_pe_is_overtime = True
        self.param.tareaje_late_tolerance = 0.25
        monday = date(2026, 3, 2)
        self._attendance(monday, 8.0 + 10 / 60.0, 16.5)
        wizard = self.env['l10n_pe.hr.attendance.register.wizard'].create({
            'date_from': monday, 'date_to': monday,
            'employee_ids': [(6, 0, self.employee.ids)],
        })
        row = wizard._register_rows()[0]
        self.assertEqual((row[5], row[6]), ('16:00', '16:30'))
        # Tareaje del periodo sin HE: el registro tampoco muestra
        # sobretiempo.
        self.Tareaje.create({
            'name': 'Sin HE', 'date_start': monday, 'date_end': monday,
            'is_compute_he': False})
        row = wizard._register_rows()[0]
        self.assertEqual((row[5], row[6]), ('', ''))

    # ------------------------------------------------------------------
    # #14 Horario vigente el día
    # ------------------------------------------------------------------
    def test_14_calendar_of_the_day_version(self):
        late = self.env['resource.calendar'].create({
            'name': 'Tarde revisión',
            'attendance_ids': [(5, 0, 0)] + [
                (0, 0, {'dayofweek': str(dia), 'hour_from': 14.0,
                        'hour_to': 22.0, 'day_period': 'afternoon'})
                for dia in range(0, 5)],
        })
        self.employee.version_id.date_version = date(2026, 1, 1)
        self.employee.create_version({
            'date_version': date(2026, 3, 16),
            'resource_calendar_id': late.id,
        })
        tareaje = self.Tareaje.create({
            'name': 'Horario', 'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31)})
        self.assertEqual(
            tareaje._get_day_calendar(self.employee, date(2026, 3, 2)),
            self.calendar)
        self.assertEqual(
            tareaje._get_day_calendar(self.employee, date(2026, 3, 17)), late)
        # Lunes 02/03, 08:00-16:00: sin tardanza con el horario de ese día
        # (con el actual, 14:00-22:00, eran 6 h de «sobretiempo» previo).
        self._attendance(date(2026, 3, 2), 8.0, 16.0)
        tareaje.action_generate()
        day = self._day(tareaje.tareaje_line_ids, date(2026, 3, 2))
        self.assertAlmostEqual(day.htd, 8.0, places=2)

    # ------------------------------------------------------------------
    # #15 Redondeo de minutos
    # ------------------------------------------------------------------
    def test_15_round_half_up(self):
        """Con pasos de 15 min, 37,5 min suben a 45 (no bajan a 30)."""
        self.assertAlmostEqual(
            self.Tareaje._round_to_minutes(37.5 / 60.0, 15), 0.75, places=4)
        self.assertAlmostEqual(
            self.Tareaje._round_to_minutes(22.5 / 60.0, 15), 0.5, places=4)

    # ------------------------------------------------------------------
    # #17 Detalle de un tareaje aplicado
    # ------------------------------------------------------------------
    def test_17_applied_detail_is_locked(self):
        tareaje = self.Tareaje.create({
            'name': 'Bloqueo', 'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31)})
        line = self.env['hr.tareaje.manager.line'].create({
            'tareaje_id': tareaje.id, 'employee_id': self.employee.id})
        day = self.env['hr.tareaje.manager.line.attendance'].create({
            'tareaje_line_id': line.id, 'employee_id': self.employee.id,
            'fecha': date(2026, 3, 2), 'state': 'ok', 'dlab': 1.0})
        tareaje.action_close()
        with self.assertRaises(UserError):
            day.write({'he25': 4.0})
        with self.assertRaises(UserError):
            day.unlink()
        with self.assertRaises(UserError):
            self.env['hr.tareaje.manager.line.attendance'].create({
                'tareaje_line_id': line.id, 'employee_id': self.employee.id,
                'fecha': date(2026, 3, 3), 'state': 'ok', 'dlab': 1.0})
        with self.assertRaises(UserError):
            line.write({'dlab': 30.0})
        tareaje.action_reopen()
        day.write({'he25': 4.0})
        self.assertAlmostEqual(day.he25, 4.0, places=2)


@tagged('post_install', '-at_install', 'al_hr_pe_attendance')
class TestReviewTareajePayslip(TransactionCase):
    """Volcado del tareaje a la boleta (#2 y #3)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'PE Tareaje Revisión SAC',
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.env.user.company_ids |= cls.company
        cls.env.user.group_ids |= cls.env.ref(
            'hr_payroll.group_hr_payroll_manager')
        cls.env['hr.main.parameter'].create({
            'company_id': cls.company.id, 'rmv': 1130.0})
        cls.structure = cls.env.ref('al_hr_pe.base_structure')
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Trabajador boleta revisión',
            'company_id': cls.company.id,
            'tz': 'America/Lima',
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'wage': 3000.0,
            'structure_type_id': cls.structure.type_id.id,
        })

    def _tareaje(self, start, end, he25_days=()):
        """Tareaje aplicado: laborables con DLAB, fines de semana DOM."""
        tareaje = self.env['hr.tareaje.manager'].create({
            'name': 'Boleta', 'date_start': start, 'date_end': end,
            'company_id': self.company.id})
        line = self.env['hr.tareaje.manager.line'].create({
            'tareaje_id': tareaje.id, 'employee_id': self.employee.id})
        days = []
        day = start
        while day <= end:
            if day.weekday() < 5:
                vals = {'state': 'ok', 'dlab': 1.0, 'htd': 8.0,
                        'he25': 1.0 if day.day in he25_days else 0.0}
            else:
                vals = {'state': 'descanso', 'dom': 1.0}
            days.append((0, 0, dict(vals, fecha=day,
                                    employee_id=self.employee.id)))
            day += timedelta(days=1)
        line.attendance_line_ids = days
        tareaje.action_close()
        return tareaje

    def _slip(self):
        return self.env['hr.payslip'].create({
            'name': 'Boleta tareaje',
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 3, 1),
            'date_to': date(2026, 3, 31),
        })

    @staticmethod
    def _sum(slip, code, field='number_of_days'):
        return sum(slip.worked_days_line_ids.filtered(
            lambda l: l.code == code).mapped(field))

    def test_02_two_versions_do_not_duplicate_the_tareaje(self):
        """Aumento desde el 16: una línea por versión, cada una con sus
        días; la suma es la del tareaje (antes, 22 días en cada una)."""
        self.employee.create_version({
            'date_version': date(2026, 3, 16), 'wage': 3600.0})
        self._tareaje(date(2026, 3, 1), date(2026, 3, 31),
                      he25_days=(2, 20))
        slip = self._slip()
        dlab = slip.worked_days_line_ids.filtered(lambda l: l.code == 'DLAB')
        self.assertEqual(len(dlab.version_id), 2)
        self.assertAlmostEqual(self._sum(slip, 'DLAB'), 22.0, places=2)
        self.assertAlmostEqual(self._sum(slip, 'DOM'), 9.0, places=2)
        self.assertAlmostEqual(
            self._sum(slip, 'HE25', 'number_of_hours'), 2.0, places=2)
        first = dlab.filtered(
            lambda l: l.version_id.date_version < date(2026, 3, 16))
        self.assertAlmostEqual(sum(first.mapped('number_of_days')), 10.0,
                               places=2)

    def test_03_partial_tareaje_keeps_native_for_the_rest(self):
        """Solo la primera quincena tareada: la segunda conserva el
        cálculo nativo (antes, DLAB 10 + DOM 5 para todo el mes)."""
        self._tareaje(date(2026, 3, 1), date(2026, 3, 15), he25_days=(3,))
        slip = self._slip()
        self.assertAlmostEqual(self._sum(slip, 'DLAB'), 22.0, places=2)
        self.assertAlmostEqual(self._sum(slip, 'DOM'), 9.0, places=2)
        self.assertAlmostEqual(self._sum(slip, 'FAL'), 0.0, places=2)
        self.assertAlmostEqual(
            self._sum(slip, 'HE25', 'number_of_hours'), 1.0, places=2)

    def test_04_entry_mid_month_prorates_on_base_30(self):
        """Ingreso el 16 con el tareaje del mes: DLAB + DOM solo del
        contrato (16 días), sin faltas antes del ingreso."""
        self.employee.version_id.contract_date_start = date(2026, 3, 16)
        tareaje = self.env['hr.tareaje.manager'].create({
            'name': 'Ingreso', 'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31), 'company_id': self.company.id})
        calendar = self.employee.resource_calendar_id
        self.assertTrue(calendar)
        for offset in range(16, 32):
            day = date(2026, 3, offset)
            if day.weekday() < 5:
                check_in = datetime(2026, 3, offset, 13, 0)
                self.env['hr.attendance'].create({
                    'employee_id': self.employee.id,
                    'check_in': check_in,
                    'check_out': check_in.replace(hour=21),
                })
        tareaje.action_generate()
        line = tareaje.tareaje_line_ids
        self.assertAlmostEqual(line.fal, 0.0, places=2)
        self.assertAlmostEqual(line.dlab + line.dom, 16.0, places=2)
