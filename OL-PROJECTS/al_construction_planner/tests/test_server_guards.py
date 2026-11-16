# -*- coding: utf-8 -*-
"""Controles del servidor del avance (auditoría del 16-nov-2026): quien
reporta tiene permiso de escritura sobre sus avances, así que validarlos no
puede depender de la vista. Datos ficticios."""
from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

G = 'al_construction_planner.group_planner_'
PHOTO = (b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE'
         b'hQGAhKmMIQAAAABJRU5ErkJggg==')


@tagged('post_install', '-at_install')
class TestProgressGuards(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['tier.definition'].search([('model', '=', 'construction.resource.plan')]).active = False
        cls.stage = env['construction.stage'].create({
            'name': 'Tabiquería (test controles)', 'code': 'guard_test_stage', 'sequence': 915})
        cls.project = env['project.project'].create({
            'name': 'Obra de los controles (test)', 'is_construction_site': True})
        cls.task = env['project.task'].create({
            'name': '04.01 Tabique (test controles)', 'project_id': cls.project.id})
        cls.activity = env['construction.labor.activity'].create({
            'code': 'GT-TAB', 'name': 'Tabique (test controles)', 'stage': cls.stage.code,
            'default_price': 30.0, 'uom_id': env.ref('uom.product_uom_unit').id})
        cls.plan = env['construction.resource.plan'].create({'project_id': cls.project.id})
        cls.line = env['construction.resource.plan.line'].create({
            'plan_id': cls.plan.id, 'task_id': cls.task.id, 'resource_type': 'labor',
            'activity_id': cls.activity.id, 'stage': cls.stage.code, 'qty_planned': 100.0,
            'price_unit_planned': 30.0, 'product_uom_id': env.ref('uom.product_uom_unit').id})
        cls.plan.action_request_approval()
        assert cls.plan.state == 'approved', cls.plan.state
        cls.reporter = new_test_user(env, 'guard_reporta', groups=G + 'progress',
                                     name='Quien reporta (test)')
        cls.validator = new_test_user(env, 'guard_valida_avance',
                                      groups=G + 'progress,' + G + 'exec_validator',
                                      name='Quien valida (test)')
        cls.executor = new_test_user(env, 'guard_ejecuta', groups=G + 'user',
                                     name='Quien ejecuta (test)')

    def _vals(self, **extra):
        return dict({
            'task_id': self.task.id, 'activity_id': self.activity.id, 'plan_line_id': self.line.id,
            'date': date(2026, 11, 4), 'qty': 10.0,
            'attachment_ids': [Command.create({'name': 'foto.png', 'datas': PHOTO})]}, **extra)

    def _reported(self):
        progress = self.env['construction.task.progress'].with_user(self.reporter).create(
            self._vals())
        self.assertEqual(progress.state, 'draft')
        return progress

    def test_validation_is_for_the_validator(self):
        progress = self._reported()
        for state in ('validated', 'rejected'):
            with self.assertRaises(UserError):
                progress.write({'state': state})
        with self.assertRaises(UserError):
            progress.write({'validator_id': self.reporter.id})
        with self.assertRaises(UserError):
            self.env['construction.task.progress'].with_user(self.reporter).create(
                self._vals(state='validated'))
        self.assertEqual(progress.state, 'draft')
        self.assertEqual(self.line.qty_executed, 0.0)
        # Quien reporta sigue corrigiendo su avance reportado.
        progress.write({'qty': 12.0})
        progress.with_user(self.validator).action_validate()
        self.assertEqual(progress.state, 'validated')
        self.assertEqual(progress.validator_id, self.validator)
        self.assertEqual(self.line.qty_executed, 12.0)
        with self.assertRaises(UserError):
            progress.write({'state': 'draft'})
        progress.with_user(self.validator).action_reset()
        self.assertEqual(progress.state, 'draft')
        progress.with_user(self.validator)._action_reject('Sin evidencia')
        self.assertEqual(progress.state, 'rejected')
        with self.assertRaises(UserError):
            progress.write({'state': 'draft'})
