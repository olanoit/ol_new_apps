# -*- coding: utf-8 -*-
"""Certificado de 5ta: el impuesto sale de la escala del art. 53 LIR y
el saldo por regularizar es impuesto − retención (antes, siempre 0)."""
from datetime import date
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'al_hr_pe_reports')
class TestFifthCertificate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'PE Certificado 5ta SAC',
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.param = cls.env['hr.main.parameter'].create(
            {'company_id': cls.company.id})
        cls.param.action_generate_brackets(2026)
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Trabajador quinta', 'company_id': cls.company.id})
        cls.wizard = cls.env['hr.fifth.certificate.wizard'].create({
            'year': 2026, 'company_id': cls.company.id,
            'date': date(2027, 2, 15),
            'employee_ids': [(6, 0, cls.employee.ids)],
        })

    def _values(self, rem, retencion):
        Line = type(self.env['hr.fifth.category.line'])
        Param = type(self.env['hr.main.parameter'])
        totals = iter((rem, retencion))
        with patch.object(Param, 'check_fifth_values', lambda self: True), \
                patch.object(Line, '_sum_payslip_rule_totals',
                             lambda self, *args: next(totals)), \
                patch.object(Line, '_get_quinta_rule',
                             lambda self, company: self.env['hr.salary.rule']):
            return self.wizard._get_certificate_values(self.employee)

    def test_tax_from_progressive_scale(self):
        # UIT 2026 = 5 500: renta 120 000 − 38 500 = 81 500 de renta
        # imponible → 8 % de 27 500 + 14 % de 54 000 = 9 760.
        vals = self._values(120000.0, 9000.0)
        self.assertAlmostEqual(vals['renta_imponible'], 81500.0)
        self.assertAlmostEqual(vals['impuesto'], 9760.0)
        self.assertAlmostEqual(vals['retencion'], 9000.0)
        self.assertAlmostEqual(vals['saldo'], 760.0)

    def test_below_seven_uit_no_tax(self):
        vals = self._values(30000.0, 0.0)
        self.assertEqual(vals['renta_imponible'], 0.0)
        self.assertEqual(vals['impuesto'], 0.0)
        self.assertEqual(vals['saldo'], 0.0)
