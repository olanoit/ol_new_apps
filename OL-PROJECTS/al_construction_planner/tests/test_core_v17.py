# -*- coding: utf-8 -*-
"""El núcleo solo (v1.7, M17-07): sin Fabricación, Ventas ni Requerimiento de
compra genera un plan desde la receta y lo aprueba.

Las pruebas de integración del planificador con todos sus puentes están en
al_construction_planner_suite."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCoreAlone(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['tier.definition'].search(
            [('model', '=', 'construction.resource.plan')]).active = False
        cls.m2 = cls.env.ref('uom.product_uom_square_meter')
        cls.unit = cls.env.ref('uom.product_uom_unit')
        stage = cls.env['construction.stage'].create({
            'name': 'Emplacado (núcleo)', 'code': 'core17_board', 'kind': 'field'})
        cls.template = cls.env['construction.level.template'].create({
            'name': 'Partidas (núcleo)', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Disciplina', 'role': 'group'}),
                (0, 0, {'sequence': 2, 'name': 'Partida', 'role': 'space'})]})
        levels = {line.name: line for line in cls.template.line_ids}
        cls.site = cls.env['project.project'].create({
            'name': 'Obra del núcleo (test)', 'is_construction_site': True,
            'construction_level_template_id': cls.template.id})
        Task = cls.env['project.task']
        discipline = Task.create({'name': 'ARQ', 'project_id': cls.site.id,
                                  'construction_level_line_id': levels['Disciplina'].id})
        board = cls.env['product.product'].create({
            'name': 'Placa (núcleo)', 'type': 'consu', 'standard_price': 30.0})
        activity = cls.env['construction.labor.activity'].create({
            'code': 'CORE17-MO', 'name': 'Emplacado (núcleo)', 'stage': stage.code,
            'uom_id': cls.m2.id, 'default_price': 12.0})
        recipe = cls.env['construction.execution.template'].create({
            'code': 'CORE17', 'name': 'Muro (núcleo)', 'uom_id': cls.m2.id,
            'line_ids': [
                (0, 0, {'resource_type': 'material', 'product_id': board.id, 'qty': 0.5,
                        'product_uom_id': cls.unit.id, 'stage': stage.code}),
                (0, 0, {'resource_type': 'contract', 'activity_id': activity.id, 'qty': 1.0,
                        'product_uom_id': cls.m2.id, 'stage': stage.code}),
            ]})
        cls.partida = Task.create({
            'name': 'ARQ-01 Muro', 'project_id': cls.site.id, 'parent_id': discipline.id,
            'construction_level_line_id': levels['Partida'].id,
            'construction_execution_template_id': recipe.id, 'construction_qty': 100.0})
        cls.plan = cls.env['construction.resource.plan'].create({'project_id': cls.site.id})

    def test_generate_and_approve_without_bridges(self):
        self.env['construction.plan.recipe.wizard'].create(
            {'plan_id': self.plan.id}).action_generate()
        self.assertEqual(len(self.plan.line_ids), 2)
        self.assertAlmostEqual(self.plan.amount_total, 100 * 0.5 * 30.0 + 100 * 12.0)
        self.plan.action_request_approval()
        self.assertEqual(self.plan.state, 'approved')
        self.assertTrue(all(self.plan.line_ids.mapped('amount_budgeted')))
        self.assertEqual(set(self.plan.line_ids.mapped('amount_baseline')),
                         set(self.plan.line_ids.mapped('amount_planned')))
        stages = self.env['construction.space.stage'].search([('project_id', '=', self.site.id)])
        self.assertEqual(stages.mapped('stage'), ['core17_board'])
