# -*- coding: utf-8 -*-
"""Avance sobre el saldo del plan (prototipo «Portal de obra CREVAL»,
pantalla 5): según la política del plan para la contrata se bloquea, solo
alerta o queda como exceso que aprueba la jefatura de proyectos antes de
validarse.

Una partida de muro drywall de 120 m² sin tolerancia: un avance de 130 m²
excede en 10 m². Datos de demostración inventados para la prueba."""

import base64
from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

PHOTO = (b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE'
         b'hQGAhKmMIQAAAABJRU5ErkJggg==')


@tagged('post_install', '-at_install')
class TestProgressExceedApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['tier.definition'].search(
            [('model', '=', 'construction.resource.plan')]).active = False
        m2 = cls.env.ref('uom.product_uom_square_meter')
        cls.env['construction.stage'].create({'name': 'Tabiquería (test)', 'code': 'testex_dry',
                                              'kind': 'field', 'sequence': 520})
        template = cls.env['construction.level.template'].create({
            'name': 'Partidas tabiquería (test)', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Partida', 'role': 'space',
                        'measure_uom_id': m2.id})]})
        cls.site = cls.env['project.project'].create({
            'name': 'Oficinas San Isidro (test)', 'is_construction_site': True,
            'construction_level_template_id': template.id})
        partida = cls.env['project.task'].create({
            'name': 'Muro drywall RF', 'project_id': cls.site.id,
            'construction_level_line_id': template.line_ids.id, 'construction_qty': 120.0})
        activity = cls.env['construction.labor.activity'].create({
            'code': 'TEX-MURO', 'name': 'Muro drywall instalado (test)', 'stage': 'testex_dry',
            'uom_id': m2.id, 'default_price': 30.0})
        cls.plan = cls.env['construction.resource.plan'].create({
            'project_id': cls.site.id, 'exceed_policy': 'approval', 'exceed_tolerance': 0.0})
        cls.wall = cls.env['construction.resource.plan.line'].create({
            'plan_id': cls.plan.id, 'task_id': partida.id, 'stage': 'testex_dry',
            'resource_type': 'contract', 'activity_id': activity.id, 'product_uom_id': m2.id,
            'partner_id': cls.env['res.partner'].create({'name': 'Tabiques Surco (test)'}).id,
            'qty_planned': 120.0, 'price_unit_planned': 30.0})
        cls.plan.action_request_approval()
        cls.supervisor = new_test_user(
            cls.env, 'exceed_supervisor', name='Supervisor de obra (test)',
            groups='al_construction_planner.group_planner_planner')
        cls.head = new_test_user(
            cls.env, 'exceed_head', name='Jefa de proyectos (test)',
            groups='al_construction_planner.group_planner_exec_approver,'
                   'al_construction_planner.group_planner_exec_validator')

    def _progress(self, qty):
        return self.env['construction.task.progress'].with_user(self.supervisor).create({
            'task_id': self.wall.task_id.id, 'activity_id': self.wall.activity_id.id,
            'qty': qty, 'attachment_ids': [Command.create({'name': 'avance.png',
                                                           'raw': base64.b64decode(PHOTO)})]})

    def test_exceed_waits_for_the_head(self):
        within = self._progress(100.0)
        self.assertEqual(within.exceed_state, 'ok')
        progress = self._progress(30.0)
        self.assertEqual(progress.exceed_state, 'exceeded')
        self.assertAlmostEqual(progress.exceed_qty, 10.0)
        self.assertIn(self.head, progress.activity_ids.user_id)
        self.assertIn('Espera la aprobación', ' '.join(progress.message_ids.mapped('body')))
        # El supervisor no valida ni aprueba el exceso; lo en plan sí se valida.
        with self.assertRaisesRegex(UserError, 'esperan la aprobación de la jefatura'):
            progress.with_user(self.supervisor).action_validate()
        with self.assertRaises(UserError):
            progress.with_user(self.supervisor).action_approve_exceed()
        within.with_user(self.supervisor).action_validate()
        progress.with_user(self.head).action_approve_exceed()
        self.assertEqual(progress.exceed_state, 'approved')
        self.assertEqual(progress.exceed_approver_id, self.head)
        self.assertFalse(progress.activity_ids)
        log = self.env['construction.exceed.log'].search([
            ('res_model', '=', progress._name), ('res_id', '=', progress.id)])
        self.assertEqual(log.kind, 'excess')
        self.assertEqual(log.user_id, self.head)
        self.assertAlmostEqual(log.qty, 10.0)
        self.assertAlmostEqual(log.amount, 300.0)
        self.assertIn(log, self.plan.exceed_log_ids)
        progress.with_user(self.supervisor).action_validate()
        self.assertAlmostEqual(self.wall.qty_executed, 130.0)

    def test_changed_qty_needs_a_new_approval(self):
        self._progress(100.0)
        progress = self._progress(30.0)
        progress.with_user(self.head).action_approve_exceed()
        progress.with_user(self.supervisor).write({'qty': 25.0})
        self.assertEqual(progress.exceed_state, 'exceeded')
        self.assertAlmostEqual(progress.exceed_qty, 5.0)
        self.assertFalse(progress.exceed_approver_id)
        # Corregido dentro del saldo, vuelve a «En plan».
        progress.with_user(self.supervisor).write({'qty': 15.0})
        self.assertEqual(progress.exceed_state, 'ok')
        progress.with_user(self.supervisor).action_validate()

    def test_rework_does_not_exceed(self):
        self._progress(120.0)
        rework = self.env['construction.task.progress'].with_user(self.supervisor).create({
            'task_id': self.wall.task_id.id, 'activity_id': self.wall.activity_id.id,
            'qty': 8.0, 'is_rework': True, 'rework_reason': 'bad_assembly',
            'attachment_ids': [Command.create({'name': 'avance.png', 'raw': base64.b64decode(PHOTO)})]})
        self.assertEqual(rework.exceed_state, 'ok')

    def test_warn_policy_validates(self):
        self.plan.exceed_policy_contract = 'warn'
        progress = self._progress(130.0)
        self.assertEqual(progress.exceed_state, 'exceeded')
        self.assertFalse(progress.activity_ids)
        progress.with_user(self.supervisor).action_validate()
        self.assertEqual(progress.state, 'validated')

    def test_block_policy_rejects(self):
        self.plan.exceed_policy = 'block'
        with self.assertRaisesRegex(ValidationError, 'presupuestados'):
            self._progress(130.0)
