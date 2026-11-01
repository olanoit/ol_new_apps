# -*- coding: utf-8 -*-
"""Revisión numérica de beneficios (ronda 2): quincena, utilidades,
préstamos y adelantos, y renta de 5ta.

Mismo caso de referencia que las fases 3 y 4 (sueldo 3 000 estable,
régimen general, boletas Nov-2025 → Jun-2026 validadas en lotes
mensuales). Cada test fija el defecto que corrige.
"""
from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_fase3_benefits import BenefitsCaseBase


@tagged('post_install', '-at_install')
class TestRev2Util5ta(BenefitsCaseBase):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _slip(self, year, month):
        return self.runs[(year, month)].slip_ids.filtered(
            lambda slip: slip.employee_id == self.employee)

    def _run(self, year, month, last):
        periodo = self.env['hr.period'].search([
            ('code', '=', '%04d%02d' % (year, month)),
            ('company_id', '=', self.company.id)], limit=1)
        return self.env['hr.payslip.run'].create({
            'name': 'Lote vacío %s-%02d' % (year, month),
            'date_start': date(year, month, 1),
            'date_end': date(year, month, last),
            'company_id': self.company.id,
            'periodo_id': periodo.id,
        })

    def _line(self, slip, code):
        return sum(slip.line_ids.filtered(
            lambda line: line.code == code).mapped('total'))

    def _input(self, slip, rule):
        return sum(slip.input_line_ids.filtered(
            lambda inp: inp.salary_rule_id == rule).mapped('amount'))

    def _fortnightly(self, lot):
        return self.env['hr.fortnightly'].create({
            'name': 'Quincena octubre', 'company_id': self.company.id,
            'date_start': date(2026, 10, 1), 'date_end': date(2026, 10, 15),
            'payslip_run_id': lot.id,
        })

    def _utilities(self, lot=None):
        WorkEntryType = self.env['hr.work.entry.type']
        self.param.write({
            'rule_total_income': self.param.basic_sr_id.id,
            'wd_dtrab': [(6, 0, WorkEntryType.search(
                [('code', 'in', ('DLAB', 'DOM'))]).ids)],
            'wd_falt': [(6, 0, WorkEntryType.search(
                [('code', '=', 'FAL')]).ids)],
            'hr_input_for_results': self.env['hr.salary.rule'].search(
                [('input_usage_payslip', '=', True)], limit=1).id,
        })
        return self.env['hr.utilities'].create({
            'company_id': self.company.id, 'year': 2026,
            'annual_rent': 100000.0, 'percentage': 10.0,
            'payslip_run_id': (lot or self.batch_jun).id,
        })

    def _add_days(self, slip, code, days):
        """Agrega ``days`` días de ``code`` a la boleta, quitándolos del
        DLAB (el total de días del mes no cambia)."""
        wet = self.env['hr.work.entry.type'].search(
            [('code', '=', code)], limit=1)
        self.env['hr.payslip.worked_days'].create({
            'payslip_id': slip.id, 'version_id': slip.version_id.id,
            'work_entry_type_id': wet.id,
            'number_of_days': days, 'number_of_hours': days * 8,
        })
        dlab = slip.worked_days_line_ids.filtered(
            lambda wd: wd.code == 'DLAB')[:1]
        dlab.number_of_days -= days

    def _special_types(self):
        """Tipos BBSS de adelanto y préstamo con sus inputs de BASE, más
        un préstamo ordinario."""
        AdvanceType = self.env['hr.advance.type']
        LoanType = self.env['hr.loan.type']

        def rule(code):
            return self.env.ref('al_hr_pe.salary_rule_%s' % code)

        types = {
            'grat_adv': AdvanceType.create({
                'name': 'Adelanto de gratificación',
                'input_id': rule('ADE_GRA').id,
                'company_id': self.company.id}),
            'ordinary_adv': AdvanceType.create({
                'name': 'Adelanto', 'input_id': rule('ADELANTO').id,
                'company_id': self.company.id}),
            'cts_loan': LoanType.create({
                'name': 'Préstamo contra la CTS',
                'input_id': rule('ADE_CTS').id,
                'company_id': self.company.id}),
            'ordinary_loan': LoanType.create({
                'name': 'Préstamo', 'input_id': rule('PREST').id,
                'company_id': self.company.id}),
        }
        self.param.write({'grat_advance_id': types['grat_adv'].id,
                          'grat_loan_id': types['cts_loan'].copy(
                              {'name': 'Préstamo de gratificación'}).id,
                          'cts_loan_id': types['cts_loan'].id})
        return types

    def _loan(self, loan_type, amount, fees, on_date):
        loan = self.env['hr.loan'].create({
            'company_id': self.company.id,
            'employee_id': self.employee.id,
            'loan_type_id': loan_type.id,
            'date': on_date, 'amount': amount, 'fees_number': fees,
        })
        loan.action_generate_fees()
        return loan

    def _advance(self, advance_type, amount, discount_date):
        return self.env['hr.advance'].create({
            'company_id': self.company.id,
            'employee_id': self.employee.id,
            'advance_type_id': advance_type.id,
            'amount': amount, 'date': discount_date,
            'discount_date': discount_date,
        })

    # ------------------------------------------------------------------
    # Quincena
    # ------------------------------------------------------------------
    def test_quincena_sin_boleta_mensual_da_error(self):
        """Sin boleta en el lote mensual el adelanto quincenal nunca se
        descontaba y el lote quedaba «exportado»."""
        self.param.write({'fortnightly_type': 'percentage', 'tasa': 0.5,
                          'compute_afiliacion': False})
        fortnightly = self._fortnightly(self._run(2026, 10, 31))
        fortnightly.action_generate_payslips()
        with self.assertRaisesRegex(UserError, 'Huamán'):
            fortnightly.action_export_to_payslips()
        self.assertEqual(fortnightly.state, 'verify')

    def test_quincena_porcentaje_prorrateada_por_contrato(self):
        """Ingreso el 14/10 (2 días de la quincena) y cese el 05/10 (5
        días): el 50 % se prorratea por los días de contrato."""
        self.param.write({'fortnightly_type': 'percentage', 'tasa': 0.5,
                          'compute_afiliacion': False})
        hired = self.env['hr.employee'].create({
            'names': 'Luis', 'last_name': 'Quispe', 'm_last_name': 'Mamani',
            'company_id': self.company.id,
            'date_version': date(2026, 10, 14),
            'contract_date_start': date(2026, 10, 14),
            'wage': self.wage,
            'structure_type_id': self.structure.type_id.id,
        })
        self.employee.version_id.contract_date_end = date(2026, 10, 5)
        fortnightly = self._fortnightly(self._run(2026, 10, 31))
        fortnightly.action_generate_payslips()

        def neto(employee):
            return self._line(fortnightly.slip_ids.filtered(
                lambda slip: slip.employee_id == employee), 'NETO_AQ')

        self.assertAlmostEqual(neto(hired), self.wage * 0.5 * 2 / 15,
                               places=2)
        self.assertAlmostEqual(neto(self.employee),
                               self.wage * 0.5 * 5 / 15, places=2)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def test_utilidades_cesado_sin_boleta_no_se_omite(self):
        """El cesado sin boleta en el lote de pago ya no se omite en
        silencio: error con su nombre; marcado «Pago aparte» se exporta."""
        util = self._utilities(lot=self._run(2026, 7, 31))
        util.action_process()
        line = util.utilities_line_ids
        self.assertTrue(line.total_utilities)
        with self.assertRaisesRegex(UserError, 'Huamán'):
            util.action_export_to_payslips()
        self.assertEqual(util.state, 'draft')
        line.paid_separately = True
        util.action_export_to_payslips()
        self.assertEqual(util.state, 'exported')

    def test_utilidades_faltas_no_se_restan_dos_veces(self):
        """DLAB ya viene sin las faltas (FAL es otra línea): restarlas
        otra vez quitaba 3 días de más."""
        util = self._utilities()
        util.action_process()
        days = util.utilities_line_ids.number_of_days
        self._add_days(self._slip(2026, 3), 'FAL', 3.0)
        util.action_process()
        self.assertAlmostEqual(
            util.utilities_line_ids.number_of_days, days - 3.0, places=2)

    def test_utilidades_suma_descanso_pre_y_posnatal(self):
        """Decisión 5: el descanso pre y posnatal (SMAR) se asimila a los
        días laborados aunque no esté en la configuración."""
        util = self._utilities()
        util.action_process()
        days = util.utilities_line_ids.number_of_days
        self._add_days(self._slip(2026, 4), 'SMAR', 10.0)
        util.action_process()
        self.assertAlmostEqual(
            util.utilities_line_ids.number_of_days, days, places=2)

    def test_utilidades_tope_con_asignacion_familiar_por_fecha(self):
        """El tope de 18 remuneraciones usa la asignación familiar de la
        RMV vigente al cierre, no el parámetro fijo de la compañía."""
        self.param.rmv = 500.0
        closing = date(2025, 12, 31)
        rmv = self.env['hr.rule.parameter']._l10n_pe_get_rmv(closing)
        self.assertTrue(rmv)
        self.assertNotAlmostEqual(rmv * 0.10, self.param.family_allowance)
        with patch.object(type(self.employee),
                          '_l10n_pe_has_family_allowance',
                          return_value=True):
            amount = self.env['hr.utilities']._closing_remuneration(
                self.employee, self.employee.version_id, self.param,
                closing)
        self.assertAlmostEqual(amount, self.wage + round(rmv * 0.10, 2),
                               places=2)

    def test_utilidades_aviso_empresa_con_20_trabajadores_o_menos(self):
        util = self._utilities()
        util.action_process()
        self.assertEqual(util.worker_count, 1)

    # ------------------------------------------------------------------
    # Préstamos y adelantos
    # ------------------------------------------------------------------
    def test_prestamo_cese_trae_todas_las_cuotas(self):
        """Cese el 20/06: las cuotas del 30/06 y 31/07 vencen después del
        cese y quedaban pendientes para siempre."""
        types = self._special_types()
        loan = self._loan(types['ordinary_loan'], 3000.0, 3,
                          date(2026, 5, 10))
        loan.line_ids.sorted('fee')[0].turn_paid_out()
        slip = self._slip(2026, 6)
        slip.write({'state': 'draft'})
        self.employee.version_id.contract_date_end = date(2026, 6, 20)
        slip.import_loans()
        self.assertAlmostEqual(
            self._input(slip, types['ordinary_loan'].input_id), 2000.0,
            places=2)
        self.assertFalse(loan.saldo_final)
        # Reimportar no pierde las cuotas de vencimiento posterior.
        slip.import_loans()
        self.assertAlmostEqual(
            self._input(slip, types['ordinary_loan'].input_id), 2000.0,
            places=2)

    def test_adelanto_de_gratificacion_lo_descuenta_su_proceso(self):
        """El adelanto de gratificación pendiente se descuenta una sola vez
        en la boleta de la gratificación, y la importación ordinaria no lo
        vuelve a sumar como regularización."""
        types = self._special_types()
        advance = self._advance(types['grat_adv'], 1000.0, date(2026, 6, 10))
        self._advance(types['ordinary_adv'], 100.0, date(2026, 6, 20))
        slip = self._slip(2026, 6)
        slip.write({'state': 'draft'})
        pending, _loans = self.env['hr.payslip']._l10n_pe_pending_advances(
            self.employee, 'grat', date(2026, 6, 30))
        self.assertEqual(pending, advance)
        self.assertAlmostEqual(
            slip._l10n_pe_discount_benefit_advances(
                'grat', on_date=date(2026, 6, 30)), 1000.0, places=2)
        self.assertEqual(advance.state, 'paid out')
        self.assertEqual(advance.l10n_pe_payslip_id, slip)
        # Exportar otra vez no duplica.
        slip._l10n_pe_discount_benefit_advances(
            'grat', on_date=date(2026, 6, 30))
        self.assertAlmostEqual(
            self._input(slip, types['grat_adv'].input_id), 1000.0, places=2)
        slip.import_advances()
        self.assertAlmostEqual(
            self._input(slip, types['ordinary_adv'].input_id), 100.0,
            places=2)

    def test_beneficios_con_el_mismo_input_no_se_pisan(self):
        """Gratificación y CTS descuentan por el mismo input (DES_BBSS): la
        segunda llamada suma lo que ya descontó la primera en la boleta."""
        types = self._special_types()
        shared = self.env.ref('al_hr_pe.salary_rule_DES_BBSS')
        types['grat_adv'].input_id = shared
        types['cts_loan'].input_id = shared
        self._advance(types['grat_adv'], 1000.0, date(2026, 6, 10))
        self._loan(types['cts_loan'], 600.0, 1, date(2026, 6, 5))
        slip = self._slip(2026, 6)
        slip.write({'state': 'draft'})
        slip._l10n_pe_discount_benefit_advances(
            'grat', on_date=date(2026, 6, 30))
        self.assertAlmostEqual(self._input(slip, shared), 1000.0, places=2)
        slip._l10n_pe_discount_benefit_advances('cts', cap=1500.0)
        self.assertAlmostEqual(self._input(slip, shared), 1600.0, places=2)
        # En orden inverso (o repitiendo) el total no cambia.
        slip._l10n_pe_discount_benefit_advances(
            'grat', on_date=date(2026, 6, 30))
        self.assertAlmostEqual(self._input(slip, shared), 1600.0, places=2)

    def test_prestamo_contra_cts_tope_50(self):
        """Contra la CTS se descuenta hasta el 50 % (art. 40 del TUO de la
        Ley de CTS): la cuota que rebasa el tope se parte y el saldo
        queda pendiente."""
        types = self._special_types()
        loan = self._loan(types['cts_loan'], 3000.0, 3, date(2026, 4, 10))
        slip = self._slip(2026, 6)
        slip.write({'state': 'draft'})
        discounted = slip._l10n_pe_discount_benefit_advances(
            'cts', cap=1500.0)
        self.assertAlmostEqual(discounted, 1500.0, places=2)
        self.assertAlmostEqual(
            self._input(slip, types['cts_loan'].input_id), 1500.0, places=2)
        self.assertAlmostEqual(loan.saldo_final, 1500.0, places=2)
        self.assertAlmostEqual(sum(loan.line_ids.mapped('amount')), 3000.0,
                               places=2)

    # ------------------------------------------------------------------
    # Renta de 5ta
    # ------------------------------------------------------------------
    def test_quinta_negativa_solo_en_mes_final(self):
        """Fuera de diciembre o del cese, una retención negativa (un
        excluido reincorporado) se exporta como 0: no hay devoluciones a
        mitad de año."""
        rule = {code: self.env['hr.salary.rule'].search([
            ('struct_ids', 'in', self.structure.ids),
            ('code', '=', code)], limit=1) for code in ('BAS', 'REAQ')}
        quinta = self.env.ref('al_hr_pe.salary_rule_QUINTA')
        self.param.write({
            'fifth_afect_sr_id': rule['BAS'].id,
            'fifth_extr_sr_id': rule['REAQ'].id,
            'proy_afect_sr_id': rule['BAS'].id,
            'fifth_category_input_id': quinta.id,
        })
        self.param.action_generate_brackets(year=2026)
        may = self._slip(2026, 5)
        line = may.line_ids.filtered(lambda line: line.code == 'QUINTA')
        line.write({'amount': 300.0, 'quantity': 1.0, 'rate': 100.0,
                    'total': 300.0})
        self.employee.version_id.contract_date_end = date(2026, 6, 30)
        fifth = self.env['hr.fifth.category'].create({
            'payslip_run_id': self.batch_jun.id,
            'company_id': self.company.id})
        fifth.action_generate()
        fifth_line = fifth.line_ids.filtered(
            lambda line: line.employee_id == self.employee)
        self.assertAlmostEqual(fifth_line.monthly_ret, -300.0, places=2)
        slip = self._slip(2026, 6)
        slip.write({'state': 'draft'})
        # Mes del cese: se devuelve.
        fifth.action_export_to_payslips()
        self.assertAlmostEqual(self._input(slip, quinta), -300.0, places=2)
        # Mismo importe fuera del mes final: 0.
        fifth.state = 'verify'
        self.employee.version_id.contract_date_end = False
        fifth.action_export_to_payslips()
        self.assertAlmostEqual(self._input(slip, quinta), 0.0, places=2)
