# -*- coding: utf-8 -*-
"""La obra fija el centro de costo del día y, en la ficha, el de los días
sin obra."""
from datetime import date, datetime

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestConstructionCost(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        plan = cls.env['account.analytic.plan'].create({'name': 'Obras (construcción)'})
        Analytic = cls.env['account.analytic.account']
        cls.analytic_a = Analytic.create({'name': 'Obra Miraflores', 'plan_id': plan.id})
        cls.analytic_b = Analytic.create({'name': 'Obra Surco', 'plan_id': plan.id})
        Site = cls.env['l10n_pe.hr.construction.site']
        cls.site_a = Site.create({'name': 'Miraflores', 'code': 'TST-A',
                                  'analytic_account_id': cls.analytic_a.id})
        cls.site_b = Site.create({'name': 'Surco', 'code': 'TST-B',
                                  'analytic_account_id': cls.analytic_b.id})
        cls.employee = cls.env['hr.employee'].create({'name': 'Operario Obra'})

    def test_attendance_takes_the_site_cost_center(self):
        attendance = self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2026, 3, 2, 13, 0),
            'check_out': datetime(2026, 3, 2, 21, 0),
            'l10n_pe_construction_site_id': self.site_a.id,
        })
        self.assertEqual(attendance.l10n_pe_analytic_account_id, self.analytic_a)
        attendance.l10n_pe_construction_site_id = self.site_b
        self.assertEqual(attendance.l10n_pe_analytic_account_id, self.analytic_b)

    def test_manual_cost_center_without_site_is_kept(self):
        attendance = self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2026, 3, 3, 13, 0),
            'check_out': datetime(2026, 3, 3, 21, 0),
            'l10n_pe_analytic_account_id': self.analytic_b.id,
        })
        self.assertEqual(attendance.l10n_pe_analytic_account_id, self.analytic_b)

    def test_day_of_tareaje_takes_the_site_cost_center(self):
        tareaje = self.env['hr.tareaje.manager'].create({
            'name': 'Tareaje obra', 'date_start': date(2026, 3, 1), 'date_end': date(2026, 3, 31)})
        line = self.env['hr.tareaje.manager.line'].create({
            'tareaje_id': tareaje.id, 'employee_id': self.employee.id})
        day = self.env['hr.tareaje.manager.line.attendance'].create({
            'tareaje_line_id': line.id, 'employee_id': self.employee.id,
            'fecha': date(2026, 3, 2), 'dlab': 1.0,
            'l10n_pe_construction_site_id': self.site_a.id,
        })
        self.assertEqual(day.l10n_pe_analytic_account_id, self.analytic_a)

    def test_site_is_copied_from_the_attendance(self):
        self.assertIn('l10n_pe_construction_site_id',
                      self.env['hr.attendance']._l10n_pe_day_cost_fields())

    def test_days_without_site_go_to_the_employee_site(self):
        self.employee.version_id.sudo().l10n_pe_construction_site_id = self.site_b
        slip = self.env['hr.payslip'].new({
            'employee_id': self.employee.id,
            'date_from': date(2026, 3, 1), 'date_to': date(2026, 3, 31)})
        self.assertEqual(slip._l10n_pe_default_cost_distribution(),
                         {str(self.analytic_b.id): 100.0})
