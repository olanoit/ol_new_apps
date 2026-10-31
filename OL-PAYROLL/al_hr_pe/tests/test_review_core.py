# -*- coding: utf-8 -*-
"""Revisión del núcleo de planillas en Odoo 20 (31/10/2026).

Cada test reproduce un hallazgo de la revisión (A1, A2…) y falla con el
código anterior a su corrección.
"""
from datetime import date
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReviewCore(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'PE Revisión SAC',
            'country_id': cls.env.ref('base.pe').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.env.user.company_ids |= cls.company
        cls.env.user.group_ids |= cls.env.ref(
            'hr_payroll.group_hr_payroll_manager')
        cls.env['hr.main.parameter'].create({
            'company_id': cls.company.id, 'rmv': 1130.0})
        cls.afp = cls.env['hr.membership'].search(
            [('is_afp', '=', True), ('company_id', '=', False)], limit=1)
        cls.structure = cls.env.ref('al_hr_pe.base_structure')
        cls.employee = cls._create_employee('María', '44556677')

    @classmethod
    def _create_employee(cls, name, dni, wage=3000.0):
        employee = cls.env['hr.employee'].create({
            'names': name, 'last_name': 'Quispe', 'm_last_name': 'Rojas',
            'company_id': cls.company.id,
            'date_version': date(2025, 1, 1),
            'contract_date_start': date(2025, 1, 1),
            'wage': wage,
            'structure_type_id': cls.structure.type_id.id,
            'l10n_pe_document_type_id':
                cls.env.ref('al_hr_pe.l10n_pe_hr_document_type_dni').id,
            'identification_id': dni,
        })
        employee.version_id.write({
            'membership_id': cls.afp.id,
            'l10n_pe_commission_type': 'flow',
        })
        return employee

    def _slip(self, employee=None, date_from=date(2026, 3, 1),
              date_to=date(2026, 3, 31), compute=True):
        slip = self.env['hr.payslip'].create({
            'name': 'Boleta revisión',
            'employee_id': (employee or self.employee).id,
            'struct_id': self.structure.id,
            'date_from': date_from,
            'date_to': date_to,
        })
        if compute:
            slip.compute_sheet()
        return slip

    def _line(self, slip, code):
        return slip.line_ids.filtered(lambda l: l.code == code)

    def _attachment_text(self, action):
        attachment_id = int(action['url'].split('/')[3].split('?')[0])
        attachment = self.env['ir.attachment'].browse(attachment_id)
        return attachment.raw.content.decode('utf-8')

    # ------------------------------------------------------------------
    # A1. Dos versiones en el periodo
    # ------------------------------------------------------------------
    def test_a1_two_versions_in_the_month(self):
        """Aumento de sueldo desde el 16: la boleta trae una línea de días
        por versión y se calcula igual (antes «Expected singleton»). Las
        reglas leen la SUMA de las líneas de un mismo código y el DOM del
        periodo va una sola vez."""
        self.employee.create_version({
            'date_version': date(2026, 3, 16), 'wage': 3600.0})
        slip = self._slip()
        dlab = slip.worked_days_line_ids.filtered(lambda l: l.code == 'DLAB')
        self.assertEqual(len(dlab.version_id), 2, 'una línea DLAB por versión')
        dom = slip.worked_days_line_ids.filtered(lambda l: l.code == 'DOM')
        self.assertEqual(
            sum(dlab.mapped('number_of_days')) + sum(dom.mapped('number_of_days')),
            31, 'DLAB + DOM = días del mes, sin duplicar el descanso')
        # Mes completo: el básico es el sueldo de la versión de la boleta.
        self.assertAlmostEqual(
            self._line(slip, 'BAS').total, slip.version_id.wage, places=2)
        self.assertTrue(self._line(slip, 'NETO').total)

    def test_a1_localdict_sums_the_lines(self):
        """``worked_days['X']`` suma días, horas e importe de todas las
        líneas del código; el resto de atributos es el de la primera."""
        slip = self._slip(compute=False)
        dlab = slip.worked_days_line_ids.filtered(lambda l: l.code == 'DLAB')
        dlab.copy({'payslip_id': slip.id, 'number_of_days': 2.0,
                   'number_of_hours': 16.0, 'amount': 10.0})
        dlab.amount = 5.0
        worked_days = slip._get_localdict()['worked_days']
        self.assertAlmostEqual(
            worked_days['DLAB'].number_of_days, dlab.number_of_days + 2.0)
        self.assertAlmostEqual(
            worked_days['DLAB'].number_of_hours, dlab.number_of_hours + 16.0)
        self.assertAlmostEqual(worked_days['DLAB'].amount, 15.0)
        self.assertEqual(worked_days['DLAB'].code, 'DLAB')
        self.assertEqual(worked_days['DLAB'].name, dlab.name)
        # Un código con una sola línea sigue siendo la línea misma.
        self.assertEqual(worked_days['FAL']._name, 'hr.payslip.worked_days')
        # Y uno ausente vale cero.
        self.assertEqual(worked_days['NO_EXISTE'].number_of_days, 0.0)

    # ------------------------------------------------------------------
    # A2. Totales nativos de la boleta
    # ------------------------------------------------------------------
    def test_a2_native_wage_totals(self):
        """``basic_wage``/``gross_wage``/``net_wage`` toman BAS, TINGR y
        NETO en la estructura peruana (antes, 0), y el coste del empleador
        suma sus aportes."""
        slip = self._slip()
        self.assertAlmostEqual(slip.basic_wage, self._line(slip, 'BAS').total)
        self.assertAlmostEqual(slip.gross_wage, self._line(slip, 'TINGR').total)
        self.assertAlmostEqual(slip.net_wage, self._line(slip, 'NETO').total)
        self.assertTrue(slip.net_wage)
        employer = slip.line_ids.filtered(
            lambda l: l.salary_rule_id.appears_on_employee_cost_dashboard)
        self.assertIn('ESSALUD', employer.mapped('code'))
        self.assertAlmostEqual(
            slip.employer_cost, sum(employer.mapped('total')), places=2)
        self.assertTrue(slip.employer_cost)
        run = self.env['hr.payslip.run'].create({
            'name': 'Lote neto', 'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31), 'company_id': self.company.id})
        slip.payslip_run_id = run
        self.assertAlmostEqual(run.net_sum, slip.net_wage)

    def test_a2_foreign_structure_keeps_native_codes(self):
        """Una estructura de otro país no suma una regla que casualmente se
        llame NETO: sus totales siguen saliendo de BASIC/GROSS/NET."""
        foreign = self.env['hr.payroll.structure'].create({
            'name': 'Estructura sin país',
            'type_id': self.structure.type_id.id,
            'country_id': self.env.ref('base.cl').id,
        })
        # La estructura nueva trae las reglas nativas por defecto (BASIC,
        # GROSS, NET…); se le añade una regla NETO ajena.
        self.env['hr.salary.rule'].create({
            'name': 'NETO', 'code': 'NETO', 'struct_ids': [(6, 0, foreign.ids)],
            'category_ids': [(6, 0, self.env.ref('al_hr_pe.SUB').ids)],
            'amount_select': 'fix', 'amount_fix': 7.0, 'sequence': 999,
        })
        self.assertEqual(
            self.env['hr.payslip']._get_net_wage_line_codes(), {'NET'})
        pe_slip = self._slip()
        foreign_slip = self._slip(
            employee=self._create_employee('Ana', '44556688'), compute=False)
        foreign_slip.struct_id = foreign
        (pe_slip | foreign_slip).compute_sheet()
        self.assertTrue(self._line(foreign_slip, 'NETO'))
        self.assertAlmostEqual(
            foreign_slip.net_wage, sum(self._line(foreign_slip, 'NET').mapped('total')))
        self.assertAlmostEqual(pe_slip.net_wage, self._line(pe_slip, 'NETO').total)

    # ------------------------------------------------------------------
    # A6. PLAME/AFPNet del lote mensual: solo boletas cerradas
    # ------------------------------------------------------------------
    def test_a6_monthly_lot_skips_cancelled_and_draft(self):
        """La boleta cancelada y la que sigue en borrador no se declaran
        (antes sí: se sumaban por DNI y código, a veces dos veces)."""
        other = self._create_employee('Rosa', '44556699')
        draft_emp = self._create_employee('Luz', '44556600')
        run = self.env['hr.payslip.run'].create({
            'name': 'Lote 2026-03', 'date_start': date(2026, 3, 1),
            'date_end': date(2026, 3, 31), 'company_id': self.company.id})
        done = self._slip()
        cancelled = self._slip(employee=other)
        draft = self._slip(employee=draft_emp)
        (done | cancelled | draft).payslip_run_id = run
        done.state = 'validated'
        cancelled.state = 'cancel'
        self.assertEqual(run._l10n_pe_plame_slips(), done)
        text = self._attachment_text(run.action_export_plame_rem())
        self.assertIn('44556677', text)
        self.assertNotIn('44556699', text)
        self.assertNotIn('44556600', text)

    # ------------------------------------------------------------------
    # A3. El complemento DOM solo descuenta los días que BAS paga o descuenta
    # ------------------------------------------------------------------
    def _dom_days(self, values):
        slip = self.env['hr.payslip'].new({
            'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 3, 1),
            'date_to': date(2026, 3, 31),
        })
        with patch.object(type(self.env['hr.payslip']),
                          '_get_worked_day_lines_values',
                          lambda self, version, work_entries_vals: [dict(v) for v in values]):
            lines = slip._get_worked_day_lines(
                slip.version_id, [], check_out_of_version=False)
        dom = self.env.ref('al_hr_pe.wd_DOM')
        return sum(v['number_of_days'] for v in lines
                   if v['work_entry_type_id'] == dom.id)

    def _wd(self, work_entry_type, days, hours=None):
        return {'sequence': 1, 'work_entry_type_id': work_entry_type.id,
                'number_of_days': days,
                'number_of_hours': days * 8 if hours is None else hours}

    def test_a3_additional_concepts_keep_rest_days(self):
        """FER, TAR y HTN son adicionales a la jornada: no restan días de
        descanso (antes, FER de 1 día dejaba BAS en 29/30)."""
        dlab = self.env.ref('al_hr_pe.wd_DLAB')
        values = [self._wd(dlab, 22.0),
                  self._wd(self.env.ref('al_hr_pe.wd_FER'), 1.0),
                  self._wd(self.env.ref('al_hr_pe.wd_TAR'), 0.25, 2.0),
                  self._wd(self.env.ref('al_hr_pe.wd_HTN'), 3.0)]
        self.assertEqual(self._dom_days(values), 31 - 22)
        # Las ausencias PE sí ocupan días.
        values.append(self._wd(self.env.ref('al_hr_pe.wd_DMED'), 2.0))
        self.assertEqual(self._dom_days(values), 31 - 22 - 2)

    def test_a3_foreign_types(self):
        """Un tipo de otro país pagado (feriado nativo) va como descanso
        remunerado; uno sin pago (licencia nativa) se descuenta."""
        dlab = self.env.ref('al_hr_pe.wd_DLAB')
        Type = self.env['hr.work.entry.type']
        paid = Type.create({'name': 'Feriado nativo', 'code': 'TESTHOL',
                            'amount_rate': 1.0})
        unpaid = Type.create({'name': 'Licencia nativa', 'code': 'TESTUNP',
                              'amount_rate': 0.0})
        self.assertEqual(
            self._dom_days([self._wd(dlab, 21.0), self._wd(paid, 1.0)]), 31 - 21)
        self.assertEqual(
            self._dom_days([self._wd(dlab, 21.0), self._wd(unpaid, 1.0)]), 31 - 22)

    # ------------------------------------------------------------------
    # A5. Snapshot de tasas AFP/RMV
    # ------------------------------------------------------------------
    def test_a5_closed_slip_keeps_its_rates(self):
        """Corregir la fecha de nacimiento o las tasas de la AFP no
        reescribe una boleta validada."""
        slip = self._slip()
        fund = slip.l10n_pe_retirement_fund
        slip.state = 'validated'
        self.afp.retirement_fund = fund + 1.0
        self.employee.birthday = date(1950, 1, 1)
        self.assertAlmostEqual(slip.l10n_pe_retirement_fund, fund)
        self.assertFalse(slip.l10n_pe_is_older)

    def test_a5_draft_slip_follows_new_rates(self):
        """Las tasas que actualiza el cron SBS y una RMV cargada después de
        crear la boleta llegan a la boleta en borrador al calcular."""
        slip = self._slip()
        self.afp.prima_insurance = 2.5
        slip.compute_sheet()
        self.assertAlmostEqual(slip.l10n_pe_prima_insurance, 2.5)
        self.env['hr.rule.parameter.value'].create({
            'rule_parameter_id':
                self.env.ref('al_hr_pe.rule_parameter_l10n_pe_rmv').id,
            'date_from': date(2026, 3, 15),
            'parameter_value': '1500.0',
        })
        slip.compute_sheet()
        self.assertEqual(slip.rmv, 1500.0)
        self.assertAlmostEqual(slip.family_allowance, 150.0)
