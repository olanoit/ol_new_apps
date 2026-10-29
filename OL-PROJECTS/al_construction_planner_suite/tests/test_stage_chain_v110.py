# -*- coding: utf-8 -*-
"""Fabricación por etapas (paquete 1.10, M110-01 a M110-06 y M110-09).

Dos plantas de prueba: el corte (producción de piezas) entrega un paquete de
piezas al armado. La cocina C07 tiene dos módulos con materiales de
producción de piezas, armado e instalación; el tornillo está en armado y en
instalación. El closet CL01B solo tiene corte."""

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tools import BinaryBytes

from odoo.addons.al_construction_planner_furniture.wizards.master_import_layout import (
    build_workbook)

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestStageChainV110(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Warehouse = cls.env['stock.warehouse']
        cls.wh_cut = Warehouse.create({
            'name': 'Planta de corte (test v110)', 'code': 'TV1C', 'company_id': cls.company.id})
        cls.wh_asm = Warehouse.create({
            'name': 'Planta de armado (test v110)', 'code': 'TV1A', 'company_id': cls.company.id})
        cls.route_mto = cls.env.ref('stock.route_warehouse0_mto')
        cls.route_mto.active = True
        cls.package_categ = cls.env['product.category'].create({
            'name': 'Paquetes de piezas (test v110)',
            # Odoo 20: «Fabricar» es de almacén (se aplica con la lista de materiales).
            'route_ids': [Command.set(cls.route_mto.ids)]})
        Stage = cls.env['construction.stage']
        cls.stage_cut = Stage._by_code(['production'])
        cls.stage_asm = Stage._by_code(['assembly'])
        cls.stage_cut.with_company(cls.company).write({
            'production_picking_type_id': cls.wh_cut.manu_type_id.id,
            'intermediate_categ_id': cls.package_categ.id})
        cls.stage_asm.with_company(cls.company).production_picking_type_id = \
            cls.wh_asm.manu_type_id
        cls.stage_asm.accessory_request = True

        Product = cls.env['product.product']
        cls.board = Product.create({'name': 'Melamina blanca (test v110)', 'type': 'consu',
                                    'default_code': 'V110-MEL', 'standard_price': 100.0})
        cls.screw = Product.create({'name': 'Tornillo 4x30 (test v110)', 'type': 'consu',
                                    'default_code': 'V110-TOR', 'standard_price': 0.1})
        cls.hinge = Product.create({'name': 'Bisagra (test v110)', 'type': 'consu',
                                    'default_code': 'V110-BIS', 'standard_price': 5.0})
        cls.site = cls.env['project.project'].create({
            'name': 'Obra Montecarmelo (test v110)', 'is_construction_site': True})

    # ------------------------------------------------------------------
    # Ayudas
    # ------------------------------------------------------------------
    @staticmethod
    def _rows():
        bom = [
            ('C07', 'MB1', 'V110-MEL', 2, 'Producción'),
            ('C07', 'MB1', 'V110-TOR', 4, 'Armado'),
            ('C07', 'MB1', 'V110-TOR', 54, 'Instalación'),
            ('C07', 'MB1', 'V110-BIS', 2, 'Armado'),
            ('C07', 'MB2', 'V110-MEL', 1, 'Producción'),
            ('C07', 'MB2', 'V110-BIS', 2, 'Armado'),
            ('CL01B', 'MC1', 'V110-MEL', 1, 'Producción'),
        ]
        return {
            'TIPOLOGIAS': [
                {'code': 'C07', 'name': 'COCINA 07', 'family': 'Cocina',
                 'product': 'COCINA 07 (test v110)'},
                {'code': 'CL01B', 'name': 'CLOSET 01B', 'family': 'Closet',
                 'product': 'CLOSET 01B (test v110)'}],
            'MODULOS': [
                {'typology': 'C07', 'sequence': 1, 'code': 'MB1', 'type': 'Bajo',
                 'name': 'MOD BAJO CAJONERA'},
                {'typology': 'C07', 'sequence': 2, 'code': 'MB2', 'type': 'Bajo',
                 'name': 'MOD BAJO 420'},
                {'typology': 'CL01B', 'sequence': 1, 'code': 'MC1', 'type': 'Otro',
                 'name': 'CUERPO CLOSET'}],
            'BOM': [{'typology': typology, 'module': module, 'product_code': code, 'qty': qty,
                     'stage': stage} for typology, module, code, qty, stage in bom],
            'ARBOL': [
                {'floor': 'Piso 3', 'apartment': 'Dpto 301', 'space': 'Cocina', 'typology': 'C07'},
                {'floor': 'Piso 3', 'apartment': 'Dpto 301', 'space': 'Closet',
                 'typology': 'CL01B'},
                {'floor': 'Piso 3', 'apartment': 'Dpto 302', 'space': 'Cocina', 'typology': 'C07'},
                {'floor': 'Piso 4', 'apartment': 'Dpto 401', 'space': 'Cocina', 'typology': 'C07'}],
        }

    def _import(self, site=None):
        wizard = self.env['construction.master.import.wizard'].create({
            'project_id': (site or self.site).id,
            'file': BinaryBytes(build_workbook(self._rows())), 'filename': 'maestro.xlsx'})
        data = wizard._analyze()
        self.assertFalse(data['errors'])
        wizard.action_import()
        return data

    def _typology(self, code, site=None):
        return self.env['construction.typology'].search(
            [('project_id', '=', (site or self.site).id), ('code', '=', code)])

    def _site_plan(self, site=None, approve=True):
        plan = self.env['construction.resource.plan'].create({'project_id': (site or self.site).id})
        self.env['construction.plan.generate.wizard'].create(
            {'plan_id': plan.id}).action_generate()
        if approve:
            lines = plan.line_ids
            lines.filtered(lambda l: not l.stage).stage = 'production'
            for line in lines.filtered(lambda l: not l.price_unit_planned):
                line.price_unit_planned = 10.0
            plan.action_request_approval()
            self.assertEqual(plan.state, 'approved')
        return plan

    def _materials(self, plan):
        result = {}
        for line in plan.line_ids.filtered(lambda l: l.resource_type == 'material'):
            key = (line.product_id.default_code, line.stage)
            result[key] = result.get(key, 0.0) + line.qty_planned
        return result

    def _productions(self, plan, **vals):
        wizard = self.env['construction.plan.production.wizard'].with_context(
            default_plan_id=plan.id, construction_selection_project=True).create(vals)
        wizard.action_create()
        return self.env['mrp.production'].search([
            ('construction_plan_id', '=', plan.id), ('construction_parent_id', '=', False)])

    def _space(self, apartment, name='Cocina'):
        return self.env['project.task'].search([
            ('project_id', '=', self.site.id), ('construction_level', '=', 'space'),
            ('name', '=', name), ('construction_apartment_task_id.name', '=', apartment)])

    def _modules(self, apartment, name='Cocina'):
        return self.env['project.task'].search([
            ('construction_space_task_id', '=', self._space(apartment, name).id),
            ('construction_level', '=', 'module')], order='id')

    # ------------------------------------------------------------------
    # M110-01
    # ------------------------------------------------------------------
    def test_production_chain(self):
        Stage = self.env['construction.stage']
        self.assertEqual(Stage._production_chain(self.company), self.stage_cut | self.stage_asm)
        self.assertEqual(Stage._production_chain(self.company)[0], self.stage_cut)
        self.stage_cut.with_company(self.company).production_picking_type_id = False
        self.assertEqual(Stage._production_chain(self.company), self.stage_asm)
        other = self.env['res.company'].create({'name': 'Otra compañía (test v110)'})
        self.assertFalse(Stage._production_chain(other))
        self.stage_asm.with_company(self.company).production_picking_type_id = False
        self.assertFalse(Stage._production_chain(self.company))

    # ------------------------------------------------------------------
    # M110-02
    # ------------------------------------------------------------------
    def test_import_builds_stage_boms(self):
        self._import()
        c07 = self._typology('C07')
        recipe = c07.bom_id
        self.assertEqual(recipe.sequence, 1000)
        screws = recipe.bom_line_ids.filtered(lambda l: l.product_id == self.screw)
        self.assertEqual(sorted((l.construction_consumption_stage, l.product_qty) for l in screws),
                         [('assembly', 4), ('installation', 54)])
        final = c07.production_bom_id
        self.assertEqual(final.sequence, 1)
        self.assertEqual(final.picking_type_id, self.wh_asm.manu_type_id)
        self.assertEqual(final.project_id, self.site)
        package_line = final.bom_line_ids.filtered('construction_intermediate')
        package = package_line.product_id
        self.assertEqual(package.default_code,
                         '%s-C07-PRODUCTION' % c07._construction_project_prefix())
        self.assertEqual(package.categ_id, self.package_categ)
        self.assertEqual(package.product_tmpl_id.construction_project_id, self.site)
        others = final.bom_line_ids - package_line
        self.assertEqual({(l.product_id, l.construction_consumption_stage, l.product_qty)
                          for l in others},
                         {(self.screw, 'assembly', 4), (self.hinge, 'assembly', 4)})
        cut = self.env['mrp.bom']._bom_find(package)[package]
        self.assertEqual(cut.picking_type_id, self.wh_cut.manu_type_id)
        self.assertEqual([(l.product_id, l.product_qty) for l in cut.bom_line_ids],
                         [(self.board, 3)])
        # Odoo elige la lista de fabricación y no la receta.
        product = c07.product_tmpl_id.product_variant_id
        self.assertEqual(self.env['mrp.bom']._bom_find(product)[product], final)
        # Closet sin armado: su lista de fabricación es la de corte.
        closet = self._typology('CL01B')
        self.assertEqual(closet.production_bom_id.picking_type_id, self.wh_cut.manu_type_id)
        self.assertFalse(closet.production_bom_id.bom_line_ids.filtered('construction_intermediate'))

    def test_reimport_keeps_operations_and_does_not_duplicate(self):
        self._import()
        c07 = self._typology('C07')
        final = c07.production_bom_id
        workcenter = self.env['mrp.workcenter'].create({'name': 'Armado (test v110)'})
        final.operation_ids = [Command.create({
            'name': 'Armado', 'workcenter_id': workcenter.id, 'time_cycle_manual': 60})]
        prefix = c07._construction_project_prefix()

        def snapshot():
            products = self.env['product.product'].with_context(active_test=False).search(
                [('default_code', '=like', prefix + '-%')])
            return (len(products), self.env['mrp.bom'].search_count(
                [('product_tmpl_id', 'in', (products.product_tmpl_id | c07.product_tmpl_id).ids)]),
                len(final.bom_line_ids))

        before = snapshot()
        self._import()
        self.assertEqual(snapshot(), before)
        self.assertEqual(c07.production_bom_id, final)
        self.assertEqual(final.operation_ids.workcenter_id, workcenter)

    def test_import_without_chain_is_unchanged(self):
        for stage in self.stage_cut | self.stage_asm:
            stage.with_company(self.company).production_picking_type_id = False
        self._import()
        c07 = self._typology('C07')
        self.assertNotEqual(c07.bom_id.sequence, 1000)
        self.assertFalse(c07.production_bom_id)

    def test_plan_materials_do_not_depend_on_chain(self):
        self._import()
        with_chain = self._materials(self._site_plan(approve=False))
        for stage in self.stage_cut | self.stage_asm:
            stage.with_company(self.company).production_picking_type_id = False
        other = self.env['project.project'].create({
            'name': 'Obra sin cadena (test v110)', 'is_construction_site': True})
        self._import(other)
        self.assertEqual(self._materials(self._site_plan(other, approve=False)), with_chain)
        self.assertEqual(with_chain[('V110-TOR', 'assembly')], 4 * 3)
        self.assertEqual(with_chain[('V110-TOR', 'installation')], 54 * 3)

    def test_module_byproducts(self):
        self._import()
        self._site_plan()
        c07 = self._typology('C07')
        byproducts = c07.production_bom_id.byproduct_ids
        self.assertEqual(byproducts.product_id, c07.module_line_ids.product_id)
        self.assertAlmostEqual(sum(byproducts.mapped('cost_share')), 100.0)
        # Lista del producto de módulo: sin instalación y en la planta del armado.
        mb1 = c07.module_line_ids.filtered(lambda m: m.code == 'MB1').product_id
        bom = self.env['mrp.bom']._bom_find(mb1)[mb1]
        self.assertNotIn('installation', bom.bom_line_ids.mapped('construction_consumption_stage'))
        self.assertEqual(bom.picking_type_id, self.wh_asm.manu_type_id)

    # ------------------------------------------------------------------
    # M110-03 y M110-04
    # ------------------------------------------------------------------
    def test_orders_without_forced_plant_and_child_inherits_plan(self):
        self._import()
        plan = self._site_plan()
        productions = self._productions(plan)
        c07 = self._typology('C07')
        kitchens = productions.filtered(lambda p: p.bom_id == c07.production_bom_id)
        closet = productions - kitchens
        self.assertEqual(len(kitchens), 2, 'una por piso')
        self.assertEqual(kitchens.picking_type_id, self.wh_asm.manu_type_id)
        self.assertEqual(closet.picking_type_id, self.wh_cut.manu_type_id)
        floor_3 = kitchens.filtered(lambda p: p.product_qty == 2)
        self.assertEqual(floor_3.construction_module_task_ids,
                         self._modules('Dpto 301') | self._modules('Dpto 302'))
        # Las dos madres confirmadas juntas: una hija para cada una.
        kitchens.action_confirm()
        children = self.env['mrp.production'].search(
            [('construction_parent_id', 'in', kitchens.ids)])
        self.assertEqual(len(children), 2)
        for child in children:
            mother = child.construction_parent_id
            self.assertEqual(child.picking_type_id, self.wh_cut.manu_type_id)
            self.assertEqual(child.construction_plan_id, plan)
            self.assertEqual(child.construction_space_task_ids, mother.construction_space_task_ids)
            self.assertEqual(child.project_id, self.site)
            self.assertFalse(child.construction_module_task_ids)
            self.assertNotEqual(child.state, 'draft')
            # Cada orden compara solo sus etapas; el paquete no es cambio de material.
            self.assertEqual(child._construction_order_stages(), ('production',))
            self.assertEqual({v['product_id'] for v in child._construction_versus_values()},
                             {self.board.id})
            values = mother._construction_versus_values()
            self.assertEqual({v['product_id'] for v in values}, {self.screw.id, self.hinge.id})
            self.assertFalse([v for v in values if v['change_type']])
            self.assertEqual(mother.construction_exceed_state, 'ok')
            # Accesorios a pedido solo en el armado.
            self.assertTrue(mother._construction_assembly_plan_lines())
            self.assertFalse(child._construction_assembly_plan_lines())
            allocations = child.construction_allocation_ids
            self.assertEqual(set(allocations.plan_line_id.mapped('stage')), {'production'})
            self.assertEqual(set(mother.construction_allocation_ids.plan_line_id.mapped('stage')),
                             {'assembly'})

    def test_forced_plant(self):
        self._import()
        plan = self._site_plan()
        productions = self._productions(plan, picking_type_id=self.wh_cut.manu_type_id.id)
        self.assertEqual(productions.picking_type_id, self.wh_cut.manu_type_id)

    def test_child_excess_does_not_block_mother(self):
        self._import()
        plan = self._site_plan()
        plan.sudo().exceed_policy = 'block'
        c07 = self._typology('C07')
        package = c07.production_bom_id.bom_line_ids.filtered('construction_intermediate').product_id
        cut = self.env['mrp.bom']._bom_find(package)[package]
        cut.bom_line_ids.product_qty = 5
        mother = self._productions(plan).filtered(
            lambda p: p.bom_id == c07.production_bom_id and p.product_qty == 1)
        mother.action_confirm()
        self.assertEqual(mother.state, 'confirmed')
        child = self.env['mrp.production'].search([('construction_parent_id', '=', mother.id)])
        self.assertEqual(child.construction_exceed_state, 'exceeded')
        self.assertTrue(mother.message_ids.filtered(lambda m: 'pide más' in (m.body or '')))

    # ------------------------------------------------------------------
    # M110-05 y M110-09
    # ------------------------------------------------------------------
    def test_module_lot_pattern(self):
        self._import()
        plan = self._site_plan()
        c07 = self._typology('C07')
        mb1, mb2 = (c07.module_line_ids.filtered(lambda m, c=code: m.code == c).product_id
                    for code in ('MB1', 'MB2'))
        apartment = self._space('Dpto 301').construction_apartment_task_id
        self.assertEqual(plan._module_lot(mb1, apartment).name,
                         '%s %s' % (self.site.name, apartment.name))
        self.company.construction_module_lot_pattern = '{obra_prefijo}-{unidad_num}-{tipologia}-{modulo}'
        code = getattr(self.site, 'construction_code', False) or self.site.name
        self.assertEqual(plan._module_lot(mb1, apartment).name,
                         '%s-0301-C07-MB1' % code.split('-')[0])
        self.assertNotEqual(plan._module_lot(mb2, apartment).name,
                            plan._module_lot(mb1, apartment).name)
        with self.assertRaises(ValidationError):
            self.company.construction_module_lot_pattern = '{obra}-{piso}'

    def test_site_dispatch_by_apartment(self):
        self._import()
        plan = self._site_plan()
        modules = self._modules('Dpto 301')
        modules.construction_unit_state = 'produced'
        apartment = modules.construction_apartment_task_id
        c07 = self._typology('C07')
        products = c07.module_line_ids.product_id
        stock = self.wh_asm.lot_stock_id
        for product in products:
            lot = plan._module_lot(product, apartment)
            self.env['stock.quant']._update_available_quantity(product, stock, 1.0, lot_id=lot)
        dispatch_type = self.wh_asm.int_type_id
        dispatch_type.construction_site_dispatch = True
        destination = plan._construction_site_location()
        picking = self.env['stock.picking'].create({
            'picking_type_id': dispatch_type.id, 'location_id': stock.id,
            'location_dest_id': destination.id,
            'move_ids': [Command.create({
                'product_id': product.id, 'product_uom_qty': 1.0,
                'uom_id': product.uom_id.id, 'location_id': stock.id,
                'location_dest_id': destination.id}) for product in products]})
        if 'construction_location_id' in self.site._fields:
            self.assertEqual(picking.construction_project_id, self.site)
        picking.construction_project_id = self.site
        picking.action_confirm()
        picking.action_assign()
        with self.assertRaises(UserError):
            picking.button_validate()
        picking.construction_apartment_task_id = apartment
        picking.action_assign()
        self.assertEqual(modules.construction_shipment_picking_id, picking)
        self.assertEqual(set(modules.mapped('construction_shipment_state')), {'in_transit'})
        # Despacho parcial: solo sale el primer módulo.
        first = modules[0]
        first_product = c07.module_line_ids.filtered(
            lambda m: m.code == first.construction_module_code).product_id
        for move in picking.move_ids:
            move.quantity = 1.0 if move.product_id == first_product else 0.0
            move.picked = move.product_id == first_product
        picking.with_context(skip_backorder=True,
                             picking_ids_not_to_backorder=picking.ids).button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(first.construction_unit_state, 'on_site')
        self.assertEqual(first.construction_shipment_picking_id, picking)
        rest = modules - first
        self.assertEqual(set(rest.mapped('construction_unit_state')), {'produced'})
        self.assertFalse(rest.construction_shipment_picking_id)
        self.assertTrue(picking.message_ids.filtered(
            lambda m: 'No se despacharon' in (m.body or '')))

    def test_internal_transfer_without_flag_changes_nothing(self):
        self._import()
        plan = self._site_plan()
        modules = self._modules('Dpto 301')
        modules.construction_unit_state = 'produced'
        product = modules[0].construction_space_task_id.construction_typology_id \
            .module_line_ids.filtered(
                lambda m: m.code == modules[0].construction_module_code).product_id
        stock = self.wh_asm.lot_stock_id
        apartment = modules.construction_apartment_task_id
        lot = plan._module_lot(product, apartment)
        self.env['stock.quant']._update_available_quantity(product, stock, 1.0, lot_id=lot)
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.wh_asm.int_type_id.id, 'location_id': stock.id,
            'location_dest_id': plan._construction_site_location().id,
            'move_ids': [Command.create({
                'product_id': product.id, 'product_uom_qty': 1.0,
                'uom_id': product.uom_id.id, 'location_id': stock.id,
                'location_dest_id': plan._construction_site_location().id})]})
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.quantity = 1.0
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(set(modules.mapped('construction_unit_state')), {'produced'})

    # ------------------------------------------------------------------
    # M110-06
    # ------------------------------------------------------------------
    def test_after_sales_reason(self):
        after_sales = self.env['stock.picking.type'].create({
            'name': 'Producción de piezas · posventa (test)', 'code': 'mrp_operation',
            'sequence_code': 'TPV', 'warehouse_id': self.wh_asm.id,
            'company_id': self.company.id,
            'default_location_src_id': self.wh_asm.lot_stock_id.id,
            'default_location_dest_id': self.wh_asm.lot_stock_id.id,
            'construction_reason_required': True})
        kitchen = self.kitchen.product_variant_id

        def production(picking_type):
            return self.env['mrp.production'].create({
                'product_id': kitchen.id, 'bom_id': self.bom.id,
                'picking_type_id': picking_type.id})

        order = production(after_sales)
        with self.assertRaises(UserError):
            order.action_confirm()
        reason = self.env['construction.production.reason'].create({
            'name': 'Cambio pedido por el cliente (test)', 'generates_additional': True})
        order.construction_reason_id = reason
        order.action_confirm()
        self.assertEqual(order.state, 'confirmed')
        self.assertIn(order, self.env['mrp.production'].search(
            [('construction_reason_id.generates_additional', '=', True)]))
        regular = production(self.wh_asm.manu_type_id)
        regular.action_confirm()
        self.assertEqual(regular.state, 'confirmed')
        operator = new_test_user(self.env, 'operario_v110', groups='mrp.group_mrp_user')
        with self.assertRaises(AccessError):
            self.env['construction.production.reason'].with_user(operator).create(
                {'name': 'Pérdida (test)'})
