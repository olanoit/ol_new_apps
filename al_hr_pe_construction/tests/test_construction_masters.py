# -*- coding: utf-8 -*-
"""Maestros de construcción civil.

El fixture es la tabla oficial de la R.M. N.° 197-2025-TR (01/01/2026 al
31/12/2026): si el módulo no reproduce esos importes, algo está mal.
"""
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestConstructionMasters(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create(
            {'name': 'Constructora Test S.A.C.', 'vat': '20512528458'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=cls.company.ids))
        cls.operario = cls.env.ref('al_hr_pe_construction.category_operario')
        cls.oficial = cls.env.ref('al_hr_pe_construction.category_oficial')
        cls.peon = cls.env.ref('al_hr_pe_construction.category_peon')
        cls.table = cls.env.ref('al_hr_pe_construction.wage_table_2026')
        cls.line_operario = cls.env.ref(
            'al_hr_pe_construction.wage_line_2026_operario')
        cls.line_peon = cls.env.ref(
            'al_hr_pe_construction.wage_line_2026_peon')
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Quispe Huamán Julio', 'company_id': cls.company.id})
        cls.version = cls.employee.version_id
        cls.version.write({
            'l10n_pe_labor_regime': 'construccion',
            'date_version': date(2026, 3, 1),
            'l10n_pe_construction_category_id': cls.operario.id,
        })

    # ------------------------------------------------------------------
    # Tabla del convenio
    # ------------------------------------------------------------------
    def test_official_2026_wages(self):
        """Jornales de la R.M. 197-2025-TR."""
        self.assertEqual(self.table.resolution, 'R.M. N.° 197-2025-TR')
        self.assertEqual(self.table.date_from, date(2026, 1, 1))
        self.assertEqual(self.table.date_to, date(2026, 12, 31),
                         'el convenio 2026 va de enero a diciembre')
        wages = {line.category_id.code: line.daily_wage
                 for line in self.table.line_ids}
        self.assertEqual(wages, {'OPE': 89.30, 'OFI': 69.75, 'PEO': 62.80})

    def test_buc_by_category(self):
        self.assertEqual(self.operario.buc_percent, 32.0)
        self.assertEqual(self.oficial.buc_percent, 30.0)
        self.assertEqual(self.peon.buc_percent, 30.0)
        self.assertAlmostEqual(self.line_operario.buc_amount, 28.58, places=2)
        self.assertAlmostEqual(self.line_peon.buc_amount, 18.84, places=2)

    def test_derived_amounts_match_the_official_table(self):
        """Los derivados del jornal, contra la columna del operario."""
        line = self.line_operario
        self.assertAlmostEqual(line.dso_amount, 14.88, places=2, msg='D.S.O.')
        self.assertAlmostEqual(line.hour_value, 11.16, places=2)
        self.assertAlmostEqual(line.overtime_60, 17.86, places=2)
        self.assertAlmostEqual(line.overtime_100, 22.33, places=2)
        self.assertAlmostEqual(line.cts_amount, 13.40, places=2,
                               msg='indemnización 15 %')
        self.assertAlmostEqual(line.vacation_amount, 8.93, places=2)
        self.assertAlmostEqual(line.school_daily, 7.44, places=2,
                               msg='asignación escolar: 30 jornales al año')

    def test_gratifications_accrue_in_different_windows(self):
        """40 jornales cada una, pero devengados en 7 y en 5 meses."""
        line = self.line_operario
        self.assertAlmostEqual(line.bonus_july_daily, 17.01, places=2)
        self.assertAlmostEqual(line.bonus_december_daily, 23.81, places=2)
        self.assertGreater(line.bonus_december_daily, line.bonus_july_daily,
                           'Navidad se devenga en menos meses, así que su '
                           'diario es mayor con el mismo jornal')
        # Las dos suman 40 jornales
        self.assertAlmostEqual(line.bonus_july_daily * 210, 89.30 * 40,
                               delta=2.0)
        self.assertAlmostEqual(line.bonus_december_daily * 150, 89.30 * 40,
                               delta=2.0)

    def test_mobility_is_the_same_for_every_category(self):
        amounts = set(self.table.line_ids.mapped('mobility_amount'))
        self.assertEqual(amounts, {8.60},
                         'la movilidad es un importe, no un porcentaje')

    def test_weekly_totals_of_the_official_table(self):
        """Totales de salarios con 6 días, para las tres categorías."""
        expected = {'OPE': 848.16, 'OFI': 665.40, 'PEO': 604.24}
        actual = {line.category_id.code: line._period_total(6)
                  for line in self.table.line_ids}
        self.assertEqual({k: round(v, 2) for k, v in actual.items()}, expected)

    def test_period_amounts_round_once(self):
        """El importe del periodo no es el diario multiplicado por los días.

        La tabla oficial redondea una sola vez, sobre el periodo. En el
        oficial se nota: el BUC semanal es 125.55, no 6 × 20.93 = 125.58.
        """
        line = self.table.line_ids.filtered(
            lambda l: l.category_id == self.oficial)
        amounts = line._period_amounts(6)
        self.assertAlmostEqual(amounts['jornal'], 418.50, places=2)
        self.assertAlmostEqual(amounts['dso'], 69.75, places=2)
        self.assertAlmostEqual(amounts['buc'], 125.55, places=2)
        self.assertAlmostEqual(amounts['movilidad'], 51.60, places=2)
        self.assertNotAlmostEqual(amounts['buc'], line.buc_amount * 6,
                                  places=2,
                                  msg='multiplicar el diario redondeado '
                                      'desvía tres céntimos')

    def test_operario_hides_the_rounding_problem(self):
        """En el operario los dos caminos coinciden por casualidad.

        Los céntimos del D.S.O. y del BUC se compensan, así que validar
        solo con esta categoría escondería el error de redondeo.
        """
        line = self.line_operario
        naive = 6 * (line.daily_wage + line.dso_amount + line.buc_amount
                     + line.mobility_amount)
        self.assertAlmostEqual(naive, line._period_total(6), places=2)

    # ------------------------------------------------------------------
    # Vigencia
    # ------------------------------------------------------------------
    def test_table_lookup_by_date(self):
        Table = self.env['l10n_pe.hr.construction.wage.table']
        self.assertEqual(Table._get_table_for_date(date(2026, 6, 15)),
                         self.table)
        self.assertFalse(Table._get_table_for_date(date(2025, 6, 15)),
                         'antes de su vigencia no hay tabla')

    def test_overlapping_tables_rejected(self):
        """Dos tablas vigentes a la vez dejarían el jornal ambiguo."""
        with self.assertRaises(ValidationError):
            self.env['l10n_pe.hr.construction.wage.table'].create({
                'name': 'Solapada',
                'date_from': date(2026, 6, 1),
                'date_to': date(2027, 5, 31),
            })

    def test_dates_must_be_coherent(self):
        with self.assertRaises(ValidationError):
            self.env['l10n_pe.hr.construction.wage.table'].create({
                'name': 'Al revés',
                'date_from': date(2027, 1, 1),
                'date_to': date(2026, 12, 31),
            })

    # ------------------------------------------------------------------
    # Jornal del trabajador
    # ------------------------------------------------------------------
    def test_daily_wage_comes_from_the_table(self):
        self.assertAlmostEqual(self.version.l10n_pe_daily_wage, 89.30,
                               places=2)
        self.assertEqual(self.version.l10n_pe_wage_line_id,
                         self.line_operario)

    def test_daily_wage_follows_the_category(self):
        self.version.l10n_pe_construction_category_id = self.peon
        self.assertAlmostEqual(self.version.l10n_pe_daily_wage, 62.80,
                               places=2)

    def test_no_category_no_wage(self):
        self.version.l10n_pe_construction_category_id = False
        self.assertFalse(self.version.l10n_pe_daily_wage)

    def test_wage_is_resolved_by_date(self):
        """Una boleta de marzo sigue con el jornal de marzo."""
        line = self.version._l10n_pe_get_wage_line(date(2026, 3, 31))
        self.assertEqual(line, self.line_operario)
        self.assertFalse(self.version._l10n_pe_get_wage_line(date(2025, 3, 31)))

    def test_is_construction_flag(self):
        self.assertTrue(self.version.l10n_pe_is_construction)
        self.version.l10n_pe_labor_regime = 'general'
        self.assertFalse(self.version.l10n_pe_is_construction)

    # ------------------------------------------------------------------
    # Bonificaciones
    # ------------------------------------------------------------------
    def test_bae_only_for_operarios(self):
        bae = self.env.ref('al_hr_pe_construction.bonus_bae_electromecanico')
        self.version.l10n_pe_construction_bae_id = bae
        self.assertAlmostEqual(bae._daily_amount(89.30), 19.65, places=2)
        with self.assertRaises(ValidationError):
            self.version.l10n_pe_construction_category_id = self.peon

    def test_bae_percentages_of_the_official_table(self):
        expected = {'BAE08': 7.14, 'BAE09': 8.04, 'BAE10': 8.93,
                    'BAE22': 19.65}
        bonuses = self.env['l10n_pe.hr.construction.bonus'].search(
            [('bonus_type', '=', 'bae')])
        actual = {b.code: round(b._daily_amount(89.30), 2) for b in bonuses}
        self.assertEqual(actual, expected)

    def test_fixed_and_percent_bonuses(self):
        altitud = self.env.ref('al_hr_pe_construction.bonus_altitud')
        agua = self.env.ref('al_hr_pe_construction.bonus_agua')
        self.assertAlmostEqual(altitud._daily_amount(89.30), 2.50, places=2,
                               msg='importe fijo, no depende del jornal')
        self.assertAlmostEqual(agua._daily_amount(89.30), 17.86, places=2,
                               msg='20 % del jornal')

    def test_bonus_needs_a_value(self):
        with self.assertRaises(ValidationError):
            self.env['l10n_pe.hr.construction.bonus'].create({
                'code': 'X', 'name': 'Sin valor', 'salary_rule_code': 'BALTI',
                'bonus_type': 'condition', 'computation': 'percent'})

    def test_site_bonuses_add_to_the_worker(self):
        """Las de la obra se suman a las del puesto."""
        altitud = self.env.ref('al_hr_pe_construction.bonus_altitud')
        cota = self.env.ref('al_hr_pe_construction.bonus_cota_cero')
        site = self.env['l10n_pe.hr.construction.site'].create({
            'name': 'Planta Cerro Verde', 'code': 'CV01',
            'company_id': self.company.id,
            'altitude': 3400,
            'bonus_ids': [(6, 0, altitud.ids)],
        })
        self.version.write({
            'l10n_pe_construction_site_id': site.id,
            'l10n_pe_construction_bonus_ids': [(6, 0, cota.ids)],
        })
        bonuses = self.version._l10n_pe_construction_bonuses()
        self.assertEqual(bonuses, altitud | cota)
        self.assertAlmostEqual(
            self.version._l10n_pe_construction_daily_total(date(2026, 3, 1)),
            2.50 + 1.90, places=2)

    def test_bonus_restricted_by_category_is_skipped(self):
        bae = self.env.ref('al_hr_pe_construction.bonus_bae_topografo')
        self.version.l10n_pe_construction_bae_id = bae
        self.assertIn(bae, self.version._l10n_pe_construction_bonuses())
        # Restringida a operarios: si el trabajador fuese peón no aplicaría
        self.assertFalse(bae._applies_to(self.peon))

    def test_site_counts_its_workers(self):
        site = self.env['l10n_pe.hr.construction.site'].create({
            'name': 'Edificio Lima', 'code': 'EL01',
            'company_id': self.company.id})
        self.assertEqual(site.employee_count, 0)
        self.version.l10n_pe_construction_site_id = site
        site.invalidate_recordset()
        self.assertEqual(site.employee_count, 1)
