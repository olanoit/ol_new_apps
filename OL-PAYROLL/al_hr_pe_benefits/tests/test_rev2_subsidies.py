# -*- coding: utf-8 -*-
"""Revisión numérica de subsidios (ronda 2, 01/11/2026).

Cada test reproduce un hallazgo de la revisión y falla con el código
anterior a su corrección:

* D2: los 20 días a cargo del empleador se cuentan por año calendario, en
  días naturales, con las suspensiones «20»/«21» previas al tramo
  (también las del mismo mes).
* D3: la base del subsidio es la remuneración afecta a EsSalud del mes
  (incluye descanso médico, licencia con goce y paternidad).
* D7: los tipos de ausencia de subsidio y descanso médico traen su código
  T21, y una enfermedad larga se parte en «20» y «21».
"""
from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_fase3_benefits import BenefitsCaseBase


@tagged('post_install', '-at_install')
class TestRev2Subsidies(BenefitsCaseBase):

    def _suspension(self, code, date_from, date_to, employee=None):
        employee = employee or self.employee
        period = self.env['hr.period'].search([
            ('company_id', '=', self.company.id),
            ('date_start', '<=', date_from), ('date_end', '>=', date_from),
        ], limit=1)
        return self.env['hr.work.suspension'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            'periodo_id': period.id,
            'suspension_type_id': self.env['hr.suspension.type'].search(
                [('code', '=', code)], limit=1).id,
            'date_from': date_from, 'date_to': date_to,
            'days': (date_to - date_from).days + 1,
            'company_id': self.company.id,
        })

    def _subsidy(self, suspension, subsidy_type='illness'):
        lot = self.env['hr.subsidies.lot'].search([
            ('company_id', '=', self.company.id),
            ('periodo_id', '=', suspension.periodo_id.id)], limit=1) \
            or self.env['hr.subsidies.lot'].create({
                'company_id': self.company.id,
                'periodo_id': suspension.periodo_id.id})
        subsidy = self.env['hr.subsidies'].create({
            'subsidies_lot_id': lot.id, 'type': subsidy_type,
            'suspension_id': suspension.id,
            'employee_id': suspension.employee_id.id,
            'date_start': suspension.date_from,
            'date_end': suspension.date_to,
        })
        # Base de 3 000 al mes: el diario es 100.
        self.env['hr.subsidies.line'].create({
            'subsidies_id': subsidy.id,
            'periodo_id': suspension.periodo_id.id, 'wage': 3000.0})
        return subsidy

    def _subsidized_days(self, suspension):
        subsidy = self._subsidy(suspension)
        subsidy.action_compute()
        return subsidy.subsidies_total_ids.days

    def _new_employee(self, name):
        employee = self.env['hr.employee'].create({
            'names': name, 'last_name': 'Rev2', 'm_last_name': 'Sub',
            'company_id': self.company.id,
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'wage': 3000.0,
            'structure_type_id': self.structure.type_id.id,
        })
        employee.version_id.membership_id = self.afp
        return employee

    # ------------------------------------------------------------------
    # D2: 20 días del empleador por año calendario, en días naturales
    # ------------------------------------------------------------------
    def test_d2_caso_b_descanso_medico_del_mismo_mes(self):
        """Descanso médico 05-24/03 (20 días) y subsidio 25/03-03/04: el
        tramo de marzo subsidia 7 días y el de abril 3 (10 en total).
        Antes daba «aún no supera los 20 días» y el subsidio salía en 0."""
        self._suspension('20', date(2026, 3, 5), date(2026, 3, 24))
        march = self._suspension('21', date(2026, 3, 25), date(2026, 3, 31))
        april = self._suspension('21', date(2026, 4, 1), date(2026, 4, 3))
        self.assertEqual(self._subsidized_days(march), 7)
        self.assertEqual(self._subsidized_days(april), 3)

    def test_d2_caso_f_descanso_medico_aparte(self):
        """Descanso médico 02-11/03 (10 días) y luego enfermedad del 20/03
        al 10/04: quedan 10 días del empleador, así que marzo subsidia 2 y
        abril 10 (12 en total)."""
        self._suspension('20', date(2026, 3, 2), date(2026, 3, 11))
        march = self._suspension('21', date(2026, 3, 20), date(2026, 3, 31))
        april = self._suspension('21', date(2026, 4, 1), date(2026, 4, 10))
        self.assertEqual(self._subsidized_days(march), 2)
        self.assertEqual(self._subsidized_days(april), 10)

    def test_d2_caso_c_dias_naturales_de_enero(self):
        """Descanso médico de 10 días naturales en enero (12-21, con un fin
        de semana) y enfermedad de 15 días en marzo: se subsidian 5. Antes
        enero contaba 8 días laborables y se subsidiaban 3."""
        self._suspension('20', date(2026, 1, 12), date(2026, 1, 21))
        march = self._suspension('21', date(2026, 3, 2), date(2026, 3, 16))
        subsidy = self._subsidy(march)
        subsidy.action_compute()
        total = subsidy.subsidies_total_ids
        self.assertEqual(total.days, 5)
        self.assertEqual(total.days_total, 25, '10 previos + 15 del tramo')
        self.assertAlmostEqual(total.total_sub, 500.0, places=2)

    def test_d2_el_anio_anterior_no_cuenta(self):
        """Un descanso médico de diciembre no consume los 20 días del año
        siguiente: una enfermedad de 15 días en marzo la paga entera el
        empleador."""
        self._suspension('20', date(2025, 12, 1), date(2025, 12, 20))
        march = self._suspension('21', date(2026, 3, 2), date(2026, 3, 16))
        with self.assertRaises(UserError):
            self._subsidized_days(march)

    # ------------------------------------------------------------------
    # D3: base = remuneración afecta a EsSalud del mes
    # ------------------------------------------------------------------
    def test_d3_base_incluye_el_descanso_medico_pagado(self):
        """Enero con 21 días laborados y 10 de descanso médico: el básico
        es 2 000 y el descanso médico 1 000. La base del mes es la afecta
        a EsSalud, 3 000; antes solo entraba el básico (2 200 en el caso C
        de la revisión)."""
        employee = self._new_employee('Base')
        slip = self.env['hr.payslip'].create({
            'name': 'Boleta enero', 'employee_id': employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 1, 1), 'date_to': date(2026, 1, 31),
            'payslip_run_id': self.runs[(2026, 1)].id,
        })
        slip.worked_days_line_ids.unlink()
        slip.worked_days_line_ids = [Command.create({
            'name': code, 'version_id': slip.version_id.id,
            'work_entry_type_id': self.env.ref('al_hr_pe.wd_%s' % code).id,
            'number_of_days': days, 'number_of_hours': days * 8,
            'amount': 0.0,
        }) for code, days in (('DLAB', 21), ('DMED', 10))]
        slip.compute_sheet()
        slip.action_payslip_done()
        essalud = sum(slip.line_ids.filtered(
            lambda line: line.code == 'AESSALUD').mapped('total'))
        self.assertAlmostEqual(essalud, 3000.0, places=2)
        suspension = self._suspension(
            '22', date(2026, 2, 10), date(2026, 2, 28), employee=employee)
        subsidy = self.env['hr.subsidies'].create({
            'type': 'maternity', 'suspension_id': suspension.id,
            'employee_id': employee.id,
            'date_start': suspension.date_from,
            'date_end': suspension.date_to,
            'subsidies_lot_id': self.env['hr.subsidies.lot'].create({
                'company_id': self.company.id,
                'periodo_id': suspension.periodo_id.id}).id,
        })
        history = subsidy._get_salary_history(self.param)
        self.assertEqual([periodo.code for periodo in history], ['202601'])
        amounts = list(history.values())[0]
        self.assertAlmostEqual(amounts['wage'], 2000.0, places=2)
        self.assertAlmostEqual(amounts['other_affected'], 1000.0, places=2)
        line = self.env['hr.subsidies.line'].create(dict(
            amounts, subsidies_id=subsidy.id,
            periodo_id=list(history)[0].id))
        self.assertAlmostEqual(line.total, essalud, places=2)

    # ------------------------------------------------------------------
    # D7: códigos T21 de fábrica y enfermedad partida en «20» y «21»
    # ------------------------------------------------------------------
    def test_d7_tipos_de_ausencia_con_codigo_t21(self):
        for code, t21 in (('DMED', '20'), ('SENF', '21'), ('SMAR', '22')):
            leave_type = self.env.ref('al_hr_pe.wd_%s' % code)
            self.assertEqual(leave_type.l10n_pe_suspension_type_id.code, t21,
                             code)

    def _illness_leave(self, employee, date_from, date_to):
        leave_type = self.env.ref('al_hr_pe.wd_SENF')
        leave_type.requires_allocation = False
        leave_type.l10n_pe_suspension_type_id = \
            self.env.ref('al_hr_pe.suspension_21')
        leave = self.env['hr.leave'].with_context(
            leave_skip_state_check=True).create({
                'name': 'Enfermedad', 'employee_id': employee.id,
                'work_entry_type_id': leave_type.id,
                'request_date_from': date_from, 'request_date_to': date_to,
            })
        if leave.state != 'validate':
            leave._action_validate(check_state=False)
        return leave

    @staticmethod
    def _summary(leave):
        return [(suspension.suspension_type_id.code, suspension.date_from,
                 suspension.date_to)
                for suspension in leave.l10n_pe_suspension_ids.sorted(
                    'date_from')]

    def test_d7_enfermedad_larga_se_parte_en_20_y_21(self):
        """Una sola ausencia de enfermedad del 05/03 al 03/04: los 20
        primeros días van como «20» (empleador) y el resto como «21»
        (subsidio), uno por mes. Antes los 30 días iban como «21»."""
        employee = self._new_employee('Partida')
        leave = self._illness_leave(
            employee, date(2026, 3, 5), date(2026, 4, 3))
        self.assertEqual(self._summary(leave), [
            ('20', date(2026, 3, 5), date(2026, 3, 24)),
            ('21', date(2026, 3, 25), date(2026, 3, 31)),
            ('21', date(2026, 4, 1), date(2026, 4, 3)),
        ])
        # El lote de marzo solo subsidia el tramo «21»: 7 días.
        march = leave.l10n_pe_suspension_ids.filtered(
            lambda s: s.suspension_type_id.code == '21'
            and s.date_from.month == 3)
        self.assertEqual(self._subsidized_days(march), 7)

    def test_d7_enfermedad_descuenta_el_descanso_medico_previo(self):
        """Con 10 días de descanso médico en enero, una enfermedad de 15
        días en marzo tiene 10 del empleador («20») y 5 subsidiados
        («21»)."""
        employee = self._new_employee('Previa')
        self._suspension('20', date(2026, 1, 12), date(2026, 1, 21),
                         employee=employee)
        leave = self._illness_leave(
            employee, date(2026, 3, 2), date(2026, 3, 16))
        self.assertEqual(self._summary(leave), [
            ('20', date(2026, 3, 2), date(2026, 3, 11)),
            ('21', date(2026, 3, 12), date(2026, 3, 16)),
        ])
