# -*- coding: utf-8 -*-
"""Presupuesto de mano de obra (paquete 1.19, M119-01) con el ejemplo de los
criterios: 400 ML, rendimiento 4 por persona-día, plazo de 30 días desde un
lunes con el horario de 45 h, banda de 10 % y jornal de S/ 120.

* 24.5 días equivalentes; metas de 16.33 ML por día, 10.20 por sábado y
  91.84 por semana completa; 100 persona-días necesarios; 4.08 personas
  exactas; 4 personas; rendimiento exigido 4.08 (+2.0 %); 98 persona-días
  presupuestados y S/ 11,760.
* Con 450 ML, 5 personas y −8.2 % sin aviso; con 440 ML, 5 personas, −10.2 %
  y «Capacidad ociosa».
* Las metas semanales suman 400 ML: 4 semanas de 91.84 y 32.65 en la quinta.
* La tabla de la obra nace con el rendimiento del catálogo; cambiarla pide
  el motivo y deja el origen «Ajustado»."""
from datetime import date, datetime

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models.construction_labor_budget import compute_budget
from .test_package_119_schedule import site_calendar

MONDAY = date(2026, 11, 2)
END = date(2026, 12, 1)


@tagged('post_install', '-at_install')
class TestLaborBudget(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # Los feriados se leen en la hora de la compañía, como en una base real.
        cls.company.resource_calendar_id.tz = 'America/Lima'
        cls.company.construction_site_calendar_id = site_calendar(cls.env, cls.company)
        cls.project = cls.env['project.project'].create({
            'name': 'Obra presupuesto MO (test 1.19)', 'is_construction_site': True})
        meter = cls.env.ref('uom.product_uom_meter')
        cls.activity = cls.env['construction.labor.activity'].create({
            'code': 'T19-INS', 'name': 'Instalación ML (test 1.19)', 'stage': 'installation',
            'uom_id': meter.id, 'productivity': 4.0, 'default_price': 7.0})
        cls.stage = cls.env['construction.stage'].search([('code', '=', 'installation')])

    def _budget(self, qty=400.0, mode='own', **values):
        return self.env['construction.labor.budget'].create(dict({
            'project_id': self.project.id, 'stage_id': self.stage.id, 'mode': mode,
            'date_start': MONDAY, 'date_end': END, 'band': 10.0, 'daily_wage': 120.0,
            'line_ids': [(0, 0, {'activity_id': self.activity.id, 'quantity': qty,
                                 'productivity': 4.0, 'rate': 7.0})],
        }, **values))

    def test_example_of_the_requirement(self):
        budget = self._budget()
        self.assertEqual(budget.equivalent_days, 24.5)
        self.assertEqual(budget.person_days_needed, 100.0)
        self.assertAlmostEqual(budget.persons_exact, 4.08, places=2)
        self.assertEqual(budget.persons, 4)
        self.assertAlmostEqual(budget.deviation_pct, 2.0, places=1)
        self.assertAlmostEqual(budget.person_days_budget, 98.0)
        self.assertAlmostEqual(budget.amount, 11760.0, places=2)
        self.assertFalse(budget.warning)
        line = budget.line_ids
        self.assertAlmostEqual(line.required_productivity, 4.08, places=2)
        self.assertAlmostEqual(line.unit_cost, 29.40, places=2)
        # Metas: 16.33 por día completo, 10.20 por sábado, 91.84 por semana.
        per_day = line.quantity / budget.equivalent_days
        self.assertAlmostEqual(per_day, 16.33, places=2)
        self.assertAlmostEqual(per_day * 0.625, 10.20, places=2)
        weeks = budget.week_ids
        self.assertEqual(len(weeks), 5)
        targets = [round(budget._target(line, week), 2) for week in weeks]
        self.assertEqual(targets[:4], [91.84] * 4)
        self.assertAlmostEqual(targets[4], 32.65, places=2)
        self.assertAlmostEqual(sum(budget._target(line, week) for week in weeks), 400.0)
        self.assertAlmostEqual(weeks[-1].amount_cumulative, 11760.0, places=2)

    def test_band_cases(self):
        budget = self._budget(qty=450.0)
        self.assertEqual(budget.persons, 5)
        self.assertAlmostEqual(budget.line_ids.required_productivity, 3.67, places=2)
        self.assertAlmostEqual(budget.deviation_pct, -8.2, places=1)
        self.assertFalse(budget.warning)
        budget.line_ids.quantity = 440.0
        self.assertEqual(budget.persons, 5)
        self.assertAlmostEqual(budget.line_ids.required_productivity, 3.59, places=2)
        self.assertAlmostEqual(budget.deviation_pct, -10.2, places=1)
        self.assertIn('Capacidad ociosa', budget.warning)

    def test_contract_is_paid_by_progress(self):
        budget = self._budget(mode='contract')
        self.assertEqual(budget.persons, 4)
        self.assertAlmostEqual(budget.amount, 400 * 7.0)

    def test_adjusted_end_needs_a_reason(self):
        budget = self._budget()
        with self.assertRaises(ValidationError):
            budget.date_end_adjusted = date(2026, 11, 28)
        budget.write({'date_end_adjusted': date(2026, 11, 28), 'adjust_reason': 'Pisos libres'})
        # Hasta el sábado de la cuarta semana: 22.5 días equivalentes.
        self.assertEqual(budget.equivalent_days, 22.5)
        self.assertEqual(len(budget.week_ids), 4)
        self.assertEqual(budget.persons, 5)

    def test_holiday_takes_one_day(self):
        self.env['resource.calendar.leaves'].create({
            'name': 'Feriado de obra (test)', 'calendar_id':
                self.company.construction_site_calendar_id.id,
            'date_from': datetime(2026, 11, 18, 13, 0), 'date_to': datetime(2026, 11, 18, 22, 0)})
        self.env.cr.cache.pop('al_construction_holidays', None)
        self.env.cr.cache.pop('al_construction_site_holidays', None)
        self.assertEqual(self._budget().equivalent_days, 23.5)

    def test_activity_without_productivity_does_not_count(self):
        result = compute_budget([{'key': 'A', 'qty': 400.0, 'productivity': 4.0},
                                 {'key': 'B', 'qty': 10.0, 'productivity': 0.0}], 24.5, 10.0,
                                120.0)
        self.assertEqual(result['person_days_needed'], 100.0)
        self.assertEqual(result['missing'], ['B'])
        budget = self._budget()
        other = self.env['construction.labor.activity'].create({
            'code': 'T19-PUSH', 'name': 'Push (test 1.19)', 'stage': 'installation',
            'uom_id': self.env.ref('uom.product_uom_unit').id})
        budget.line_ids = [(0, 0, {'activity_id': other.id, 'quantity': 8.0})]
        self.assertIn('Sin rendimiento', budget.warning)
        self.assertEqual(budget.persons, 4)

    def test_project_productivity_table(self):
        rows = self.project._construction_productivity_ensure(self.activity)
        self.assertEqual(rows.productivity, 4.0)
        self.assertEqual(rows.origin, 'initial')
        self.assertFalse(self.project._construction_productivity_ensure(self.activity))
        with self.assertRaises(UserError):
            rows.productivity = 3.5
        rows.write({'productivity': 3.5, 'reason': 'Acceso por escalera'})
        self.assertEqual(rows.origin, 'adjusted')
        self.project._construction_productivity_write({self.activity: (3.9, 'Medido S2')},
                                                      origin='measured')
        self.assertEqual(rows.productivity, 3.9)
        self.assertEqual(rows.origin, 'measured')
        self.assertEqual(self.project._construction_productivity_map()[self.activity], 3.9)

    def test_stage_flag_by_behavior(self):
        assembly = self.env['construction.stage'].search([('code', '=', 'assembly')])
        self.assertTrue(self.stage.labor_budget)
        self.assertEqual(assembly.labor_budget, not assembly.production_consumption
                         and assembly.kind == 'field')
