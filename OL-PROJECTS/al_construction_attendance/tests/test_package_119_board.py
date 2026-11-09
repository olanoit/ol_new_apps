# -*- coding: utf-8 -*-
"""Tablero de control semanal de instalación (paquete 1.19, M119-05).

* Un piso con dos cocinas programadas para terminar la instalación en la
  semana 1: con una cocina validada va «Atrasado» al 50 %; con las dos,
  «Terminado» en la semana de su último avance.
* Indicadores: pisos del período, atrasados y terminados.
* Sin «Ve montos», la mano de obra va en persona-días; un usuario sin los
  grupos del planificador no ve el tablero."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from odoo.addons.al_construction_planner_suite.tests.common import PlannerCommon


@tagged('post_install', '-at_install')
class TestInstallationBoard(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        grp = 'al_construction_planner.group_planner_'
        cls.env.user.group_ids |= cls.env.ref(grp + 'user') | cls.env.ref(
            grp + 'feature_control')
        today = fields.Date.context_today(cls.env.user)
        cls.origin = today - timedelta(days=today.weekday() + 21)
        cls.lines = cls.env['construction.resource.plan.line']
        for space in (cls.space_501, cls.space_502):
            cls.lines |= cls.env['construction.resource.plan.line'].create({
                'plan_id': cls.plan.id, 'task_id': space.id, 'resource_type': 'contract',
                'activity_id': cls.act_inst_low.id, 'stage': 'installation',
                'partner_id': cls.contractor.id, 'qty_planned': 2.0,
                'price_unit_planned': 16.0, 'product_uom_id': cls.act_inst_low.uom_id.id})
            cls.env['construction.space.stage'].create({
                'space_task_id': space.id, 'stage': 'installation',
                'date_start': cls.origin, 'date_end': cls.origin + timedelta(days=4)})
        cls.plan.action_request_approval()
        cls.Board = cls.env['construction.installation.board']

    def _validate(self, line, day):
        photo = self.env['ir.attachment'].create({'name': 'f.png', 'datas': b'eA=='})
        progress = self.env['construction.task.progress'].create({
            'task_id': line.task_id.id, 'activity_id': line.activity_id.id,
            'plan_line_id': line.id, 'date': day, 'qty': 2.0,
            'attachment_ids': [(6, 0, photo.ids)]})
        progress.sudo().write({'state': 'validated'})

    def _cell(self, data):
        floor = next(f for f in data['floors'] if f['id'] == self.floor.id)
        return next(c for c in floor['cells'] if c['stage'] == 'installation')

    def test_late_then_done(self):
        self._validate(self.lines[0], self.origin + timedelta(days=2))
        data = self.Board.get_data(self.project.id)
        self.assertFalse(data['empty'])
        self.assertEqual(data['week_to'], data['current_week'] - 1)
        cell = self._cell(data)
        self.assertEqual(cell['sched_week'], 1)
        self.assertEqual(cell['pct'], 50)
        self.assertEqual(cell['status'], 'late')
        self.assertEqual(cell['spaces_done'], 1)
        self.assertEqual(data['indicators']['late']['count'], 1)
        self.assertEqual(data['indicators']['finished'], dict(
            data['indicators']['finished'], done=0, total=1))
        # La segunda cocina se valida en la semana 2: terminado con +1 semana.
        self._validate(self.lines[1], self.origin + timedelta(days=8))
        cell = self._cell(self.Board.get_data(self.project.id))
        self.assertEqual(cell['status'], 'done')
        self.assertEqual(cell['finish_week'], 2)
        self.assertEqual(cell['delay_weeks'], 1)
        # Período «Desde el inicio»: el piso programado en él terminó.
        data = self.Board.get_data(self.project.id, 1, 3)
        self.assertEqual(data['indicators']['period'], {'done': 1, 'total': 1})
        self.assertIn('Semanas 1 a 3', data['period_label'])
        # Desde mayor que hasta: hasta se mueve a la misma semana.
        data = self.Board.get_data(self.project.id, 3, 2)
        self.assertEqual((data['week_from'], data['week_to']), (3, 3))

    def test_curves_and_stage_switches(self):
        data = self.Board.get_data(self.project.id, None, None, False, False)
        # Siempre queda una etapa prendida: sin ninguna, la instalación.
        self.assertTrue(data['installation'])
        self.assertTrue(all(stage['installation'] for stage in data['stages']))
        curve = next(c for c in data['curves'] if 'Instalación' in c['stage'])
        self.assertEqual(curve['points'][0]['planned'], 1)

    def test_access(self):
        outsider = new_test_user(self.env, 'board_outsider', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.Board.with_user(outsider).get_data(self.project.id)
        supervisor = new_test_user(
            self.env, 'board_supervisor',
            groups='al_construction_planner.group_planner_user,'
                   'al_construction_planner.group_planner_feature_control')
        data = self.Board.with_user(supervisor).get_data(self.project.id)
        self.assertFalse(data['show_amounts'])
