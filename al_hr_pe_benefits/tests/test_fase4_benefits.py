# -*- coding: utf-8 -*-
"""Fase 4: renta de 5ta (tramos/tabla escalonada), préstamos,
provisiones mensuales y utilidades D.L. 892.

Mismo caso de referencia que la Fase 3 (sueldo 3 000 estable, régimen
general, sin variables ni hijos ni faltas); expectativas derivadas de
las fórmulas legales, no números mágicos.
"""
from datetime import date

from odoo.tests import tagged

from .test_fase3_benefits import BenefitsCaseBase


@tagged('post_install', '-at_install')
class TestFase4Benefits(BenefitsCaseBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Uit = cls.env['l10n_pe.hr.uit']
        year = date.today().year
        cls.uit = Uit.search([('year', '=', year)], limit=1)
        if not cls.uit:
            cls.uit = Uit.create({'year': year, 'amount': 5350.0})

    def test_generate_tramos_uit(self):
        """Tramos IR 5ta: [8, 14, 17, 20, 30] % sobre
        [5, 20, 35, 45, ∞] × UIT (∞ = 0)."""
        self.param.generate_tramos()
        tramos = self.param.rate_limit_ids.sorted('range')
        self.assertEqual(len(tramos), 5)
        self.assertEqual(tramos.mapped('rate'), [8, 14, 17, 20, 30])
        amount = self.uit.amount
        self.assertEqual(
            tramos.mapped('limit'),
            [int(5 * amount), int(20 * amount), int(35 * amount),
             int(45 * amount), 0])
        self.assertTrue(all(t.company_id == self.company for t in tramos))

    def test_tax_proy_tabla_escalonada(self):
        """Impuesto proyectado: 8 % hasta 5 UIT y 14 % por el exceso
        (renta neta dentro del 2º tramo)."""
        self.param.generate_tramos()
        uit = self.uit.amount
        net_rent = 8 * uit  # entre 5 y 20 UIT
        tax = self.env['hr.fifth.category.line'].get_tax_proy(
            net_rent, self.param.rate_limit_ids.sorted('range'))
        expected = 5 * uit * 0.08 + (net_rent - 5 * uit) * 0.14
        self.assertAlmostEqual(tax, expected, places=2)
        # Primer tramo puro: tasa plana del 8 %
        self.assertAlmostEqual(
            self.env['hr.fifth.category.line'].get_tax_proy(
                3 * uit, self.param.rate_limit_ids.sorted('range')),
            3 * uit * 0.08, places=2)

    def test_loan_cronograma(self):
        """Cuotas iguales a fin de mes con saldo decreciente."""
        loan_type = self.env['hr.loan.type'].create({
            'name': 'Préstamo personal', 'company_id': self.company.id})
        loan = self.env['hr.loan'].create({
            'company_id': self.company.id,
            'employee_id': self.employee.id,
            'loan_type_id': loan_type.id,
            'date': date(2026, 1, 15),
            'amount': 1200.0,
            'fees_number': 4,
        })
        loan.get_fees()
        lines = loan.line_ids.sorted('fee')
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines.mapped('amount'), [300.0] * 4)
        self.assertEqual(lines.mapped('date'), [
            date(2026, 1, 31), date(2026, 2, 28),
            date(2026, 3, 31), date(2026, 4, 30)])
        self.assertEqual(lines.mapped('debt'), [900.0, 600.0, 300.0, 0.0])
        self.assertAlmostEqual(loan.saldo_final, 1200.0, places=2)

    def test_provision_mensual(self):
        """Provisión del mes (régimen general, computable = básico):
        CTS y vacaciones = básico/12; gratificación = básico/6."""
        prov = self.env['hr.provisiones'].create({
            'company_id': self.company.id,
            'payslip_run_id': self.batch.id,
        })
        prov.actualizar()
        cts = prov.cts_lines.filtered(
            lambda l: l.employee_id == self.employee)
        vaca = prov.vaca_lines.filtered(
            lambda l: l.employee_id == self.employee)
        grati = prov.grati_lines.filtered(
            lambda l: l.employee_id == self.employee)
        self.assertTrue(cts and vaca and grati,
                        'Faltan líneas de provisión del empleado')
        self.assertAlmostEqual(
            cts.provisiones_cts, self.wage / 12, places=2)
        self.assertAlmostEqual(
            vaca.provisiones_vaca, self.wage / 12, places=2)
        self.assertAlmostEqual(
            grati.provisiones_grati, self.wage / 6, places=2)
        # Sin seguro social en la versión: bono 0
        self.assertAlmostEqual(grati.boni_grati, 0.0, places=2)

    def test_utilidades_50_50(self):
        """Un solo trabajador recibe el 100 % del monto a distribuir
        (50 % por remuneraciones + 50 % por días)."""
        self.param.write({
            'rule_total_income': self.param.basic_sr_id.id,
            'wd_dtrab': [(6, 0, self.env['hr.work.entry.type'].search(
                [('code', 'in', ('DLAB', 'DOM'))]).ids)],
            'wd_falt': [(6, 0, self.env['hr.work.entry.type'].search(
                [('code', '=', 'FAL')]).ids)],
            'hr_input_for_results': self.env[
                'hr.payslip.input.type'].search([], limit=1).id,
        })
        util = self.env['hr.utilities'].create({
            'company_id': self.company.id,
            'year': 2026,
            'annual_rent': 100000.0,
            'percentage': 10.0,
            'payslip_run_id': self.batch_jun.id,
        })
        util.calculate()
        line = util.utilities_line_ids.filtered(
            lambda l: l.employee_id == self.employee)
        self.assertTrue(line, 'Utilidades sin línea del empleado')
        # Ene-Jun 2026: 6 boletas × 3 000 de básico
        self.assertAlmostEqual(line.salary, self.wage * 6, places=2)
        self.assertGreater(line.number_of_days, 0)
        self.assertAlmostEqual(util.distribution, 10000.0, places=2)
        # Único trabajador → se lleva todo el reparto
        self.assertAlmostEqual(line.total_utilities, 10000.0, places=2)
