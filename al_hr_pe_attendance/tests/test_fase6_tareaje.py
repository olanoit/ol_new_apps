# -*- coding: utf-8 -*-
"""Tests de la Fase 6 — tareaje (clasificación peruana de horas).

Cubren los métodos puros de clasificación (nocturnidad con cruce de
medianoche, HE 25 %→35 %, descanso/feriado al 100 %, tardanzas y
redondeo), el flujo del gestor de tareaje (port de los tests v18 de
``hr_attendance_payslip``) y la agregación hacia la boleta con
compensación de horas — todo sin marcaciones reales.
"""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'al_hr_pe_attendance')
class TestTareajeClassification(TransactionCase):
    """Métodos puros de hr.tareaje.manager (sin registros)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Tareaje = cls.env['hr.tareaje.manager']

    # ----- Nocturnidad (art. 8 D.S. 007-2002-TR) -----
    def test_split_night_day_shift(self):
        day, night = self.Tareaje._split_night_hours(8.0, 17.0)
        self.assertAlmostEqual(day, 9.0, places=2)
        self.assertAlmostEqual(night, 0.0, places=2)

    def test_split_night_cross_midnight(self):
        # 21:00 → 06:00 del día siguiente: 1 h diurna (21-22) y
        # 8 h nocturnas (22-24 + 00-06).
        day, night = self.Tareaje._split_night_hours(21.0, 6.0)
        self.assertAlmostEqual(day, 1.0, places=2)
        self.assertAlmostEqual(night, 8.0, places=2)

    def test_split_night_early_morning(self):
        # 02:00 → 08:00: 4 h nocturnas (02-06) y 2 h diurnas.
        day, night = self.Tareaje._split_night_hours(2.0, 8.0)
        self.assertAlmostEqual(day, 2.0, places=2)
        self.assertAlmostEqual(night, 4.0, places=2)

    def test_split_night_custom_window(self):
        # Ventana parametrizada 21:00-05:00.
        day, night = self.Tareaje._split_night_hours(
            20.0, 23.0, night_from=21.0, night_to=5.0)
        self.assertAlmostEqual(day, 1.0, places=2)
        self.assertAlmostEqual(night, 2.0, places=2)

    # ----- Sobretiempo (art. 10 D.S. 007-2002-TR) -----
    def test_split_overtime_under_limit(self):
        self.assertEqual(
            self.Tareaje._split_overtime_hours(1.5), (1.5, 0.0))

    def test_split_overtime_at_limit(self):
        self.assertEqual(
            self.Tareaje._split_overtime_hours(2.0), (2.0, 0.0))

    def test_split_overtime_over_limit(self):
        self.assertEqual(
            self.Tareaje._split_overtime_hours(3.5), (2.0, 1.5))

    def test_split_overtime_custom_limit(self):
        self.assertEqual(
            self.Tareaje._split_overtime_hours(3.5, he25_limit=3.0),
            (3.0, 0.5))

    def test_split_overtime_negative(self):
        self.assertEqual(
            self.Tareaje._split_overtime_hours(-1.0), (0.0, 0.0))

    # ----- Clasificación del día completo -----
    def test_workday_normal(self):
        res = self.Tareaje._classify_day(
            8.0, 17.0, sched_in=8.0, sched_out=17.0, break_hours=1.0)
        self.assertAlmostEqual(res['htd'], 8.0, places=2)
        self.assertAlmostEqual(res['htn'], 0.0, places=2)
        self.assertAlmostEqual(res['dlab'], 1.0, places=2)
        self.assertAlmostEqual(res['dlabn'], 0.0, places=2)
        for key in ('tar', 'he25', 'he35', 'he100', 'fal', 'dom', 'fer',
                    'incos'):
            self.assertAlmostEqual(res[key], 0.0, places=2, msg=key)

    def test_workday_overtime_25_then_35(self):
        # 3 h tras la salida programada: 2 al 25 % y 1 al 35 %.
        res = self.Tareaje._classify_day(
            8.0, 20.0, sched_in=8.0, sched_out=17.0, break_hours=1.0)
        self.assertAlmostEqual(res['he25'], 2.0, places=2)
        self.assertAlmostEqual(res['he35'], 1.0, places=2)
        self.assertAlmostEqual(res['htd'], 8.0, places=2)

    def test_workday_overtime_disabled(self):
        # Trabajador no sujeto a HE (art. 5 D.S. 007-2002-TR).
        res = self.Tareaje._classify_day(
            8.0, 20.0, sched_in=8.0, sched_out=17.0, break_hours=1.0,
            compute_overtime=False)
        self.assertAlmostEqual(res['he25'], 0.0, places=2)
        self.assertAlmostEqual(res['he35'], 0.0, places=2)

    def test_workday_tardiness_within_tolerance(self):
        res = self.Tareaje._classify_day(
            8.25, 17.0, sched_in=8.0, sched_out=17.0, tolerance=0.5)
        self.assertAlmostEqual(res['tar'], 0.0, places=2)

    def test_workday_tardiness_beyond_tolerance(self):
        # Fuera de tolerancia se computa el retraso completo (v18).
        res = self.Tareaje._classify_day(
            8.5, 17.0, sched_in=8.0, sched_out=17.0, tolerance=0.25)
        self.assertAlmostEqual(res['tar'], 0.5, places=2)

    def test_night_shift_cross_midnight(self):
        # Turno 22:00 → 06:00: día íntegramente nocturno.
        res = self.Tareaje._classify_day(
            22.0, 6.0, sched_in=22.0, sched_out=6.0)
        self.assertAlmostEqual(res['htn'], 8.0, places=2)
        self.assertAlmostEqual(res['htd'], 0.0, places=2)
        self.assertAlmostEqual(res['dlabn'], 1.0, places=2)
        self.assertAlmostEqual(res['dlab'], 0.0, places=2)

    def test_workday_absence(self):
        res = self.Tareaje._classify_day(None, None, day_kind='workday')
        self.assertAlmostEqual(res['fal'], 1.0, places=2)
        self.assertAlmostEqual(res['dom'], 0.0, places=2)

    def test_rest_day_not_worked(self):
        res = self.Tareaje._classify_day(None, None, day_kind='descanso')
        self.assertAlmostEqual(res['dom'], 1.0, places=2)
        self.assertAlmostEqual(res['fal'], 0.0, places=2)

    def test_rest_day_worked_without_schedule(self):
        # D.Leg. 713 arts. 3-4: descanso laborado → FER computa el día;
        # sin turno de referencia, HE100 = horas sobre la jornada legal.
        res = self.Tareaje._classify_day(
            8.0, 17.0, day_kind='descanso')
        self.assertAlmostEqual(res['fer'], 1.0, places=2)
        self.assertAlmostEqual(res['he100'], 1.0, places=2)
        self.assertAlmostEqual(res['dlab'], 0.0, places=2)
        self.assertAlmostEqual(res['htd'], 0.0, places=2)

    def test_holiday_worked_with_schedule(self):
        res = self.Tareaje._classify_day(
            8.0, 19.0, sched_in=8.0, sched_out=17.0, day_kind='feriado')
        self.assertAlmostEqual(res['fer'], 1.0, places=2)
        self.assertAlmostEqual(res['he100'], 2.0, places=2)

    def test_incomplete_marks(self):
        res = self.Tareaje._classify_day(8.0, None)
        self.assertAlmostEqual(res['incos'], 1.0, places=2)
        self.assertAlmostEqual(res['fal'], 0.0, places=2)

    def test_round_to_minutes(self):
        self.assertAlmostEqual(
            self.Tareaje._round_to_minutes(0.24, 15), 0.25, places=4)
        self.assertAlmostEqual(
            self.Tareaje._round_to_minutes(0.24, 0), 0.24, places=4)

    def test_overtime_rounded_to_minutes(self):
        # Redondeo a 30 min: 1.2 h extra → 1.0 h.
        res = self.Tareaje._classify_day(
            8.0, 18.2, sched_in=8.0, sched_out=17.0, round_minutes=30)
        self.assertAlmostEqual(res['he25'], 1.0, places=2)


@tagged('post_install', '-at_install', 'al_hr_pe_attendance')
class TestTareajeFlow(TransactionCase):
    """Flujo del gestor (port de los tests v18)."""

    def _create_tareaje(self, name='Tareaje Test'):
        return self.env['hr.tareaje.manager'].create({
            'name': name,
            'date_start': date(2026, 1, 1),
            'date_end': date(2026, 1, 31),
        })

    def test_defaults(self):
        tareaje = self._create_tareaje()
        self.assertEqual(tareaje.company_id, self.env.company)
        self.assertEqual(tareaje.state, 'draft')

    def test_close_and_reopen(self):
        tareaje = self._create_tareaje('Tareaje Cierre')
        tareaje.set_close()
        self.assertEqual(tareaje.state, 'done')
        tareaje.set_reopen()
        self.assertEqual(tareaje.state, 'draft')

    def test_unlink_done_raises(self):
        tareaje = self._create_tareaje('Tareaje Bloqueo')
        tareaje.set_close()
        with self.assertRaises(UserError):
            tareaje.unlink()

    def test_line_company_follows_tareaje(self):
        tareaje = self._create_tareaje('Tareaje Línea')
        employee = self.env['hr.employee'].create(
            {'name': 'Empleado Tareaje'})
        line = self.env['hr.tareaje.manager.line'].create({
            'tareaje_id': tareaje.id,
            'employee_id': employee.id,
            'dlab': 22.0,
        })
        self.assertEqual(line.company_id, self.env.company)

    def test_version_overtime_flag_default(self):
        employee = self.env['hr.employee'].create(
            {'name': 'Empleado HE Test'})
        self.assertFalse(employee.version_id.l10n_pe_is_overtime)
        employee.version_id.l10n_pe_is_overtime = True
        self.assertTrue(employee.version_id.l10n_pe_is_overtime)


@tagged('post_install', '-at_install', 'al_hr_pe_attendance')
class TestTareajePayslipTotals(TransactionCase):
    """Agregación hacia la boleta y compensación de horas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create(
            {'name': 'Empleado Totales'})
        cls.tareaje = cls.env['hr.tareaje.manager'].create({
            'name': 'Tareaje Totales',
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31),
        })
        cls.line = cls.env['hr.tareaje.manager.line'].create({
            'tareaje_id': cls.tareaje.id,
            'employee_id': cls.employee.id,
        })
        Day = cls.env['hr.tareaje.manager.line.attendance']
        cls.day_normal = Day.create({
            'tareaje_line_id': cls.line.id,
            'employee_id': cls.employee.id,
            'fecha': date(2026, 3, 2),
            'state': 'ok',
            'dlab': 1.0, 'htd': 8.0, 'he25': 2.0, 'he35': 1.0,
        })
        cls.day_compensated = Day.create({
            'tareaje_line_id': cls.line.id,
            'employee_id': cls.employee.id,
            'fecha': date(2026, 3, 3),
            'state': 'ok',
            'dlab': 1.0, 'htd': 8.0, 'he25': 2.0, 'he35': 1.5,
            'hours_compensate': 3.0,
        })

    def test_totals_require_done_state(self):
        totals = self.env['hr.tareaje.manager']._get_payslip_totals(
            self.employee, date(2026, 3, 1), date(2026, 3, 31))
        self.assertEqual(totals, {}, 'Un tareaje en borrador no alimenta '
                                     'la boleta.')

    def test_totals_with_compensation(self):
        self.tareaje.set_close()
        totals = self.env['hr.tareaje.manager']._get_payslip_totals(
            self.employee, date(2026, 3, 1), date(2026, 3, 31))
        self.assertAlmostEqual(totals['dlab'], 2.0, places=2)
        self.assertAlmostEqual(totals['htd'], 16.0, places=2)
        # Día 2: sin compensar (2.0 / 1.0). Día 3: 3 h compensadas →
        # 2 h descuentan HE25 y 1 h descuenta HE35 (2.0→0.0 / 1.5→0.5).
        self.assertAlmostEqual(totals['he25'], 2.0, places=2)
        self.assertAlmostEqual(totals['he35'], 1.5, places=2)

    def test_totals_filter_by_period(self):
        self.tareaje.set_close()
        totals = self.env['hr.tareaje.manager']._get_payslip_totals(
            self.employee, date(2026, 3, 1), date(2026, 3, 2))
        self.assertAlmostEqual(totals['dlab'], 1.0, places=2)
        self.assertAlmostEqual(totals['he35'], 1.0, places=2)

    def test_totals_other_employee_empty(self):
        self.tareaje.set_close()
        other = self.env['hr.employee'].create({'name': 'Otro Empleado'})
        totals = self.env['hr.tareaje.manager']._get_payslip_totals(
            other, date(2026, 3, 1), date(2026, 3, 31))
        self.assertEqual(totals, {})


@tagged('post_install', '-at_install', 'al_hr_pe_attendance')
class TestTareajeMainParameter(TransactionCase):
    """Extensión de hr.main.parameter: defaults y mapa de work entries."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Param = cls.env['hr.main.parameter']
        cls.param = Param.search(
            [('company_id', '=', cls.env.company.id)], limit=1)
        if not cls.param:
            cls.param = Param.create({'company_id': cls.env.company.id})

    def test_parameter_defaults(self):
        self.assertAlmostEqual(self.param.tareaje_night_from, 22.0)
        self.assertAlmostEqual(self.param.tareaje_night_to, 6.0)
        self.assertAlmostEqual(self.param.tareaje_he25_hours, 2.0)

    def test_wet_map_defaults_by_code(self):
        wet_map = self.param.get_tareaje_wet_map()
        for bucket, code in (('dlab', 'DLAB'), ('dom', 'DOM'),
                             ('fer', 'FER'), ('fal', 'FAL'),
                             ('tar', 'TAR'), ('he25', 'HE25'),
                             ('he35', 'HE35'), ('he100', 'HE100')):
            self.assertTrue(wet_map[bucket], 'Falta el tipo %s' % code)
            self.assertEqual(wet_map[bucket].code, code)
        # Nocturnidad sin tipo por defecto (aún no existe en al_hr_pe).
        self.assertFalse(wet_map['noct'])
