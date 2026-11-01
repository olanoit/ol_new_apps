# -*- coding: utf-8 -*-
"""Revisión numérica de beneficios sociales (ronda 2): CTS, gratificación
y provisiones.

Mismo caso de referencia que la Fase 3 (sueldo 3 000, régimen general,
boletas Nov-2025 → Jun-2026 validadas en lotes mensuales). Cada test fija
el defecto que corrige.
"""
import warnings
from datetime import date

from odoo.tests import tagged

from . import test_audit_fixes_a as audit_a
from .test_fase3_benefits import BenefitsCaseBase


@tagged('post_install', '-at_install')
class TestRev2CtsGrat(BenefitsCaseBase):

    _slip = audit_a.TestAuditFixesA._slip
    _move_days = audit_a.TestAuditFixesA._move_days
    _new_cts = audit_a.TestAuditFixesA._new_cts
    _reopen_slips_after = audit_a.TestAuditFixesA._reopen_slips_after
    _cessation_in_july = audit_a.TestAuditFixesA._cessation_in_july

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _gratification(self, grat_type='07', year=2026, **vals):
        grati = self.env['hr.gratification'].create(dict({
            'company_id': self.company.id, 'year': year, 'type': grat_type,
            'with_bonus': False, 'payslip_run_id': self.batch_jun.id,
            'deposit_date': date(year, int(grat_type), 15),
        }, **vals))
        grati.action_process()
        line = grati.line_ids.filtered(
            lambda line: line.employee_id == self.employee)
        self.assertEqual(len(line), 1)
        return line

    def _provision(self, run):
        provision = self.env['hr.provisiones'].create({
            'company_id': self.company.id, 'payslip_run_id': run.id})
        provision.action_process()
        return provision

    def _extra_slip(self, year, month, last):
        """Boleta adicional del trabajador en el lote del mes (reintegro)."""
        slip = self.env['hr.payslip'].create({
            'name': 'Reintegro %s-%02d' % (year, month),
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(year, month, 1),
            'date_to': date(year, month, last),
            'payslip_run_id': self.runs[(year, month)].id,
        })
        slip.compute_sheet()
        return slip

    def _commission(self, slip, amount):
        """Línea de comisión (regla de comisiones del parámetro)."""
        rule = self.param.commission_sr_ids[:1]
        self.env['hr.payslip.line'].create({
            'name': rule.name, 'code': rule.code, 'slip_id': slip.id,
            'salary_rule_id': rule.id, 'version_id': slip.version_id.id,
            'employee_id': slip.employee_id.id, 'amount': amount,
            'quantity': 1.0, 'rate': 100.0, 'total': amount,
        })

    def _family_allowance(self, on_date):
        rmv = self.env['hr.rule.parameter']._l10n_pe_get_rmv(on_date)
        self.assertTrue(rmv, 'la tabla RMV debe cubrir %s' % on_date)
        return round(rmv * 0.10, 2)

    # ------------------------------------------------------------------
    # 1. Asignación familiar con la RMV de la fecha, no la fija
    # ------------------------------------------------------------------
    def test_asignacion_familiar_por_fecha(self):
        """Con ``param.rmv`` desactualizado (1 500) la gratificación y la
        provisión toman el 10 % de la RMV de la tabla en su fecha."""
        self.param.rmv = 1500.0
        for month in (4, 6):
            self._slip(2026, month).l10n_pe_family_allowance_ok = True
        line = self._gratification()
        expected = self._family_allowance(date(2026, 7, 15))
        self.assertNotEqual(expected, 150.0)
        self.assertAlmostEqual(line.household_allowance, expected, places=2)
        self.assertAlmostEqual(line.total_grat, self.wage + expected,
                               delta=0.05)
        provision = self._provision(self.batch)
        self.assertAlmostEqual(
            provision.cts_lines.asignacion,
            self._family_allowance(date(2026, 4, 30)), places=2)

    # ------------------------------------------------------------------
    # 2. Faltas de un mes que no cuenta en la gratificación
    # ------------------------------------------------------------------
    def test_faltas_de_mes_incompleto_no_se_descuentan(self):
        """Enero incompleto (15 días sin computar) con 2 faltas: enero no
        cuenta y sus faltas tampoco se descuentan (antes 2 500 − 2/180)."""
        self.env['hr.work.entry.type'].create({
            'name': 'Licencia sin goce (prueba)', 'code': 'TLSG'})
        self._move_days(2026, 1, 'TLSG', 15)
        self._move_days(2026, 1, 'FAL', 2)
        line = self._gratification()
        self.assertEqual((line.months, line.days, line.lacks), (5, 0, 0.0))
        self.assertAlmostEqual(line.total_grat, self.wage * 5 / 6,
                               delta=0.05)

    def test_faltas_de_mes_completo_si_se_descuentan(self):
        """Decisión 6: en un mes que cuenta, 1/180 por día de falta."""
        self._move_days(2026, 3, 'FAL', 3)
        line = self._gratification()
        self.assertEqual((line.months, line.lacks), (6, 3.0))
        self.assertAlmostEqual(line.total_grat, self.wage - 3 * self.wage / 180,
                               delta=0.05)

    # ------------------------------------------------------------------
    # 3. Boletas canceladas fuera de promedios, meses e historial
    # ------------------------------------------------------------------
    def test_boletas_canceladas_no_cuentan(self):
        """Tres reintegros con comisión, anulados: no promedian."""
        for month, last in ((1, 31), (2, 28), (3, 31)):
            slip = self._extra_slip(2026, month, last)
            self._commission(slip, 600.0)
            slip.state = 'cancel'
        line = self._gratification()
        self.assertEqual(line.commission, 0.0)
        self.assertAlmostEqual(line.total_grat, self.wage, delta=0.05)
        history = self.env['hr.main.parameter'].get_salary_history(
            self.employee, self.company, date(2026, 7, 15))
        self.assertFalse(sum(bucket['commission']
                             for bucket in history.values()))

    def test_boletas_canceladas_vigentes_si_promedian(self):
        """Control: los mismos reintegros sin anular sí promedian."""
        for month, last in ((1, 31), (2, 28), (3, 31)):
            self._commission(self._extra_slip(2026, month, last), 600.0)
        line = self._gratification()
        self.assertAlmostEqual(line.commission, 300.0, places=2)

    # ------------------------------------------------------------------
    # 4. Bonificación Ley 30334 sin seguro social en la versión
    # ------------------------------------------------------------------
    def test_bonificacion_sin_seguro_usa_tasa_essalud(self):
        self.employee.version_id.social_insurance_id = False
        rate = float(self.env['hr.rule.parameter']._get_parameter_from_code(
            'l10n_pe_essalud_rate', date(2026, 7, 15)))
        self.assertTrue(rate)
        line = self._gratification(with_bonus=True)
        expected = round(self.wage * rate / 100, 2)
        self.assertAlmostEqual(line.bonus_essalud, expected, places=2)
        line.action_compute()
        self.assertAlmostEqual(line.bonus_essalud, expected, places=2)
        provision = self._provision(self.batch)
        self.assertAlmostEqual(provision.grati_lines.tasa, rate, places=2)
        self.assertAlmostEqual(provision.grati_lines.boni_grati,
                               round(self.wage / 6 * rate / 100, 2),
                               places=2)

    # ------------------------------------------------------------------
    # 5. Gratificación de julio con la remuneración vigente al pagarla
    # ------------------------------------------------------------------
    def test_gratificacion_julio_con_aumento_desde_julio(self):
        """Aumento a 3 500 desde el 01/07: la gratificación de Fiestas
        Patrias (pago el 15/07) se calcula con 3 500."""
        self.employee.create_version({
            'date_version': date(2026, 7, 1), 'wage': 3500.0})
        line = self._gratification()
        self.assertEqual(line.wage, 3500.0)
        self.assertAlmostEqual(line.total_grat, 3500.0, delta=0.05)

    # ------------------------------------------------------------------
    # 6. Provisiones: días calendario, faltas y sexto deducido
    # ------------------------------------------------------------------
    def test_provision_mes_de_ingreso_dias_calendario(self):
        """Ingreso el 15/02: 14 días (antes 16); ingreso el día 31: 1 día
        (antes 0)."""
        for start, run_key, days in ((date(2026, 2, 15), (2026, 2), 14),
                                     (date(2026, 3, 31), (2026, 3), 1)):
            employee = self.env['hr.employee'].create({
                'names': 'Ingreso %s' % start, 'last_name': 'Prueba',
                'm_last_name': 'Provisión', 'company_id': self.company.id,
                'date_version': start, 'contract_date_start': start,
                'wage': 3000.0,
                'structure_type_id': self.structure.type_id.id,
            })
            employee.version_id.membership_id = self.afp
            run = self.runs[run_key]
            self.env['hr.payslip'].create({
                'name': 'Ingreso', 'employee_id': employee.id,
                'struct_id': self.structure.id,
                'date_from': run.date_start, 'date_to': run.date_end,
                'payslip_run_id': run.id,
            }).compute_sheet()
            provision = self.env['hr.provisiones'].search([
                ('payslip_run_id', '=', run.id)]) or self._provision(run)
            provision.action_process()
            cts_line = provision.cts_lines.filtered(
                lambda line: line.employee_id == employee)
            self.assertAlmostEqual(cts_line.provisiones_cts,
                                   round(3000.0 / 12 / 30 * days, 2),
                                   places=2)

    def test_provision_descuenta_faltas(self):
        self._move_days(2026, 4, 'FAL', 3)
        provision = self._provision(self.batch)
        self.assertEqual(provision.cts_lines.faltas, 3.0)
        self.assertAlmostEqual(provision.cts_lines.provisiones_cts,
                               round(self.wage / 12 / 30 * 27, 2), places=2)
        self.assertAlmostEqual(provision.grati_lines.provisiones_grati,
                               round(self.wage / 6 / 30 * 27, 2), places=2)
        self.assertAlmostEqual(provision.vaca_lines.provisiones_vaca,
                               round(self.wage / 12 / 30 * 27, 2), places=2)

    def test_provision_sexto_sin_elegir_gratificacion(self):
        """Lote de abril sin ``gratificacion_id``: el sexto sale de la
        gratificación de Navidad del año anterior."""
        grati = self.env['hr.gratification'].create({
            'company_id': self.company.id, 'year': 2025, 'type': '12',
            'payslip_run_id': self.runs[(2025, 12)].id,
            'deposit_date': date(2025, 12, 15),
        })
        self.env['hr.gratification.line'].create({
            'gratification_id': grati.id, 'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id, 'total_grat': 3000.0,
        })
        provision = self._provision(self.batch)
        self.assertFalse(provision.gratificacion_id)
        self.assertAlmostEqual(provision.cts_lines.un_sexto_grati, 500.0,
                               places=2)

    # ------------------------------------------------------------------
    # 7. Tipos de día por defecto
    # ------------------------------------------------------------------
    def test_tipos_de_dia_por_defecto(self):
        company = self.env['res.company'].create({
            'name': 'PE nueva', 'country_id': self.env.ref('base.pe').id})
        param = self.env['hr.main.parameter'].get_main_parameter(company)
        self.assertEqual(
            set(param.working_wd_ids.mapped('code')),
            {'DLAB', 'DOM', 'DVAC', 'LCGH', 'DPAT', 'SMAR'})
        self.assertEqual(param.lack_wd_ids.mapped('code'), ['FAL'])
        self.assertEqual(set(param.medical_rest_wd_ids.mapped('code')),
                         {'DMED', 'SENF'})
        # Migración: solo se llenan los vacíos.
        dlab = param.working_wd_ids.filtered(lambda wet: wet.code == 'DLAB')
        param.write({'working_wd_ids': [(6, 0, dlab.ids)],
                     'lack_wd_ids': [(5, 0, 0)]})
        param._l10n_pe_set_benefit_wd_defaults()
        self.assertEqual(param.working_wd_ids, dlab)
        self.assertEqual(param.lack_wd_ids.mapped('code'), ['FAL'])

    def test_mes_de_vacaciones_cuenta_con_los_valores_por_defecto(self):
        """15 días de vacaciones en enero: con los tipos por defecto el
        mes cuenta (antes, sin DVAC, se perdía un sexto)."""
        self._move_days(2026, 1, 'DVAC', 15)
        self.param.write({'working_wd_ids': [(5, 0, 0)],
                          'lack_wd_ids': [(5, 0, 0)],
                          'medical_rest_wd_ids': [(5, 0, 0)]})
        self.param._l10n_pe_set_benefit_wd_defaults()
        line = self._gratification()
        self.assertEqual(line.months, 6)

    # ------------------------------------------------------------------
    # 8. Decisión 2: comisión como remuneración principal
    # ------------------------------------------------------------------
    def test_comisionista_promedia_sin_regla_de_3(self):
        """Comisiones de 4 000 y 5 000 en 2 de 6 meses: sin el indicador
        no promedian; con él, 9 000 / 6 = 1 500."""
        self._commission(self._extra_slip(2026, 2, 28), 4000.0)
        self._commission(self._extra_slip(2026, 5, 31), 5000.0)
        line = self._gratification()
        self.assertEqual(line.commission, 0.0)
        line.gratification_id.unlink()
        self.employee.version_id.l10n_pe_commission_principal = True
        line = self._gratification()
        self.assertAlmostEqual(line.commission, 1500.0, places=2)
        self.assertAlmostEqual(line.total_grat, self.wage + 1500.0,
                               delta=0.05)

    # ------------------------------------------------------------------
    # 9. Decisión 7: un solo criterio de promedios en las truncas
    # ------------------------------------------------------------------
    def test_ventana_de_truncas(self):
        Param = self.env['hr.main.parameter']
        self.assertEqual(Param._l10n_pe_truncated_window(date(2026, 10, 20)),
                         (date(2026, 4, 1), date(2026, 9, 30)))
        self.assertEqual(Param._l10n_pe_truncated_window(date(2026, 10, 31)),
                         (date(2026, 5, 1), date(2026, 10, 31)))

    def test_truncas_mismo_promedio_en_cts_y_gratificacion(self):
        """Cese el 10/07 con comisiones en ene, feb y mar: la ventana es
        ene-jun para la gratificación y la CTS truncas (antes la CTS
        may-jul promediaba 0)."""
        for month, last in ((1, 31), (2, 28), (3, 31)):
            self._commission(self._extra_slip(2026, month, last), 600.0)
        liquidation = self._cessation_in_july()
        liquidation.action_process()
        self.assertTrue(liquidation.gratification_line_ids)
        self.assertTrue(liquidation.cts_line_ids)
        for line in list(liquidation.gratification_line_ids) \
                + list(liquidation.cts_line_ids):
            self.assertAlmostEqual(line.commission, 300.0, places=2)

    # ------------------------------------------------------------------
    # 10. union() de Odoo 20 sin aviso de obsolescencia
    # ------------------------------------------------------------------
    def test_exportar_sin_aviso_de_union(self):
        self._slip(2026, 4).write({'state': 'draft'})
        cts = self._new_cts()
        cts.action_process()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            cts.action_export_to_payslips()
        self.assertFalse([warning for warning in caught
                          if 'union' in str(warning.message)])

    # ------------------------------------------------------------------
    # Adelantos de gratificación y CTS al exportar
    # ------------------------------------------------------------------
    def _benefit_advance(self, field_name, rule_code, amount, on_date):
        advance_type = self.env['hr.advance.type'].create({
            'name': 'Adelanto %s' % field_name,
            'input_id': self.env.ref('al_hr_pe.salary_rule_%s' % rule_code).id,
            'company_id': self.company.id})
        self.param[field_name] = advance_type
        return self.env['hr.advance'].create({
            'company_id': self.company.id,
            'employee_id': self.employee.id,
            'advance_type_id': advance_type.id,
            'amount': amount, 'date': on_date, 'discount_date': on_date,
        })

    def test_exportar_gratificacion_descuenta_adelanto(self):
        advance = self._benefit_advance(
            'grat_advance_id', 'ADE_GRA', 400.0, date(2026, 6, 10))
        slip = self._slip(2026, 6)
        slip.write({'state': 'draft'})
        line = self._gratification()
        line.gratification_id.action_export_to_payslips()
        self.assertEqual(advance.state, 'paid out')
        self.assertEqual(advance.l10n_pe_payslip_id, slip)

    def test_exportar_cts_descuenta_adelanto_con_tope(self):
        """Adelanto contra la CTS mayor que el 50 % del depósito: se
        descuenta solo hasta el tope."""
        advance = self._benefit_advance(
            'cts_advance_id', 'ADE_CTS', 5000.0, date(2026, 4, 10))
        slip = self._slip(2026, 4)
        slip.write({'state': 'draft'})
        cts = self._new_cts()
        cts.action_process()
        line = cts.line_ids.filtered(
            lambda line: line.employee_id == self.employee)
        cts.action_export_to_payslips()
        discounted = self.env['hr.advance'].search([
            ('employee_id', '=', self.employee.id),
            ('l10n_pe_payslip_id', '=', slip.id)])
        self.assertTrue(discounted)
        self.assertAlmostEqual(sum(discounted.mapped('amount')),
                               round(line.total_cts * 0.5, 2), places=2)
        # El resto del adelanto queda pendiente para el siguiente depósito.
        self.assertTrue(self.env['hr.advance'].search([
            ('employee_id', '=', self.employee.id),
            ('state', '=', 'not payed')]))
        self.assertTrue(advance)

    # ------------------------------------------------------------------
    # Practicantes: media subvención cada 6 meses (Ley 28518, art. 47)
    # ------------------------------------------------------------------
    def _trainee(self, start, subsidy=1200.0):
        employee = self.env['hr.employee'].create({
            'names': 'Practicante %s' % start, 'last_name': 'Prueba',
            'm_last_name': 'Ley 28518', 'company_id': self.company.id,
            'date_version': start, 'contract_date_start': start,
            'wage': subsidy, 'structure_type_id': self.structure.type_id.id,
        })
        employee.version_id.write({
            'membership_id': self.afp.id,
            'l10n_pe_labor_regime': 'practicante'})
        self.env['hr.payslip'].create({
            'name': 'Practicante', 'employee_id': employee.id,
            'struct_id': self.structure.id,
            'date_from': self.batch_jun.date_start,
            'date_to': self.batch_jun.date_end,
            'payslip_run_id': self.batch_jun.id,
        }).compute_sheet()
        return employee

    def test_practicante_media_subvencion_a_los_6_meses(self):
        """Convenio desde el 01/01: cumple 6 meses el 30/06 y recibe media
        subvención (600) sin bonificación. Desde el 01/02 los cumple el
        31/07: nada en Fiestas Patrias aunque esté en planilla en julio."""
        complete = self._trainee(date(2026, 1, 1))
        incomplete = self._trainee(date(2026, 2, 1))
        self.batch_jun.slip_ids.write({'state': 'draft'})
        grati = self.env['hr.gratification'].create({
            'company_id': self.company.id, 'year': 2026, 'type': '07',
            'with_bonus': True, 'payslip_run_id': self.batch_jun.id,
            'deposit_date': date(2026, 7, 15),
        })
        grati.action_process()
        line = grati.line_ids.filtered(
            lambda line: line.employee_id == complete)
        self.assertEqual(len(line), 1)
        self.assertEqual((line.total_grat, line.bonus_essalud, line.total),
                         (600.0, 0.0, 600.0))
        self.assertFalse(grati.line_ids.filtered(
            lambda line: line.employee_id == incomplete))
        line.action_compute()
        self.assertEqual((line.total_grat, line.bonus_essalud), (600.0, 0.0))
        # Exportación por el input propio de la media subvención.
        own_input = self.env.ref('al_hr_pe.salary_rule_INDEM').copy(
            {'name': 'Media subvención', 'code': 'TSUBV'})
        self.param.trainee_subsidy_input_id = own_input
        grati.action_export_to_payslips()
        slip = self.batch_jun.slip_ids.filtered(
            lambda slip: slip.employee_id == complete)
        exported = slip.input_line_ids.filtered(
            lambda inp: inp.salary_rule_id == own_input)
        self.assertEqual(exported.amount, 600.0)

    # ------------------------------------------------------------------
    # CTS trunca: al menos un mes de servicios
    # ------------------------------------------------------------------
    def test_cts_trunca_exige_un_mes_de_servicios(self):
        """Ingreso el 25/06 y cese el 05/07 (11 días): sin CTS trunca; el
        trabajador de referencia, cesado el 10/07, sí la tiene."""
        liquidation = self._cessation_in_july()
        short = self.env['hr.employee'].create({
            'names': 'Corto', 'last_name': 'Prueba', 'm_last_name': 'CTS',
            'company_id': self.company.id,
            'date_version': date(2026, 6, 25),
            'contract_date_start': date(2026, 6, 25),
            'contract_date_end': date(2026, 7, 5),
            'wage': 3000.0, 'structure_type_id': self.structure.type_id.id,
        })
        short.version_id.write({
            'membership_id': self.afp.id,
            'situation_id': self.env.ref('al_hr_pe.situation_0').id})
        for run in (self.batch_jun, liquidation.payslip_run_id):
            self.env['hr.payslip'].create({
                'name': 'Corto', 'employee_id': short.id,
                'struct_id': self.structure.id,
                'date_from': run.date_start, 'date_to': run.date_end,
                'payslip_run_id': run.id,
            }).compute_sheet()
        liquidation.action_process()
        self.assertTrue(liquidation.cts_line_ids.filtered(
            lambda line: line.employee_id == self.employee))
        self.assertFalse(liquidation.cts_line_ids.filtered(
            lambda line: line.employee_id == short))
