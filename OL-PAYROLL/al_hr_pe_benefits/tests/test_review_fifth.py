# -*- coding: utf-8 -*-
"""Revisión Odoo 20 (renta de 5ta y quinta proporcional de vacaciones).

Mismo caso de referencia que las fases 3 y 4 (sueldo 3 000 estable,
régimen general, boletas Nov-2025 → Jun-2026 validadas en lotes
mensuales). Cada test fija el defecto que corrige.
"""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_fase3_benefits import BenefitsCaseBase


@tagged('post_install', '-at_install')
class TestReviewFifth(BenefitsCaseBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Line = cls.env['hr.fifth.category.line']
        cls.quinta_input = cls.env.ref('al_hr_pe.salary_rule_QUINTA')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _slip(self, year, month):
        return self.runs[(year, month)].slip_ids.filtered(
            lambda slip: slip.employee_id == self.employee)

    def _set_rule_amount(self, slip, code, amount):
        line = slip.line_ids.filtered(lambda line: line.code == code)
        self.assertTrue(line, 'La boleta no tiene la línea %s' % code)
        line.write({'amount': amount, 'quantity': 1.0, 'rate': 100.0,
                    'total': amount})

    def _configure_fifth(self):
        Rule = self.env['hr.salary.rule']
        rule = {code: Rule.search([('struct_ids', 'in', self.structure.ids),
                                   ('code', '=', code)], limit=1)
                for code in ('BAS', 'REAQ')}
        self.param.write({
            'fifth_afect_sr_id': rule['BAS'].id,
            'fifth_extr_sr_id': rule['REAQ'].id,
            'proy_afect_sr_id': rule['BAS'].id,
            'fifth_category_input_id': self.quinta_input.id,
        })
        self.param.action_generate_brackets(year=2026)

    def _fifth(self, run=None):
        fifth = self.env['hr.fifth.category'].create({
            'payslip_run_id': (run or self.batch_jun).id,
            'company_id': self.company.id})
        fifth.action_generate()
        return fifth

    def _employee_line(self, fifth):
        """Línea afecta o excluida del trabajador (ambas llevan las
        gratificaciones)."""
        def mine(lines):
            return lines.filtered(
                lambda line: line.employee_id == self.employee)
        return mine(fifth.line_ids) or mine(fifth.line_excluidos_ids)

    def _reopen(self, slips):
        slips.write({'state': 'draft'})

    # ------------------------------------------------------------------
    # A1: mes del cese descuenta todo lo retenido
    # ------------------------------------------------------------------
    def test_cese_descuenta_todas_las_retenciones_previas(self):
        """Cese el 30/06 con 300 retenidos en mayo: el impuesto del año
        (0, por debajo de 7 UIT) menos TODO lo retenido devuelve los 300.
        Antes la ventana de junio (ene-abr) los ignoraba: ni se devolvían
        y, con impuesto, se volvían a retener."""
        self._configure_fifth()
        self._set_rule_amount(self._slip(2026, 5), 'QUINTA', 300.0)
        self.employee.version_id.contract_date_end = date(2026, 6, 30)
        fifth = self._fifth()
        line = fifth.line_ids.filtered(
            lambda line: line.employee_id == self.employee)
        self.assertEqual(len(line), 1, 'la devolución no se excluye')
        self.assertAlmostEqual(line.past_months_ret, 300.0, places=2)
        self.assertAlmostEqual(line.monthly_ret, -300.0, places=2)

    def test_cese_en_marzo_descuenta_enero_y_febrero(self):
        self._set_rule_amount(self._slip(2026, 1), 'QUINTA', 40.0)
        self._set_rule_amount(self._slip(2026, 2), 'QUINTA', 60.0)
        march = self._slip(2026, 3)
        self.assertAlmostEqual(
            self.Line.get_past_months_ret(march, date(2026, 1, 1),
                                          final=True), 100.0, places=2)
        # Fuera del cese, enero-marzo no descuenta nada (art. 40).
        self.assertAlmostEqual(
            self.Line.get_past_months_ret(march, date(2026, 1, 1)), 0.0,
            places=2)

    # ------------------------------------------------------------------
    # A2: reglas afectas que suman la gratificación
    # ------------------------------------------------------------------
    def test_regla_afecta_con_gratificacion_se_rechaza(self):
        """RAU suma GRA y BON9: con ella la gratificación entraba dos
        veces (en las remuneraciones pasadas y como real/proyectada)."""
        self._configure_fifth()
        self.param.check_fifth_values()
        rau = self.env.ref('al_hr_pe.salary_rule_RAU')
        self.param.fifth_extr_sr_id = rau
        with self.assertRaises(UserError):
            self.param.check_fifth_values()

    # ------------------------------------------------------------------
    # A3: gratificación proyectada según el régimen
    # ------------------------------------------------------------------
    def test_gratificacion_proyectada_pequena_empresa(self):
        self._configure_fifth()
        self.employee.version_id.l10n_pe_labor_regime = 'small'
        line = self._employee_line(self._fifth())
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.grat_july, self.wage / 2, places=2)
        self.assertAlmostEqual(line.grat_december, self.wage / 2, places=2)

    def test_gratificacion_proyectada_microempresa_y_practicante(self):
        self._configure_fifth()
        for regime in ('micro', 'practicante'):
            self.employee.version_id.l10n_pe_labor_regime = regime
            fifth = self._fifth()
            line = self._employee_line(fifth)
            self.assertEqual(len(line), 1)
            self.assertEqual((line.grat_july, line.grat_december),
                             (0.0, 0.0), regime)
            fifth.unlink()

    # ------------------------------------------------------------------
    # A4: una línea y una retención por trabajador
    # ------------------------------------------------------------------
    def test_una_linea_por_trabajador_con_dos_boletas(self):
        """Odoo 20 genera una boleta por versión: dos boletas en el lote
        dan una sola línea, que suma la remuneración de ambas, y la
        retención se exporta a una sola boleta."""
        self._configure_fifth()
        june = self._slip(2026, 6)
        second = self.env['hr.payslip'].create({
            'name': 'Boleta 2026-06 (2)',
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30),
            'payslip_run_id': self.batch_jun.id,
        })
        second.compute_sheet()
        self._reopen(june)
        fifth = self._fifth()
        line = self._employee_line(fifth)
        self.assertEqual(len(line), 1)
        bas = sum((june | second).line_ids.filtered(
            lambda pl: pl.code == 'BAS').mapped('total'))
        self.assertAlmostEqual(line.monthly_rem, bas, places=2)
        if fifth.line_ids:
            fifth.action_export_to_payslips()
            exported = (june | second).input_line_ids.filtered(
                lambda inp: inp.salary_rule_id == self.quinta_input)
            self.assertEqual(len(exported), 1)

    # ------------------------------------------------------------------
    # S1 / C1: estados y boletas cerradas
    # ------------------------------------------------------------------
    def test_no_se_regenera_ni_reexporta_por_rpc(self):
        self._configure_fifth()
        self._reopen(self._slip(2026, 6))
        fifth = self._fifth()
        with self.assertRaises(UserError):
            fifth.action_generate()
        fifth.action_export_to_payslips()
        with self.assertRaises(UserError):
            fifth.action_export_to_payslips()
        with self.assertRaises(UserError):
            fifth.action_recompute()

    def test_no_exporta_a_boleta_validada(self):
        self._configure_fifth()
        june = self._slip(2026, 6)
        self.assertEqual(june.state, 'validated')
        self._set_rule_amount(june, 'REAQ', 10000.0)
        fifth = self._fifth()
        self.assertTrue(fifth.line_ids)
        with self.assertRaises(UserError):
            fifth.action_export_to_payslips()

    # ------------------------------------------------------------------
    # M2: vacaciones y quinta sobre el input QUINTA
    # ------------------------------------------------------------------
    def _vacation_line(self, quinta=0.0):
        vacation = self.env['hr.vacation'].create({
            'company_id': self.company.id, 'year': 2026,
            'payslip_run_id': self.batch_jun.id,
        })
        line = self.env['hr.vacation.line'].create({
            'vacation_id': vacation.id,
            'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id,
            'wage': self.wage,
            'accrued_vacation': 15,
        })
        line.with_context(line_form=True).action_compute()
        line.quinta = quinta
        return vacation, line

    def test_vacaciones_no_pisan_la_quinta_exportada(self):
        self._configure_fifth()
        june = self._slip(2026, 6)
        self._reopen(june)
        self._set_rule_amount(june, 'REAQ', 10000.0)
        fifth = self._fifth()
        fifth.action_export_to_payslips()
        quinta = june.input_line_ids.filtered(
            lambda inp: inp.salary_rule_id == self.quinta_input)
        monthly = quinta.amount
        self.assertGreater(monthly, 0.0)
        vacation, _line = self._vacation_line(quinta=25.0)
        vacation.action_export_to_payslips()
        self.assertAlmostEqual(quinta.amount, monthly, places=2)

    def test_quinta_exportada_anula_la_proporcional_en_excluidos(self):
        """Exportar las vacaciones primero y la quinta después: el excluido
        (sin retención) no se queda con la quinta proporcional."""
        self._configure_fifth()
        # Cese el 30/06: 6 × 3 000 no llega a 7 UIT, sin retención.
        self.employee.version_id.contract_date_end = date(2026, 6, 30)
        june = self._slip(2026, 6)
        self._reopen(june)
        vacation, _line = self._vacation_line(quinta=25.0)
        vacation.action_export_to_payslips()
        quinta = june.input_line_ids.filtered(
            lambda inp: inp.salary_rule_id == self.quinta_input)
        self.assertAlmostEqual(quinta.amount, 25.0, places=2)
        fifth = self._fifth()
        self.assertFalse(fifth.line_ids, 'sin renta neta no hay retención')
        fifth.action_export_to_payslips()
        self.assertAlmostEqual(quinta.amount, 0.0, places=2)

    # ------------------------------------------------------------------
    # M7: quinta proporcional de vacaciones
    # ------------------------------------------------------------------
    def test_quinta_vacaciones_solo_boletas_cerradas_y_ordinaria(self):
        may = self._slip(2026, 5)
        self._set_rule_amount(may, 'QUINTA', 100.0)
        draft = self.env['hr.payslip'].create({
            'name': 'Borrador mayo', 'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 5, 1), 'date_to': date(2026, 5, 31),
            'payslip_run_id': self.runs[(2026, 5)].id,
        })
        draft.compute_sheet()
        self._set_rule_amount(draft, 'QUINTA', 500.0)
        vacation, line = self._vacation_line()
        line.compute_quinta_line(self.batch_jun)
        self.assertAlmostEqual(line.quinta, 100.0 / 30 * 15, places=2)
        # Con la quinta de mayo exportada, solo la retención ordinaria.
        fifth_may = self.env['hr.fifth.category'].create({
            'payslip_run_id': self.runs[(2026, 5)].id,
            'company_id': self.company.id, 'state': 'exported'})
        self.Line.create({
            'fifth_category_id': fifth_may.id, 'slip_id': may.id,
            'monthly_ret': 80.0, 'ext_ret': 20.0})
        line.compute_quinta_line(self.batch_jun)
        self.assertAlmostEqual(line.quinta, 80.0 / 30 * 15, places=2)

    # ------------------------------------------------------------------
    # Retenciones previas: boletas sin lote y otras estructuras
    # ------------------------------------------------------------------
    def test_retenciones_previas_sin_lote_y_otra_estructura(self):
        """Una boleta cerrada fuera de lote y la regla QUINTA de otra
        estructura también son retenciones ya practicadas."""
        other_struct = self.env['hr.payroll.structure'].create({
            'name': 'Otra estructura', 'type_id': self.structure.type_id.id})
        other_quinta = self.quinta_input.copy({
            'struct_ids': [(6, 0, other_struct.ids)]})
        # La copia renombra el código: se le devuelve el de la regla.
        other_quinta.code = 'QUINTA'
        self.assertEqual(other_quinta.code, 'QUINTA')
        off_cycle = self.env['hr.payslip'].create({
            'name': 'Fuera de lote', 'employee_id': self.employee.id,
            'struct_id': other_struct.id,
            'date_from': date(2026, 5, 1), 'date_to': date(2026, 5, 31),
        })
        self.env['hr.payslip.line'].create({
            'slip_id': off_cycle.id, 'salary_rule_id': other_quinta.id,
            'name': 'QUINTA', 'code': 'QUINTA', 'amount': 70.0,
            'quantity': 1.0, 'rate': 100.0, 'total': 70.0,
            'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id})
        off_cycle.state = 'validated'
        self._set_rule_amount(self._slip(2026, 5), 'QUINTA', 30.0)
        june = self._slip(2026, 6)
        self.assertAlmostEqual(
            self.Line.get_past_months_ret(june, date(2026, 1, 1),
                                          final=True), 100.0, places=2)
