# -*- coding: utf-8 -*-
"""Ambiente medido (paquete 1.9, M19-06).

El supervisor marca la cocina del Dpto 501 como medida con fecha y archivo,
sin cantidades ni aprobación; aparece en la lista de pendientes de
Optimización y sale de ella cuando entra en una orden de fabricación. La
orden de un ambiente sin marcar se prepara con aviso."""
import base64

from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from .common import PlannerCommon

PLAN_PDF = base64.b64encode(b'%PDF-1.4 plano de la cocina (test)')


@tagged('post_install', '-at_install')
class TestMeasuredSpace(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supervisor = new_test_user(
            cls.env, 'medido_supervisor', groups='al_construction_planner.group_planner_user',
            name='Supervisor de proyectos (test)')

    def setUp(self):
        super().setUp()
        self._generate_and_approve()

    def _mark(self, spaces, user=None):
        action = spaces.with_user(user or self.supervisor).action_construction_mark_measured()
        wizard = self.env[action['res_model']].with_user(user or self.supervisor).with_context(
            action['context']).create({
                'date': '2026-10-15', 'file': PLAN_PDF, 'file_name': 'cocina_501.skp'})
        wizard.action_confirm()

    def _pending(self):
        return self.env['project.task'].search([
            ('project_id', '=', self.project.id), ('construction_level', '=', 'space'),
            ('construction_measured_pending', '=', True)])

    def _production_wizard(self):
        return self.env['construction.plan.production.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_project=True).create({})

    def test_mark_measured_with_date_and_file(self):
        self._mark(self.space_501)
        space = self.space_501
        self.assertTrue(space.construction_measured)
        self.assertEqual(str(space.construction_measured_date), '2026-10-15')
        self.assertEqual(space.construction_measured_user_id, self.supervisor)
        self.assertEqual(space.construction_measured_attachment_ids.name, 'cocina_501.skp')
        self.assertEqual(space.construction_measured_attachment_ids.res_id, space.id)
        message = space.message_ids.filtered(lambda m: m.attachment_ids)[:1]
        self.assertEqual(message.author_id, self.supervisor.partner_id)
        self.assertFalse(self.env['construction.measurement'].search(
            [('task_id', '=', space.id)]), 'sin metrado ni aprobación')

    def test_pending_list_until_production(self):
        self._mark(self.space_501)
        self.assertEqual(self._pending(), self.space_501)
        wizard = self._production_wizard()
        self.assertIn('Sin marcar como medidos', wizard.note)
        self.assertIn(self.space_502.display_name, wizard.note)
        wizard.action_create()
        self.assertFalse(self._pending(), 'ya está en una orden de fabricación')
        self.assertTrue(self.space_501.construction_production_ids)
        with self.assertRaises(UserError):
            self.space_501.with_user(self.supervisor).action_construction_unmark_measured()
        # Cancelar la orden lo devuelve a la lista.
        self.space_501.construction_production_ids.action_cancel()
        self.assertEqual(self._pending(), self.space_501)

    def test_unmark_and_rights(self):
        self._mark(self.space_501)
        self.space_501.with_user(self.supervisor).action_construction_unmark_measured()
        self.assertFalse(self.space_501.construction_measured)
        self.assertFalse(self._pending())
        with self.assertRaises(UserError):
            self.floor.with_user(self.supervisor).action_construction_mark_measured()
        with self.assertRaises(AccessError):
            self.space_501.with_user(self.reporter).action_construction_mark_measured()
