# -*- coding: utf-8 -*-
"""Productos del proyecto y envíos (v1.8, M18-15 y M18-16), metrado como
receta real (M17-15) y versus con autorización en producción (M17-20)."""
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestModuleProductsV18(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Product = cls.env['product.product']
        cls.board = Product.create({'name': 'Melamina blanca (test v18p)', 'type': 'consu',
                                    'standard_price': 100.0})
        cls.hinge = Product.create({'name': 'Bisagra (test v18p)', 'type': 'consu',
                                    'standard_price': 5.0})
        cls.typology_p = cls.env['construction.typology'].create({
            'project_id': cls.project.id, 'code': 'C10', 'name': 'COCINA 10 (test)',
            'family': 'kitchen', 'module_line_ids': [Command.create({
                'code': 'MB1', 'name': 'MOD BAJO 600', 'module_type': 'low', 'width_mm': 600,
                'ml_group': 'low', 'assembly_activity_id': cls.act_screw.id,
                'material_ids': [
                    Command.create({'product_id': cls.board.id, 'qty': 1.0,
                                    'stage': 'production'}),
                    Command.create({'product_id': cls.hinge.id, 'qty': 4.0,
                                    'stage': 'assembly'})]})]})
        cls.space_p = cls.task('Cocina 503', 'space', cls.apt_502,
                               construction_typology_id=cls.typology_p.id)
        cls.head = new_test_user(
            cls.env, 'plan18_jefatura_p', name='Jefatura (test)',
            groups='al_construction_planner.group_planner_manager,'
                   'al_construction_planner.group_planner_project_head,mrp.group_mrp_user')
        cls._generate_and_approve(space_task_ids=[Command.set(cls.space_p.ids)])

    @classmethod
    def _generate_and_approve(cls, **vals):
        wizard = cls.env['construction.plan.generate.wizard'].create(
            dict({'plan_id': cls.plan.id}, **vals))
        wizard.action_generate()
        lines = cls.plan.line_ids
        lines.filtered(lambda l: not l.stage).stage = 'production'
        for line in lines.filtered(lambda l: not l.price_unit_planned):
            line.price_unit_planned = 10.0
        cls.plan.action_request_approval()

    def _module_task(self):
        return self.env['project.task'].search([
            ('construction_space_task_id', '=', self.space_p.id),
            ('construction_level', '=', 'module')])

    def test_products_per_module_with_bom_and_lot(self):
        """Criterio M18-15: al aprobar el plan existen los productos de sus
        módulos con su lista de materiales y la OF los produce con el lote del
        departamento."""
        template = self.typology_p.module_line_ids
        product = template.product_id
        self.assertTrue(product)
        self.assertEqual(product.tracking, 'lot')
        self.assertIn('C10-MB1', product.default_code)
        self.assertEqual(product.product_tmpl_id.construction_project_id, self.project)
        attributes = product.product_tmpl_id.attribute_line_ids.attribute_id.mapped('name')
        self.assertIn('Tipo de módulo', attributes)
        bom = self.env['mrp.bom']._bom_find(product)[product]
        self.assertEqual(bom.bom_line_ids.product_id, self.board | self.hinge)
        action = self.plan.action_create_module_productions(self.apt_502)
        production = self.env['mrp.production'].search(action['domain'])
        self.assertEqual(production.product_id, product)
        self.assertEqual(production.lot_producing_ids.name,
                         '%s %s' % (self.project.name, self.apt_502.name))
        self.assertEqual(production.construction_module_task_ids, self._module_task())

    def test_shipment_to_site(self):
        """Criterio M18-16: el envío de los módulos de un departamento genera su
        transferencia; al recibirla, los módulos pasan a «En obra»."""
        product = self.typology_p.module_line_ids.product_id
        lot = self.plan._department_lot(product, self.apt_502)
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.plan.company_id.id)], limit=1)
        self.env['stock.quant']._update_available_quantity(
            product, warehouse.lot_stock_id, 1.0, lot_id=lot)
        module = self._module_task()
        module.construction_unit_state = 'produced'
        picking = self.plan.action_ship_modules(self.apt_502)
        self.assertEqual(picking.construction_project_id, self.project)
        self.assertEqual(module.construction_shipment_picking_id, picking)
        picking.action_confirm()
        picking.action_assign()
        self.assertEqual(picking.move_ids.move_line_ids.lot_id, lot)
        self.assertEqual(module.construction_shipment_state, 'in_transit')
        picking.move_ids.quantity = 1.0
        picking.button_validate()
        self.assertEqual(module.construction_unit_state, 'on_site')
        self.assertEqual(module.construction_shipment_state, 'on_site')

    def test_real_recipe_versus_and_threshold(self):
        """M17-15 y criterio de M17-20: planificado y real lado a lado; con 8 %
        sobre lo planificado producción sigue, con 12 % espera a la jefatura."""
        module = self._module_task()
        Recipe = self.env['construction.real.recipe']
        # Planificado: 1 × 100 + 4 × 5 = 120.
        small = Recipe.create({'task_id': module.id, 'line_ids': [
            Command.create({'product_id': self.board.id, 'qty': 1.0}),
            Command.create({'product_id': self.hinge.id, 'qty': 4.0 + 9.6 / 5})]})
        self.assertEqual(small.template_id, self.typology_p.module_line_ids)
        self.assertAlmostEqual(small.difference_pct, 8.0)
        self.assertIn('Bisagra', str(small.comparison_html))
        small.action_confirm()
        self.assertFalse(small.needs_authorization)
        self.assertEqual(len(small.versus_ids), 2)
        product = self.typology_p.module_line_ids.product_id
        bom = self.env['mrp.bom']._bom_find(product)[product]
        self.assertAlmostEqual(bom.bom_line_ids.filtered(
            lambda l: l.product_id == self.hinge).product_qty, 4.0 + 9.6 / 5, places=2)
        small.action_draft()
        small.line_ids.filtered(lambda l: l.product_id == self.hinge).qty = 4.0 + 14.4 / 5
        small.action_confirm()
        self.assertAlmostEqual(small.difference_pct, 12.0)
        self.assertTrue(small.needs_authorization)
        action = self.plan.action_create_module_productions(self.apt_502)
        production = self.env['mrp.production'].search(action['domain'])
        with self.assertRaises(UserError):
            production.action_confirm()
        with self.assertRaises(UserError):
            small.with_user(self.planner).action_authorize()
        small.with_user(self.head).action_authorize()
        production.action_confirm()
        self.assertEqual(production.state, 'confirmed')
