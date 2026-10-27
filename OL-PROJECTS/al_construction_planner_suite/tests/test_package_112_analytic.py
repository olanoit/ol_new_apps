# -*- coding: utf-8 -*-
"""Paquete 1.12, M112-01 y M112-02: costo analítico por etapa de las
órdenes de una obra.

Cadena de dos plantas: el corte fabrica el paquete de piezas con tableros;
el armado consume el paquete (intermedio) y las bisagras. Las reglas
analíticas ponen la etapa (corte, armado) y la partida (tableros,
accesorios). Confirma y termina «Fabricación: usuario»."""
from odoo import Command
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestPackage112Analytic(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Plan = cls.env['account.analytic.plan']
        Account = cls.env['account.analytic.account']
        cls.plan_stage = Plan.create({'name': 'Etapa (test 112)'})
        cls.plan_cost = Plan.create({'name': 'Partida (test 112)'})

        def account(name, plan):
            return Account.create({'name': name, 'plan_id': plan.id})

        cls.cut = account('1.1 Corte', cls.plan_stage)
        cls.asm = account('1.2 Armado', cls.plan_stage)
        cls.rework = account('3 Reproceso', cls.plan_stage)
        cls.boards = account('Tableros', cls.plan_cost)
        cls.accessories = account('Accesorios', cls.plan_cost)
        Category = cls.env['product.category']
        cls.categ_board = Category.create({'name': 'Tableros (test 112)'})
        cls.categ_accessory = Category.create({'name': 'Accesorios (test 112)'})
        cls.env['construction.analytic.rule'].create([
            {'sequence': 10, 'stage': 'production', 'stage_account_id': cls.cut.id},
            {'sequence': 11, 'stage': 'assembly', 'stage_account_id': cls.asm.id},
            {'sequence': 20, 'resource_type': 'material', 'product_categ_id': cls.categ_board.id,
             'cost_account_id': cls.boards.id},
            {'sequence': 21, 'resource_type': 'material',
             'product_categ_id': cls.categ_accessory.id, 'cost_account_id': cls.accessories.id},
        ])
        cls.site = cls.env['project.project'].create({
            'name': 'Obra de prueba (test 112)', 'is_construction_site': True})
        if not cls.site.account_id:
            cls.site._create_analytic_account()

        Product = cls.env['product.product']

        def product(name, categ, price):
            return Product.create({'name': name, 'is_storable': True, 'categ_id': categ.id,
                                   'standard_price': price})

        cls.board = product('Melamina blanca (test 112)', cls.categ_board, 100.0)
        cls.hinge = product('Bisagra (test 112)', cls.categ_accessory, 5.0)
        cls.package = product('Paquete de piezas MB01 (test 112)', cls.categ_accessory, 200.0)
        cls.module = product('MB01 (test 112)', cls.categ_accessory, 0.0)
        Bom = cls.env['mrp.bom']
        cls.bom_cut = Bom.create({
            'product_tmpl_id': cls.package.product_tmpl_id.id, 'product_qty': 1.0,
            'consumption': 'flexible',
            'bom_line_ids': [Command.create({
                'product_id': cls.board.id, 'product_qty': 2,
                'construction_consumption_stage': 'production'})]})
        cls.bom_asm = Bom.create({
            'product_tmpl_id': cls.module.product_tmpl_id.id, 'product_qty': 1.0,
            'consumption': 'flexible',
            'bom_line_ids': [
                Command.create({'product_id': cls.package.id, 'product_qty': 1,
                                'construction_intermediate': True}),
                Command.create({'product_id': cls.hinge.id, 'product_qty': 2,
                                'construction_consumption_stage': 'assembly'})]})
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        cls.after_sales = cls.warehouse.manu_type_id.copy({
            'name': 'Producción de piezas · posventa (test 112)', 'sequence_code': 'PV12',
            'construction_reason_required': True})
        cls.operator = new_test_user(
            cls.env, 'm112_operario', groups='mrp.group_mrp_user,stock.group_stock_user',
            name='Fabricación: usuario (test 112)')

    def _produce(self, bom, **vals):
        production = self.env['mrp.production'].create(dict({
            'product_id': bom.product_tmpl_id.product_variant_id.id, 'bom_id': bom.id,
            'product_qty': 1.0, 'project_id': self.site.id}, **vals))
        production = production.with_user(self.operator)
        production.action_confirm()
        production.qty_producing = 1
        for move in production.move_raw_ids:
            move.quantity = move.product_uom_qty
        production.move_raw_ids.picked = True
        production.button_mark_done()
        self.assertEqual(production.state, 'done')
        return production.sudo()

    def _lines(self, production):
        """{producto: (importe, cuentas)} de los apuntes de la orden en la obra."""
        result = {}
        for line in production.move_raw_ids.analytic_account_line_ids:
            self.assertEqual(line.account_id, self.site.account_id)
            accounts = line.account_id
            for plan in (self.plan_stage, self.plan_cost):
                accounts |= line[plan._column_name()]
            result[line.product_id] = (line.amount, accounts)
        return result

    # M112-01
    def test_intermediate_not_charged_again(self):
        cut = self._lines(self._produce(self.bom_cut))
        self.assertEqual(set(cut), {self.board}, 'el corte carga sus tableros como hoy')
        self.assertAlmostEqual(cut[self.board][0], -200.0)
        assembly = self._lines(self._produce(self.bom_asm))
        self.assertEqual(set(assembly), {self.hinge}, 'el paquete no tiene apunte')
        self.assertAlmostEqual(assembly[self.hinge][0], -10.0)

    def test_intermediate_keeps_stock_value(self):
        production = self._produce(self.bom_asm)
        package_move = production.move_raw_ids.filtered(lambda m: m.product_id == self.package)
        self.assertAlmostEqual(package_move.value, 200.0, msg='la valorización no cambia')

    def test_setting_off_behaves_as_before(self):
        self.company.construction_intermediate_no_analytic = False
        assembly = self._lines(self._produce(self.bom_asm))
        self.assertEqual(set(assembly), {self.package, self.hinge})

    def test_order_without_project_unchanged(self):
        production = self._produce(self.bom_asm, project_id=False)
        self.assertFalse(production.move_raw_ids.analytic_account_line_ids)

    # M112-02
    def test_stage_from_bom_line(self):
        cut = self._lines(self._produce(self.bom_cut))
        self.assertEqual(cut[self.board][1], self.site.account_id | self.cut | self.boards)
        assembly = self._lines(self._produce(self.bom_asm))
        self.assertEqual(assembly[self.hinge][1], self.site.account_id | self.asm | self.accessories,
                         'el armado ya no cae en el corte')

    def test_reason_stage_wins(self):
        reason = self.env['construction.production.reason'].create({
            'name': 'Falla de fabricación (test 112)', 'company_id': self.company.id,
            'analytic_account_id': self.rework.id})
        production = self._produce(self.bom_asm, picking_type_id=self.after_sales.id,
                                   construction_reason_id=reason.id)
        lines = self._lines(production)
        self.assertEqual(lines[self.hinge][1],
                         self.site.account_id | self.rework | self.accessories,
                         'la etapa del motivo y la partida de las reglas')

    def test_reason_without_stage_uses_bom_line(self):
        reason = self.env['construction.production.reason'].create(
            {'name': 'Cambio pedido por el cliente (test 112)'})
        production = self._produce(self.bom_asm, picking_type_id=self.after_sales.id,
                                   construction_reason_id=reason.id)
        self.assertEqual(self._lines(production)[self.hinge][1],
                         self.site.account_id | self.asm | self.accessories)

    def test_bom_line_without_stage_uses_first_production_stage(self):
        self.bom_asm.bom_line_ids.filtered(
            lambda l: l.product_id == self.hinge).construction_consumption_stage = False
        lines = self._lines(self._produce(self.bom_asm))
        self.assertEqual(lines[self.hinge][1], self.site.account_id | self.cut | self.accessories)

    def test_other_stage_catalog(self):
        """Otra etapa de fabricación del catálogo: su regla, sin tocar código."""
        Stage = self.env['construction.stage']
        Stage.create({'name': 'Lacado (test 112)', 'code': 'lacquer112', 'kind': 'production'})
        lacquer = self.env['account.analytic.account'].create(
            {'name': '1.3 Lacado', 'plan_id': self.plan_stage.id})
        self.env['construction.analytic.rule'].create(
            {'sequence': 12, 'stage': 'lacquer112', 'stage_account_id': lacquer.id})
        self.bom_asm.bom_line_ids.filtered(
            lambda l: l.product_id == self.hinge).construction_consumption_stage = 'lacquer112'
        lines = self._lines(self._produce(self.bom_asm))
        self.assertEqual(lines[self.hinge][1], self.site.account_id | lacquer | self.accessories)
