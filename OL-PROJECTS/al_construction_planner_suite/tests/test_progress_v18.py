# -*- coding: utf-8 -*-
"""Avance por driver de la partida (v1.8, M18-12) y avance en formulario con
trazabilidad (M18-11).

Una partida de muro drywall de 120 m²: la instalación del muro se mide en el
driver de la partida y el emplacado en su propio driver (m² de placa, el
doble). Con 48 m² de muro ejecutados la partida va al 40 %; el emplacado
avanza y se liquida por su cantidad sin mover el avance de la partida.
Datos de demostración inventados para la prueba."""

from odoo import Command
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

PHOTO = (b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE'
         b'hQGAhKmMIQAAAABJRU5ErkJggg==')


@tagged('post_install', '-at_install')
class TestPartidaDriver(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['tier.definition'].search(
            [('model', '=', 'construction.resource.plan')]).active = False
        cls.m2 = cls.env.ref('uom.product_uom_square_meter')
        cls.unit = cls.env.ref('uom.product_uom_unit')
        Stage = cls.env['construction.stage']
        cls.stage = Stage.create({'name': 'Ejecución drywall (test)', 'code': 'test18_dry',
                                  'kind': 'field', 'sequence': 510})
        template = cls.env['construction.level.template'].create({
            'name': 'Partidas drywall (test)', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Subpartida', 'role': 'group'}),
                (0, 0, {'sequence': 2, 'name': 'Partida', 'role': 'space',
                        'measure_uom_id': cls.m2.id,
                        'stage_ids': [Command.set(cls.stage.ids)]})]})
        levels = {line.name: line for line in template.line_ids}
        cls.site = cls.env['project.project'].create({
            'name': 'Oficinas Miraflores (test)', 'is_construction_site': True,
            'construction_level_template_id': template.id})
        Task = cls.env['project.task']
        cls.group = Task.create({'name': 'ARQ-03 Tabiquería', 'project_id': cls.site.id,
                                 'construction_level_line_id': levels['Subpartida'].id})
        cls.partida = Task.create({
            'name': 'Muro drywall RF', 'project_id': cls.site.id, 'parent_id': cls.group.id,
            'construction_level_line_id': levels['Partida'].id, 'construction_qty': 120.0})
        Activity = cls.env['construction.labor.activity']
        cls.act_wall = Activity.create({
            'code': 'T18-MURO', 'name': 'Muro drywall instalado (test)', 'stage': 'test18_dry',
            'uom_id': cls.m2.id, 'default_price': 30.0, 'driver_source': 'level'})
        cls.act_board = Activity.create({
            'code': 'T18-PLACA', 'name': 'Emplacado (test)', 'stage': 'test18_dry',
            'uom_id': cls.m2.id, 'default_price': 8.0})
        cls.contractor = cls.env['res.partner'].create({'name': 'Drywall Lima (test)'})
        cls.plan = cls.env['construction.resource.plan'].create({'project_id': cls.site.id})
        Line = cls.env['construction.resource.plan.line']
        base = {'plan_id': cls.plan.id, 'task_id': cls.partida.id, 'stage': 'test18_dry',
                'resource_type': 'contract', 'partner_id': cls.contractor.id,
                'product_uom_id': cls.m2.id}
        cls.wall = Line.create(dict(base, activity_id=cls.act_wall.id, qty_planned=120.0,
                                    price_unit_planned=30.0))
        cls.board = Line.create(dict(base, activity_id=cls.act_board.id, qty_planned=240.0,
                                     price_unit_planned=8.0))
        cls.plan.action_request_approval()
        cls.supervisor = new_test_user(
            cls.env, 'plan18_supervisor', name='Supervisor (test)',
            groups='al_construction_planner.group_planner_planner')

    def _progress(self, line, qty, user=None):
        Progress = self.env['construction.task.progress'].with_user(user or self.supervisor)
        return Progress.create({
            'task_id': line.task_id.id, 'activity_id': line.activity_id.id, 'qty': qty,
            'attachment_ids': [Command.create({'name': 'avance.png', 'datas': PHOTO})]})

    def test_partida_progress_by_its_driver(self):
        self.assertTrue(self.wall.uses_level_driver)
        self.assertFalse(self.board.uses_level_driver)
        self.assertEqual(self.partida.construction_driver_uom_id, self.m2)
        self._progress(self.wall, 48.0).action_validate()
        self._progress(self.board, 60.0).action_validate()
        self.partida.invalidate_recordset()
        self.assertAlmostEqual(self.partida.construction_driver_progress_pct, 0.40)
        self.assertAlmostEqual(self.partida.construction_driver_qty_executed, 48.0)
        # El emplacado avanza en su propio driver.
        self.assertAlmostEqual(self.board.progress_pct, 0.25)
        self.assertAlmostEqual(self.board.qty_executed, 60.0)
        node = self.plan.get_tree_nodes(str(self.group.id))[0]
        self.assertEqual(node['task_id'], self.partida.id)
        self.assertAlmostEqual(node['progress'], 0.40)

    def test_progress_traceability(self):
        """M18-11: el avance con su foto se abre en formulario, la foto está en
        el chatter, el supervisor evalúa y valida, todo con autor y fecha."""
        progress = self._progress(self.wall, 12.0)
        report = progress.message_ids.filtered(lambda m: m.attachment_ids)
        self.assertEqual(len(report), 1)
        self.assertEqual(report.author_id, self.supervisor.partner_id)
        self.assertEqual(report.attachment_ids, progress.attachment_ids)
        # Mail no sigue los cambios de un registro creado en la misma
        # transacción: se cierra como si el avance se hubiera guardado antes.
        self.env.flush_all()
        self.env.cr.precommit.run()
        progress.with_user(self.supervisor).write({
            'supervisor_evaluation': 'observed',
            'evaluation_note': 'Falta masillar las juntas del eje 3.'})
        progress.with_user(self.supervisor).action_validate()
        bodies = ' '.join(progress.message_ids.mapped('body'))
        self.assertIn('Validado', bodies)
        # El seguimiento de campos se escribe en el precommit.
        self.env.flush_all()
        self.env.cr.precommit.run()
        tracked = progress.sudo().message_ids.tracking_value_ids.mapped('field_id.name')
        self.assertIn('supervisor_evaluation', tracked)
        self.assertIn('state', tracked)
        rejected = self._progress(self.wall, 6.0)
        rejected.with_user(self.supervisor)._action_reject('Fotos de otra partida')
        self.assertIn('Fotos de otra partida', ' '.join(rejected.message_ids.mapped('body')))
