# -*- coding: utf-8 -*-
"""Boleta de construcción civil contra la tabla del convenio.

El criterio de cierre de la fase 2 (§5 del análisis): reproducir los
totales de salarios de la R.M. N.° 197-2025-TR con 6 días —**las tres
categorías**, porque en el operario el error de redondeo se compensa
solo—.
"""
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestConstructionPayslip(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create(
            {'name': 'Obras Test S.A.C.', 'vat': '20512528458'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.structure = cls.env.ref(
            'al_hr_pe_construction.construction_structure')
        cls.wd_dlab = cls.env.ref('al_hr_pe.wd_DLAB')
        cls.wd_he60 = cls.env.ref('al_hr_pe_construction.wd_HE60')
        cls.wd_he100 = cls.env.ref('al_hr_pe.wd_HE100')
        cls.categories = {
            'OPE': cls.env.ref('al_hr_pe_construction.category_operario'),
            'OFI': cls.env.ref('al_hr_pe_construction.category_oficial'),
            'PEO': cls.env.ref('al_hr_pe_construction.category_peon'),
        }

    def _worker(self, category_code, **version_vals):
        employee = self.env['hr.employee'].create({
            'name': 'Trabajador %s' % category_code,
            'company_id': self.company.id})
        # En v19 la estructura va en la boleta, no en la versión: la
        # versión solo lleva el tipo de estructura.
        vals = {
            'l10n_pe_labor_regime': 'construccion',
            'l10n_pe_construction_category_id':
                self.categories[category_code].id,
        }
        vals.update(version_vals)
        employee.version_id.write(vals)
        return employee

    def _payslip(self, employee, days=6, overtime=None):
        """Boleta semanal con `days` días laborados."""
        payslip = self.env['hr.payslip'].create({
            'name': 'Semana 2026-03-02 · %s' % employee.name,
            'employee_id': employee.id,
            'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 3, 2),
            'date_to': date(2026, 3, 8),
        })
        payslip.worked_days_line_ids.unlink()
        lines = [(0, 0, {
            'name': 'Días laborados',
            'work_entry_type_id': self.wd_dlab.id,
            'number_of_days': days,
            'number_of_hours': days * 8,
            'amount': 0.0,
        })]
        for work_entry_type, hours in (overtime or {}).items():
            lines.append((0, 0, {
                'name': work_entry_type.name,
                'work_entry_type_id': work_entry_type.id,
                'number_of_days': 0,
                'number_of_hours': hours,
                'amount': 0.0,
            }))
        payslip.worked_days_line_ids = lines
        payslip.compute_sheet()
        return payslip

    @staticmethod
    def _line(payslip, code):
        line = payslip.line_ids.filtered(lambda l: l.code == code)
        return round(line.total, 2) if line else 0.0

    # ------------------------------------------------------------------
    # El criterio de cierre de la fase
    # ------------------------------------------------------------------
    def test_weekly_totals_match_the_official_table(self):
        """Total de salarios con 6 días, en las tres categorías."""
        expected = {
            #            jornal    dso     buc    movil    total
            'OPE': (535.80, 89.30, 171.46, 51.60, 848.16),
            'OFI': (418.50, 69.75, 125.55, 51.60, 665.40),
            'PEO': (376.80, 62.80, 113.04, 51.60, 604.24),
        }
        for code, (jor, dso, buc, mov, total) in expected.items():
            with self.subTest(categoria=code):
                payslip = self._payslip(self._worker(code))
                self.assertEqual(self._line(payslip, 'JOR'), jor)
                self.assertEqual(self._line(payslip, 'DSO'), dso)
                self.assertEqual(self._line(payslip, 'BUC'), buc)
                self.assertEqual(self._line(payslip, 'MOV'), mov)
                # «Total de salarios» de la tabla SIN beneficios sociales:
                # los de la fase 3 (indemnización, vacaciones,
                # gratificación) ya entran en TINGR, así que se comparan
                # los cuatro conceptos, no el total de la boleta.
                self.assertEqual(
                    round(sum(self._line(payslip, code)
                              for code in ('JOR', 'DSO', 'BUC', 'MOV')), 2),
                    total, 'total de salarios del convenio')

    def test_oficial_is_the_one_that_catches_the_rounding(self):
        """En el oficial, multiplicar el diario por 6 daría 665.46."""
        payslip = self._payslip(self._worker('OFI'))
        self.assertEqual(self._line(payslip, 'BUC'), 125.55)
        self.assertNotEqual(self._line(payslip, 'BUC'), 125.58)
        self.assertEqual(self._line(payslip, 'DSO'), 69.75)
        self.assertNotEqual(self._line(payslip, 'DSO'), 69.78)

    # ------------------------------------------------------------------
    # Días
    # ------------------------------------------------------------------
    def test_amounts_scale_with_the_days(self):
        payslip = self._payslip(self._worker('OPE'), days=3)
        self.assertEqual(self._line(payslip, 'JOR'), 267.90)
        self.assertEqual(self._line(payslip, 'DSO'), 44.65,
                         'medio día de descanso por tres trabajados')
        self.assertEqual(self._line(payslip, 'BUC'), 85.73)
        self.assertEqual(self._line(payslip, 'MOV'), 25.80)

    def test_no_days_no_pay(self):
        payslip = self._payslip(self._worker('OPE'), days=0)
        self.assertEqual(self._line(payslip, 'JOR'), 0.0)
        self.assertEqual(self._line(payslip, 'TINGR'), 0.0)

    def test_worker_documents_are_unique(self):
        """Dos trabajadores del fixture no pueden chocar por documento."""
        first, second = self._worker('OPE'), self._worker('OFI')
        self.assertNotEqual(first.id, second.id)

    # ------------------------------------------------------------------
    # Sobretiempo
    # ------------------------------------------------------------------
    def test_overtime_rates_60_and_100(self):
        """Sobre el valor hora sin redondear: 22.33, no 22.32."""
        payslip = self._payslip(
            self._worker('OPE'),
            overtime={self.wd_he60: 2.0, self.wd_he100: 1.0})
        self.assertEqual(self._line(payslip, 'HE60'), 35.72,
                         '2 h × 11.1625 × 1.6')
        self.assertEqual(self._line(payslip, 'HE100'), 22.33,
                         '1 h × 11.1625 × 2 = 22.325 → 22.33')

    def test_overtime_is_not_the_general_regime(self):
        """El régimen general paga 25/35; aquí es 60/100."""
        payslip = self._payslip(self._worker('OPE'),
                                overtime={self.wd_he60: 1.0})
        self.assertEqual(self._line(payslip, 'HE60'), 17.86)
        self.assertNotEqual(self._line(payslip, 'HE60'), 13.95,
                            'no es la sobretasa del 25 %')

    # ------------------------------------------------------------------
    # Bonificaciones
    # ------------------------------------------------------------------
    def test_bae_only_when_the_worker_has_it(self):
        plain = self._payslip(self._worker('OPE'))
        self.assertEqual(self._line(plain, 'BAE'), 0.0)

        bae = self.env.ref('al_hr_pe_construction.bonus_bae_electromecanico')
        specialist = self._worker('OPE', l10n_pe_construction_bae_id=bae.id)
        payslip = self._payslip(specialist)
        self.assertEqual(self._line(payslip, 'BAE'), 117.88,
                         '22 % de 535.80, como la tabla de especializados')

    def test_condition_bonuses_fixed_and_percent(self):
        altitud = self.env.ref('al_hr_pe_construction.bonus_altitud')
        agua = self.env.ref('al_hr_pe_construction.bonus_agua')
        worker = self._worker(
            'OPE',
            l10n_pe_construction_bonus_ids=[(6, 0, (altitud | agua).ids)])
        payslip = self._payslip(worker)
        self.assertEqual(self._line(payslip, 'BALTI'), 15.00,
                         '2.50 × 6 días')
        self.assertEqual(self._line(payslip, 'BAGUA'), 107.16,
                         '20 % de 535.80')

    def test_site_bonuses_reach_the_payslip(self):
        """Las de la obra se pagan aunque el puesto no las tenga."""
        cota = self.env.ref('al_hr_pe_construction.bonus_cota_cero')
        site = self.env['l10n_pe.hr.construction.site'].create({
            'name': 'Sótano Miraflores', 'code': 'SM01',
            'company_id': self.company.id,
            'bonus_ids': [(6, 0, cota.ids)]})
        payslip = self._payslip(
            self._worker('OPE', l10n_pe_construction_site_id=site.id))
        self.assertEqual(self._line(payslip, 'BCOTA'), 11.40, '1.90 × 6')

    def test_a_new_bonus_needs_no_code(self):
        """Añadir una bonificación al convenio es crear un registro."""
        extra = self.env['l10n_pe.hr.construction.bonus'].create({
            'code': 'BNOC', 'name': 'Bonificación nocturna del convenio',
            'bonus_type': 'condition', 'computation': 'percent',
            'percent': 5.0, 'salary_rule_code': 'BALTI',
            'company_id': self.company.id})
        altitud = self.env.ref('al_hr_pe_construction.bonus_altitud')
        worker = self._worker(
            'OPE',
            l10n_pe_construction_bonus_ids=[(6, 0, (extra | altitud).ids)])
        payslip = self._payslip(worker)
        # 5 % de 535.80 = 26.79, más los 15.00 de altitud
        self.assertEqual(self._line(payslip, 'BALTI'), 41.79,
                         'las bonificaciones que comparten regla se suman')

    # ------------------------------------------------------------------
    # Snapshot del jornal
    # ------------------------------------------------------------------
    def test_wage_is_frozen_on_the_payslip(self):
        """Una boleta de marzo conserva el jornal de marzo."""
        payslip = self._payslip(self._worker('OPE'))
        self.assertEqual(payslip.l10n_pe_daily_wage, 89.30)
        self.assertEqual(payslip.l10n_pe_wage_line_id,
                         self.env.ref(
                             'al_hr_pe_construction.wage_line_2026_operario'))

    def test_manual_wage_override_is_respected(self):
        """Si se ajusta el jornal de la boleta, el cálculo lo sigue."""
        worker = self._worker('OPE')
        payslip = self._payslip(worker)
        payslip.l10n_pe_daily_wage = 100.00
        payslip.compute_sheet()
        self.assertEqual(self._line(payslip, 'JOR'), 600.00)
        self.assertEqual(self._line(payslip, 'BUC'), 192.00, '32 % de 600')

    def test_general_regime_worker_has_no_construction_wage(self):
        employee = self._worker('OPE')
        employee.version_id.l10n_pe_labor_regime = 'general'
        payslip = self.env['hr.payslip'].create({
            'name': 'Régimen general',
            'employee_id': employee.id,
            'company_id': self.company.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 3, 2),
            'date_to': date(2026, 3, 8),
        })
        self.assertFalse(payslip.l10n_pe_daily_wage)
