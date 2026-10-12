# -*- coding: utf-8 -*-
"""v1.5, fase 19: adicionales, deductivos y dependencias de terceros."""
import base64
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import new_test_user, tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestChangeV15(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = new_test_user(
            cls.env, 'plan_jefe_cambios', name='Jefatura cambios (test)',
            groups='al_construction_planner.group_planner_manager')

    def _change(self, kind='additional', lines=None):
        return self.env['construction.change.order'].create({
            'project_id': self.project.id, 'kind': kind, 'reason': 'Pedido del cliente (test)',
            'line_ids': [Command.create(vals) for vals in lines or [{
                'task_id': self.space_501.id, 'resource_type': 'material',
                'product_id': self.p_cognac.id, 'stage': 'production', 'qty': 2,
                'price_unit': 50.0, 'sale_price_unit': 80.0}]],
        })

    def test_price_rule_follows_unit_state(self):
        self._generate()
        change = self._change()
        line = change.line_ids
        self.assertEqual((line.unit_state, line.price_rule), ('planned', 'difference'))
        modules = self.env['project.task'].search([
            ('construction_space_task_id', '=', self.space_501.id),
            ('construction_level', '=', 'module')])
        modules[0].construction_unit_state = 'on_site'
        self.assertEqual(self._change().line_ids.price_rule, 'loose_part')
        modules[0].construction_unit_state = 'installed'
        reinstall = self._change()
        self.assertEqual(reinstall.line_ids.price_rule, 'reinstall')
        reinstall.line_ids.reinstall_amount = 40.0
        self.assertEqual(reinstall.amount_sale, 2 * 80.0 + 40.0)
        self.assertEqual(reinstall.amount_cost, 100.0)

    def test_signs_by_kind(self):
        with self.assertRaises(ValidationError):
            self._change('deductive')
        with self.assertRaises(ValidationError):
            self._change('additional', [{'task_id': self.space_501.id, 'resource_type': 'material',
                                         'product_id': self.p_white.id, 'qty': -1}])
        rework = self._change('rework')
        self.assertEqual(rework.amount_sale, 0.0, 'rehacer no se cobra')

    def test_approve_adds_lines_to_approved_plan_and_budget(self):
        self._generate_and_approve()
        budget_before = sum(self.plan.budget_analytic_id.budget_line_ids.mapped('budget_amount'))
        change = self._change('net', [
            {'task_id': self.space_501.id, 'resource_type': 'material',
             'product_id': self.p_cognac.id, 'stage': 'production', 'qty': 2, 'price_unit': 50.0},
            {'task_id': self.space_501.id, 'resource_type': 'material',
             'product_id': self.p_white.id, 'stage': 'production', 'qty': -1, 'price_unit': 30.0},
        ])
        self.assertEqual(change.plan_id, self.plan)
        self.assertEqual(change.task_ids, self.apt_501)
        with self.assertRaises(UserError):
            change.with_user(self.planner).action_approve()  # sin ser jefatura
        change.with_user(self.manager).action_approve()
        self.assertEqual(change.state, 'approved')
        lines = change.plan_line_ids
        self.assertEqual(len(lines), 2)
        self.assertEqual(set(lines.mapped('source')), {'change'})
        self.assertEqual(set(lines.mapped('source_ref')), {change.name})
        self.assertEqual(lines.plan_id, self.plan)
        self.assertEqual(sum(lines.mapped('amount_budgeted')), 70.0)
        budget_after = sum(self.plan.budget_analytic_id.budget_line_ids.mapped('budget_amount'))
        self.assertAlmostEqual(budget_after - budget_before, 70.0, 2)
        with self.assertRaises(UserError):
            change.action_cancel()

    def test_dependency_blocks_progress_and_schedule(self):
        self._generate_and_approve()
        self.plan.action_sync_space_stages()
        Stage = self.env['construction.space.stage']
        stage_501 = Stage.search([('space_task_id', '=', self.space_501.id),
                                  ('stage', '=', 'assembly')])
        stage_502 = Stage.search([('space_task_id', '=', self.space_502.id),
                                  ('stage', '=', 'assembly')])
        self.assertTrue(stage_501 and stage_502)
        expected = stage_501.date_start + timedelta(days=10)
        dependency = self.env['construction.dependency'].create({
            'name': 'Piloto aprobado (test)', 'project_id': self.project.id, 'kind': 'pilot',
            'stage': 'assembly', 'task_ids': [Command.set(self.apt_501.ids)],
            'date_expected': expected})
        self.assertEqual(dependency.stage_count, 1, 'solo el 501')
        self.assertTrue(stage_501.blocked)
        self.assertFalse(stage_502.blocked)
        # Sin avances mientras está abierta.
        line = self.plan.line_ids.filtered(
            lambda l: l.resource_type == 'contract' and l.stage == 'assembly'
            and l.space_task_id == self.space_501)[0]
        photo = self.env['ir.attachment'].create({'name': 'f.png', 'datas': base64.b64encode(b'x')})
        progress_vals = {'task_id': line.task_id.id, 'activity_id': line.activity_id.id,
                         'plan_line_id': line.id, 'qty': 1,
                         'attachment_ids': [Command.set(photo.ids)]}
        with self.assertRaises(UserError):
            self.env['construction.task.progress'].create(progress_vals)
        # No se programa antes de la fecha prevista.
        with self.assertRaises(UserError):
            stage_501.action_gantt_reschedule(stage_501.date_start, stage_501.date_end)
        # «Mover cronograma» la lleva al día hábil siguiente a la fecha prevista.
        dependency.action_shift_schedule()
        self.assertGreater(stage_501.date_start, expected)
        self.assertTrue(self.env.company._construction_is_site_day(stage_501.date_start))
        later = Stage.search([('space_task_id', '=', self.space_501.id),
                              ('stage', 'in', ('installation', 'finishing'))])
        self.assertTrue(all(s.date_start > stage_501.date_end for s in later))
        # Cumplida: el avance entra.
        dependency.action_done()
        stage_501.invalidate_recordset(['blocked', 'dependency_ids'])
        self.assertFalse(stage_501.blocked)
        progress = self.env['construction.task.progress'].create(
            dict(progress_vals, attachment_ids=[Command.set(photo.copy().ids)]))
        self.assertTrue(progress)
        self.assertEqual(dependency.date_done, fields.Date.context_today(dependency))


@tagged('post_install', '-at_install')
class TestDataValidationV15(PlannerCommon):
    """M15-11: validaciones de datos."""

    def test_unit_matches_floor(self):
        from odoo.addons.al_construction_planner.wizards.master_import_wizard import (
            _unit_matches_floor)
        self.assertTrue(_unit_matches_floor('Piso 05', 'Dpto 501'))
        self.assertTrue(_unit_matches_floor('P12', '1203'))
        self.assertTrue(_unit_matches_floor('Piso 1', 'Ducto 2'), 'no comparable')
        self.assertFalse(_unit_matches_floor('Piso 05', 'Dpto 601'))
        self.assertFalse(_unit_matches_floor('P1', '1001'))

    def test_import_warns_duplicates_and_floor(self):
        from odoo.addons.al_construction_planner.wizards.master_import_layout import (
            build_workbook)
        site = self.env['project.project'].create({
            'name': 'Obra validaciones (test)', 'is_construction_site': True})
        rows = {
            'TIPOLOGIAS': [{'code': 'C1', 'name': 'Cocina'}, {'code': 'C1', 'name': 'Cocina bis'}],
            'ARBOL': [{'floor': 'Piso 1', 'apartment': 'D101', 'space': 'Cocina', 'typology': 'C1'},
                      {'floor': 'Piso 1', 'apartment': 'D101', 'space': 'Cocina', 'typology': 'C1'},
                      {'floor': 'Piso 1', 'apartment': 'D201', 'space': 'Cocina', 'typology': 'C1'}],
        }
        wizard = self.env['construction.master.import.wizard'].create({
            'project_id': site.id, 'file': base64.b64encode(build_workbook(rows)),
            'filename': 'maestro.xlsx'})
        warnings = wizard._analyze()['warnings']
        self.assertEqual(len(warnings['typology_duplicate']), 1)
        self.assertIn('fila 3', warnings['tree_duplicate'][0])
        self.assertIn('D201', warnings['unit_floor_mismatch'][0])
        self.assertIn('repetidos', wizard.warning_html)

    def test_possible_duplicate_progress(self):
        self._generate_and_approve()
        line = self.plan.line_ids.filtered(lambda l: l.resource_type == 'contract')[0]
        Progress = self.env['construction.task.progress']

        def report():
            photo = self.env['ir.attachment'].create(
                {'name': 'f.png', 'datas': base64.b64encode(b'x')})
            return Progress.create({
                'task_id': line.task_id.id, 'activity_id': line.activity_id.id,
                'plan_line_id': line.id, 'qty': line.qty_planned / 4,
                'attachment_ids': [Command.set(photo.ids)]})
        first = report()
        self.assertFalse(first.possible_duplicate)
        second = report()
        first.invalidate_recordset(['possible_duplicate'])
        self.assertTrue(first.possible_duplicate and second.possible_duplicate)
        self.assertEqual(Progress.search([('possible_duplicate', '=', True),
                                          ('plan_line_id', '=', line.id)]), first | second)
        second.write({'state': 'rejected'})
        first.invalidate_recordset(['possible_duplicate'])
        self.assertFalse(first.possible_duplicate)
