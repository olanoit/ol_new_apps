# -*- coding: utf-8 -*-
"""Récord vacacional por año de servicios (D.Leg. 713, art. 10 y 12).

Antes el recálculo de saldos daba 30 días por cada año completo sin
mirar el récord. Las boletas se crean cerradas y con sus líneas de días
escritas a mano (sin pasar por el motor): una boleta por año de récord
basta para fijar los días que suman.
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVacationRecord(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'PE Récord SAC', 'country_id': cls.env.ref('base.pe').id})
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.env.user.company_ids |= cls.company
        cls.env.user.group_ids |= cls.env.ref(
            'hr_payroll.group_hr_payroll_manager')
        cls.structure = cls.env.ref('al_hr_pe.base_structure')
        cls.Record = cls.env['hr.vacation.record']
        cls.Rest = cls.env['hr.vacation.rest']
        cls.wet = {
            wet.code: wet for wet in cls.env['hr.work.entry.type'].search([
                ('country_id.code', '=', 'PE')])}
        cls.calendars = {
            days: cls._calendar(days) for days in (6, 5, 4)}

    @classmethod
    def _calendar(cls, days):
        return cls.env['resource.calendar'].create({
            'name': 'Jornada de %s días' % days,
            'company_id': cls.company.id,
            'attendance_ids': [(5, 0, 0)] + [
                (0, 0, {'dayofweek': str(day),
                        'hour_from': 8.0, 'hour_to': 16.0})
                for day in range(days)],
        })

    def _employee(self, weekly_days=6, admission=date(2025, 1, 1)):
        employee = self.env['hr.employee'].create({
            'names': 'Ana', 'last_name': 'Quispe', 'm_last_name': 'Mamani',
            'company_id': self.company.id,
            'date_version': admission,
            'contract_date_start': admission,
            'wage': 3000.0,
            'structure_type_id': self.structure.type_id.id,
            'resource_calendar_id': self.calendars[weekly_days].id,
        })
        return employee

    def _closed_slip(self, employee, date_from, date_to, days, state='paid'):
        """Boleta cerrada con las líneas de días ``days`` ({código: días})."""
        slip = self.env['hr.payslip'].with_context(
            salary_simulation=True).create({
                'name': 'Boleta %s' % date_from,
                'employee_id': employee.id,
                'struct_id': self.structure.id,
                'date_from': date_from,
                'date_to': date_to,
                'company_id': self.company.id,
                'worked_days_line_ids': [(0, 0, {
                    'work_entry_type_id': self.wet[code].id,
                    'version_id': employee.version_id.id,
                    'number_of_days': number,
                    'number_of_hours': number * 8,
                }) for code, number in days.items()],
            })
        slip.state = state
        return slip

    def _year_record(self, employee, date_from=date(2025, 1, 1),
                     date_to=date(2025, 12, 31)):
        return self.Record._l10n_pe_get_record(employee, date_from, date_to)

    def _rest_days(self, employee, date_from=date(2025, 1, 1)):
        self.Rest.get_vacation_employee(employee, False)
        rest = self.Rest.search([
            ('employee_id', '=', employee.id),
            ('date_from', '=', date_from),
            ('internal_motive', '=', 'normal'),
        ])
        self.assertEqual(len(rest), 1)
        return rest

    def _year(self, employee, days):
        self._closed_slip(
            employee, date(2025, 1, 1), date(2025, 12, 31), days)
        return self._year_record(employee)

    # ------------------------------------------------------------------
    # Jornada de seis días: 260 días efectivos
    # ------------------------------------------------------------------
    def test_six_days_260_meets(self):
        employee = self._employee(6)
        record = self._year(employee, {'DLAB': 250, 'FER': 4, 'DVAC': 6,
                                       'DOM': 52, 'FAL': 53})
        self.assertEqual(record.workweek, 'six')
        self.assertEqual(record.threshold, 260)
        self.assertAlmostEqual(record.effective_days, 260.0)
        self.assertEqual(record.state, 'meets')
        rest = self._rest_days(employee)
        self.assertAlmostEqual(rest.days, 30.0)

    def test_six_days_259_fails_and_blocks_the_year(self):
        employee = self._employee(6)
        record = self._year(employee, {'DLAB': 253, 'DVAC': 6, 'LSGH': 20,
                                       'DOM': 52, 'FAL': 34})
        self.assertAlmostEqual(record.effective_days, 259.0)
        self.assertEqual(record.state, 'fails')
        rest = self._rest_days(employee)
        self.assertEqual(rest.days, 0.0,
                         'el año sin récord no genera los 30 días')
        self.assertEqual(rest.amount, 0.0)
        self.assertIn('no cumple el récord', rest.motive)

    # ------------------------------------------------------------------
    # Jornada de cinco días: 210 días efectivos
    # ------------------------------------------------------------------
    def test_five_days_210_meets_209_fails(self):
        employee = self._employee(5)
        record = self._year(employee, {'DLAB': 200, 'LCGH': 5, 'DPAT': 5,
                                       'DOM': 104, 'FAL': 51})
        self.assertEqual(record.workweek, 'five')
        self.assertEqual(record.threshold, 210)
        self.assertEqual(record.state, 'meets')

        other = self._employee(5)
        record = self._year(other, {'DLAB': 209, 'DOM': 104, 'FAL': 52})
        self.assertEqual(record.state, 'fails')
        self.assertEqual(self._rest_days(other).days, 0.0)

    # ------------------------------------------------------------------
    # Jornada de menos de cinco días: máximo 10 faltas injustificadas
    # ------------------------------------------------------------------
    def test_four_days_10_absences_meets_11_fails(self):
        employee = self._employee(4)
        record = self._year(employee, {'DLAB': 198, 'DOM': 157, 'FAL': 10})
        self.assertEqual(record.workweek, 'less')
        self.assertEqual(record.threshold, 10)
        self.assertEqual(record.state, 'meets',
                         'con jornada de 4 días no se exigen 210 días')

        other = self._employee(4)
        record = self._year(other, {'DLAB': 197, 'DOM': 157, 'FAL': 11})
        self.assertEqual(record.state, 'fails')
        self.assertEqual(self._rest_days(other).days, 0.0)

    # ------------------------------------------------------------------
    # Descanso médico: efectivo hasta 60 días al año
    # ------------------------------------------------------------------
    def test_medical_rest_over_60_days_does_not_count(self):
        employee = self._employee(6)
        record = self._year(employee, {'DLAB': 189, 'DMED': 50, 'SENF': 20,
                                       'DOM': 52, 'FAL': 54})
        self.assertAlmostEqual(record.sick_days, 70.0)
        self.assertAlmostEqual(record.sick_days_counted, 60.0)
        self.assertAlmostEqual(record.effective_days, 249.0)

        other = self._employee(6)
        record = self._year(other, {'DLAB': 199, 'DMED': 70,
                                    'DOM': 52, 'FAL': 44})
        self.assertAlmostEqual(record.effective_days, 259.0)
        self.assertEqual(record.state, 'fails',
                         'los 10 días de descanso médico por encima de 60 '
                         'no cuentan')
        third = self._employee(6)
        record = self._year(third, {'DLAB': 200, 'DMED': 60,
                                    'DOM': 52, 'FAL': 53})
        self.assertEqual(record.state, 'meets')

    # ------------------------------------------------------------------
    # El año de récord va de aniversario a aniversario
    # ------------------------------------------------------------------
    def test_record_year_counts_from_anniversary(self):
        """Ingreso 01-07-2024: 6 faltas en mayo-2025 y 6 en agosto-2025
        son 12 en el año calendario 2025, pero 6 en cada año de récord."""
        employee = self._employee(4, admission=date(2024, 7, 1))
        months = [(2024, month) for month in range(7, 13)] \
            + [(2025, month) for month in range(1, 13)] \
            + [(2026, month) for month in range(1, 7)]
        for year, month in months:
            last = (date(year + month // 12, month % 12 + 1, 1)
                    - date.resolution)
            lacks = 6 if (year, month) in ((2025, 5), (2025, 8)) else 0
            self._closed_slip(employee, date(year, month, 1), last, {
                'DLAB': 16 - lacks, 'FAL': lacks,
                'DOM': last.day - 16})
        records = self.Record._l10n_pe_evaluate_employees(
            employee, on_date=date(2026, 10, 1))
        self.assertEqual(
            [(r.date_from, r.date_to) for r in records.sorted('date_from')],
            [(date(2024, 7, 1), date(2025, 6, 30)),
             (date(2025, 7, 1), date(2026, 6, 30))])
        for record in records:
            self.assertAlmostEqual(record.absence_days, 6.0)
            self.assertEqual(record.covered_days, record.period_days)
            self.assertEqual(record.state, 'meets')

    def test_slip_across_anniversary_is_prorated(self):
        """Una boleta mensual que cruza el aniversario aporta solo los días
        que caen dentro del año de récord; una boleta duplicada del mismo
        periodo (otro lote) no se suma dos veces."""
        employee = self._employee(6, admission=date(2025, 1, 16))
        self._closed_slip(employee, date(2025, 1, 16), date(2025, 12, 31),
                          {'DLAB': 240, 'DOM': 50})
        # Enero de 2026 (31 días): 15 de ellos son del año 2025-2026.
        self._closed_slip(employee, date(2026, 1, 1), date(2026, 1, 31),
                          {'DLAB': 31})
        self._closed_slip(employee, date(2026, 1, 1), date(2026, 1, 31),
                          {'DLAB': 10}, state='validated')
        record = self._year_record(
            employee, date(2025, 1, 16), date(2026, 1, 15))
        self.assertEqual(record.slip_count, 2)
        self.assertEqual(record.covered_days, record.period_days)
        self.assertAlmostEqual(record.effective_days, 255.0)
        self.assertEqual(record.state, 'fails')

    # ------------------------------------------------------------------
    # Sin boletas: «sin datos», no bloquea
    # ------------------------------------------------------------------
    def test_without_slips_no_data_does_not_block(self):
        employee = self._employee(6)
        record = self._year_record(employee)
        self.assertEqual(record.state, 'no_data')
        self.assertEqual(record.slip_count, 0)
        rest = self._rest_days(employee)
        self.assertAlmostEqual(rest.days, 30.0)
        self.assertIn('sin datos', rest.motive)

    def test_partial_slips_no_data_unless_threshold_unreachable(self):
        employee = self._employee(6)
        self._closed_slip(employee, date(2025, 1, 1), date(2025, 6, 30),
                          {'DLAB': 150, 'DOM': 31})
        record = self._year_record(employee)
        self.assertEqual(record.state, 'no_data',
                         'con medio año sin boletas aún podría cumplir')
        # Un segundo semestre lleno de faltas: ya no llega a 260.
        self._closed_slip(employee, date(2025, 7, 1), date(2025, 12, 31),
                          {'DLAB': 100, 'DOM': 26, 'FAL': 58})
        record.action_evaluate()
        self.assertEqual(record.state, 'fails')

    def test_draft_slips_do_not_count(self):
        employee = self._employee(6)
        self._closed_slip(employee, date(2025, 1, 1), date(2025, 12, 31),
                          {'DLAB': 300}, state='draft')
        self.assertEqual(self._year_record(employee).state, 'no_data')

    def test_less_than_four_hours_not_applicable(self):
        employee = self._employee(6)
        employee.version_id.l10n_pe_less_than_four = True
        record = self._year(employee, {'DLAB': 300, 'DOM': 65})
        self.assertEqual(record.state, 'not_applicable')
        self.Rest.get_vacation_employee(employee, False)
        self.assertFalse(self.Rest.search(
            [('employee_id', '=', employee.id)]),
            'la jornada menor a 4 horas no tiene vacaciones')

    # ------------------------------------------------------------------
    # Ajuste manual con trazabilidad
    # ------------------------------------------------------------------
    def test_manual_adjustment(self):
        employee = self._employee(6)
        record = self._year(employee, {'DLAB': 200, 'DOM': 52, 'FAL': 113})
        self.assertEqual(record.state, 'fails')
        with self.assertRaises(ValidationError):
            record.write({'manual_state': 'meets'})
        self.env.cr.precommit.run()
        messages = len(record.message_ids)
        record.write({'manual_state': 'meets',
                      'manual_note': 'Faltas compensadas (acuerdo).'})
        self.env.cr.precommit.run()
        self.assertEqual(record.state, 'meets')
        self.assertEqual(record.computed_state, 'fails')
        self.assertEqual(record.manual_user_id, self.env.user)
        self.assertTrue(record.manual_date)
        record.invalidate_recordset(['message_ids'])
        self.assertGreater(len(record.message_ids), messages,
                           'el ajuste queda en el historial')
        # Reevaluar no pisa el ajuste, y el saldo se genera.
        record.action_evaluate()
        self.assertEqual(record.state, 'meets')
        self.assertAlmostEqual(self._rest_days(employee).days, 30.0)
        record.action_clear_manual()
        self.assertEqual(record.state, 'fails')
        self.assertFalse(record.manual_user_id)

    # ------------------------------------------------------------------
    # Evaluación desde la ficha y cron
    # ------------------------------------------------------------------
    def test_employee_button_and_cron(self):
        # Ingreso hace dos años y un mes: dos años cumplidos, el tercero
        # en curso.
        admission = fields.Date.context_today(self.Record) \
            - relativedelta(years=2, months=1)
        employee = self._employee(6, admission=admission)
        action = employee.action_l10n_pe_vacation_records()
        self.assertEqual(action['res_model'], 'hr.vacation.record')
        records = self.Record.search([('employee_id', '=', employee.id)])
        self.assertEqual(len(records), 2)
        self.assertEqual(employee.l10n_pe_vacation_record_count, 2)
        records.unlink()
        self.Record._cron_evaluate_vacation_records()
        records = self.Record.search([('employee_id', '=', employee.id)])
        self.assertEqual(records.date_from,
                         admission + relativedelta(years=1),
                         'el cron evalúa el último año cumplido')
