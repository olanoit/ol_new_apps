# -*- coding: utf-8 -*-
"""Regresiones de la revisión de reportes de planilla (octubre 2026).

* La boleta indica la fecha de salida y de retorno de las vacaciones
  gozadas en el periodo (D.S. 001-98-TR art. 19).
* El neto en letras sale en la moneda de la boleta.
* El período de prueba de la LPCL no pisa las versiones de otros países.
"""
from datetime import date

from odoo.tests import TransactionCase, tagged

from .test_audit_fixes import _PayslipCase


@tagged('post_install', '-at_install')
class TestReportsReviewFixes(TransactionCase, _PayslipCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_payslip()
        cls.env['hr.main.parameter'].create({'company_id': cls.company.id})

    def test_voucher_shows_vacation_dates(self):
        dvac = self.env.ref('al_hr_pe.wd_DVAC')
        dvac.requires_allocation = False
        leave = self.env['hr.leave'].with_context(
            leave_skip_state_check=True).create({
                'employee_id': self.employee.id,
                'work_entry_type_id': dvac.id,
                'request_date_from': date(2026, 3, 25),
                'request_date_to': date(2026, 4, 8),
            })
        leave.state = 'validate'
        data = self.slip._get_voucher_report_data()
        self.assertEqual(data['vacaciones'], [{
            'salida': date(2026, 3, 25), 'retorno': date(2026, 4, 9)}])
        leave.state = 'refuse'
        self.assertEqual(self.slip._get_voucher_report_data()['vacaciones'],
                         [])

    def test_net_in_words_uses_the_slip_currency(self):
        self.assertTrue(
            self.slip._get_voucher_report_data()['neto_letras']
            .endswith('SOLES'))
        usd = self.env.ref('base.USD')
        usd.active = True
        company = self.env['res.company'].create({
            'name': 'PE Dólares SAC', 'country_id': self.env.ref('base.pe').id,
            'currency_id': usd.id})
        employee = self.env['hr.employee'].create({
            'name': 'Trabajador USD', 'company_id': company.id,
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1), 'wage': 1000.0})
        slip = self.env['hr.payslip'].create({
            'name': 'Boleta USD', 'employee_id': employee.id,
            'version_id': employee.version_id.id, 'company_id': company.id,
            'date_from': date(2026, 4, 1), 'date_to': date(2026, 4, 30)})
        self.assertNotEqual(slip._voucher_currency_words(), 'SOLES')

    def test_trial_period_only_for_peru(self):
        company = self.env['res.company'].create({
            'name': 'US Payroll Inc', 'country_id': self.env.ref('base.us').id})
        employee = self.env['hr.employee'].create({
            'name': 'US worker', 'company_id': company.id,
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'trial_date_end': date(2025, 1, 31)})
        version = employee.version_id
        version.contract_date_start = date(2025, 2, 1)
        self.assertEqual(version.trial_date_end, date(2025, 1, 31))
        # En Perú sigue el cálculo de la LPCL (3 meses por defecto).
        self.employee.version_id.contract_date_start = date(2025, 2, 1)
        self.assertEqual(self.employee.version_id.trial_date_end,
                         date(2025, 5, 1))
