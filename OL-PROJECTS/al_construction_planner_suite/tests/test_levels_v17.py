# -*- coding: utf-8 -*-
"""Niveles de profundidad libre (v1.7, M17-01).

Una constructora arma su obra con la plantilla Disciplina › Subpartida ›
Partida › Actividad, sin unidad ni mueble: el árbol acumula los montos en
cada nivel, la ruta almacenada permite sumar cualquier nivel y la partida
programa sus etapas (trazo, emplacado, masillado) en el cronograma.
"""
from odoo.tests import tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestFreeLevels(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.m2 = cls.env.ref('uom.product_uom_square_meter')
        Stage = cls.env['construction.stage']
        cls.trace = Stage.create({'name': 'Trazo (test)', 'code': 'test17_trace',
                                  'sequence': 210})
        cls.board = Stage.create({'name': 'Emplacado (test)', 'code': 'test17_board',
                                  'sequence': 220, 'previous_stage_id': cls.trace.id})
        cls.putty = Stage.create({'name': 'Masillado (test)', 'code': 'test17_putty',
                                  'sequence': 230, 'previous_stage_id': cls.board.id})
        cls.template = cls.env['construction.level.template'].create({
            'name': 'Construcción por partidas (test)', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Disciplina', 'role': 'group'}),
                (0, 0, {'sequence': 2, 'name': 'Subpartida', 'role': 'group'}),
                (0, 0, {'sequence': 3, 'name': 'Partida', 'role': 'space', 'is_measured': True,
                        'measure_uom_id': cls.m2.id,
                        'stage_ids': [(6, 0, (cls.trace | cls.board | cls.putty).ids)]}),
                (0, 0, {'sequence': 4, 'name': 'Actividad', 'role': 'module'}),
            ]})
        cls.levels = {line.name: line for line in cls.template.line_ids}
        cls.site = cls.env['project.project'].create({
            'name': 'Oficinas Torre Lima (test)', 'is_construction_site': True,
            'construction_level_template_id': cls.template.id})
        Task = cls.env['project.task']

        def node(name, level_name, parent=None):
            return Task.create({
                'name': name, 'project_id': cls.site.id,
                'construction_level_line_id': cls.levels[level_name].id,
                'parent_id': parent.id if parent else False})

        cls.arq = node('ARQ Arquitectura', 'Disciplina')
        cls.iee = node('IEE Instalaciones eléctricas', 'Disciplina')
        cls.walls = node('ARQ-03 Tabiquería', 'Subpartida', cls.arq)
        cls.paint = node('ARQ-05 Pintura', 'Subpartida', cls.arq)
        cls.lights = node('IEE-02 Luminarias', 'Subpartida', cls.iee)
        cls.drywall = node('ARQ-03.02.01 Muro drywall RF', 'Partida', cls.walls)
        cls.latex = node('ARQ-05.01.01 Pintura látex', 'Partida', cls.paint)
        cls.led = node('IEE-02.01.01 Luminaria LED', 'Partida', cls.lights)
        cls.drywall_a = node('Muro eje A', 'Actividad', cls.drywall)
        cls.plan_site = cls.env['construction.resource.plan'].create({'project_id': cls.site.id})
        cls.board_mat = cls.env['product.product'].create({
            'name': 'Placa RF 1/2" (test)', 'type': 'consu', 'standard_price': 33.0})
        cls.plaster = cls.env['product.product'].create({
            'name': 'Masilla (test)', 'type': 'consu', 'standard_price': 24.4})
        Line = cls.env['construction.resource.plan.line']

        def line(task, stage, **vals):
            return Line.create(dict({
                'plan_id': cls.plan_site.id, 'task_id': task.id, 'stage': stage,
                'product_uom_id': cls.unit.id}, **vals))

        # Drywall: 120 m² con placa (trazo y emplacado) y masilla; mano de obra
        # de contrata en el emplacado.
        line(cls.drywall, 'test17_board', resource_type='material', product_id=cls.board_mat.id,
             qty_planned=66.0, price_unit_planned=33.0)
        line(cls.drywall, 'test17_putty', resource_type='material', product_id=cls.plaster.id,
             qty_planned=10.8, price_unit_planned=24.4)
        line(cls.drywall_a, 'test17_board', resource_type='contract',
             activity_id=cls.act_doors.id, qty_planned=120.0, price_unit_planned=28.39)
        line(cls.latex, 'test17_putty', resource_type='material', product_id=cls.plaster.id,
             qty_planned=5.0, price_unit_planned=24.4)
        line(cls.led, 'test17_trace', resource_type='material', product_id=cls.board_mat.id,
             qty_planned=2.0, price_unit_planned=33.0)

    def test_template_without_unit_or_furniture(self):
        self.assertEqual(self.template.summary, 'Disciplina › Subpartida › Partida › Actividad')
        self.assertEqual(self.levels['Disciplina'].level, 'group')
        self.assertEqual(self.levels['Subpartida'].level, 'floor')
        partida = self.levels['Partida']
        self.assertTrue(partida.has_stages)
        self.assertTrue(partida.has_recipe and partida.receives_progress)
        self.assertEqual(partida.measure_uom_id, self.m2)
        self.assertFalse(self.levels['Disciplina'].has_stages)
        self.assertEqual(self.drywall.construction_level_name, 'Partida')
        self.assertEqual(self.drywall_a.construction_level, 'module')

    def test_stored_path(self):
        self.assertEqual(self.drywall_a.construction_path, '%s/%s/%s/%s/' % (
            self.arq.id, self.walls.id, self.drywall.id, self.drywall_a.id))
        lines = self.plan_site.line_ids
        self.assertEqual(set(lines.filtered(lambda l: l.task_id == self.drywall).mapped(
            'task_path')), {self.drywall.construction_path})
        # Lo de la disciplina ARQ, sin recorrer el árbol.
        arq = self.env['construction.resource.plan.line'].search([
            ('plan_id', '=', self.plan_site.id),
            ('task_path', '=like', self.arq.construction_path + '%')])
        self.assertEqual(len(arq), 4)
        # Mover una subpartida mueve la ruta de lo que tiene debajo.
        self.walls.parent_id = self.iee
        self.assertTrue(self.drywall_a.construction_path.startswith(self.iee.construction_path))

    def test_tree_accumulates_every_level(self):
        drywall = 66 * 33.0 + 10.8 * 24.4 + 120 * 28.39
        latex = 5 * 24.4
        led = 2 * 33.0
        root = self.plan_site.get_tree_nodes('root')[0]
        self.assertAlmostEqual(root['total'], round(drywall + latex + led, 2))
        disciplines = {n['name']: n for n in self.plan_site.get_tree_nodes('p')}
        self.assertEqual(set(disciplines), {'ARQ Arquitectura', 'IEE Instalaciones eléctricas'})
        self.assertAlmostEqual(disciplines['ARQ Arquitectura']['total'],
                               round(drywall + latex, 2))
        self.assertEqual(disciplines['ARQ Arquitectura']['level_name'], 'Disciplina')
        subs = {n['name']: n for n in self.plan_site.get_tree_nodes(str(self.arq.id))}
        self.assertAlmostEqual(subs['ARQ-03 Tabiquería']['total'], round(drywall, 2))
        self.assertAlmostEqual(subs['ARQ-03 Tabiquería']['contract'], round(120 * 28.39, 2))
        partidas = self.plan_site.get_tree_nodes(str(self.walls.id))
        self.assertEqual([n['name'] for n in partidas], ['ARQ-03.02.01 Muro drywall RF'])
        self.assertAlmostEqual(partidas[0]['total'], round(drywall, 2))
        self.assertTrue(partidas[0]['has_children'])
        activity = self.plan_site.get_tree_nodes(str(self.drywall.id))[0]
        self.assertAlmostEqual(activity['total'], round(120 * 28.39, 2))

    def test_schedule_chains_the_partida_stages(self):
        Stage = self.env['construction.space.stage']
        created = Stage._sync_from_plan(self.plan_site)
        drywall = created.filtered(lambda s: s.space_task_id == self.drywall).sorted('sequence')
        self.assertEqual(drywall.mapped('stage'), ['test17_board', 'test17_putty'])
        self.assertEqual(drywall[1].predecessor_id, drywall[0])
        self.assertEqual(created.filtered(lambda s: s.space_task_id == self.led).stage,
                         'test17_trace')
        payload = self.env['al.gantt.data'].with_user(self.planner).get_data(
            [self.site.id], {'construction_schedule': True})
        levels = {task['construction']['level'] for task in payload['tasks']}
        self.assertEqual(levels, {'group', 'floor', 'space'})
        names = {task['name'] for task in payload['tasks']}
        self.assertIn('ARQ-03.02.01 Muro drywall RF', names)
        rows = [r for r in payload['construction_stages']
                if r['space_task_id'] == self.drywall.id]
        self.assertEqual({r['name'] for r in rows}, {'Emplacado (test)', 'Masillado (test)'})
        self.assertEqual(payload['construction']['stage_colors']['test17_board'], '#3d85c6')
