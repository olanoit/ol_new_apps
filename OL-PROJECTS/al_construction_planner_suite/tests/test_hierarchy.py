# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestHierarchy(PlannerCommon):

    def test_ancestors(self):
        module = self.task('Tarugo 1', 'module', self.space_501)
        self.assertEqual(module.construction_floor_task_id, self.floor)
        self.assertEqual(module.construction_apartment_task_id, self.apt_501)
        self.assertEqual(module.construction_space_task_id, self.space_501)
        self.assertEqual(self.space_501.construction_space_task_id, self.space_501)
        self.assertEqual(self.floor.construction_floor_task_id, self.floor)
        # Mover el departamento a otro piso arrastra a toda su descendencia.
        floor_06 = self.task('Piso 06', 'floor')
        self.apt_501.parent_id = floor_06
        self.assertEqual(module.construction_floor_task_id, floor_06)

    def test_level_must_follow_parent(self):
        with self.assertRaises(ValidationError):
            self.task('Cocina suelta', 'space', self.floor)
        with self.assertRaises(ValidationError):
            self.task('Dpto sin piso', 'apartment')

    def test_amount_rolls_up(self):
        self._generate()
        lines = self.plan.line_ids
        lines.filtered(lambda l: l.resource_type == 'material').write({'price_unit_planned': 1.0})
        total_501 = sum(lines.filtered(lambda l: l.apartment_task_id == self.apt_501)
                        .mapped('amount_planned'))
        self.assertAlmostEqual(self.apt_501.construction_plan_amount, total_501)
        self.assertAlmostEqual(self.floor.construction_plan_amount, self.plan.amount_total)
        module = lines.filtered('module_task_id')[:1].module_task_id
        self.assertAlmostEqual(module.construction_plan_amount, sum(
            lines.filtered(lambda l: l.module_task_id == module).mapped('amount_planned')))

    def test_plan_versions(self):
        Plan = self.env['construction.resource.plan']
        self.assertEqual(self.plan.version, 1)
        self.assertTrue(self.plan.name.startswith('PLR/'))
        with self.assertRaises(ValidationError):
            Plan.create({'project_id': self.project.id})
        self.plan.state = 'approved'
        replan = Plan.create({'project_id': self.project.id, 'parent_id': self.plan.id,
                              'replan_reason': 'Cambio de tipologías'})
        self.assertEqual(replan.version, 2)
        with self.assertRaises(ValidationError):
            Plan.create({'project_id': self.project.id, 'state': 'approved'})

    def test_lines_locked_outside_draft(self):
        self._generate()
        line = self.plan.line_ids[:1]
        self.plan.state = 'approved'
        with self.assertRaises(UserError):
            line.qty_planned = 5
        with self.assertRaises(UserError):
            line.unlink()
        line.date_needed = '2026-11-02'
        with self.assertRaises(UserError):
            self.plan.action_open_generate_wizard()

    def test_date_needed_from_task_start(self):
        self._generate()
        self.plan.lead_days_material = 7
        material = self.plan.line_ids.filtered(
            lambda l: l.resource_type == 'material' and l.task_id == self.space_501)[:1]
        self.assertEqual(material.date_needed, self.plan.date_start - timedelta(days=7))
