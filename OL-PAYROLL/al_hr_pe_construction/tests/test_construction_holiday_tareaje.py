# -*- coding: utf-8 -*-
"""Feriado laborado unas pocas horas, del tareaje a la boleta de obra.

D.Leg. 713 art. 9: la sobretasa del 100 % paga «la labor efectuada». El
tareaje (al_hr_pe_attendance) lleva a la línea FER de la boleta las horas
trabajadas en el feriado (``hfer``) y deja el día FER en 1; la sobretasa
FER100 de construcción se calcula con esas horas, el jornal del día (JOR)
y la movilidad siguen yendo por el día.
"""
from datetime import date, datetime, timedelta

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.al_hr_pe.tools import custom_round


def _lima(day, hour, minute=0):
    """Hora de Lima (UTC−5) → datetime UTC ingenuo, como se guarda."""
    return datetime(day.year, day.month, day.day, hour, minute) \
        + timedelta(hours=5)


@tagged('post_install', '-at_install')
class TestConstructionHolidayTareaje(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Obra Feriado Tareaje S.A.C.',
            'vat': '20512528458',
            'country_id': cls.env.ref('base.pe').id,
            'tz': 'America/Lima',
        })
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.env.user.company_ids |= cls.company
        cls.env.user.group_ids |= cls.env.ref(
            'hr_payroll.group_hr_payroll_manager')
        cls.env['hr.main.parameter'].get_main_parameter(cls.company)
        cls.structure = cls.env.ref(
            'al_hr_pe_construction.construction_structure')
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Obra L-V', 'company_id': cls.company.id,
            'hours_per_day': 8.0,
            'attendance_ids': [(5, 0, 0)] + [
                (0, 0, {'dayofweek': str(dia),
                        'hour_from': 8.0, 'hour_to': 16.0,
                        'day_period': 'morning'})
                for dia in range(0, 5)],
        })
        dni = cls.env.ref('al_hr_pe.l10n_pe_hr_document_type_dni')
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Operario feriado',
            'company_id': cls.company.id,
            'identification_id': '49000001',
            'l10n_pe_document_type_id': dni.id,
            'tz': 'America/Lima',
        })
        cls.employee.version_id.write({
            'contract_date_start': date(2026, 1, 1),
            'resource_calendar_id': cls.calendar.id,
            'l10n_pe_labor_regime': 'construccion',
            'l10n_pe_construction_category_id': cls.env.ref(
                'al_hr_pe_construction.category_operario').id,
        })
        # Miércoles 4 de marzo de 2026: feriado.
        cls.holiday_day = date(2026, 3, 4)
        holiday = cls.env['pe.public.holiday'].create({
            'name': 'Feriado de prueba', 'date': cls.holiday_day})
        leave = cls.env['resource.calendar.leaves'].create({
            'name': 'Feriado de prueba',
            'calendar_id': cls.calendar.id,
            'company_id': cls.company.id,
            'date_from': _lima(cls.holiday_day, 0),
            'date_to': _lima(cls.holiday_day, 23, 59),
            'pe_public_holiday_id': holiday.id,
        })
        leave.write({'date_from': _lima(cls.holiday_day, 0),
                     'date_to': _lima(cls.holiday_day, 23, 59)})

    def _attendance(self, day, hour_in, hour_out):
        return self.env['hr.attendance'].with_context(
            skip_time_rules=True).create({
                'employee_id': self.employee.id,
                'check_in': _lima(day, hour_in),
                'check_out': _lima(day, hour_out),
            })

    @staticmethod
    def _line(payslip, code):
        line = payslip.line_ids.filtered(lambda l: l.code == code)
        return round(sum(line.mapped('total')), 2)

    def test_two_hours_on_the_holiday_surcharge_two_hours(self):
        for offset in (2, 3, 5, 6):
            self._attendance(date(2026, 3, offset), 8, 16)
        self._attendance(self.holiday_day, 8, 10)
        tareaje = self.env['hr.tareaje.manager'].create({
            'name': 'Semana feriado', 'company_id': self.company.id,
            'date_start': date(2026, 3, 2), 'date_end': date(2026, 3, 8)})
        tareaje.action_generate()
        tareaje.action_close()
        payslip = self.env['hr.payslip'].create({
            'name': 'Semana feriado',
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 3, 2), 'date_to': date(2026, 3, 8),
        })
        payslip.compute_sheet()
        fer = payslip.worked_days_line_ids.filtered(
            lambda wd: wd.work_entry_type_id.code == 'FER')
        self.assertAlmostEqual(sum(fer.mapped('number_of_days')), 1.0,
                               places=2)
        self.assertAlmostEqual(sum(fer.mapped('number_of_hours')), 2.0,
                               places=2)
        self.assertEqual(self._line(payslip, 'FER100'),
                         custom_round(2 * 89.30 / 8.0),
                         '2 h × valor hora (89.30 ÷ 8), no el jornal entero')
        self.assertEqual(self._line(payslip, 'MOV'), round(8.60 * 5, 2),
                         'el feriado laborado es día en obra: movilidad')
