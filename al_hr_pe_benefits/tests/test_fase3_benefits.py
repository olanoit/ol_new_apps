# -*- coding: utf-8 -*-
"""Fase 3: paridad de CTS, gratificación y récord vacacional.

Caso de referencia: trabajador régimen general, sueldo 3 000 estable
todo el semestre, sin variables ni hijos ni faltas. Expectativas
derivadas de las fórmulas legales, no números mágicos:
- CTS semestral completa = computable/12 × 6 = computable/2
- Gratificación completa = computable/6 × 6 = computable (+ bono 9 %)
- Récord vacacional: 2.5 días/mes.
"""
from datetime import date

from odoo.tests import TransactionCase, tagged


class BenefitsCaseBase(TransactionCase):
    """Setup compartido (compañía PE, parámetros, empleado con boletas
    Nov-2025 → Jun-2026 en lotes mensuales) para las fases 3 y 4."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'PE BBSS SAC', 'country_id': cls.env.ref('base.pe').id})
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.env.user.company_ids |= cls.company
        cls.env.user.group_ids |= cls.env.ref(
            'hr_payroll.group_hr_payroll_manager')
        cls.structure = cls.env.ref('al_hr_pe.base_structure')
        Rule = cls.env['hr.salary.rule']
        cls.param = cls.env['hr.main.parameter'].create({
            'company_id': cls.company.id, 'rmv': 1130.0,
            # Configuración del motor de BBSS (reglas/inputs de la
            # estructura BASE portada)
            'basic_sr_id': Rule.search([('code', '=', 'BAS')], limit=1).id,
            'household_allowance_sr_id':
                Rule.search([('code', '=', 'AF')], limit=1).id,
            'extra_hours_sr_id':
                Rule.search([('code', '=', 'HE25')], limit=1).id,
            # Reglas de variables en estructura aparte: el caso de
            # referencia NO tiene comisiones/bonos (promedios = 0)
            'commission_sr_ids': [(6, 0, cls._dummy_rule('TCOMIS').ids)],
            'bonus_sr_ids': [(6, 0, cls._dummy_rule('TBON').ids)],
            'cts_input_id': cls.env['hr.payslip.input.type'].search(
                [], limit=1).id,
            'gratification_input_id':
                cls.env['hr.payslip.input.type'].search([], limit=1).id,
            'bonus_nine_input_id':
                cls.env['hr.payslip.input.type'].search([], limit=1).id,
            'lack_wd_ids': [(6, 0, cls.env['hr.work.entry.type'].search(
                [('code', '=', 'FAL')]).ids)],
            'working_wd_ids': [(6, 0, cls.env['hr.work.entry.type'].search(
                [('code', 'in', ('DLAB', 'DOM'))]).ids)],
        })
        cls.afp = cls.env['hr.membership'].search(
            [('is_afp', '=', True), ('company_id', '=', False)], limit=1)
        cls.wage = 3000.0
        cls.employee = cls.env['hr.employee'].create({
            'names': 'Rosa', 'last_name': 'Huamán', 'm_last_name': 'Cruz',
            'company_id': cls.company.id,
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'wage': cls.wage,
            'structure_type_id': cls.structure.type_id.id,
        })
        cls.employee.version_id.membership_id = cls.afp
        # Periodos 2025-2026 (el motor exige el periodo de cierre)
        for year in (2025, 2026):
            cls.env['hr.period.generator'].create({
                'year': year, 'company_id': cls.company.id,
            }).action_generate()
        # Boletas Nov-2025 → Jun-2026, cada una en su lote mensual con
        # periodo (el motor selecciona empleados vía lote del periodo y
        # cuenta meses por los lotes del semestre).
        cls.runs = {}
        for year, month, last in [(2025, 11, 30), (2025, 12, 31),
                                  (2026, 1, 31), (2026, 2, 28),
                                  (2026, 3, 31), (2026, 4, 30),
                                  (2026, 5, 31), (2026, 6, 30)]:
            periodo = cls.env['hr.period'].search([
                ('code', '=', '%04d%02d' % (year, month)),
                ('company_id', '=', cls.company.id)], limit=1)
            run = cls.env['hr.payslip.run'].create({
                'name': 'Lote %s-%02d' % (year, month),
                'date_start': date(year, month, 1),
                'date_end': date(year, month, last),
                'company_id': cls.company.id,
                'periodo_id': periodo.id,
            })
            slip = cls.env['hr.payslip'].create({
                'name': 'Boleta %s-%02d' % (year, month),
                'employee_id': cls.employee.id,
                'struct_id': cls.structure.id,
                'date_from': date(year, month, 1),
                'date_to': date(year, month, last),
                'payslip_run_id': run.id,
            })
            slip.compute_sheet()
            slip.action_payslip_done()
            cls.runs[(year, month)] = run
        cls.batch = cls.runs[(2026, 4)]
        cls.batch_jun = cls.runs[(2026, 6)]

    @classmethod
    def _dummy_rule(cls, code):
        struct = cls.env['hr.payroll.structure'].create({
            'name': 'Aux %s' % code,
            'type_id': cls.structure.type_id.id,
        })
        return cls.env['hr.salary.rule'].create({
            'name': code, 'code': code,
            'category_id': cls.env.ref('al_hr_pe.ING').id,
            'struct_id': struct.id, 'sequence': 5,
            'amount_select': 'fix', 'amount_fix': 0.0,
        })


@tagged('post_install', '-at_install')
class TestFase3Benefits(BenefitsCaseBase):

    def test_cts_semestre_completo(self):
        cts = self.env['hr.cts'].create({
            'company_id': self.company.id,
            'year': 2026,
            'type': '05',  # semestre Nov-Abr
            'payslip_run_id': self.batch.id,
            'deposit_date': date(2026, 5, 15),
        })
        cts.get_cts()
        line = cts.line_ids.filtered(
            lambda l: l.employee_id == self.employee)
        self.assertTrue(line, 'CTS sin línea del empleado')
        # Sin grati previa ni variables: computable = sueldo
        self.assertAlmostEqual(line.computable_remuneration, self.wage,
                               places=1)
        self.assertEqual(line.months, 6)
        self.assertEqual(line.days, 0)
        # 6 meses → computable/12 × 6 = computable / 2
        self.assertAlmostEqual(line.total_cts, self.wage / 2, delta=1.0)

    def test_gratification_con_bono(self):
        essalud = self.env['hr.social.insurance'].search(
            [('name', 'ilike', 'salud'), ('company_id', '=', False)],
            limit=1)
        if essalud:
            self.employee.version_id.social_insurance_id = essalud
        grati = self.env['hr.gratification'].create({
            'company_id': self.company.id,
            'year': 2026,
            'type': '07',  # Fiestas Patrias (Ene-Jun)
            'with_bonus': True,
            'payslip_run_id': self.batch_jun.id,
            'deposit_date': date(2026, 7, 15),
        })
        grati.get_gratification()
        line = grati.line_ids.filtered(
            lambda l: l.employee_id == self.employee)
        self.assertTrue(line, 'Gratificación sin línea del empleado')
        self.assertAlmostEqual(
            line.computable_remuneration, self.wage, places=1)
        # Semestre Ene-Jun completo → 6/6
        expected = round(self.wage / 6 * line.months, 1)
        self.assertAlmostEqual(line.total_grat, expected, delta=2.0)
        if essalud and line.total_grat:
            self.assertAlmostEqual(
                line.bonus_essalud,
                round(line.total_grat * essalud.percent / 100, 1),
                delta=1.0)

    def test_vacation_rest_devengo(self):
        Rest = self.env['hr.vacation.rest']
        Rest.get_vacation_employee(self.employee, False)
        rests = Rest.search([('employee_id', '=', self.employee.id)])
        self.assertTrue(rests, 'Sin récord vacacional')
        # Ingreso 2025-01-01: primer año vacacional completo = 30 días
        full_year = rests.filtered(
            lambda r: r.date_from == date(2025, 1, 1))
        if full_year:
            self.assertAlmostEqual(full_year[0].days, 30.0, delta=0.1)

    def test_multicompany_isolation(self):
        """El recálculo vacacional no borra saldos de otra compañía."""
        other = self.env['res.company'].create({
            'name': 'PE Otra SAC', 'country_id': self.env.ref('base.pe').id})
        foreign = self.env['hr.vacation.rest'].sudo().create({
            'employee_id': self.env['hr.employee'].sudo().create({
                'name': 'Ajeno', 'company_id': other.id}).id,
            'internal_motive': 'normal',
            'date_from': date(2025, 1, 1), 'date_end': date(2025, 12, 31),
            'days': 30, 'company_id': other.id,
        })
        self.env['hr.vacation.rest'].get_vacation_employee(
            self.employee, False)
        self.assertTrue(foreign.exists(),
                        'El recálculo borró saldos de otra compañía')
