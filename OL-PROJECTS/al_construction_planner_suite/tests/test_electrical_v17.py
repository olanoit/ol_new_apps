# -*- coding: utf-8 -*-
"""Contrata eléctrica (v1.7, casos de prueba por rubro).

Un tablero con dos sistemas y cuatro partidas, con control, contratas y
compras: canalización y cableado encadenados en el cronograma, la compra
masiva por partida, la contrata de cableado por punto con su OC de servicio,
el avance validado como ejecutado y el control por tablero y por sistema.
Datos de demostración inventados para la prueba.
"""
import base64
from datetime import date

from odoo import Command
from odoo.tests import tagged

from .common import PlannerCommon

PHOTO = (b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE'
         b'hQGAhKmMIQAAAABJRU5ErkJggg==')
# Cada partida: 100 m de tubo a 4.50, 150 m de cable a 2.80 y 20 puntos de
# cableado a 12.00.
PARTIDA = 100 * 4.5 + 150 * 2.8 + 20 * 12.0


@tagged('post_install', '-at_install')
class TestElectricalContractor(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Stage = cls.env['construction.stage']
        cls.duct = Stage.create({'name': 'Canalización (test)', 'code': 'test17e_duct',
                                 'sequence': 410})
        cls.wire = Stage.create({'name': 'Cableado (test)', 'code': 'test17e_wire',
                                 'sequence': 420, 'previous_stage_id': cls.duct.id})
        template = cls.env['construction.level.template'].create({
            'name': 'Contrata eléctrica (test)', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Tablero', 'role': 'group'}),
                (0, 0, {'sequence': 2, 'name': 'Sistema', 'role': 'group'}),
                (0, 0, {'sequence': 3, 'name': 'Partida', 'role': 'space', 'is_measured': True,
                        'measure_uom_id': cls.meter.id,
                        'stage_ids': [Command.set((cls.duct | cls.wire).ids)]})]})
        levels = {line.name: line for line in template.line_ids}
        cls.site = cls.env['project.project'].create({
            'name': 'Instalaciones eléctricas Clínica Sur (test)', 'is_construction_site': True,
            'construction_level_template_id': template.id})
        Task = cls.env['project.task']

        def node(name, level, parent=None):
            return Task.create({'name': name, 'project_id': cls.site.id,
                                'construction_level_line_id': levels[level].id,
                                'parent_id': parent.id if parent else False})

        cls.board = node('TG-01 Tablero general', 'Tablero')
        cls.systems = [node('Alumbrado', 'Sistema', cls.board),
                       node('Tomacorrientes', 'Sistema', cls.board)]
        cls.partidas = [
            node('IEE-01 Circuitos de alumbrado', 'Partida', cls.systems[0]),
            node('IEE-02 Luminarias', 'Partida', cls.systems[0]),
            node('IEE-03 Circuitos de tomacorrientes', 'Partida', cls.systems[1]),
            node('IEE-04 Tomacorrientes dobles', 'Partida', cls.systems[1])]
        Product = cls.env['product.product']
        cls.conduit = Product.create({'name': 'Tubo conduit 3/4" (test)', 'type': 'consu',
                                      'uom_id': cls.meter.id, 'standard_price': 4.5})
        cls.cable = Product.create({'name': 'Cable 2.5 mm² (test)', 'type': 'consu',
                                    'uom_id': cls.meter.id, 'standard_price': 2.8})
        cls.act_wiring = cls.env['construction.labor.activity'].create({
            'code': 'T17E-CAB', 'name': 'Cableado por punto (test)', 'stage': 'test17e_wire',
            'default_price': 12.0, 'uom_id': cls.unit.id})
        cls.electrician = cls.env['res.partner'].create({'name': 'Electricistas Sur (test)'})
        cls.plan = cls.env['construction.resource.plan'].create({'project_id': cls.site.id})
        values = []
        for partida in cls.partidas:
            base = {'plan_id': cls.plan.id, 'task_id': partida.id}
            values += [
                dict(base, resource_type='material', product_id=cls.conduit.id,
                     stage='test17e_duct', qty_planned=100.0, price_unit_planned=4.5,
                     product_uom_id=cls.meter.id),
                dict(base, resource_type='material', product_id=cls.cable.id,
                     stage='test17e_wire', qty_planned=150.0, price_unit_planned=2.8,
                     product_uom_id=cls.meter.id),
                dict(base, resource_type='contract', activity_id=cls.act_wiring.id,
                     stage='test17e_wire', qty_planned=20.0, price_unit_planned=12.0,
                     product_uom_id=cls.unit.id)]
        cls.env['construction.resource.plan.line'].create(values)

    def test_tree_and_schedule(self):
        root = self.plan.get_tree_nodes('root')[0]
        self.assertAlmostEqual(root['total'], 4 * PARTIDA)
        board = self.plan.get_tree_nodes('p')
        self.assertEqual([(n['name'], n['level_name']) for n in board],
                         [('TG-01 Tablero general', 'Tablero')])
        systems = {n['name']: n['total'] for n in self.plan.get_tree_nodes(str(self.board.id))}
        self.assertEqual(systems, {'Alumbrado': 2 * PARTIDA, 'Tomacorrientes': 2 * PARTIDA})
        stages = self.env['construction.space.stage']._sync_from_plan(self.plan)
        first = stages.filtered(lambda s: s.space_task_id == self.partidas[0]).sorted('sequence')
        self.assertEqual(first.mapped('stage'), ['test17e_duct', 'test17e_wire'])
        self.assertEqual(first[1].predecessor_id, first[0])

    def test_purchase_contract_and_control(self):
        self.plan.action_request_approval()
        self.assertEqual(self.plan.state, 'approved')
        # Compra masiva por partida: una línea por producto y partida.
        wizard = self.env['construction.plan.purchase.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_project=True,
        ).create({'group_by': 'task'})
        cable = wizard.line_ids.filtered(lambda l: l.product_id == self.cable)
        self.assertEqual(sorted(cable.mapped('group_label')),
                         sorted(p.display_name for p in self.partidas))
        self.assertEqual(cable.mapped('qty_need'), [150.0] * 4)
        request = self.env['purchase.request'].browse(wizard.action_create()['res_id'])
        self.assertEqual(len(request.line_ids), 8)
        self.assertAlmostEqual(sum(request.line_ids.filtered(
            lambda l: l.product_id == self.conduit).mapped('product_qty')), 400.0)
        # Contrata de cableado en todo el tablero: una OC de servicio de 80 puntos.
        contract = self.env['construction.plan.contract.wizard'].with_user(
            self.planner).with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=self.board.ids,
        ).create({'stage': 'test17e_wire', 'partner_id': self.electrician.id,
                  'date_start': date(2026, 11, 2)})
        self.assertAlmostEqual(contract.amount_total, 80 * 12.0)
        contract.action_assign()
        order = self.env['purchase.order'].search([
            ('construction_is_service_order', '=', True),
            ('partner_id', '=', self.electrician.id),
            ('construction_project_id', '=', self.site.id)])
        self.assertEqual(len(order), 1)
        self.assertAlmostEqual(sum(order.order_line.mapped('product_qty')), 80.0)
        order.button_confirm()
        # El electricista reporta 20 puntos de la primera partida y se validan.
        progress = self.env['construction.task.progress'].with_user(self.reporter).create({
            'task_id': self.partidas[0].id, 'activity_id': self.act_wiring.id,
            'date': date(2026, 11, 4), 'qty': 20.0,
            'attachment_ids': [Command.create({'name': 'tablero.jpg', 'raw': base64.b64decode(PHOTO)})]})
        progress.with_user(self.planner).action_validate()
        wiring = self.plan.line_ids.filtered(
            lambda l: l.task_id == self.partidas[0] and l.resource_type == 'contract')
        self.assertAlmostEqual(wiring.qty_executed, 20.0)
        # Control por tablero y por sistema (los niveles de la plantilla).
        Line = self.env['construction.resource.plan.line']
        self.assertEqual(set(self.plan.line_ids.mapped('level_1_id')), {self.board})
        by_system = dict(Line._read_group(
            [('plan_id', '=', self.plan.id)], ['level_2_id'], ['amount_planned:sum']))
        self.assertEqual({task.name: amount for task, amount in by_system.items()},
                         {'Alumbrado': 2 * PARTIDA, 'Tomacorrientes': 2 * PARTIDA})
