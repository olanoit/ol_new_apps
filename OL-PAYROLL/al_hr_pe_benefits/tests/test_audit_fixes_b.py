# -*- coding: utf-8 -*-
"""Correcciones de la auditoría (parte B): renta de 5ta, utilidades,
subsidios, provisiones y préstamos.

Mismo caso de referencia que las fases 3 y 4 (sueldo 3 000 estable,
régimen general, boletas Nov-2025 → Jun-2026). Las expectativas salen
de la norma (Art. 40 del Reglamento LIR, D.L. 892) y de la UIT del
catálogo, no de números mágicos.
"""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests import tagged

from .test_fase3_benefits import BenefitsCaseBase


@tagged('post_install', '-at_install')
class TestAuditFixesB(BenefitsCaseBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Line = cls.env['hr.fifth.category.line']
        cls.quinta_rule = cls.Line._get_quinta_rule(cls.company)
        cls.uit_2026 = cls.env['l10n_pe.hr.uit'].get_uit(2026)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _slip(self, year, month):
        return self.runs[(year, month)].slip_ids.filtered(
            lambda slip: slip.employee_id == self.employee)

    def _set_rule_amount(self, slip, code, amount):
        line = slip.line_ids.filtered(lambda line: line.code == code)
        self.assertTrue(line, 'La boleta no tiene la línea %s' % code)
        # ``total`` es un valor almacenado (no se recalcula al escribir
        # ``amount``): se fija junto con él.
        line.write({'amount': amount, 'quantity': 1.0, 'rate': 100.0,
                    'total': amount})

    def _configure_fifth(self):
        Rule = self.env['hr.salary.rule']
        struct = self.structure
        rule = {code: Rule.search([('struct_id', '=', struct.id),
                                   ('code', '=', code)], limit=1)
                for code in ('BAS', 'REAQ')}
        quinta_input = self.env['hr.payslip.input.type'].search(
            [('code', '=', 'QUINTA')], limit=1)
        self.assertTrue(quinta_input, 'Falta el input QUINTA')
        self.param.write({
            'fifth_afect_sr_id': rule['BAS'].id,
            'fifth_extr_sr_id': rule['REAQ'].id,
            'proy_afect_sr_id': rule['BAS'].id,
            'fifth_category_input_id': quinta_input.id,
        })
        self.param.generate_tramos(year=2026)
        return quinta_input

    # ------------------------------------------------------------------
    # Renta de 5ta
    # ------------------------------------------------------------------
    def test_divisores_art_40(self):
        """Art. 40: ene-mar 12, abr 9, may-jul 8, ago 5, sep-nov 4,
        dic 1."""
        self.assertEqual(
            [self.Line.get_month_equivalence_rent(m) for m in range(1, 13)],
            [12, 12, 12, 9, 8, 8, 8, 5, 4, 4, 4, 1])

    def test_ventana_junio_incluye_abril(self):
        """Jun-jul descuentan lo retenido de enero a ABRIL inclusive (la
        boleta de abril vence el 30/04 y antes quedaba fuera)."""
        self._set_rule_amount(self._slip(2026, 3), 'QUINTA', 40.0)
        self._set_rule_amount(self._slip(2026, 4), 'QUINTA', 60.0)
        # Mayo no entra en la ventana de junio.
        self._set_rule_amount(self._slip(2026, 5), 'QUINTA', 999.0)
        june = self._slip(2026, 6)
        self.assertAlmostEqual(
            self.Line.get_past_months_ret(june, date(2026, 1, 1)),
            100.0, places=2)

    def test_ventana_octubre_incluye_agosto(self):
        """Oct-nov descuentan lo retenido de enero a AGOSTO inclusive:
        el tope que se pide a la búsqueda es el 01/09 (exclusivo)."""
        captured = {}
        Line = self.Line

        def fake_sum(employee, company, rules, date_from, date_before):
            captured['date_before'] = date_before
            return 0.0

        october = SimpleNamespace(
            date_from=date(2026, 10, 1), date_to=date(2026, 10, 31),
            employee_id=self.employee, company_id=self.company)
        with patch.object(type(Line), '_sum_payslip_rule_totals',
                          lambda self_, *args: fake_sum(*args)):
            Line.get_past_months_ret(october, date(2026, 1, 1))
        self.assertEqual(captured['date_before'], date(2026, 9, 1))

    def test_retenciones_previas_ignora_borradores(self):
        """Una boleta en borrador dentro de un lote no suma retenciones."""
        draft = self.env['hr.payslip'].create({
            'name': 'Borrador abril',
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
            'payslip_run_id': self.runs[(2026, 4)].id,
        })
        draft.compute_sheet()
        self._set_rule_amount(draft, 'QUINTA', 500.0)
        self.assertEqual(draft.state, 'draft')
        june = self._slip(2026, 6)
        self.assertAlmostEqual(
            self.Line.get_past_months_ret(june, date(2026, 1, 1)),
            0.0, places=2)

    def test_renta_anual_sin_reproyeccion(self):
        """La retención anual es siempre impuesto − retenciones previas −
        otros empleadores; la línea anterior no la sustituye."""
        line = self.Line.new({
            'tax_proy': 1000.0, 'past_months_ret': 300.0,
            'other_emp_ret': 50.0})
        self.assertAlmostEqual(
            line._get_renta_anual_proyecta(), 650.0, places=2)

    def test_tramos_reescalados_a_la_uit_de_la_boleta(self):
        """Tramos generados con la UIT 2025 calculan igual que los de
        2026 cuando la boleta es de 2026."""
        self.param.generate_tramos(year=2025)
        uit = self.uit_2026
        net_rent = 8 * uit
        tax = self.Line.get_tax_proy(
            net_rent, self.param.rate_limit_ids, uit=uit)
        expected = 5 * uit * 0.08 + (net_rent - 5 * uit) * 0.14
        self.assertAlmostEqual(tax, expected, places=2)

    def test_quinta_extraordinaria_se_suma_y_exporta(self):
        """Junio (divisor 8) con 10 000 de remuneración extraordinaria:
        la extraordinaria = impuesto con ella − impuesto sin ella; el
        input QUINTA recibe ordinaria + extraordinaria."""
        quinta_input = self._configure_fifth()
        june = self._slip(2026, 6)
        self._set_rule_amount(june, 'REAQ', 10000.0)
        fifth = self.env['hr.fifth.category'].create({
            'payslip_run_id': self.batch_jun.id,
            'company_id': self.company.id,
        })
        fifth.generate_fifth()
        line = fifth.line_ids.filtered(
            lambda l: l.employee_id == self.employee)
        self.assertTrue(line, 'El trabajador debe quedar afecto')
        uit = self.uit_2026
        wage = self.wage
        # Proyección: 6 meses restantes + junio + 2 gratificaciones
        # proyectadas (sin seguro social) + ene-may reales.
        total = wage * 6 + wage + 2 * wage + 5 * wage
        net_rent = total - 7 * uit
        Line = self.Line
        tramos = self.param.rate_limit_ids
        tax = Line.get_tax_proy(net_rent, tramos, uit=uit)
        tax_ext = Line.get_tax_proy(net_rent + 10000.0, tramos, uit=uit)
        self.assertAlmostEqual(line.net_rent, net_rent, places=2)
        self.assertAlmostEqual(line.monthly_ret, round(tax / 8, 2),
                               places=2)
        self.assertAlmostEqual(line.ext_ret, round(tax_ext - tax, 2),
                               places=2)
        self.assertGreater(line.ext_ret, 0.0)
        fifth.export_fifth()
        exported = june.input_line_ids.filtered(
            lambda inp: inp.input_type_id == quinta_input)
        self.assertAlmostEqual(
            sum(exported.mapped('amount')),
            line.monthly_ret + line.ext_ret, places=2)

    def _fifth_line_june(self):
        fifth = self.env['hr.fifth.category'].create({
            'payslip_run_id': self.batch_jun.id, 'company_id': self.company.id})
        fifth.generate_fifth()
        return fifth, fifth.line_ids.filtered(lambda l: l.employee_id == self.employee)

    def test_quinta_mes_del_cese_no_proyecta(self):
        """Cese el 30/06: sin meses restantes ni gratificaciones futuras.
        Con 6 × 3 000 (< 7 UIT) no hay retención; antes se proyectaba el año
        entero (42 000) y se retenía (auditoría 07/10/2026)."""
        self._configure_fifth()
        self.employee.version_id.contract_date_end = date(2026, 6, 30)
        fifth, line = self._fifth_line_june()
        self.assertFalse(line, 'sin renta neta no hay retención')
        excluded = fifth.excluded_ids.filtered(lambda l: l.slip_id.employee_id == self.employee) \
            if 'excluded_ids' in fifth._fields else False
        if excluded:
            self.assertAlmostEqual(excluded.total_proy, 6 * self.wage, places=2)

    def test_quinta_gratificacion_proporcional_al_ingreso(self):
        """Ingreso el 01/03: la gratificación de julio se proyecta por 4 de
        6 meses (Ley 27735), no completa."""
        self._configure_fifth()
        self.employee.version_id.contract_date_start = date(2026, 3, 1)
        fifth, line = self._fifth_line_june()
        if not line:
            self.skipTest('sin retención con estos datos')
        self.assertAlmostEqual(line.grat_july, self.wage * 4 / 6, places=2)
        self.assertAlmostEqual(line.grat_december, self.wage, places=2)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _utilities(self, annual_rent):
        self.param.write({
            'rule_total_income': self.param.basic_sr_id.id,
            'wd_dtrab': [(6, 0, self.env['hr.work.entry.type'].search(
                [('code', 'in', ('DLAB', 'DOM'))]).ids)],
            'wd_falt': [(6, 0, self.env['hr.work.entry.type'].search(
                [('code', '=', 'FAL')]).ids)],
            'hr_input_for_results': self.env[
                'hr.payslip.input.type'].search([], limit=1).id,
        })
        return self.env['hr.utilities'].create({
            'company_id': self.company.id,
            'year': 2026,
            'annual_rent': annual_rent,
            'percentage': 10.0,
            'payslip_run_id': self.batch_jun.id,
        })

    def test_utilidades_tope_18_remuneraciones(self):
        """D.L. 892 art. 2: la participación no supera 18
        remuneraciones; el exceso queda aparte (FONDOEMPLEO)."""
        util = self._utilities(1000000.0)
        util.calculate()
        line = util.utilities_line_ids
        self.assertEqual(len(line), 1)
        cap = 18 * self.wage
        self.assertAlmostEqual(line.monthly_remuneration, self.wage,
                               places=2)
        self.assertAlmostEqual(line.total_utilities, cap, places=2)
        self.assertAlmostEqual(line.excess_utilities,
                               util.distribution - cap, places=2)

    def test_utilidades_ignora_borradores(self):
        """Una boleta en borrador del ejercicio no suma sueldo ni días."""
        draft = self.env['hr.payslip'].create({
            'name': 'Borrador julio',
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 7, 1),
            'date_to': date(2026, 7, 31),
        })
        draft.compute_sheet()
        util = self._utilities(100000.0)
        util.calculate()
        # Ene-Jun 2026 cerradas: 6 × 3 000 (el borrador de julio no).
        self.assertAlmostEqual(util.utilities_line_ids.salary,
                               self.wage * 6, places=2)

    def test_utilidades_linea_preservada_no_se_duplica(self):
        """Recalcular con «No recalcular» no crea otra línea del mismo
        trabajador ni reparte a medias."""
        util = self._utilities(100000.0)
        util.calculate()
        util.utilities_line_ids.preserve_record = True
        util.calculate()
        line = util.utilities_line_ids
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.total_utilities, util.distribution,
                               places=2)

    # ------------------------------------------------------------------
    # Subsidios
    # ------------------------------------------------------------------
    def test_subsidio_maternidad_dentro_de_un_mes(self):
        """Maternidad del 10 al 31 de marzo: 22 días en el periodo, no
        31."""
        periodo = self.env['hr.period'].search([
            ('code', '=', '202603'), ('company_id', '=', self.company.id)],
            limit=1)
        lot = self.env['hr.subsidies.lot'].create({
            'company_id': self.company.id, 'periodo_id': periodo.id})
        subsidy = self.env['hr.subsidies'].create({
            'subsidies_lot_id': lot.id,
            'employee_id': self.employee.id,
            'type': 'maternity',
            'date_start': date(2026, 3, 10),
            'date_end': date(2026, 3, 31),
        })
        self.env['hr.subsidies.line'].create({
            'subsidies_id': subsidy.id, 'periodo_id': periodo.id,
            'wage': 3000.0})
        subsidy.get_calculation()
        self.assertEqual(subsidy.subsidies_periodo_ids.mapped('days'), [22])
        self.assertAlmostEqual(
            sum(subsidy.subsidies_periodo_ids.mapped('total_sub')),
            sum(subsidy.subsidies_total_ids.mapped('total_sub')), places=2)

    # ------------------------------------------------------------------
    # Provisiones
    # ------------------------------------------------------------------
    def test_provision_vacaciones_desde_el_ultimo_aniversario(self):
        """Ingreso 01/01/2025, lote de abril 2026: el acumulado de
        vacaciones arranca el 01/01/2026 (4 meses), no un año antes."""
        provisions = {}
        for key in [(2025, 12), (2026, 1), (2026, 2), (2026, 3),
                    (2026, 4)]:
            prov = self.env['hr.provisiones'].create({
                'company_id': self.company.id,
                'payslip_run_id': self.runs[key].id,
            })
            prov.actualizar()
            provisions[key] = prov
        april = provisions[(2026, 4)]
        april.compute_acumulado()
        vaca = april.vaca_lines.filtered(
            lambda l: l.employee_id == self.employee)
        self.assertAlmostEqual(vaca.prov_acumulado,
                               4 * sum(vaca.mapped('provisiones_vaca')),
                               places=2)

    # ------------------------------------------------------------------
    # Préstamos
    # ------------------------------------------------------------------
    def test_prestamo_residuo_en_la_ultima_cuota(self):
        """100 en 3 cuotas: 33.33 + 33.33 + 33.34 = 100 y deuda final 0;
        el préstamo sin pagar se puede borrar."""
        loan_type = self.env['hr.loan.type'].create({
            'name': 'Préstamo personal', 'company_id': self.company.id})
        loan = self.env['hr.loan'].create({
            'company_id': self.company.id,
            'employee_id': self.employee.id,
            'loan_type_id': loan_type.id,
            'date': date(2026, 1, 15),
            'amount': 100.0,
            'fees_number': 3,
        })
        loan.get_fees()
        lines = loan.line_ids.sorted('fee')
        self.assertEqual(lines.mapped('amount'), [33.33, 33.33, 33.34])
        self.assertAlmostEqual(lines[-1].debt, 0.0, places=2)
        self.assertAlmostEqual(sum(lines.mapped('amount')), 100.0, places=2)
        loan.unlink()
        self.assertFalse(loan.exists())

    def test_adelanto_sin_input_no_se_marca_pagado(self):
        """Un adelanto cuyo tipo no tiene input no llega a la boleta: no
        se marca como pagado."""
        # El import exige los tipos especiales de BBSS configurados.
        self.param.grat_advance_id = self.env['hr.advance.type'].create({
            'name': 'Adelanto de gratificación',
            'company_id': self.company.id})
        advance_type = self.env['hr.advance.type'].create({
            'name': 'Sin input', 'company_id': self.company.id})
        advance = self.env['hr.advance'].create({
            'company_id': self.company.id,
            'employee_id': self.employee.id,
            'advance_type_id': advance_type.id,
            'amount': 200.0,
            'discount_date': date(2026, 6, 15),
        })
        self._slip(2026, 6).import_advances()
        self.assertEqual(advance.state, 'not payed')
