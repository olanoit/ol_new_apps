# -*- coding: utf-8 -*-
"""Metrado del ambiente y su aprobación (v1.6, M16-03 y M16-04).

Cocina tipo 01: 2.12 ML de mueble bajo y 2.10 de alto a S/ 18.00 por ML
(tarifa de la obra) y 7 módulos con S/ 54.00 de armado (6 + 3 × 8 + 10 + 7
+ 7). Un metrado de 2.90 ML de mueble bajo da 0.78 ML de diferencia, S/
14.04, y la orden de fabricación de ese ambiente espera la aprobación de la
jefatura.
"""
from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged
from odoo.tools import mute_logger

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestMeasurement(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supervisor = new_test_user(
            cls.env, 'metrado_supervisor', groups='al_construction_planner.group_planner_user',
            name='Supervisor de obra (test)')
        cls.manager = new_test_user(
            cls.env, 'metrado_jefatura', groups='al_construction_planner.group_planner_project_head',
            name='Jefatura de proyectos (test)')

    def setUp(self):
        super().setUp()
        self._generate_and_approve()

    def _measure(self, space, **measured):
        measurement = self.env['construction.measurement'].with_user(self.supervisor).create(
            {'task_id': space.id})
        for line in measurement.line_ids:
            if line.driver in measured:
                line.qty_measured = measured[line.driver]
        return measurement

    def _production_wizard(self):
        return self.env['construction.plan.production.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_project=True).create({})

    def test_planned_values_and_difference(self):
        measurement = self._measure(self.space_501, ml_low=2.90)
        self.assertEqual(measurement.plan_id, self.plan)
        lines = {line.driver: line for line in measurement.line_ids}
        self.assertEqual(set(lines), {'ml_low', 'ml_high', 'units'})
        self.assertAlmostEqual(lines['ml_low'].qty_planned, 2.12)
        self.assertAlmostEqual(lines['ml_high'].qty_planned, 2.10)
        self.assertEqual(lines['units'].qty_planned, 7)
        self.assertAlmostEqual(lines['ml_low'].unit_amount, 18.0)
        self.assertAlmostEqual(lines['units'].unit_amount, 54.0 / 7, places=4)
        self.assertAlmostEqual(lines['ml_low'].qty_difference, 0.78)
        self.assertAlmostEqual(lines['ml_low'].amount_difference, 14.04)
        self.assertTrue(measurement.has_difference)
        self.assertAlmostEqual(measurement.amount_difference, 14.04)
        self.assertTrue(measurement.name.startswith('MET/'))

    def test_difference_blocks_production_until_approved(self):
        measurement = self._measure(self.space_501, ml_low=2.90)
        wizard = self._production_wizard()
        self.assertEqual(wizard.line_ids.space_task_ids, self.space_502)
        self.assertIn('Metrado con diferencia por aprobar', wizard.note)

        measurement.with_user(self.supervisor).action_submit()
        self.assertEqual(measurement.state, 'submitted')
        self.assertTrue(measurement.review_ids)
        self.assertEqual(self._production_wizard().line_ids.space_task_ids, self.space_502)

        measurement.with_user(self.manager).validate_tier()
        self.assertEqual(measurement.state, 'approved')
        self.assertEqual(self._production_wizard().line_ids.space_task_ids,
                         self.space_501 | self.space_502)

    def test_without_difference_is_approved_on_submit(self):
        measurement = self._measure(self.space_501)
        self.assertFalse(measurement.has_difference)
        self.assertEqual(self._production_wizard().line_ids.space_task_ids,
                         self.space_501 | self.space_502)
        measurement.with_user(self.supervisor).action_submit()
        self.assertEqual(measurement.state, 'approved')
        self.assertFalse(measurement.review_ids)

    def test_rejection_returns_to_draft(self):
        measurement = self._measure(self.space_501, units=8)
        measurement.with_user(self.supervisor).action_submit()
        measurement.with_user(self.manager).reject_tier()
        self.assertEqual(measurement.state, 'draft')
        # En borrador se corrige y se vuelve a enviar.
        measurement.line_ids.filtered(lambda l: l.driver == 'units').qty_measured = 7
        measurement.with_user(self.supervisor).action_submit()
        self.assertEqual(measurement.state, 'approved')

    def test_measured_qty_locked_after_submit(self):
        measurement = self._measure(self.space_501, ml_high=2.30)
        measurement.with_user(self.supervisor).action_submit()
        with self.assertRaises(UserError):
            measurement.line_ids[0].qty_measured = 5

    def test_reopen_blocked_by_production(self):
        measurement = self._measure(self.space_501)
        measurement.with_user(self.supervisor).action_submit()
        self._production_wizard().action_create()
        with self.assertRaises(UserError):
            measurement.action_draft()

    def test_one_measurement_per_space(self):
        self._measure(self.space_501)
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            self._measure(self.space_501)

    def test_generate_wizard_for_a_floor(self):
        self._measure(self.space_501)
        wizard = self.env['construction.measurement.generate.wizard'].with_user(
            self.supervisor).with_context(
            construction_selection_task_ids=[self.floor.id]).create({})
        self.assertEqual(wizard.project_id, self.project)
        self.assertEqual(wizard.space_count, 1)
        action = wizard.action_generate()
        lines = self.env['construction.measurement.line'].search(action['domain'])
        self.assertEqual(lines.task_id, self.space_502)
        self.assertEqual(len(lines), 3)
        with self.assertRaises(UserError):
            wizard.action_generate()
