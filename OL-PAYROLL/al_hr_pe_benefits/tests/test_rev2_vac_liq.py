# -*- coding: utf-8 -*-
"""Revisión numérica de beneficios sociales (ronda 2): vacaciones y
liquidación de cese.

Casos reproducidos de la revisión (lotes mensuales, boletas validadas y
los procesos reales de ``hr.vacation`` y ``hr.liquidation``). Cada test
fija el defecto que corrige; los importes salen de las fórmulas legales.
"""
from calendar import monthrange
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRev2VacLiq(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'PE REV2 VACLIQ', 'country_id': cls.env.ref('base.pe').id})
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids,
            tz='America/Lima'))
        cls.env.user.company_ids |= cls.company
        cls.env.user.group_ids |= cls.env.ref(
            'hr_payroll.group_hr_payroll_manager')
        cls.structure = cls.env.ref('al_hr_pe.base_structure')
        rule = cls._rule
        work = cls._work
        cls.param = cls.env['hr.main.parameter'].create({
            'company_id': cls.company.id, 'rmv': 1130.0,
            'basic_sr_id': rule('BAS').id,
            'household_allowance_sr_id': rule('AF').id,
            'extra_hours_sr_id': rule('HE25').id,
            'commission_sr_ids': [(6, 0, rule('COMI').ids)],
            'bonus_sr_ids': [(6, 0, rule('BONR').ids)],
            'cts_input_id': rule('CTS').id,
            'gratification_input_id': rule('GRA').id,
            'bonus_nine_input_id': rule('BON9').id,
            'truncated_gratification_input_id': rule('GRA_TRU').id,
            'truncated_bonus_nine_input_id': rule('BON9_TRU').id,
            'truncated_cts_input_id': rule('CTS_TRU').id,
            'vacation_input_id': rule('VAC').id,
            'truncated_vacation_input_id': rule('VATRU').id,
            'lack_wd_ids': [(6, 0, work('FAL').ids)],
            'working_wd_ids': [(6, 0, (work('DLAB') | work('DOM')).ids)],
            'medical_rest_wd_ids': [(6, 0, work('DMED').ids)],
        })
        cls.afp = cls.env['hr.membership'].search(
            [('is_afp', '=', True), ('company_id', '=', False)], limit=1)
        for year in (2024, 2025, 2026, 2027):
            cls.env['hr.period.generator'].create({
                'year': year, 'company_id': cls.company.id,
            }).action_generate()
        cls.situation_ceased = cls.env.ref('al_hr_pe.situation_0')

    def setUp(self):
        super().setUp()
        # Los lotes se crean dentro de cada test (se deshacen con él).
        self.runs = {}
        self.liquidation_oct = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @classmethod
    def _rule(cls, code):
        return cls.env.ref('al_hr_pe.salary_rule_' + code)

    @classmethod
    def _work(cls, code):
        return cls.env['hr.work.entry.type'].search(
            [('code', '=', code)], limit=1)

    def _run(self, year, month):
        if (year, month) not in self.runs:
            periodo = self.env['hr.period'].search([
                ('code', '=', '%04d%02d' % (year, month)),
                ('company_id', '=', self.company.id)], limit=1)
            self.runs[(year, month)] = self.env['hr.payslip.run'].create({
                'name': 'Lote %s-%02d' % (year, month),
                'date_start': date(year, month, 1),
                'date_end': date(year, month, monthrange(year, month)[1]),
                'company_id': self.company.id, 'periodo_id': periodo.id})
        return self.runs[(year, month)]

    def _employee(self, wage, start, end=False, regime='general',
                  children=0):
        employee = self.env['hr.employee'].create({
            'names': 'Prueba %s' % start, 'last_name': 'Rev',
            'm_last_name': 'Dos', 'company_id': self.company.id,
            'date_version': start, 'contract_date_start': start,
            'contract_date_end': end, 'wage': wage,
            'structure_type_id': self.structure.type_id.id,
            'children': children})
        employee.version_id.membership_id = self.afp
        employee.version_id.l10n_pe_labor_regime = regime
        return employee

    def _slip(self, employee, year, month, done=True):
        slip = self.env['hr.payslip'].create({
            'name': '%s %s-%02d' % (employee.names, year, month),
            'employee_id': employee.id, 'struct_id': self.structure.id,
            'date_from': date(year, month, 1),
            'date_to': date(year, month, monthrange(year, month)[1]),
            'payslip_run_id': self._run(year, month).id})
        slip.compute_sheet()
        if done:
            slip.action_payslip_done()
        return slip

    def _slips(self, employee, date_from, date_to):
        current = date(date_from.year, date_from.month, 1)
        while current <= date_to:
            self._slip(employee, current.year, current.month)
            current += relativedelta(months=1)

    def _cease(self, employee):
        employee.version_id.situation_id = self.situation_ceased

    def _liquidation(self, year, month):
        liquidation = self.env['hr.liquidation'].create({
            'company_id': self.company.id, 'year': year,
            'payslip_run_id': self._run(year, month).id,
            'gratification_type': '12', 'cts_type': '11'})
        liquidation._get_type()
        return liquidation

    def _suspension(self, employee, date_from, date_to):
        periodo = self.env['hr.period'].search([
            ('company_id', '=', self.company.id),
            ('date_start', '<=', date_from), ('date_end', '>=', date_from),
        ], limit=1)
        return self.env['hr.work.suspension'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            'periodo_id': periodo.id,
            'suspension_type_id': self.env['hr.suspension.type'].search(
                [('code', '=', '23')], limit=1).id,
            'date_from': date_from, 'date_to': date_to,
            'days': (date_to - date_from).days + 1,
            'company_id': self.company.id})

    def _vacation(self, year, month):
        return self.env['hr.vacation'].create({
            'company_id': self.company.id, 'year': year,
            'payslip_run_id': self._run(year, month).id})

    @staticmethod
    def _input(slip, rule):
        return sum(slip.input_line_ids.filtered(
            lambda inp: inp.salary_rule_id == rule).mapped('amount'))

    # ------------------------------------------------------------------
    # 1. Cese en noviembre: la CTS de may-oct no depositada
    # ------------------------------------------------------------------
    def test_cese_noviembre_paga_cts_mayo_octubre(self):
        """Cese el 10-11 sin depósito de may-oct (el regular no incluye al
        cesado): la liquidación paga may-oct (3 500/2) y nov (10 días),
        no solo nov."""
        employee = self._employee(3000.0, date(2026, 1, 1),
                                  end=date(2026, 11, 10))
        self._slips(employee, date(2026, 1, 1), date(2026, 10, 1))
        grati = self.env['hr.gratification'].create({
            'company_id': self.company.id, 'year': 2026, 'type': '07',
            'with_bonus': False, 'payslip_run_id': self._run(2026, 6).id,
            'deposit_date': date(2026, 7, 15)})
        grati.action_process()
        self._cease(employee)
        self._slip(employee, 2026, 11, done=False)
        liquidation = self._liquidation(2026, 11)
        self.assertEqual(liquidation.cts_type, '05')
        liquidation.action_process()
        lines = liquidation.cts_line_ids.filtered(
            lambda line: line.employee_id == employee)
        may_oct = lines.filtered(
            lambda line: line.compute_date == date(2026, 5, 1))
        self.assertEqual(len(may_oct), 1, 'Falta la CTS de may-oct')
        self.assertAlmostEqual(may_oct.total_cts, 3500 / 2, delta=0.05)
        self.assertAlmostEqual(sum(lines.mapped('total_cts')),
                               3500 / 2 + 3500 / 360 * 10, delta=0.05)

    # ------------------------------------------------------------------
    # 2, 9, 10, 14. Devengadas, indemnización, meses calendario, export
    # ------------------------------------------------------------------
    def _ceased_with_pending_years(self):
        """Ingreso 10-03-2024, cese 20-10-2026 y sin goces: dos años
        cumplidos sin gozar (el primero con el plazo vencido el
        09-03-2026). Los años previos no tienen boletas (récord «sin
        datos»: se generan)."""
        employee = self._employee(2500.0, date(2024, 3, 10),
                                  end=date(2026, 10, 20))
        self._slips(employee, date(2026, 3, 1), date(2026, 9, 1))
        self._cease(employee)
        slip = self._slip(employee, 2026, 10, done=False)
        liquidation = self._liquidation(2026, 10)
        liquidation.action_process()
        line = liquidation.vacation_line_ids.filtered(
            lambda line: line.employee_id == employee)
        self.assertEqual(len(line), 1)
        return employee, slip, liquidation, line

    def test_liquidacion_paga_devengadas_e_indemnizacion(self):
        _employee, _slip, _liquidation, line = \
            self._ceased_with_pending_years()
        self.assertAlmostEqual(line.computable_remuneration, 2500.0)
        self.assertAlmostEqual(line.accrued_days, 60.0)
        self.assertAlmostEqual(line.accrued_vacation, 5000.0, places=2)
        self.assertAlmostEqual(line.indemnity_days, 30.0)
        self.assertAlmostEqual(line.vacation_indemnity, 2500.0, places=2)

    def test_truncas_en_meses_calendario(self):
        """10-03 → 20-10 son 7 meses y 11 días (antes 7 y 12: sumaba los
        días sueltos de marzo y octubre como días comerciales)."""
        _employee, _slip, _liquidation, line = \
            self._ceased_with_pending_years()
        self.assertEqual(line.compute_date, date(2026, 3, 10))
        self.assertEqual((line.months, line.days), (7, 11))
        self.assertAlmostEqual(line.truncated_vacation,
                               2500 / 12 * 7 + 2500 / 360 * 11, delta=0.02)

    def test_truncas_ingreso_y_cese_a_mitad_de_mes(self):
        """16-03 → 15-09: 6 meses exactos (antes 6 meses y 1 día)."""
        employee = self._employee(1800.0, date(2026, 3, 16),
                                  end=date(2026, 9, 15))
        self._slips(employee, date(2026, 3, 1), date(2026, 8, 1))
        self._cease(employee)
        self._slip(employee, 2026, 9, done=False)
        liquidation = self._liquidation(2026, 9)
        liquidation.action_process()
        line = liquidation.vacation_line_ids.filtered(
            lambda line: line.employee_id == employee)
        self.assertEqual((line.months, line.days), (6, 0))
        self.assertAlmostEqual(line.truncated_vacation, 900.0, places=2)

    def test_export_suma_conceptos_y_no_pisa_el_goce(self):
        """Dos conceptos extra con el mismo input se suman; el input VAC
        lleva el goce exportado del mes + las devengadas; la indemnización
        va por su propio input (INDVAC)."""
        employee, slip, liquidation, line = \
            self._ceased_with_pending_years()
        vacation = self._vacation(2026, 10)
        self.env['hr.vacation.line'].create({
            'vacation_id': vacation.id, 'employee_id': employee.id,
            'version_id': employee.version_id.id, 'vacation_kind': 'rest',
            'accrued_vacation': 3, 'total_vacation': 250.0,
            'compute_date_ini': date(2026, 10, 1),
            'compute_date_fin': date(2026, 10, 3)})
        vacation.action_export_to_payslips()
        indem = self._rule('INDEM')
        concepts = liquidation.liq_ext_concept_ids.filtered(
            lambda concept: concept.employee_id == employee)
        concepts.conceptos_lines = [
            (0, 0, {'name_input_id': indem.id, 'amount': 100.0}),
            (0, 0, {'name_input_id': indem.id, 'amount': 50.0})]
        liquidation.action_export_to_payslips()
        self.assertAlmostEqual(self._input(slip, indem), 150.0)
        self.assertAlmostEqual(self._input(slip, self._rule('VAC')),
                               250.0 + line.accrued_vacation, places=2)
        self.assertAlmostEqual(self._input(slip, self._rule('INDVAC')),
                               line.vacation_indemnity, places=2)

    # ------------------------------------------------------------------
    # 3. Asignación familiar del mes de vacaciones
    # ------------------------------------------------------------------
    def test_goce_no_duplica_la_asignacion_familiar(self):
        """15 días de goce con hijos: la boleta ya paga la AF entera; la
        remuneración vacacional es 3 000/30 × 15 (antes +AF/2)."""
        employee = self._employee(3000.0, date(2025, 1, 1), children=1)
        self._slip(employee, 2026, 10, done=False)
        self._suspension(employee, date(2026, 10, 1), date(2026, 10, 15))
        vacation = self._vacation(2026, 10)
        vacation.action_process()
        line = vacation.line_ids
        self.assertEqual(line.household_allowance, 0.0)
        self.assertAlmostEqual(line.total_vacation, 1500.0, places=2)

    # ------------------------------------------------------------------
    # 4. El goce descuenta el saldo; adelanto sin saldo
    # ------------------------------------------------------------------
    def test_goce_exportado_descuenta_saldo_y_adelanto(self):
        """Ingreso 01-08 y 15 días gozados en octubre: es adelanto (aviso),
        al exportar crea el movimiento que descuenta el saldo y la
        liquidación lo ve como días adelantados; al volver a borrador se
        quita."""
        employee = self._employee(2000.0, date(2026, 8, 1))
        self._slips(employee, date(2026, 8, 1), date(2026, 9, 1))
        self._slip(employee, 2026, 10, done=False)
        self._suspension(employee, date(2026, 10, 1), date(2026, 10, 15))
        vacation = self._vacation(2026, 10)
        result = vacation.action_process()
        self.assertEqual(result['params']['type'], 'warning')
        self.assertEqual(vacation.line_ids.advance_days, 15.0)
        vacation.action_export_to_payslips()
        accrual = self.env['hr.accrual.vacation'].search([
            ('employee_id', '=', employee.id)])
        self.assertEqual((accrual.days, accrual.kind), (15, 'rest'))
        Rest = self.env['hr.vacation.rest']
        _years, advance = Rest._l10n_pe_pending_vacation(
            employee, date(2026, 10, 31))
        self.assertEqual(advance, 15.0)
        Rest.get_vacation_employee(employee, False)
        enjoyed = Rest.search([('employee_id', '=', employee.id),
                               ('days', '<', 0)])
        self.assertEqual(enjoyed.days, -15.0)
        self.assertAlmostEqual(enjoyed.amount,
                               -vacation.line_ids.total_vacation, places=2)
        vacation.action_draft()
        self.assertFalse(accrual.exists())

    # ------------------------------------------------------------------
    # 5. Asignación familiar del saldo por fecha
    # ------------------------------------------------------------------
    def test_saldo_toma_la_asignacion_familiar_por_fecha(self):
        """El importe del saldo usa el 10 % de la RMV de la tabla a la
        fecha, no el valor fijo de Parámetros Principales."""
        self.param.rmv = 1000.0
        employee = self._employee(3000.0, date(2025, 1, 1),
                                  end=date(2026, 6, 30), children=1)
        Rest = self.env['hr.vacation.rest']
        Rest.get_vacation_employee(employee, False)
        year = Rest.search([('employee_id', '=', employee.id),
                            ('date_from', '=', date(2025, 1, 1))])
        rmv = self.env['hr.rule.parameter']._l10n_pe_get_rmv(
            date(2026, 6, 30))
        self.assertTrue(rmv and rmv != 1000.0)
        self.assertAlmostEqual(year.amount, 3000.0 + round(rmv * 0.10, 2),
                               places=2)

    # ------------------------------------------------------------------
    # 6. Mínimo de un mes de servicios
    # ------------------------------------------------------------------
    def test_menos_de_un_mes_sin_truncas_ni_cts(self):
        """Ingreso 25-08, cese 05-09 (12 días): sin vacaciones truncas ni
        CTS trunca."""
        employee = self._employee(2000.0, date(2026, 8, 25),
                                  end=date(2026, 9, 5))
        self._slip(employee, 2026, 8)
        self._cease(employee)
        self._slip(employee, 2026, 9, done=False)
        liquidation = self._liquidation(2026, 9)
        liquidation.action_process()
        self.assertFalse(liquidation.vacation_line_ids.filtered(
            lambda line: line.employee_id == employee))
        self.assertFalse(liquidation.cts_line_ids.filtered(
            lambda line: line.employee_id == employee))

    # ------------------------------------------------------------------
    # 7. Venta de vacaciones y fraccionamiento
    # ------------------------------------------------------------------
    def _manual_line(self, vacation, employee, kind, days, date_from=False):
        return self.env['hr.vacation.line'].create({
            'vacation_id': vacation.id, 'employee_id': employee.id,
            'version_id': employee.version_id.id, 'vacation_kind': kind,
            'compute_date': date(2026, 1, 1), 'accrued_vacation': days,
            'compute_date_ini': date_from,
            'compute_date_fin': date_from
            and date_from + relativedelta(days=days - 1)})

    def test_venta_de_vacaciones_con_tope(self):
        employee = self._employee(2000.0, date(2025, 1, 1))
        vacation = self._vacation(2026, 10)
        with self.assertRaises(ValidationError):
            self._manual_line(vacation, employee, 'sale', 20)
        self._manual_line(vacation, employee, 'sale', 15)
        with self.assertRaises(ValidationError):
            self._manual_line(vacation, employee, 'sale', 1)
        small = self._employee(2000.0, date(2025, 1, 1), regime='small')
        with self.assertRaises(ValidationError):
            self._manual_line(vacation, small, 'sale', 8)
        self._manual_line(vacation, small, 'sale', 7)

    def test_fraccionamiento_de_periodos_cortos(self):
        """Los periodos de menos de 7 días no pasan de 15 en el año; un
        goce partido por meses (31-01 y 01-02…) es un solo periodo."""
        employee = self._employee(2000.0, date(2025, 1, 1))
        vacation = self._vacation(2026, 10)
        # 4 + 4 días seguidos = un periodo de 8: no es corto.
        self._manual_line(vacation, employee, 'rest', 4, date(2026, 6, 27))
        self._manual_line(vacation, employee, 'rest', 4, date(2026, 7, 1))
        self._manual_line(vacation, employee, 'rest', 5, date(2026, 3, 1))
        self._manual_line(vacation, employee, 'rest', 5, date(2026, 4, 1))
        self._manual_line(vacation, employee, 'rest', 5, date(2026, 5, 1))
        with self.assertRaises(ValidationError):
            self._manual_line(vacation, employee, 'rest', 4,
                              date(2026, 9, 1))

    # ------------------------------------------------------------------
    # 8. Indemnización por despido arbitrario
    # ------------------------------------------------------------------
    def _concept(self, regime='general', admission=date(2024, 3, 10),
                 **vals):
        employee = self._employee(2500.0, admission,
                                  end=date(2026, 10, 20), regime=regime)
        if not self.liquidation_oct:
            self.liquidation_oct = self._liquidation(2026, 10)
        liquidation = self.liquidation_oct
        return self.env['hr.liquidation.extra_concepts'].create(dict({
            'liquidation_id': liquidation.id, 'employee_id': employee.id,
            'version_id': employee.version_id.id,
            'admission_date': admission,
            'cessation_date': date(2026, 10, 20),
            'l10n_pe_cessation_reason': 'arbitrary',
            'l10n_pe_indemnity_base': 2500.0}, **vals))

    def _indem(self, concept):
        concept.action_compute_indemnity()
        return sum(concept.conceptos_lines.filtered(
            lambda line: line.name_input_id == self._rule('INDEM')
        ).mapped('amount'))

    def test_indemnizacion_por_despido_arbitrario(self):
        # Plazo indeterminado: 2 años, 7 meses y 11 días.
        years = 2 + 7 / 12 + 11 / 360
        self.assertAlmostEqual(self._indem(self._concept()),
                               1.5 * 2500 * years, delta=0.01)
        # Tope de 12 remuneraciones.
        self.assertAlmostEqual(
            self._indem(self._concept(admission=date(2010, 1, 1))),
            12 * 2500, places=2)
        # Plazo fijo: 3 meses que faltaban.
        self.assertAlmostEqual(self._indem(self._concept(
            l10n_pe_contract_kind='fixed',
            l10n_pe_planned_end=date(2027, 1, 20))), 1.5 * 2500 * 3,
            places=2)
        # Pequeña empresa: 20 remuneraciones diarias por año.
        self.assertAlmostEqual(self._indem(self._concept(regime='small')),
                               2500 / 30 * 20 * years, delta=0.01)
        # Microempresa: tope de 90 remuneraciones diarias.
        self.assertAlmostEqual(self._indem(self._concept(
            regime='micro', admission=date(2000, 1, 1))), 2500 / 30 * 90,
            places=2)
        # Otro motivo: sin indemnización.
        concept = self._concept(l10n_pe_cessation_reason='other')
        self.assertEqual(self._indem(concept), 0.0)

    # ------------------------------------------------------------------
    # 11. Récord del primer año con ingreso a mitad de mes
    # ------------------------------------------------------------------
    def test_record_primer_anio_no_prorratea_la_boleta_de_ingreso(self):
        """La boleta de marzo de un ingreso el 16-03 solo trae los días del
        contrato: cuentan enteros (antes × 16/31)."""
        employee = self._employee(2000.0, date(2025, 3, 16))
        slip = self._slip(employee, 2025, 3)
        worked = sum(slip.worked_days_line_ids.filtered(
            lambda line: line.code in ('DLAB', 'FER')
        ).mapped('number_of_days'))
        self.assertTrue(worked)
        record = self.env['hr.vacation.record']._l10n_pe_get_record(
            employee, date(2025, 3, 16), date(2026, 3, 15))
        self.assertAlmostEqual(record.worked_days, worked, places=2)

    # ------------------------------------------------------------------
    # 12. Saldo inicial fuera del aniversario y régimen por año
    # ------------------------------------------------------------------
    def test_saldo_inicial_fuera_del_aniversario(self):
        """Saldo inicial de 10 días al 30-06-2025 (ingreso 01-01-2024): los
        años siguen anclados al ingreso. El año 2025 devenga solo jul-dic
        y con el régimen de ese año (micro: 15 días/año → 7,5); 2026 ya es
        régimen general (ene-jun: 15)."""
        employee = self._employee(2000.0, date(2024, 1, 1),
                                  end=date(2026, 6, 30), regime='micro')
        employee.create_version({
            'date_version': date(2026, 1, 1),
            'l10n_pe_labor_regime': 'general'})
        Rest = self.env['hr.vacation.rest']
        Rest.create({
            'employee_id': employee.id, 'internal_motive': 'rest',
            'date_aplication': date(2025, 6, 30), 'days': 10.0,
            'days_rest': 10.0, 'company_id': self.company.id})
        Rest.get_vacation_employee(employee, False)
        movements = Rest.search([('employee_id', '=', employee.id),
                                 ('internal_motive', '=', 'normal')],
                                order='date_aplication')
        self.assertEqual(
            [(m.date_from, m.date_end, m.days) for m in movements],
            [(date(2025, 7, 1), date(2025, 12, 31), 7.5),
             (date(2026, 1, 1), date(2026, 6, 30), 15.0)])
        final = Rest.search([('employee_id', '=', employee.id),
                             ('is_saldo_final', '=', True)])
        self.assertAlmostEqual(final.days_rest, 32.5)

    # ------------------------------------------------------------------
    # 13. Un mes calendario completo de vacaciones vale 30 días
    # ------------------------------------------------------------------
    def test_febrero_completo_paga_30_dias(self):
        employee = self._employee(3000.0, date(2024, 1, 1))
        self._slip(employee, 2026, 2, done=False)
        self._suspension(employee, date(2026, 2, 1), date(2026, 2, 28))
        vacation = self._vacation(2026, 2)
        vacation.action_process()
        line = vacation.line_ids
        self.assertEqual(line.accrued_vacation, 28)
        self.assertEqual(line.paid_days, 30.0)
        self.assertAlmostEqual(line.total_vacation, 3000.0, places=2)

    # ------------------------------------------------------------------
    # Adelantos y préstamos de beneficios al exportar
    # ------------------------------------------------------------------
    def _benefit_advance_types(self, input_code='DES_BBSS'):
        Type = self.env['hr.advance.type']
        rule = self._rule(input_code)
        types = {kind: Type.create({
            'name': 'Adelanto %s' % kind, 'input_id': rule.id,
            'company_id': self.company.id})
            for kind in ('grat', 'cts', 'liqui', 'vaca')}
        self.param.write({'%s_advance_id' % kind: advance_type.id
                          for kind, advance_type in types.items()})
        return types

    def _benefit_advance(self, employee, advance_type, amount):
        return self.env['hr.advance'].create({
            'company_id': self.company.id, 'employee_id': employee.id,
            'advance_type_id': advance_type.id, 'amount': amount})

    def test_liquidacion_descuenta_adelantos_de_beneficios(self):
        """Al exportar la liquidación se descuentan los adelantos de
        gratificación y vacaciones enteros y el de CTS hasta el 50 % de la
        CTS trunca; todos por el mismo input sin pisarse."""
        types = self._benefit_advance_types()
        employee, slip, liquidation, _line = \
            self._ceased_with_pending_years()
        cts_total = sum(liquidation.cts_line_ids.filtered(
            lambda line: line.employee_id == employee).mapped('total_cts'))
        self.assertTrue(cts_total)
        grat = self._benefit_advance(employee, types['grat'], 100.0)
        vaca = self._benefit_advance(employee, types['vaca'], 200.0)
        cts = self._benefit_advance(employee, types['cts'], 100000.0)
        liquidation.action_export_to_payslips()
        cap = round(cts_total * 0.5, 2)
        self.assertEqual((grat.state, vaca.state, cts.state),
                         ('paid out', 'paid out', 'paid out'))
        self.assertAlmostEqual(cts.amount, cap, places=2)
        self.assertAlmostEqual(self._input(slip, self._rule('DES_BBSS')),
                               300.0 + cap, places=2)

    def test_vacaciones_descuentan_su_adelanto_por_otro_input(self):
        employee = self._employee(3000.0, date(2025, 1, 1))
        slip = self._slip(employee, 2026, 10, done=False)
        self._suspension(employee, date(2026, 10, 1), date(2026, 10, 15))
        vacation = self._vacation(2026, 10)
        vacation.action_process()
        # Con el input ADE_VAC (el del neto adelantado) se pisarían.
        types = self._benefit_advance_types('ADE_VAC')
        with self.assertRaises(UserError):
            vacation.action_export_to_payslips()
        types['vaca'].input_id = self._rule('DES_BBSS')
        advance = self._benefit_advance(employee, types['vaca'], 250.0)
        vacation.action_export_to_payslips()
        self.assertEqual(advance.l10n_pe_payslip_id, slip)
        self.assertAlmostEqual(self._input(slip, self._rule('DES_BBSS')),
                               250.0)
        self.assertAlmostEqual(self._input(slip, self._rule('ADE_VAC')),
                               vacation.line_ids.total)

    def test_record_cuenta_ausencias_en_dias_de_jornada(self):
        """La boleta trae las vacaciones en días naturales (con los
        descansos semanales): en el récord valen como días de jornada."""
        employee = self._employee(2000.0, date(2025, 3, 1))
        slip = self._slip(employee, 2025, 3, done=False)
        lines = slip.worked_days_line_ids
        vacation = lines.filtered(lambda line: line.code == 'DVAC')
        if not vacation:
            vacation = self.env['hr.payslip.worked_days'].create({
                'payslip_id': slip.id, 'version_id': slip.version_id.id,
                'work_entry_type_id': self._work('DVAC').id,
                'number_of_days': 0.0, 'number_of_hours': 0.0})
        others = lines - vacation
        others.write({'number_of_days': 0.0, 'number_of_hours': 0.0})
        vacation.write({'number_of_days': 31.0, 'number_of_hours': 0.0})
        slip.action_payslip_done()
        record = self.env['hr.vacation.record']._l10n_pe_get_record(
            employee, date(2025, 3, 1), date(2026, 2, 28))
        self.assertTrue(record.weekly_days)
        self.assertAlmostEqual(record.paid_leave_days, 31.0)
        self.assertAlmostEqual(record.effective_days,
                               round(31 * record.weekly_days / 7, 2),
                               places=2)

    # ------------------------------------------------------------------
    # Practicante: descanso subvencionado (Ley 28518, art. 47)
    # ------------------------------------------------------------------
    def test_practicante_devenga_15_dias_por_12_meses(self):
        """15 días por cada 12 meses de convenio cumplidos, sin récord de
        días efectivos ni truncas; sin indemnización vacacional."""
        employee = self._employee(1130.0, date(2024, 1, 1),
                                  end=date(2026, 6, 30),
                                  regime='practicante')
        Rest = self.env['hr.vacation.rest']
        Rest.get_vacation_employee(employee, False)
        movements = Rest.search([('employee_id', '=', employee.id)],
                                order='date_aplication')
        self.assertEqual(
            [(m.date_from, m.date_end, m.days) for m in movements],
            [(date(2024, 1, 1), date(2024, 12, 31), 15.0),
             (date(2025, 1, 1), date(2025, 12, 31), 15.0)])
        self.assertAlmostEqual(movements[-1].amount, 1130.0 / 2, places=2)
        self.assertFalse(self.env['hr.vacation.record'].search(
            [('employee_id', '=', employee.id)]))
        years, _advance = Rest._l10n_pe_pending_vacation(
            employee, date(2026, 6, 30))
        self.assertTrue(all(year['formative'] for year in years))
