# -*- coding: utf-8 -*-
"""Correcciones de la auditoría (parte A): CTS, gratificación,
vacaciones y liquidación de cese.

Mismo caso de referencia que la Fase 3 (sueldo 3 000, régimen general,
boletas Nov-2025 → Jun-2026 en lotes mensuales). Cada test fija una
regla legal concreta que el cálculo anterior incumplía.
"""
from calendar import monthrange
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_fase3_benefits import BenefitsCaseBase


@tagged('post_install', '-at_install')
class TestAuditFixesA(BenefitsCaseBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        WorkEntryType = cls.env['hr.work.entry.type']
        cls.wet_dmed = WorkEntryType.search([('code', '=', 'DMED')], limit=1)
        cls.param.medical_rest_wd_ids = cls.wet_dmed

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _slip(self, year, month):
        return self.runs[(year, month)].slip_ids.filtered(
            lambda slip: slip.employee_id == self.employee)

    def _move_days(self, year, month, code, days):
        """Pasa ``days`` días del DLAB (y del DOM si no alcanza) al
        concepto ``code`` en la boleta del mes, sin cambiar el total de
        días del mes (DLAB + DOM + … = días del mes)."""
        slip = self._slip(year, month)
        lines = slip.worked_days_line_ids
        target = lines.filtered(lambda wd: wd.code == code)
        if not target:
            wet = self.env['hr.work.entry.type'].search(
                [('code', '=', code)], limit=1)
            target = self.env['hr.payslip.worked_days'].create({
                'payslip_id': slip.id, 'work_entry_type_id': wet.id,
                'number_of_days': 0.0, 'number_of_hours': 0.0,
            })
        pending = days
        for source_code in ('DLAB', 'DOM'):
            source = lines.filtered(lambda wd: wd.code == source_code)[:1]
            taken = min(pending, source.number_of_days)
            source.number_of_days -= taken
            pending -= taken
        self.assertFalse(pending, 'el mes no tiene días suficientes')
        target.number_of_days += days

    def _new_cts(self, cts_type='05', year=2026, run=None):
        return self.env['hr.cts'].create({
            'company_id': self.company.id,
            'year': year,
            'type': cts_type,
            'payslip_run_id': (run or self.batch).id,
            'deposit_date': date(year, 5 if cts_type == '05' else 11, 15),
        })

    def _cts_line(self, cts):
        cts.action_process()
        line = cts.line_ids.filtered(
            lambda line: line.employee_id == self.employee)
        self.assertEqual(len(line), 1)
        return line

    # ------------------------------------------------------------------
    # Faltas: cuentan para el mes y se descuentan una sola vez
    # ------------------------------------------------------------------
    def test_cts_lack_discounted_once(self):
        self._move_days(2026, 1, 'FAL', 2)
        line = self._cts_line(self._new_cts())
        self.assertEqual(line.months, 6, 'una falta no hace perder el mes')
        self.assertEqual(line.days, 0)
        self.assertAlmostEqual(line.lacks, 2.0)
        per_day = self.wage / 12 / 30
        self.assertAlmostEqual(
            line.total_cts, self.wage / 2 - 2 * per_day, delta=0.05)

    def test_gratification_lack_discounted_once(self):
        self._move_days(2026, 3, 'FAL', 1)
        grati = self.env['hr.gratification'].create({
            'company_id': self.company.id, 'year': 2026, 'type': '07',
            'with_bonus': False, 'payslip_run_id': self.batch_jun.id,
            'deposit_date': date(2026, 7, 15),
        })
        grati.action_process()
        line = grati.line_ids.filtered(
            lambda line: line.employee_id == self.employee)
        self.assertEqual(line.months, 6)
        self.assertAlmostEqual(
            line.total_grat, self.wage - self.wage / 6 / 30, delta=0.05)

    # ------------------------------------------------------------------
    # Descanso médico: computable, tope de 60 días por año CTS
    # ------------------------------------------------------------------
    def test_medical_rest_excess_per_semester(self):
        self._move_days(2026, 1, 'DMED', 31)
        self._move_days(2026, 2, 'DMED', 28)
        self._move_days(2026, 3, 'DMED', 10)
        self._move_days(2026, 5, 'DMED', 5)
        Param = self.env['hr.main.parameter']
        self.assertEqual(
            Param.calculate_excess_medical_rest(
                self.employee, self.company, date(2025, 11, 1),
                date(2026, 4, 30)),
            (69.0, 9.0))
        # El segundo semestre no vuelve a contar los días del primero:
        # solo los 5 de mayo, que ya exceden el tope completo.
        self.assertEqual(
            Param.calculate_excess_medical_rest(
                self.employee, self.company, date(2026, 5, 1),
                date(2026, 10, 31)),
            (5.0, 5.0))

    def test_cts_medical_rest_counts_and_excess_discounted(self):
        self._move_days(2026, 1, 'DMED', 31)
        self._move_days(2026, 2, 'DMED', 28)
        self._move_days(2026, 3, 'DMED', 10)
        line = self._cts_line(self._new_cts())
        self.assertEqual(line.months, 6, 'el descanso médico computa')
        self.assertAlmostEqual(line.excess_medical_rest, 9.0)
        per_day = self.wage / 12 / 30
        self.assertAlmostEqual(
            line.total_cts, self.wage / 2 - 9 * per_day, delta=0.05)

    def test_gratification_counts_medical_rest(self):
        """Ley 27735 art. 7: los días subsidiados son laborados."""
        self._move_days(2026, 2, 'DMED', 28)
        grati = self.env['hr.gratification'].create({
            'company_id': self.company.id, 'year': 2026, 'type': '07',
            'with_bonus': False, 'payslip_run_id': self.batch_jun.id,
            'deposit_date': date(2026, 7, 15),
        })
        grati.action_process()
        line = grati.line_ids.filtered(
            lambda line: line.employee_id == self.employee)
        self.assertEqual(line.months, 6)
        self.assertAlmostEqual(line.total_grat, self.wage, delta=0.05)

    # ------------------------------------------------------------------
    # Recalcular una línea de CTS no cambia su importe
    # ------------------------------------------------------------------
    def test_cts_recompute_keeps_amount(self):
        previous = self._new_cts('11', 2025, run=self.runs[(2025, 11)])
        self.env['hr.cts.line'].create({
            'cts_id': previous.id, 'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id,
            'less_than_one_month': True, 'total_cts': 100.0,
        })
        self._move_days(2026, 1, 'DMED', 31)
        self._move_days(2026, 2, 'DMED', 28)
        self._move_days(2026, 3, 'DMED', 10)
        line = self._cts_line(self._new_cts())
        self.assertAlmostEqual(line.remaining_wage, 100.0)
        engine_total = line.total_cts
        line.action_compute()
        self.assertAlmostEqual(line.total_cts, engine_total, delta=0.05)

    # ------------------------------------------------------------------
    # Regla de las 3 apariciones: cuenta meses, no boletas
    # ------------------------------------------------------------------
    def test_count_months_not_slips(self):
        Param = self.env['hr.main.parameter']
        slips = self.env['hr.payslip'].search(
            [('employee_id', '=', self.employee.id)])
        self.assertEqual(Param._count_months(slips), 8)
        extra = self.env['hr.payslip'].create({
            'name': 'Segunda boleta de abril',
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 4, 1), 'date_to': date(2026, 4, 30),
        })
        self.assertEqual(Param._count_months(slips | extra), 8)

    # ------------------------------------------------------------------
    # Estados: lo exportado no se recalcula
    # ------------------------------------------------------------------
    def test_exported_cts_cannot_be_recomputed(self):
        cts = self._new_cts()
        cts.action_process()
        cts.state = 'exported'
        with self.assertRaises(UserError):
            cts.action_process()
        with self.assertRaises(UserError):
            cts.action_export_to_payslips()
        with self.assertRaises(UserError):
            cts.line_ids.action_compute()
        cts.action_draft()
        cts.action_process()

    def test_bonus_default_on(self):
        grati = self.env['hr.gratification'].create({
            'company_id': self.company.id, 'year': 2026, 'type': '07',
            'payslip_run_id': self.batch_jun.id,
            'deposit_date': date(2026, 7, 15),
        })
        self.assertTrue(grati.with_bonus, 'la bonificación es permanente')

    # ------------------------------------------------------------------
    # Vacaciones
    # ------------------------------------------------------------------
    def test_last_anniversary(self):
        anniversary = self.env['hr.liquidation']._last_anniversary
        self.assertEqual(anniversary(date(2020, 3, 1), date(2026, 10, 15)),
                         date(2026, 3, 1))
        self.assertEqual(anniversary(date(2020, 3, 1), date(2026, 2, 10)),
                         date(2025, 3, 1))
        self.assertEqual(anniversary(date(2020, 2, 29), date(2026, 3, 1)),
                         date(2026, 2, 28))
        self.assertEqual(anniversary(date(2026, 1, 5), date(2026, 8, 1)),
                         date(2026, 1, 5))

    def test_vacation_rest_small_company_15_days(self):
        self.employee.version_id.l10n_pe_labor_regime = 'small'
        Rest = self.env['hr.vacation.rest']
        Rest.get_vacation_employee(self.employee, False)
        full_year = Rest.search([
            ('employee_id', '=', self.employee.id),
            ('date_from', '=', date(2025, 1, 1)),
        ])
        self.assertEqual(len(full_year), 1)
        self.assertAlmostEqual(full_year.days, 15.0)
        self.assertAlmostEqual(full_year.amount, self.wage / 2, delta=0.01)

    def test_vacation_rest_ceased_before_anniversary(self):
        """Un cesado no recibe un año vacacional que no completó."""
        self.employee.version_id.contract_date_end = date(2025, 12, 15)
        Rest = self.env['hr.vacation.rest']
        Rest.get_vacation_employee(self.employee, False)
        first = Rest.search([
            ('employee_id', '=', self.employee.id),
            ('date_from', '=', date(2025, 1, 1)),
        ])
        self.assertEqual(len(first), 1)
        self.assertEqual(first.date_end, date(2025, 12, 15))
        # 11 meses + 15 días a 2.5 días/mes
        self.assertAlmostEqual(first.days, 11 * 2.5 + 15 * 2.5 / 30,
                               delta=0.01)

    def test_vacation_line_small_company_rate(self):
        """15 días de la pequeña empresa valen medio sueldo, no un
        cuarto: el día vale remuneración/30 en todos los regímenes."""
        self.employee.version_id.l10n_pe_labor_regime = 'small'
        vacation = self.env['hr.vacation'].create({
            'company_id': self.company.id, 'year': 2026,
            'payslip_run_id': self.batch_jun.id,
        })
        line = self.env['hr.vacation.line'].create({
            'vacation_id': vacation.id,
            'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id,
            'wage': self.wage,
            'accrued_vacation': 15,
        })
        line.with_context(line_form=True).action_compute()
        self.assertAlmostEqual(line.total_vacation, self.wage / 2,
                               delta=0.01)

    # ------------------------------------------------------------------
    # Liquidación de cese
    # ------------------------------------------------------------------
    def _cessation_in_july(self, day=10, month=7):
        version = self.employee.version_id
        version.write({
            'contract_date_end': date(2026, month, day),
            'situation_id': self.env.ref('al_hr_pe.situation_0').id,
        })
        periodo = self.env['hr.period'].search([
            ('code', '=', '2026%02d' % month),
            ('company_id', '=', self.company.id)], limit=1)
        last = monthrange(2026, month)[1]
        run = self.env['hr.payslip.run'].create({
            'name': 'Lote 2026-%02d' % month,
            'date_start': date(2026, month, 1),
            'date_end': date(2026, month, last),
            'company_id': self.company.id,
            'periodo_id': periodo.id,
        })
        slip = self.env['hr.payslip'].create({
            'name': 'Boleta 2026-%02d' % month,
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, month, 1),
            'date_to': date(2026, month, last),
            'payslip_run_id': run.id,
        })
        slip.compute_sheet()
        input_type = self.env['hr.payslip.input.type'].search([], limit=1)
        self.param.write({
            'truncated_gratification_input_id': input_type.id,
            'truncated_bonus_nine_input_id': input_type.id,
            'truncated_cts_input_id': input_type.id,
            'vacation_input_id': input_type.id,
            'truncated_vacation_input_id': input_type.id,
        })
        return self.env['hr.liquidation'].create({
            'company_id': self.company.id, 'year': 2026,
            'gratification_type': '12' if month > 6 else '07',
            'cts_type': '11',
            'payslip_run_id': run.id,
        })

    def test_liquidation_may_pays_november_april_cts(self):
        """Cese el 10-may (antes del depósito del 15): la CTS de
        nov-abr se paga en la liquidación; antes no la pagaba nadie."""
        liquidation = self._cessation_in_july(month=5)
        liquidation.action_process()
        winter = liquidation.cts_line_ids.filtered(
            lambda line: line.cessation_date == date(2026, 5, 10)
            and line.compute_date <= date(2025, 11, 1))
        self.assertEqual(len(winter), 1)

    def test_liquidation_exports_vacation_indemnity(self):
        """La indemnización vacacional va a la boleta por INDVAC y suma
        al neto de la línea sin pagar aportes."""
        liquidation = self._cessation_in_july()
        liquidation.action_process()
        line = liquidation.vacation_line_ids[:1]
        if not line:
            self.skipTest('el cese no generó línea de vacaciones')
        total = line.total
        line.with_context(line_form=True).action_compute()
        self.assertAlmostEqual(line.total, total, places=2,
                               msg='recalcular no cambia el importe')
        line.vacation_indemnity = 1000.0
        line.with_context(line_form=True).action_compute()
        self.assertAlmostEqual(line.total, total + 1000.0, places=2)
        liquidation.action_export_to_payslips()
        slip = liquidation.payslip_run_id.slip_ids.filtered(
            lambda s: s.employee_id == self.employee)
        indem = slip.input_line_ids.filtered(
            lambda i: i.input_type_id == self.env.ref('al_hr_pe.input_type_INDVAC'))
        self.assertAlmostEqual(indem.amount, 1000.0, 2)

    def test_liquidation_july_pays_first_semester(self):
        """Cese el 10-jul (antes del pago del 15): ene-jun se paga
        como gratificación trunca."""
        liquidation = self._cessation_in_july()
        liquidation.action_process()
        first_semester = liquidation.gratification_line_ids.filtered(
            lambda line: line.compute_date == date(2026, 1, 1))
        self.assertEqual(len(first_semester), 1)
        self.assertEqual(first_semester.months, 6)
        self.assertAlmostEqual(first_semester.total_grat, self.wage,
                               delta=0.05)

    def test_liquidation_exports_advanced_vacation(self):
        """Las vacaciones adelantadas van a la boleta como descuento
        (ADE_VAC), no solo restadas en el total de la línea (07/10/2026)."""
        liquidation = self._cessation_in_july()
        liquidation.action_process()
        line = liquidation.vacation_line_ids[:1]
        if not line:
            self.skipTest('el cese no generó línea de vacaciones')
        line.advanced_vacation = 300.0
        liquidation.action_export_to_payslips()
        slip = liquidation.payslip_run_id.slip_ids.filtered(
            lambda s: s.employee_id == self.employee)
        ade = slip.input_line_ids.filtered(
            lambda i: i.input_type_id == self.env.ref('al_hr_pe.input_type_ADE_VAC'))
        self.assertAlmostEqual(ade.amount, 300.0, 2)

    def test_liquidation_detail_views_do_not_crash(self):
        liquidation = self._cessation_in_july()
        cts_line = self.env['hr.cts.line'].create({
            'liquidation_id': liquidation.id,
            'employee_id': self.employee.id,
            'cessation_date': date(2026, 7, 10),
        })
        self.assertEqual(cts_line.action_show_details()['type'],
                         'ir.actions.act_window')
        grati_line = self.env['hr.gratification.line'].create({
            'liquidation_id': liquidation.id,
            'employee_id': self.employee.id,
            'cessation_date': date(2026, 7, 10),
        })
        self.assertEqual(grati_line.action_show_details()['type'],
                         'ir.actions.act_window')
