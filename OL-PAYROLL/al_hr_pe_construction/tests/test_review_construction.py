# -*- coding: utf-8 -*-
"""Revisión de construcción civil en Odoo 20 (31/10/2026).

Cada test reproduce un hallazgo de la revisión (#11, #16) y falla con el
código anterior a su corrección.
"""
from datetime import date, datetime

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestReviewConstruction(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create(
            {'name': 'Revisión Obras S.A.C.', 'vat': '20512528458'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.structure = cls.env.ref(
            'al_hr_pe_construction.construction_structure')
        cls.wd_dlab = cls.env.ref('al_hr_pe.wd_DLAB')
        cls.operario = cls.env.ref('al_hr_pe_construction.category_operario')
        Table = cls.env['l10n_pe.hr.construction.wage.table']
        # Tablas propias de la compañía (mandan sobre la global).
        for year, wage in ((2025, 80.0), (2026, 90.0)):
            Table.create({
                'name': 'Convenio %s (revisión)' % year,
                'company_id': cls.company.id,
                'date_from': date(year, 1, 1), 'date_to': date(year, 12, 31),
                'line_ids': [Command.create({
                    'category_id': cls.operario.id,
                    'daily_wage': wage, 'mobility_amount': 8.0})],
            })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Operario revisión',
            'company_id': cls.company.id,
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
        })
        cls.employee.version_id.write({
            'l10n_pe_labor_regime': 'construccion',
            'l10n_pe_construction_category_id': cls.operario.id,
        })

    def _payslip(self, date_from, date_to, days):
        payslip = self.env['hr.payslip'].create({
            'name': 'Semana %s' % date_from,
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date_from, 'date_to': date_to,
        })
        payslip.worked_days_line_ids.unlink()
        payslip.worked_days_line_ids = [Command.create({
            'name': self.wd_dlab.name,
            'version_id': payslip.version_id.id,
            'work_entry_type_id': self.wd_dlab.id,
            'number_of_days': days, 'number_of_hours': days * 8,
            'amount': 0.0,
        })]
        payslip.compute_sheet()
        return payslip

    @staticmethod
    def _line(payslip, code):
        return round(sum(payslip.line_ids.filtered(
            lambda l: l.code == code).mapped('total')), 2)

    # ------------------------------------------------------------------
    # #11 Semana que cruza el inicio del convenio
    # ------------------------------------------------------------------
    def test_11_week_across_new_agreement_splits_the_wage(self):
        """Del 29/12/2025 al 04/01/2026 (lunes a viernes: 3 días con la
        tabla 2025 y 2 con la 2026). Antes, los 5 días con el jornal
        nuevo (450.00)."""
        payslip = self._payslip(date(2025, 12, 29), date(2026, 1, 4), 5)
        self.assertEqual(payslip.l10n_pe_daily_wage, 90.0,
                         'el snapshot sigue siendo la tabla al cierre')
        self.assertEqual(self._line(payslip, 'JOR'), 80.0 * 3 + 90.0 * 2)
        self.assertEqual(
            payslip._l10n_pe_construction_amount('movilidad'), 8.0 * 5)
        self.assertAlmostEqual(
            payslip._l10n_pe_construction_effective_wage(),
            (80.0 * 3 + 90.0 * 2) / 5, places=2)

    def test_11_week_inside_one_agreement_is_unchanged(self):
        payslip = self._payslip(date(2026, 1, 5), date(2026, 1, 11), 5)
        self.assertEqual(self._line(payslip, 'JOR'), 450.0)
        self.assertEqual(payslip._l10n_pe_construction_effective_wage(), 90.0)

    # ------------------------------------------------------------------
    # #16 Obra de otra compañía en la marcación
    # ------------------------------------------------------------------
    def test_16_attendance_site_must_be_of_the_employee_company(self):
        other = self.env['res.company'].create({'name': 'Otra Obras S.A.C.'})
        foreign = self.env['l10n_pe.hr.construction.site'].sudo().create({
            'name': 'Obra ajena', 'code': 'REV-X', 'company_id': other.id})
        own = self.env['l10n_pe.hr.construction.site'].create({
            'name': 'Obra propia', 'code': 'REV-P',
            'company_id': self.company.id})
        with self.assertRaises(ValidationError):
            self.env['hr.attendance'].create({
                'employee_id': self.employee.id,
                'check_in': datetime(2026, 3, 2, 13, 0),
                'check_out': datetime(2026, 3, 2, 21, 0),
                'l10n_pe_construction_site_id': foreign.id,
            })
        attendance = self.env['hr.attendance'].create({
            'employee_id': self.employee.id,
            'check_in': datetime(2026, 3, 3, 13, 0),
            'check_out': datetime(2026, 3, 3, 21, 0),
            'l10n_pe_construction_site_id': own.id,
        })
        self.assertEqual(attendance.l10n_pe_construction_site_id, own)
