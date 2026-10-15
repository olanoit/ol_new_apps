# -*- coding: utf-8 -*-
"""Operación en la aplicación nativa (v1.7, M17-08 a M17-11).

- Compras: la compra masiva de dos partidas llega a Compras como requerimiento
  (una línea por producto y partida), se cotiza a tres proveedores y el
  comprado vuelve a las líneas del plan.
- Producción: una obra de tuberías propone las OF de los spools de un área
  desde la línea de producción del plan, y el consumo vuelve a sus líneas.
- Cuadrillas: un operario, un oficial y un peón asignados a una partida son
  turnos de Planificación con su rol y sus horas suben el real.
"""
from datetime import date

from odoo import Command
from odoo.tests import tagged

from .common import PlannerCommon
from .test_levels_v17 import TestFreeLevels


@tagged('post_install', '-at_install')
class TestNativePurchase(TestFreeLevels):

    def test_mass_purchase_by_partida_quoted_in_purchase(self):
        self.plan_site.action_request_approval()
        wizard = self.env['construction.plan.purchase.wizard'].with_context(
            default_plan_id=self.plan_site.id, construction_selection_project=True,
        ).create({'group_by': 'task'})
        board = wizard.line_ids.filtered(lambda l: l.product_id == self.board_mat)
        # La placa va en dos partidas: el muro (66) y las luminarias (2).
        self.assertEqual(sorted(board.mapped('group_label')),
                         sorted([self.drywall.display_name, self.led.display_name]))
        self.assertEqual(sorted(board.mapped('qty_need')), [2.0, 66.0])
        action = wizard.action_create()
        request = self.env['purchase.request'].browse(action['res_id'])
        pr_line = request.line_ids.filtered(
            lambda l: l.product_id == self.board_mat and self.drywall.name in l.name)
        self.assertEqual(pr_line.product_qty, 66.0)
        # Compras cotiza el muro a tres proveedores desde el requerimiento.
        request.button_to_approve()
        request.button_approved()
        vendors = self.env['res.partner'].create([
            {'name': 'Proveedor %s (test)' % n} for n in 'ABC'])
        orders = self.env['purchase.order']
        for vendor in vendors:
            maker = self.env['purchase.request.line.make.purchase.order'].with_context(
                active_model='purchase.request.line', active_ids=pr_line.ids,
            ).create({'supplier_id': vendor.id})
            maker.item_ids.product_qty = 66.0
            action = maker.make_purchase_order()
            orders |= self.env['purchase.order'].browse(set(action['domain'][0][2]))
        self.assertEqual(orders.partner_id, vendors)
        orders.order_line.price_unit = 33.0
        (orders - orders[1]).button_cancel()
        orders[1].button_confirm()
        drywall_board = self.plan_site.line_ids.filtered(
            lambda l: l.task_id == self.drywall and l.product_id == self.board_mat)
        self.assertEqual(drywall_board.qty_purchased, 66.0)


@tagged('post_install', '-at_install')
class TestNativeProduction(PlannerCommon):
    """Tuberías para minería: Área › Línea › Spool, con prefabricación en
    taller (fabricación) seguida de montaje (campo)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Stage = cls.env['construction.stage']
        cls.shop = Stage.create({'name': 'Prefabricación en taller (test)', 'code': 'test17_shop',
                                 'kind': 'production', 'sequence': 310})
        cls.erect = Stage.create({'name': 'Montaje (test)', 'code': 'test17_erect',
                                  'kind': 'field', 'sequence': 320,
                                  'previous_stage_id': cls.shop.id})
        template = cls.env['construction.level.template'].create({
            'name': 'Tuberías (test)', 'line_ids': [
                (0, 0, {'sequence': 1, 'name': 'Área', 'role': 'group'}),
                (0, 0, {'sequence': 2, 'name': 'Línea', 'role': 'group'}),
                (0, 0, {'sequence': 3, 'name': 'Spool', 'role': 'space'})]})
        levels = {line.name: line for line in template.line_ids}
        cls.site = cls.env['project.project'].create({
            'name': 'Planta concentradora (test)', 'is_construction_site': True,
            'construction_level_template_id': template.id})
        Task = cls.env['project.task']

        def node(name, level, parent=None):
            return Task.create({'name': name, 'project_id': cls.site.id,
                                'construction_level_line_id': levels[level].id,
                                'parent_id': parent.id if parent else False})

        area = node('Área 210 Molienda', 'Área')
        lines = [node('Línea %s' % n, 'Línea', area) for n in ('A', 'B')]
        cls.spools = [node('Spool %s-%s' % (line.name[-1], n), 'Spool', line)
                      for line in lines for n in (1, 2, 3)]
        Product = cls.env['product.product']
        cls.pipe = Product.create({'name': 'Tubo 6" SCH40 (test)', 'type': 'consu',
                                   'uom_id': cls.meter.id, 'standard_price': 80.0})
        cls.flange = Product.create({'name': 'Brida 6" (test)', 'type': 'consu',
                                     'standard_price': 45.0})
        cls.spool_product = Product.create({'name': 'Spool 6" (test)', 'type': 'consu'})
        cls.env['mrp.bom'].create({
            'product_tmpl_id': cls.spool_product.product_tmpl_id.id, 'product_qty': 1.0,
            'bom_line_ids': [
                (0, 0, {'product_id': cls.pipe.id, 'product_qty': 6.0,
                        'product_uom_id': cls.meter.id,
                        'construction_consumption_stage': 'test17_shop'}),
                (0, 0, {'product_id': cls.flange.id, 'product_qty': 2.0,
                        'construction_consumption_stage': 'test17_shop'})]})
        cls.site_plan = cls.env['construction.resource.plan'].create({'project_id': cls.site.id})
        values = []
        for spool in cls.spools:
            values += [
                {'resource_type': 'production', 'product_id': cls.spool_product.id,
                 'qty_planned': 1.0, 'stage': 'test17_shop', 'product_uom_id': cls.unit.id},
                {'resource_type': 'material', 'product_id': cls.pipe.id, 'qty_planned': 6.0,
                 'stage': 'test17_shop', 'product_uom_id': cls.meter.id},
                {'resource_type': 'material', 'product_id': cls.flange.id, 'qty_planned': 2.0,
                 'stage': 'test17_shop', 'product_uom_id': cls.unit.id},
                {'resource_type': 'contract', 'activity_id': cls.act_doors.id,
                 'qty_planned': 1.0, 'stage': 'test17_erect', 'product_uom_id': cls.unit.id},
            ]
            for vals in values[-4:]:
                vals.update(plan_id=cls.site_plan.id, task_id=spool.id, price_unit_planned=10.0)
        cls.env['construction.resource.plan.line'].create(values)
        cls.site_plan.action_request_approval()

    def test_spools_of_an_area(self):
        self.assertEqual(self.site_plan.state, 'approved')
        stages = self.env['construction.space.stage']._sync_from_plan(self.site_plan)
        spool = stages.filtered(lambda s: s.space_task_id == self.spools[0]).sorted('sequence')
        self.assertEqual(spool.mapped('stage'), ['test17_shop', 'test17_erect'])
        self.assertEqual(spool[1].predecessor_id, spool[0])
        wizard = self.env['construction.plan.production.wizard'].with_context(
            default_plan_id=self.site_plan.id, construction_selection_project=True).create({})
        # Una OF por línea con sus tres spools.
        self.assertEqual(len(wizard.line_ids), 2)
        self.assertEqual(wizard.line_ids.mapped('qty'), [3.0, 3.0])
        self.assertEqual(set(wizard.line_ids.mapped('product_id')), {self.spool_product})
        action = wizard.action_create()
        productions = self.env['mrp.production'].search(action.get('domain') or
                                                        [('id', '=', action.get('res_id'))])
        self.assertEqual(len(productions), 2)
        production = productions.filtered(lambda p: self.spools[0] in p.construction_space_task_ids)
        pipe_lines = self.site_plan.line_ids.filtered(
            lambda l: l.product_id == self.pipe and l.task_id in production.construction_space_task_ids)
        self.assertEqual(set(pipe_lines.allocation_ids.mapped('kind')), {'production'})
        production.action_confirm()
        production.qty_producing = production.product_qty
        for move in production.move_raw_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        production.button_mark_done()
        self.assertAlmostEqual(sum(pipe_lines.mapped('qty_consumed')), 18.0)


@tagged('post_install', '-at_install')
class TestNativeCrew(TestFreeLevels):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hour = cls.env.ref('uom.product_uom_hour')
        Role = cls.env['planning.role']
        cls.roles = {name: Role.create({'name': '%s (test)' % name})
                     for name in ('Operario', 'Oficial', 'Peón')}
        cls.workers = {}
        values = []
        for name, role in cls.roles.items():
            activity = cls.env['construction.labor.activity'].create({
                'code': 'T17-HH-%s' % name[:3].upper(), 'name': 'Horas %s (test)' % name,
                'stage': 'test17_board', 'uom_id': cls.hour.id, 'role_id': role.id})
            values.append({
                'plan_id': cls.plan_site.id, 'task_id': cls.drywall.id, 'stage': 'test17_board',
                'resource_type': 'labor', 'activity_id': activity.id, 'role_id': role.id,
                'qty_planned': 40.0, 'product_uom_id': cls.hour.id, 'price_unit_planned': 20.0})
            employee = cls.env['hr.employee'].create({
                'name': '%s de la cuadrilla (test)' % name, 'hourly_cost': 15.0,
                'planning_role_ids': [Command.link(role.id)]})
            cls.workers[name] = employee
        cls.labor_lines = cls.env['construction.resource.plan.line'].create(values)
        cls.plan_site.action_request_approval()

    def test_crew_by_role_on_a_partida(self):
        wizard = self.env['construction.plan.crew.wizard'].with_context(
            default_plan_id=self.plan_site.id, construction_selection_task_ids=self.drywall.ids,
        ).create({
            'member_ids': [Command.create({'role_id': self.roles[name].id,
                                           'resource_id': self.workers[name].resource_id.id})
                           for name in ('Operario', 'Oficial', 'Peón')],
            'date_start': date(2026, 11, 2), 'weeks': 1, 'hours_per_week': 40.0})
        self.assertEqual(len(wizard.line_ids), 3)
        self.assertEqual(wizard.hours_total, 120.0)
        for row in wizard.line_ids:
            self.assertEqual(row.plan_line_id.role_id, row.role_id)
        wizard.action_assign()
        slots = self.env['planning.slot'].search(
            [('construction_plan_line_id', 'in', self.labor_lines.ids)])
        self.assertEqual(len(slots), 3)
        self.assertEqual(set(slots.mapped('role_id')), set(self.roles.values()))
        operario = self.workers['Operario']
        line = self.labor_lines.filtered(lambda l: l.role_id == self.roles['Operario'])
        self.assertAlmostEqual(line.amount_committed, 40 * 15.0)
        self.env['account.analytic.line'].create({
            'name': 'Emplacado (test)', 'project_id': self.site.id, 'task_id': self.drywall.id,
            'employee_id': operario.id, 'unit_amount': 8.0, 'date': date(2026, 11, 2)})
        self.assertAlmostEqual(line.qty_executed, 8.0)
        self.assertAlmostEqual(line.amount_actual, 8 * 15.0)


# Solo las pruebas propias: las de TestFreeLevels ya corren en su clase.
for _cls in (TestNativePurchase, TestNativeCrew):
    for _name in dir(TestFreeLevels):
        if _name.startswith('test_') and callable(getattr(TestFreeLevels, _name)) \
                and _name not in vars(_cls):
            setattr(_cls, _name, None)
