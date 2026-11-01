# -*- coding: utf-8 -*-
"""Revisión de beneficios sociales, ronda 2 (01/11/2026): núcleo.

* Ausencias en días naturales: los sábados y domingos dentro de una
  ausencia son de la ausencia, no días de descanso pagados en el básico.
* BAS: el sueldo completo solo con una boleta del mes calendario entero.
* Decisión 3: la indemnización vacacional (INDVAC) no es renta de 5ta.
* Decisión 4: la proyección de 5ta (PIAQ) es solo la remuneración ordinaria.
* Neto negativo: aviso nativo de la boleta, sin bloquear.

Cada test falla con el código anterior a su corrección.
"""
from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRev2Core(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'PE Ronda 2 SAC',
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids,
            tz='America/Lima'))
        cls.env.user.company_ids |= cls.company
        cls.env.user.group_ids |= cls.env.ref(
            'hr_payroll.group_hr_payroll_manager')
        cls.env['hr.main.parameter'].create({
            'company_id': cls.company.id, 'rmv': 1130.0})
        cls.onp = cls.env['hr.membership'].search(
            [('is_afp', '=', False), ('company_id', '=', False),
             ('retirement_fund', '>', 0)], limit=1)
        cls.structure = cls.env.ref('al_hr_pe.base_structure')
        # Jornada de lunes a viernes (la de por defecto de Odoo).
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'L-V 8 h ronda 2', 'company_id': cls.company.id})
        cls.employee = cls._create_employee('Rosa')

    @classmethod
    def _create_employee(cls, name, wage=3000.0, start=date(2025, 1, 1),
                         end=False):
        employee = cls.env['hr.employee'].create({
            'names': name, 'last_name': 'Huamán', 'm_last_name': 'Ríos',
            'company_id': cls.company.id,
            'date_version': start,
            'contract_date_start': start,
            'contract_date_end': end,
            'wage': wage,
            'structure_type_id': cls.structure.type_id.id,
            'resource_calendar_id': cls.calendar.id,
        })
        employee.version_id.write({
            'membership_id': cls.onp.id,
            'resource_calendar_id': cls.calendar.id,
        })
        return employee

    def _slip(self, employee=None, date_from=date(2026, 3, 1),
              date_to=date(2026, 3, 31), inputs=None, family=False):
        slip = self.env['hr.payslip'].create({
            'name': 'Boleta ronda 2',
            'employee_id': (employee or self.employee).id,
            'struct_id': self.structure.id,
            'date_from': date_from,
            'date_to': date_to,
        })
        if family:
            slip.l10n_pe_family_allowance_ok = True
        for xmlid, amount in (inputs or {}).items():
            slip.write({'input_line_ids': [(0, 0, {
                'salary_rule_id': self.env.ref('al_hr_pe.%s' % xmlid).id,
                'amount': amount})]})
        slip.compute_sheet()
        return slip

    def _leave(self, code, date_from, date_to, employee=None):
        work_entry_type = self.env['hr.work.entry.type'].search(
            [('code', '=', code)], limit=1)
        work_entry_type.requires_allocation = False
        leave = self.env['hr.leave'].with_context(
            leave_skip_state_check=True).create({
                'name': code,
                'employee_id': (employee or self.employee).id,
                'work_entry_type_id': work_entry_type.id,
                'request_date_from': date_from,
                'request_date_to': date_to,
            })
        if leave.state != 'validate':
            leave._action_validate(check_state=False)
        return leave

    def _line(self, slip, code):
        return sum(slip.line_ids.filtered(lambda l: l.code == code).mapped('total'))

    def _days(self, slip, code):
        return sum(slip.worked_days_line_ids.filtered(
            lambda l: l.code == code).mapped('number_of_days'))

    # ------------------------------------------------------------------
    # D1. Ausencias que cruzan sábados y domingos: días naturales
    # ------------------------------------------------------------------
    def test_maternity_whole_month(self):
        """Maternidad todo marzo: los 31 días son de subsidio. Sin
        remuneración no hay básico, ONP, EsSalud ni asignación familiar
        (antes: 22 días SMAR + 9 DOM, BAS 800, ONP 104 y EsSalud 101,70)."""
        self._leave('SMAR', date(2026, 3, 1), date(2026, 6, 6))
        slip = self._slip(family=True)
        self.assertEqual(self._days(slip, 'SMAR'), 31)
        self.assertEqual(self._days(slip, 'DOM'), 0)
        self.assertEqual(self._days(slip, 'DLAB'), 0)
        for code in ('BAS', 'BAS_M', 'ONP', 'ESSALUD', 'AF'):
            self.assertFalse(self._line(slip, code), code)

    def test_maternity_from_the_tenth(self):
        """Maternidad desde el 10/04: 21 días de subsidio y 9 de sueldo
        (antes: 15 días SMAR + 15 DOM, básico 1 500)."""
        self._leave('SMAR', date(2026, 4, 10), date(2026, 7, 16))
        slip = self._slip(date_from=date(2026, 4, 1), date_to=date(2026, 4, 30))
        self.assertEqual(self._days(slip, 'SMAR'), 21)
        self.assertEqual(self._days(slip, 'DLAB') + self._days(slip, 'DOM'), 9)
        self.assertAlmostEqual(self._line(slip, 'BAS_M'), 900.0)

    def test_unpaid_leave_counts_the_weekend(self):
        """Licencia sin goce del 09 al 18/02 (10 días naturales, 8
        laborables): el básico del mes es 2 000 de 3 000 (antes 2 200)."""
        self._leave('LSGH', date(2026, 2, 9), date(2026, 2, 18))
        slip = self._slip(date_from=date(2026, 2, 1), date_to=date(2026, 2, 28))
        self.assertEqual(self._days(slip, 'LSGH'), 10)
        self.assertEqual(
            self._days(slip, 'DLAB') + self._days(slip, 'DOM')
            + self._days(slip, 'LSGH'), 28)
        self.assertAlmostEqual(self._line(slip, 'LSGH'), 1000.0)
        self.assertAlmostEqual(self._line(slip, 'BAS_M'), 2000.0)

    def test_medical_rest_counts_the_weekend(self):
        """Descanso médico del viernes 06 al lunes 09/03: 4 días de
        descanso médico; el mes sigue pagando el sueldo completo."""
        self._leave('DMED', date(2026, 3, 6), date(2026, 3, 9))
        slip = self._slip()
        self.assertEqual(self._days(slip, 'DMED'), 4)
        self.assertEqual(
            self._days(slip, 'DLAB') + self._days(slip, 'DOM')
            + self._days(slip, 'DMED'), 31)
        self.assertAlmostEqual(self._line(slip, 'BAS_M'), 3000.0)

    # ------------------------------------------------------------------
    # BAS: la boleta parcial paga sus días
    # ------------------------------------------------------------------
    def test_termination_slip_pays_its_days(self):
        """Cese el 20/09 con sueldo 7 000: 20 × 7 000 / 30 = 4 666,67, en la
        boleta del 1 al 20 (antes, el sueldo completo) y en la del mes."""
        employee = self._create_employee(
            'Lucía', wage=7000.0, end=date(2026, 9, 20))
        for date_to in (date(2026, 9, 20), date(2026, 9, 30)):
            slip = self._slip(employee, date(2026, 9, 1), date_to)
            self.assertAlmostEqual(self._line(slip, 'BAS'), 4666.67, msg=date_to)

    def test_raise_mid_month_two_slips(self):
        """Aumento de 6 000 a 9 000 desde el 16/03 con una boleta por
        versión: 15 × 200 + 16 × 300 = 7 800 (antes, 6 000 + 4 800)."""
        employee = self._create_employee('Elena', wage=6000.0)
        employee.create_version({
            'date_version': date(2026, 3, 16), 'wage': 9000.0})
        first = self._slip(employee, date(2026, 3, 1), date(2026, 3, 15))
        second = self._slip(employee, date(2026, 3, 16), date(2026, 3, 31))
        self.assertAlmostEqual(self._line(first, 'BAS'), 3000.0)
        self.assertAlmostEqual(self._line(second, 'BAS'), 4800.0)

    def test_full_month_keeps_the_wage(self):
        """Mes completo de 31 o 28 días: el sueldo, sin prorrateo."""
        for date_from, date_to in ((date(2026, 3, 1), date(2026, 3, 31)),
                                   (date(2026, 2, 1), date(2026, 2, 28))):
            slip = self._slip(date_from=date_from, date_to=date_to)
            self.assertAlmostEqual(self._line(slip, 'BAS'), 3000.0)

    # ------------------------------------------------------------------
    # Decisiones 3 y 4: renta de 5ta
    # ------------------------------------------------------------------
    def test_vacation_indemnity_not_fifth_category(self):
        """La indemnización vacacional llega al neto pero no a la renta
        extraordinaria de 5ta (REAQ)."""
        slip = self._slip(inputs={'salary_rule_INDVAC': 900.0})
        self.assertAlmostEqual(self._line(slip, 'INDVAC'), 900.0)
        self.assertFalse(self._line(slip, 'REAQ'))

    def test_projection_only_ordinary_pay(self):
        """PIAQ proyecta sueldo + asignación familiar: sin las horas extra,
        comisiones ni bonos del mes (que sí van en la renta del mes)."""
        slip = self._slip(family=True, inputs={
            'salary_rule_COMI': 500.0, 'salary_rule_BONR': 300.0})
        self.assertAlmostEqual(self._line(slip, 'COMI'), 500.0)
        self.assertAlmostEqual(
            self._line(slip, 'PIAQ'), 3000.0 + self._line(slip, 'AF'))
        self.assertAlmostEqual(
            self._line(slip, 'ROAQ'),
            self._line(slip, 'BAS_M') + self._line(slip, 'AF') + 800.0)

    def test_formulas_are_synced(self):
        """Bases instaladas: BAS, REAQ y PIAQ (noupdate) con la fórmula
        anterior pasan a la nueva al actualizar."""
        from odoo.addons.al_hr_pe.models.l10n_pe_rule_formulas import (
            L10N_PE_AUDIT_RULES)
        for xmlid in ('salary_rule_BAS', 'salary_rule_REAQ', 'salary_rule_PIAQ'):
            rule = self.env.ref('al_hr_pe.%s' % xmlid)
            new_code = rule.amount_python_compute
            old = L10N_PE_AUDIT_RULES[xmlid][0]
            rule.amount_python_compute = old[-1] if isinstance(old, tuple) else old
            self.env['hr.salary.rule']._l10n_pe_sync_formulas()
            self.assertEqual(rule.amount_python_compute.strip(), new_code.strip())

    # ------------------------------------------------------------------
    # Neto negativo: aviso, no bloqueo
    # ------------------------------------------------------------------
    def test_negative_net_warns(self):
        """Un adelanto mayor que el sueldo deja el NETO negativo: la boleta
        lo muestra con el aviso nativo «neto cero o negativo» (sin
        bloquear) y al validarla queda marcado el neto negativo a
        reportar."""
        slip = self._slip(inputs={'salary_rule_ADELANTO': 5000.0})
        self.assertLess(self._line(slip, 'NETO'), 0)
        self.assertAlmostEqual(slip.net_wage, self._line(slip, 'NETO'))
        slip.with_context(hr_payroll_force_compute_issue=True)._compute_issues()
        warning = self.env.ref(
            'hr_payroll.hr_payroll_warning_payslip_zero_or_negative_net')
        self.assertIn(warning._get_warning_issue()['message'],
                      [issue['message'] for issue in slip.issues.values()])
        self.assertFalse(slip.error_count)
        slip.action_payslip_done()
        self.assertTrue(slip.has_negative_net_to_report)
