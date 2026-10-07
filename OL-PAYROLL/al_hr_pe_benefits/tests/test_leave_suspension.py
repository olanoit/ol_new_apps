# -*- coding: utf-8 -*-
"""Ausencias aprobadas → suspensiones PLAME (sin doble registro)."""
from datetime import date

from odoo.tests import tagged

from .test_fase3_benefits import BenefitsCaseBase


@tagged('post_install', '-at_install')
class TestLeaveSuspension(BenefitsCaseBase):

    def _leave(self, leave_type):
        return self.env['hr.leave'].with_context(
            leave_skip_state_check=True).create({
                'name': 'Vacaciones',
                'employee_id': self.employee.id,
                'holiday_status_id': leave_type.id,
                'request_date_from': date(2026, 1, 28),
                'request_date_to': date(2026, 2, 3),
            })

    def test_validated_leave_creates_monthly_suspensions(self):
        vacation = self.env.ref('al_hr_pe.suspension_23')
        leave_type = self.env['hr.leave.type'].create({
            'name': 'Vacaciones PE', 'requires_allocation': False,
            'company_id': self.company.id,
            'l10n_pe_suspension_type_id': vacation.id,
        })
        leave = self._leave(leave_type)
        self.assertFalse(leave.l10n_pe_suspension_ids, 'sin aprobar, nada')
        leave._action_validate(check_state=False)
        suspensions = leave.l10n_pe_suspension_ids.sorted('date_from')
        self.assertEqual(suspensions.mapped('days'), [4, 3],
                         '28-31 de enero y 1-3 de febrero')
        self.assertEqual(suspensions.suspension_type_id, vacation)
        self.assertEqual(
            suspensions.mapped('periodo_id.date_start'),
            [date(2026, 1, 1), date(2026, 2, 1)])
        leave.action_refuse()
        self.assertFalse(leave.l10n_pe_suspension_ids,
                         'rechazada, las suspensiones desaparecen')

    def test_leave_type_without_code_creates_nothing(self):
        leave_type = self.env['hr.leave.type'].create({
            'name': 'Permiso sin código', 'requires_allocation': False,
            'company_id': self.company.id,
        })
        leave = self._leave(leave_type)
        leave._action_validate(check_state=False)
        self.assertFalse(leave.l10n_pe_suspension_ids)

    def test_paid_time_off_defaults_to_vacation(self):
        leave_type = self.env.ref('hr_holidays.holiday_status_cl',
                                  raise_if_not_found=False)
        if not leave_type:
            self.skipTest('sin el tipo de ausencia de demostración')
        self.assertEqual(leave_type.l10n_pe_suspension_type_id.code, '23')
