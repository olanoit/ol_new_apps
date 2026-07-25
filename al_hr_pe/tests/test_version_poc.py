# -*- coding: utf-8 -*-
"""PoC Fase 0: valida las dos hipótesis de la migración (plan §8 fase 0):

1. Los campos PE en hr.version se versionan correctamente (histórico por
   fecha, como hacía hr.contract en v18).
2. Una nómina calcula sobre una estructura con regla que LEE los campos
   PE de la versión (el patrón de las 65 reglas peruanas de la Fase 2).
"""
from datetime import date

from odoo.addons.hr_payroll.tests.common import TestPayslipBase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestVersionPoc(TestPayslipBase):

    def test_version_fields_and_history(self):
        """Los campos PE viven en la versión y el versionado los conserva."""
        emp = self.richard_emp
        version = emp.version_id
        # Defaults del PoC
        self.assertEqual(version.l10n_pe_labor_regime, 'general')
        self.assertEqual(version.l10n_pe_commission_type, 'flow')
        version.write({
            'l10n_pe_cuspp': '577814ABCDE9',
            'l10n_pe_commission_type': 'mixed',
        })
        # Nueva versión con régimen distinto: la anterior conserva el suyo
        new_version = emp.create_version({'date_version': date(2024, 1, 1)})
        new_version.l10n_pe_labor_regime = 'small'
        self.assertEqual(version.l10n_pe_labor_regime, 'general')
        self.assertEqual(new_version.l10n_pe_labor_regime, 'small')
        # El CUSPP acompaña a la nueva versión (copiado del snapshot)
        self.assertEqual(new_version.l10n_pe_cuspp, '577814ABCDE9')

    def test_payslip_computes_with_pe_rule(self):
        """Una regla salarial que lee los campos PE de la versión calcula
        en la boleta (patrón de las reglas peruanas de Fase 2)."""
        structure = self.developer_pay_structure
        self.env['hr.salary.rule'].create({
            'name': 'Divisor por régimen (PoC)',
            'code': 'PE_POC',
            'category_id': self.env.ref('hr_payroll.ALW').id,
            'struct_id': structure.id,
            'sequence': 6,
            'amount_select': 'code',
            'amount_python_compute': (
                "result = version.wage / "
                "(24 if version.l10n_pe_labor_regime == 'small' else 12)"
            ),
        })
        emp = self.richard_emp
        emp.version_id.l10n_pe_labor_regime = 'small'
        payslip = self.env['hr.payslip'].create({
            'name': 'PoC PE',
            'employee_id': emp.id,
            'struct_id': structure.id,
            'date_from': date(2023, 1, 1),
            'date_to': date(2023, 1, 31),
        })
        payslip.compute_sheet()
        line = payslip.line_ids.filtered(lambda l: l.code == 'PE_POC')
        self.assertTrue(line, 'La regla PE no generó línea')
        self.assertAlmostEqual(line.total, emp.version_id.wage / 24, places=2)
