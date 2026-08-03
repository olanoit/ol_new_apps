# -*- coding: utf-8 -*-
"""Beneficios pagados en la planilla de construcción civil.

El fixture es la **tabla salarial con beneficios sociales** de la
R.M. N.° 197-2025-TR: el operario con 6 días y gratificación de Navidad
suma 1 163.80 de total de salarios.
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestConstructionBenefits(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create(
            {'name': 'Beneficios Test S.A.C.', 'vat': '20512528458'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.structure = cls.env.ref(
            'al_hr_pe_construction.construction_structure')
        cls.wd_dlab = cls.env.ref('al_hr_pe.wd_DLAB')
        cls.wd_he60 = cls.env.ref('al_hr_pe_construction.wd_HE60')
        cls.dni = cls.env.ref('l10n_pe.it_DNI')
        cls.child_type = cls.env.ref('al_hr_pe.dependent_type_05')

    def _worker(self, category='category_operario'):
        # Documento distinto por trabajador: el módulo base exige que sea
        # único por compañía.
        self._doc_seq = getattr(self, '_doc_seq', 0) + 1
        employee = self.env['hr.employee'].create({
            'name': 'Obrero Beneficios %d' % self._doc_seq,
            'company_id': self.company.id,
            'identification_id': '4123456%d' % self._doc_seq,
            'l10n_latam_identification_type_id': self.dni.id})
        employee.version_id.write({
            'l10n_pe_labor_regime': 'construccion',
            'l10n_pe_construction_category_id': self.env.ref(
                'al_hr_pe_construction.%s' % category).id,
        })
        return employee

    def _payslip(self, employee, date_from, date_to, days=6, overtime=0.0):
        payslip = self.env['hr.payslip'].create({
            'name': 'Semana %s' % date_from,
            'employee_id': employee.id,
            'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date_from, 'date_to': date_to,
        })
        payslip.worked_days_line_ids.unlink()
        lines = [(0, 0, {
            'name': 'Días laborados',
            'work_entry_type_id': self.wd_dlab.id,
            'number_of_days': days, 'number_of_hours': days * 8,
            'amount': 0.0})]
        if overtime:
            lines.append((0, 0, {
                'name': 'Horas extras',
                'work_entry_type_id': self.wd_he60.id,
                'number_of_days': 0, 'number_of_hours': overtime,
                'amount': 0.0}))
        payslip.worked_days_line_ids = lines
        payslip.compute_sheet()
        return payslip

    @staticmethod
    def _line(payslip, code):
        line = payslip.line_ids.filtered(lambda l: l.code == code)
        return round(line.total, 2) if line else 0.0

    def _child(self, employee, years, **kwargs):
        today = date(2026, 3, 8)
        vals = {
            'employee_id': employee.id,
            'type_id': self.child_type.id,
            'last_name': 'Hijo', 'names': 'Uno',
            'l10n_latam_identification_type_id': self.dni.id,
            'identification_id': kwargs.pop(
                'identification_id', '7111111%d' % employee.id),
            'birthday': today - relativedelta(years=years),
            'date_start': today - relativedelta(years=years),
        }
        vals.update(kwargs)
        return self.env['l10n_pe.hr.dependent'].create(vals)

    # ------------------------------------------------------------------
    # El criterio de cierre de la fase
    # ------------------------------------------------------------------
    def test_weekly_with_benefits_matches_the_official_table(self):
        """Operario, 6 días, semana de Navidad: 1 163.80 de salarios.

        Es la columna «TABLA SALARIAL CON BENEFICIOS SOCIALES» del
        convenio, con la gratificación devengada en la ventana de agosto
        a diciembre.
        """
        payslip = self._payslip(self._worker(),
                                date(2026, 11, 2), date(2026, 11, 8))
        self.assertEqual(self._line(payslip, 'JOR'), 535.80)
        self.assertEqual(self._line(payslip, 'DSO'), 89.30)
        self.assertEqual(self._line(payslip, 'BUC'), 171.46)
        self.assertEqual(self._line(payslip, 'MOV'), 51.60)
        self.assertEqual(self._line(payslip, 'INDEM'), 80.37,
                         'indemnización 15 %')
        self.assertEqual(self._line(payslip, 'VAC10'), 53.58,
                         'vacaciones 10 %')
        self.assertEqual(self._line(payslip, 'GRAT'), 166.69,
                         'gratificación de Navidad, 7 días de devengo')
        self.assertEqual(self._line(payslip, 'BEXT'), 15.00,
                         '9 % de la gratificación, Ley 30334')
        self.assertEqual(self._line(payslip, 'TINGR'), 1163.80)

    def test_official_table_has_a_one_cent_mismatch_on_the_oficial(self):
        """El total impreso del oficial no cuadra con sus componentes.

        La tabla del convenio publica 911.94 para el oficial, pero sus
        propias columnas suman 911.95: 418.50 + 69.75 + 125.55 + 51.60 +
        62.78 + 41.85 + 130.20 + 11.72. El descuadre es de la fuente —que
        suma importes ya redondeados—, no del cálculo: cada concepto
        coincide uno a uno.

        Este test existe para que nadie «corrija» el motor buscando el
        911.94 y desajuste un concepto que sí está bien.
        """
        payslip = self._payslip(self._worker('category_oficial'),
                                date(2026, 11, 2), date(2026, 11, 8))
        componentes = {
            'JOR': 418.50, 'DSO': 69.75, 'BUC': 125.55, 'MOV': 51.60,
            'INDEM': 62.78, 'VAC10': 41.85, 'GRAT': 130.20, 'BEXT': 11.72,
        }
        for code, expected in componentes.items():
            self.assertEqual(self._line(payslip, code), expected, code)
        self.assertEqual(self._line(payslip, 'TINGR'), 911.95)
        self.assertEqual(round(sum(componentes.values()), 2), 911.95,
                         'los componentes de la propia tabla suman 911.95')

    def test_peon_with_benefits_matches_the_official_table(self):
        payslip = self._payslip(self._worker('category_peon'),
                                date(2026, 11, 2), date(2026, 11, 8))
        self.assertEqual(self._line(payslip, 'GRAT'), 117.23)
        self.assertEqual(self._line(payslip, 'BEXT'), 10.55)
        self.assertEqual(self._line(payslip, 'TINGR'), 826.22)

    def test_july_gratification_uses_the_other_window(self):
        """Fiestas Patrias se devenga en 210 días, no en 150."""
        payslip = self._payslip(self._worker(),
                                date(2026, 3, 2), date(2026, 3, 8))
        self.assertEqual(self._line(payslip, 'GRAT'), 119.07,
                         '40 × 89.30 × 7 ÷ 210')
        self.assertEqual(self._line(payslip, 'BEXT'), 10.72)
        self.assertLess(self._line(payslip, 'GRAT'), 166.69,
                        'la de julio es menor que la de Navidad')

    def test_gratification_switches_in_august(self):
        worker = self._worker()
        july = self._payslip(worker, date(2026, 7, 27), date(2026, 8, 2))
        august = self._payslip(worker, date(2026, 8, 3), date(2026, 8, 9))
        # La ventana la fija el mes de la fecha de fin del periodo.
        self.assertEqual(self._line(july, 'GRAT'), 166.69,
                         'termina en agosto: ya devenga Navidad')
        self.assertEqual(self._line(august, 'GRAT'), 166.69)

    def test_benefits_for_every_category(self):
        expected = {
            'category_operario': (80.37, 53.58),
            'category_oficial': (62.78, 41.85),
            'category_peon': (56.52, 37.68),
        }
        for category, (cts, vacation) in expected.items():
            with self.subTest(categoria=category):
                payslip = self._payslip(self._worker(category),
                                        date(2026, 3, 2), date(2026, 3, 8))
                self.assertEqual(self._line(payslip, 'INDEM'), cts)
                self.assertEqual(self._line(payslip, 'VAC10'), vacation)

    # ------------------------------------------------------------------
    # Indemnización sobre las horas extras
    # ------------------------------------------------------------------
    def test_cts_includes_overtime_at_simple_value(self):
        """La tabla da 1.67 de indemnización por hora extra del operario.

        Es el 15 % del valor hora **simple** (11.16), no de la hora ya
        recargada.
        """
        plain = self._payslip(self._worker(),
                              date(2026, 3, 2), date(2026, 3, 8))
        with_overtime = self._payslip(self._worker(),
                                      date(2026, 3, 2), date(2026, 3, 8),
                                      overtime=1.0)
        delta = round(self._line(with_overtime, 'INDEM')
                      - self._line(plain, 'INDEM'), 2)
        self.assertEqual(delta, 1.67)

    # ------------------------------------------------------------------
    # Días parciales
    # ------------------------------------------------------------------
    def test_benefits_scale_with_the_days(self):
        payslip = self._payslip(self._worker(),
                                date(2026, 3, 2), date(2026, 3, 8), days=3)
        self.assertEqual(self._line(payslip, 'INDEM'), 40.19,
                         '15 % de 267.90')
        self.assertEqual(self._line(payslip, 'VAC10'), 26.79)
        self.assertEqual(self._line(payslip, 'GRAT'), 59.53,
                         'medio devengo: 3.5 días en vez de 7')

    def test_no_days_no_benefits(self):
        payslip = self._payslip(self._worker(),
                                date(2026, 3, 2), date(2026, 3, 8), days=0)
        for code in ('INDEM', 'VAC10', 'GRAT', 'BEXT', 'AESC'):
            self.assertEqual(self._line(payslip, code), 0.0, code)

    # ------------------------------------------------------------------
    # Asignación escolar
    # ------------------------------------------------------------------
    def test_school_allowance_per_child(self):
        worker = self._worker()
        payslip = self._payslip(worker, date(2026, 3, 2), date(2026, 3, 8))
        self.assertEqual(self._line(payslip, 'AESC'), 0.0,
                         'sin hijos no hay asignación')

        self._child(worker, 8)
        payslip = self._payslip(worker, date(2026, 3, 2), date(2026, 3, 8))
        # 30 jornales al año ÷ 360 × 7 días = 7.4417 × 7
        self.assertEqual(self._line(payslip, 'AESC'), 52.09)

        self._child(worker, 12, identification_id='71111112')
        payslip = self._payslip(worker, date(2026, 3, 2), date(2026, 3, 8))
        self.assertEqual(self._line(payslip, 'AESC'), 104.18,
                         'se paga por cada hijo')

    def test_school_allowance_expires_with_the_age(self):
        worker = self._worker()
        self._child(worker, 19)
        payslip = self._payslip(worker, date(2026, 3, 2), date(2026, 3, 8))
        self.assertEqual(self._line(payslip, 'AESC'), 0.0,
                         'a los 18 cumplidos se acaba')

    def test_school_allowance_extends_while_studying(self):
        """En este régimen el tope estudiando es 21, no 24."""
        worker = self._worker()
        child = self._child(worker, 20, is_studying=True)
        payslip = self._payslip(worker, date(2026, 3, 2), date(2026, 3, 8))
        self.assertGreater(self._line(payslip, 'AESC'), 0.0)

        child.birthday = date(2026, 3, 8) - relativedelta(years=22)
        payslip = self._payslip(worker, date(2026, 3, 2), date(2026, 3, 8))
        self.assertEqual(self._line(payslip, 'AESC'), 0.0,
                         'pasados los 21 se acaba aunque siga estudiando')

    def test_company_can_move_the_age_limits(self):
        worker = self._worker()
        self._child(worker, 19)
        self.company.l10n_pe_construction_school_age = 20
        payslip = self._payslip(worker, date(2026, 3, 2), date(2026, 3, 8))
        self.assertGreater(self._line(payslip, 'AESC'), 0.0,
                           'el tope es un parámetro, no una constante')

    # ------------------------------------------------------------------
    # Base afecta
    # ------------------------------------------------------------------
    def test_social_benefits_are_out_of_the_taxable_base(self):
        """La CTS, las vacaciones y la gratificación no aportan.

        Si TREM sumara `categories['ING']` los metería dentro sin que
        nadie lo note; por eso enumera lo afecto.
        """
        payslip = self._payslip(self._worker(),
                                date(2026, 11, 2), date(2026, 11, 8))
        total = self._line(payslip, 'TINGR')
        taxable = self._line(payslip, 'TREM')
        self.assertEqual(taxable, 796.56,
                         'jornal + D.S.O. + BUC, sin la movilidad')
        self.assertEqual(
            round(total - taxable, 2),
            round(self._line(payslip, 'INDEM') + self._line(payslip, 'VAC10')
                  + self._line(payslip, 'GRAT') + self._line(payslip, 'BEXT')
                  + self._line(payslip, 'MOV'), 2),
            'fuera quedan los beneficios sociales y la movilidad, que es '
            'condición de trabajo y no remuneración')

    def test_school_allowance_is_taxable(self):
        worker = self._worker()
        self._child(worker, 8)
        payslip = self._payslip(worker, date(2026, 3, 2), date(2026, 3, 8))
        self.assertEqual(self._line(payslip, 'TREM'),
                         round(796.56 + self._line(payslip, 'AESC'), 2))
