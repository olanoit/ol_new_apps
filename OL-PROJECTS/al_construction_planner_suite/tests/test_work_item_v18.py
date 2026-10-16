# -*- coding: utf-8 -*-
"""Receta sincronizada con los Work Items (v1.8, M18-13).

El Work Item es un modelo ``x_`` del paquete Construction que esta base no
tiene: se simula en memoria por los dos puntos por los que pasa todo acceso
(``_work_item_read`` y ``_work_item_apply``). Criterio: cambiar el
rendimiento de la cuadrilla en el Work Item marca la receta vinculada como
desactualizada; al aceptar la propuesta, la receta queda igual al Work Item y
los planes aprobados no cambian."""
import copy
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestWorkItemSync(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['tier.definition'].search(
            [('model', '=', 'construction.resource.plan')]).active = False
        cls.m2 = cls.env.ref('uom.product_uom_square_meter')
        cls.hour = cls.env.ref('uom.product_uom_hour')
        Product = cls.env['product.product']
        cls.board = Product.create({'name': 'Placa RF 1/2" (test)', 'type': 'consu',
                                    'uom_id': cls.m2.id, 'standard_price': 25.0})
        cls.operator = Product.create({'name': 'Operario (test)', 'type': 'service',
                                       'default_code': 'T18-OPE', 'uom_id': cls.hour.id})
        cls.stage = cls.env['construction.stage'].create({
            'name': 'Emplacado (test)', 'code': 'test18w_board', 'kind': 'field',
            'sequence': 610})
        cls.activity = cls.env['construction.labor.activity'].create({
            'code': 'T18-OPE', 'name': 'Operario (test)', 'stage': 'test18w_board',
            'uom_id': cls.hour.id, 'default_price': 12.0, 'product_id': cls.operator.id})
        cls.template = cls.env['construction.execution.template'].create({
            'code': 'ARQ-03.02.01', 'name': 'Muro drywall RF (test)', 'uom_id': cls.m2.id,
            'source': 'work_item', 'source_ref': 'x_work_item,19', 'line_ids': [
                (0, 0, {'resource_type': 'material', 'product_id': cls.board.id,
                        'qty': 1.05, 'price_unit': 25.0, 'product_uom_id': cls.m2.id,
                        'stage': 'test18w_board'}),
                (0, 0, {'resource_type': 'labor', 'activity_id': cls.activity.id,
                        'qty': 0.042105, 'price_unit': 12.0, 'product_uom_id': cls.hour.id,
                        'stage': 'test18w_board'})]})

    def setUp(self):
        super().setUp()
        self.items = {19: {'name': 'Muro drywall RF', 'product_id': False,
                           'uom_id': self.m2.id, 'lines': [
                               {'id': 191, 'product_id': self.board.id, 'qty': 1.05,
                                'cost': 25.0, 'nature': 'material'},
                               {'id': 192, 'product_id': self.operator.id, 'qty': 0.042105,
                                'cost': 12.0, 'nature': 'labour'}]}}
        Template = self.registry['construction.execution.template']
        test = self

        def read(self, item_ids):
            return {item_id: copy.deepcopy(test.items[item_id])
                    for item_id in item_ids if item_id in test.items}

        def apply(self, item_id, changes):
            item = test.items[item_id]
            for line in item['lines']:
                if line['id'] in changes.get('update', {}):
                    line.update(changes['update'][line['id']])
            item['lines'] = [line for line in item['lines']
                             if line['id'] not in changes.get('unlink', [])]
            created = {}
            for index, vals in enumerate(changes.get('create', [])):
                created[index] = 900 + index
                item['lines'].append(dict(vals, id=900 + index))
            return created

        for name, method in (('_work_item_available', lambda self: True),
                             ('_work_item_read', read), ('_work_item_apply', apply)):
            patcher = patch.object(Template, name, method)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.template._link_work_item(19)

    def test_work_item_change_reaches_the_recipe(self):
        self.assertEqual(self.template.sync_state, 'synced')
        self.assertEqual(sorted(self.template.line_ids.mapped('work_item_line_id')), [191, 192])
        # Un plan aprobado con la receta de hoy.
        site = self.env['project.project'].create({'name': 'Oficinas (test)',
                                                   'is_construction_site': True})
        plan = self.env['construction.resource.plan'].create({'project_id': site.id})
        labor = self.env['construction.resource.plan.line'].create({
            'plan_id': plan.id, 'resource_type': 'labor', 'activity_id': self.activity.id,
            'stage': 'test18w_board', 'qty_planned': 5.05, 'price_unit_planned': 12.0,
            'product_uom_id': self.hour.id, 'source': 'recipe'})
        plan.action_request_approval()
        self.assertEqual(plan.state, 'approved')
        # Cambia el rendimiento de la cuadrilla en el Work Item.
        self.items[19]['lines'][1]['qty'] = 0.05
        self.template.action_check_work_items()
        self.assertEqual(self.template.sync_state, 'work_item')
        action = self.template.action_open_sync_wizard()
        wizard = self.env[action['res_model']].browse(action['res_id'])
        self.assertEqual(wizard.direction, 'to_template')
        self.assertIn('0.042105', str(wizard.preview_html))
        wizard.action_apply()
        line = self.template.line_ids.filtered('activity_id')
        self.assertAlmostEqual(line.qty, 0.05)
        self.assertEqual(self.template.sync_state, 'synced')
        self.assertAlmostEqual(labor.qty_planned, 5.05)

    def test_recipe_change_goes_to_the_work_item(self):
        material = self.template.line_ids.filtered('product_id')
        material.qty = 1.10
        self.assertEqual(self.template.sync_state, 'template')
        action = self.template.action_open_sync_wizard()
        wizard = self.env[action['res_model']].browse(action['res_id'])
        self.assertEqual(wizard.direction, 'to_work_item')
        wizard.action_apply()
        self.assertAlmostEqual(self.items[19]['lines'][0]['qty'], 1.10)
        self.assertEqual(self.template.sync_state, 'synced')
        # Los dos cambian: queda marcada y la propuesta es elegir el sentido.
        self.items[19]['lines'][0]['cost'] = 27.0
        material.price_unit = 26.0
        self.assertEqual(self.template.sync_state, 'both')

    def test_new_resource_in_the_work_item(self):
        screw = self.env['product.product'].create({'name': 'Tornillo 6x1 (test)',
                                                    'type': 'consu', 'standard_price': 0.05})
        self.items[19]['lines'].append({'id': 193, 'product_id': screw.id, 'qty': 18.0,
                                        'cost': 0.05, 'nature': 'material'})
        self.template.action_check_work_items()
        self.assertEqual(self.template.sync_state, 'work_item')
        rows = self.template._sync_differences(self.items[19])
        self.assertEqual([row['kind'] for row in rows], ['only_work_item'])
        wizard = self.env['construction.work.item.sync.wizard'].create({
            'template_id': self.template.id, 'direction': 'to_template'})
        wizard.action_apply()
        added = self.template.line_ids.filtered(lambda l: l.product_id == screw)
        self.assertEqual(added.work_item_line_id, 193)
        self.assertEqual(self.template.sync_state, 'synced')
