# -*- coding: utf-8 -*-
"""Revisión Odoo 20 (CTS, gratificación y liquidación de cese).

Mismo caso de referencia que la Fase 3 (sueldo 3 000, régimen general,
boletas Nov-2025 → Jun-2026 validadas en lotes mensuales). Cada test fija
el defecto que corrige.
"""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from . import test_audit_fixes_a as audit_a
from .test_fase3_benefits import BenefitsCaseBase


@tagged('post_install', '-at_install')
class TestReviewBenefits(BenefitsCaseBase):

    # Helpers de la auditoría A (sin heredar su clase: no se repiten sus
    # tests).
    _slip = audit_a.TestAuditFixesA._slip
    _move_days = audit_a.TestAuditFixesA._move_days
    _new_cts = audit_a.TestAuditFixesA._new_cts
    _reopen_slips_after = audit_a.TestAuditFixesA._reopen_slips_after
    _cessation_in_july = audit_a.TestAuditFixesA._cessation_in_july

    def _gratification(self, **vals):
        grati = self.env['hr.gratification'].create(dict({
            'company_id': self.company.id, 'year': 2026, 'type': '07',
            'with_bonus': False, 'payslip_run_id': self.batch_jun.id,
            'deposit_date': date(2026, 7, 15),
        }, **vals))
        grati.action_process()
        line = grati.line_ids.filtered(
            lambda line: line.employee_id == self.employee)
        self.assertEqual(len(line), 1)
        return line

    def _extra_slip(self, run, month, last):
        slip = self.env['hr.payslip'].create({
            'name': 'Boleta adicional 2026-%02d' % month,
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, month, 1),
            'date_to': date(2026, month, last),
            'payslip_run_id': run.id,
        })
        slip.compute_sheet()
        return slip

    # ------------------------------------------------------------------
    # A6: meses por mes calendario, no por lote
    # ------------------------------------------------------------------
    def test_gratificacion_lote_aparte_no_suma_un_mes(self):
        """Un segundo lote en marzo con boleta del trabajador: el semestre
        sigue siendo de 6 meses (antes 7/6 de gratificación)."""
        run = self.env['hr.payslip.run'].create({
            'name': 'Lote aparte 2026-03', 'company_id': self.company.id,
            'date_start': date(2026, 3, 1), 'date_end': date(2026, 3, 31),
        })
        self._extra_slip(run, 3, 31)
        line = self._gratification()
        self.assertEqual(line.months, 6)
        self.assertAlmostEqual(line.total_grat, self.wage, delta=0.05)

    # ------------------------------------------------------------------
    # M1: sin días sueltos, los días no se convierten en meses
    # ------------------------------------------------------------------
    def test_gratificacion_sin_dias_sueltos_no_los_convierte(self):
        """16 días computables en enero y 16 en marzo (licencia sin goce):
        4 meses completos, no 5 (Ley 27735: meses calendario completos)."""
        self.env['hr.work.entry.type'].create({
            'name': 'Licencia sin goce (prueba)', 'code': 'TLSG'})
        self._move_days(2026, 1, 'TLSG', 15)
        self._move_days(2026, 3, 'TLSG', 15)
        line = self._gratification()
        self.assertEqual((line.months, line.days), (4, 0))
        self.assertAlmostEqual(line.total_grat, self.wage * 4 / 6,
                               delta=0.05)

    # ------------------------------------------------------------------
    # C1 / C2: exportación de CTS
    # ------------------------------------------------------------------
    def test_cts_no_exporta_a_boleta_validada(self):
        cts = self._new_cts()
        cts.action_process()
        with self.assertRaises(UserError):
            cts.action_export_to_payslips()
        self._slip(2026, 4).write({'state': 'draft'})
        cts.action_export_to_payslips()
        self.assertEqual(cts.state, 'exported')

    def test_cts_dos_boletas_se_paga_una_vez(self):
        """Dos boletas del trabajador en el lote (una por versión) que ya
        tenían el input de CTS: la CTS va a una sola."""
        april = self._slip(2026, 4)
        april.write({'state': 'draft'})
        second = self._extra_slip(self.batch, 4, 30)
        input_cts = self.param.cts_input_id
        for slip in april | second:
            slip.write({'input_line_ids': [(0, 0, {
                'salary_rule_id': input_cts.id, 'amount': 0.0})]})
        cts = self._new_cts()
        cts.action_process()
        line = cts.line_ids.filtered(
            lambda line: line.employee_id == self.employee)
        self.assertTrue(line.total_cts)
        cts.action_export_to_payslips()
        amounts = (april | second).input_line_ids.filtered(
            lambda inp: inp.salary_rule_id == input_cts).mapped('amount')
        self.assertEqual(sorted(amounts), [0.0, line.total_cts])

    # ------------------------------------------------------------------
    # A5: cese en mayo con dos CTS truncas
    # ------------------------------------------------------------------
    def test_liquidacion_mayo_exporta_las_dos_cts(self):
        liquidation = self._cessation_in_july(month=5)
        cts_tru = self.env.ref('al_hr_pe.salary_rule_CTS_TRU')
        self.param.truncated_cts_input_id = cts_tru
        liquidation.action_process()
        lines = liquidation.cts_line_ids.filtered(
            lambda line: line.employee_id == self.employee)
        self.assertEqual(len(lines), 2, 'nov-abr y mayo')
        liquidation.action_export_to_payslips()
        slip = liquidation.payslip_run_id.slip_ids.filtered(
            lambda slip: slip.employee_id == self.employee)
        exported = slip.input_line_ids.filtered(
            lambda inp: inp.salary_rule_id == cts_tru)
        self.assertAlmostEqual(exported.amount,
                               sum(lines.mapped('total_cts')), places=2)

    # ------------------------------------------------------------------
    # A7: subsidio de varios meses con la base de la contingencia
    # ------------------------------------------------------------------
    def _suspension(self, code, date_from, date_to):
        period = self.env['hr.period'].search([
            ('company_id', '=', self.company.id),
            ('date_start', '<=', date_from), ('date_end', '>=', date_from),
        ], limit=1)
        return self.env['hr.work.suspension'].create({
            'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id,
            'periodo_id': period.id,
            'suspension_type_id': self.env['hr.suspension.type'].search(
                [('code', '=', code)], limit=1).id,
            'date_from': date_from, 'date_to': date_to,
            'days': (date_to - date_from).days + 1,
            'company_id': self.company.id,
        })

    def test_subsidio_por_tramos_usa_el_inicio_de_la_contingencia(self):
        """Maternidad del 10/01 al 31/03 partida en tres suspensiones: el
        tramo de marzo promedia los 12 meses previos a ENERO (nov y dic de
        2025), no los previos a marzo (que incluyen enero y febrero ya
        subsidiados)."""
        self._suspension('22', date(2026, 1, 10), date(2026, 1, 31))
        self._suspension('22', date(2026, 2, 1), date(2026, 2, 28))
        march = self._suspension('22', date(2026, 3, 1), date(2026, 3, 31))
        lot = self.env['hr.subsidies.lot'].create({
            'company_id': self.company.id, 'periodo_id': march.periodo_id.id})
        subsidy = self.env['hr.subsidies'].create({
            'subsidies_lot_id': lot.id, 'type': 'maternity', 'suspension_id': march.id,
            'employee_id': self.employee.id,
            'date_start': march.date_from, 'date_end': march.date_to,
        })
        self.assertEqual(subsidy._l10n_pe_contingency_start(),
                         date(2026, 1, 10))
        history = subsidy._get_salary_history(self.param)
        self.assertEqual(
            sorted(periodo.date_start for periodo in history),
            [date(2025, 11, 1), date(2025, 12, 1)])

    def test_enfermedad_por_tramos_no_repite_los_20_dias(self):
        """Enfermedad del 20/02 al 15/03: el tramo de marzo ya no paga los
        20 días del empleador (9 se consumieron en febrero), así que se
        subsidian 15 - (20 - 9) = 4 días."""
        self._suspension('21', date(2026, 2, 20), date(2026, 2, 28))
        march = self._suspension('21', date(2026, 3, 1), date(2026, 3, 15))
        periodo = self.env['hr.period'].search([
            ('code', '=', '202603'), ('company_id', '=', self.company.id)],
            limit=1)
        lot = self.env['hr.subsidies.lot'].create({
            'company_id': self.company.id, 'periodo_id': periodo.id})
        subsidy = self.env['hr.subsidies'].create({
            'subsidies_lot_id': lot.id,
            'type': 'illness', 'suspension_id': march.id,
            'employee_id': self.employee.id,
            'date_start': march.date_from, 'date_end': march.date_to,
        })
        self.env['hr.subsidies.line'].create({
            'subsidies_id': subsidy.id, 'periodo_id': periodo.id,
            'wage': 3000.0})
        subsidy.action_compute()
        self.assertEqual(subsidy.subsidies_total_ids.days, 4)
