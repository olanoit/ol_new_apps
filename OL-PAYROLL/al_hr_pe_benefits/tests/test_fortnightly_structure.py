# -*- coding: utf-8 -*-
"""Adelanto quincenal con estructura propia (sin aportes de medio mes)."""
from datetime import date

from odoo.tests import tagged

from .test_fase3_benefits import BenefitsCaseBase


@tagged('post_install', '-at_install')
class TestFortnightlyStructure(BenefitsCaseBase):

    def _fortnightly(self):
        run = self.env['hr.payslip.run'].search([
            ('company_id', '=', self.company.id),
            ('date_start', '=', date(2026, 3, 1))], limit=1)
        return self.env['hr.fortnightly'].create({
            'name': 'Quincena marzo', 'company_id': self.company.id,
            'date_start': date(2026, 3, 1), 'date_end': date(2026, 3, 15),
            'payslip_run_id': run.id,
        })

    def _line(self, slip, code):
        return sum(slip.line_ids.filtered(lambda l: l.code == code).mapped('total'))

    def test_percentage_advance_without_contributions(self):
        self.param.write({'fortnightly_type': 'percentage', 'tasa': 0.5,
                          'compute_afiliacion': False})
        fortnightly = self._fortnightly()
        fortnightly.action_generate_payslips()
        slip = fortnightly.slip_ids.filtered(
            lambda s: s.employee_id == self.employee)
        self.assertEqual(
            slip.struct_id,
            self.env.ref('al_hr_pe_benefits.fortnightly_structure'))
        self.assertAlmostEqual(self._line(slip, 'NETO_AQ'), self.wage * 0.5)
        self.assertFalse(slip.line_ids.filtered(
            lambda l: l.code in ('ESSALUD', 'QUINTA', 'AAFP')),
            'los aportes y la 5ta van en la boleta mensual')
        self.assertEqual(self.param.net_fortnightly_sr_id,
                         self.env.ref('al_hr_pe_benefits.rule_NETO_AQ'))

    def test_pension_on_account_when_requested(self):
        self.param.write({'fortnightly_type': 'percentage', 'tasa': 0.5,
                          'compute_afiliacion': True})
        fortnightly = self._fortnightly()
        fortnightly.action_generate_payslips()
        slip = fortnightly.slip_ids.filtered(
            lambda s: s.employee_id == self.employee)
        self.assertGreater(self._line(slip, 'TAT_AQ'), 0.0)
        self.assertAlmostEqual(
            self._line(slip, 'NETO_AQ'),
            self.wage * 0.5 - self._line(slip, 'TAT_AQ'))

    def test_export_falls_back_to_neto_aq(self):
        """Con el neto quincenal apuntando a una regla de BASE (como antes),
        la exportación toma NETO_AQ en vez de exportar 0."""
        self.param.write({'fortnightly_type': 'percentage', 'tasa': 0.5,
                          'net_fortnightly_sr_id': self.env.ref(
                              'al_hr_pe.salary_rule_NETO').id})
        fortnightly = self._fortnightly()
        fortnightly.action_generate_payslips()
        lot = fortnightly.payslip_run_id
        if not lot.slip_ids.filtered(lambda s: s.employee_id == self.employee):
            self.env['hr.payslip'].create({
                'name': 'Mensual', 'employee_id': self.employee.id,
                'struct_id': self.structure.id, 'payslip_run_id': lot.id,
                'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 31),
            })
        fortnightly.set_amounts(
            fortnightly.slip_ids, fortnightly.payslip_run_id, self.param)
        monthly = fortnightly.payslip_run_id.slip_ids.filtered(
            lambda s: s.employee_id == self.employee)
        advance = monthly.input_line_ids.filtered(
            lambda i: i.input_type_id == self.param.fortnightly_input_id)
        self.assertAlmostEqual(sum(advance.mapped('amount')), self.wage * 0.5)
