# -*- coding: utf-8 -*-
"""Reparto del costo de la boleta por centro de costo del tareaje."""
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'al_hr_pe_attendance')
class TestTareajeCostDistribution(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        plan = cls.env['account.analytic.plan'].create({'name': 'Obras (test)'})
        Analytic = cls.env['account.analytic.account']
        cls.obra_a = Analytic.create({'name': 'Obra A', 'plan_id': plan.id})
        cls.obra_b = Analytic.create({'name': 'Obra B', 'plan_id': plan.id})
        cls.oficina = Analytic.create({'name': 'Oficina', 'plan_id': plan.id})
        cls.employee = cls.env['hr.employee'].create({'name': 'Obrero Reparto'})
        cls.param = cls.env['hr.main.parameter'].get_main_parameter(cls.env.company)
        cls.tareaje = cls.env['hr.tareaje.manager'].create({
            'name': 'Tareaje reparto',
            'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31),
        })
        cls.line = cls.env['hr.tareaje.manager.line'].create({
            'tareaje_id': cls.tareaje.id,
            'employee_id': cls.employee.id,
        })

    def _day(self, day, analytic=None, dlab=1.0, htd=8.0, **extra):
        return self.env['hr.tareaje.manager.line.attendance'].create(dict({
            'tareaje_line_id': self.line.id,
            'employee_id': self.employee.id,
            'fecha': date(2026, 3, day),
            'state': 'ok',
            'dlab': dlab, 'htd': htd,
            'l10n_pe_analytic_account_id': analytic.id if analytic else False,
        }, **extra))

    def _distribution(self):
        slip = self.env['hr.payslip'].new({
            'employee_id': self.employee.id,
            'date_from': date(2026, 3, 1),
            'date_to': date(2026, 3, 31),
            'company_id': self.env.company.id,
        })
        return slip._l10n_pe_tareaje_distribution()

    def test_three_days_a_two_days_b_is_60_40(self):
        for day in (2, 3, 4):
            self._day(day, self.obra_a)
        for day in (5, 6):
            self._day(day, self.obra_b)
        self.tareaje.action_close()
        self.assertEqual(self._distribution(), {
            str(self.obra_a.id): 60.0, str(self.obra_b.id): 40.0})

    def test_by_hours_counts_overtime(self):
        self.param.tareaje_cost_basis = 'hours'
        self._day(2, self.obra_a, htd=8.0, he25=2.0)   # 10 h
        self._day(3, self.obra_b, htd=8.0)             # 8 h
        self._day(4, self.obra_b, htd=2.0, dlab=0.25)  # 2 h
        self.tareaje.action_close()
        self.assertEqual(self._distribution(), {
            str(self.obra_a.id): 50.0, str(self.obra_b.id): 50.0})
        self.param.tareaje_cost_basis = 'days'

    def test_days_without_cost_center_go_to_the_employee_file(self):
        self.employee.version_id.analytic_distribution = {str(self.oficina.id): 100.0}
        for day in (2, 3):
            self._day(day, self.obra_a)
        for day in (4, 5):
            self._day(day)
        self.tareaje.action_close()
        self.assertEqual(self._distribution(), {
            str(self.obra_a.id): 50.0, str(self.oficina.id): 50.0})

    def test_without_cost_centers_keeps_previous_behaviour(self):
        for day in (2, 3):
            self._day(day)
        self.tareaje.action_close()
        self.assertFalse(self._distribution(), 'sin centros de costo: regla o ficha, como antes')

    def test_draft_tareaje_is_ignored(self):
        self._day(2, self.obra_a)
        self.assertFalse(self._distribution(), 'solo el tareaje aplicado reparte')

    def test_rounding_keeps_the_total(self):
        for day, analytic in ((2, self.obra_a), (3, self.obra_b), (4, self.oficina)):
            self._day(day, analytic)
        self.tareaje.action_close()
        distribution = self._distribution()
        self.assertAlmostEqual(sum(distribution.values()), 100.0, places=2)
