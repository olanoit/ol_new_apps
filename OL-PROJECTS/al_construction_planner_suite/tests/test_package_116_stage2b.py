# -*- coding: utf-8 -*-
"""Paquete 1.16, etapa 2 · bloque 2b: analítica nativa por nivel y por rubro.

- M116-05: plan analítico por nivel de la plantilla (catálogo, mixto, por
  obra), cuenta de la tarea y distribución de la línea con la ruta.
- Rubro de mobiliario (familia de la tipología) en la línea y en el consumo
  de la orden de fabricación (D1).
- I-01: el traslado a la obra lleva la analítica del requerimiento.
- D3: el control de compras compara solo en los planes de control.
- Punto 7: «Aplicar analítica a las obras» recalcula los planes cargados."""
from odoo import Command
from odoo.tests import tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestPackage116Stage2b(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Plan = env['account.analytic.plan']
        Account = env['account.analytic.account']
        cls.plan_specialty = Plan.create({'name': 'Especialidad (test 2b)'})
        cls.plan_subspecialty = Plan.create({'name': 'Sub-especialidad (test 2b)'})
        cls.plan_partida = Plan.create({'name': 'Partida (test 2b)'})
        cls.plan_stage = Plan.create({'name': 'Etapa (test 2b)'})
        cls.plan_rubro = Plan.create({'name': 'Rubro (test 2b)'})
        cls.architecture = Account.create({
            'name': 'Arquitectura', 'code': '03', 'plan_id': cls.plan_specialty.id})
        cls.execution = Account.create({'name': 'Ejecución (test 2b)', 'plan_id': cls.plan_stage.id})
        cls.env['construction.analytic.rule'].create(
            {'sequence': 10, 'stage': 'works_execution', 'stage_account_id': cls.execution.id})
        cls.template = env['construction.level.template'].create({
            'name': 'PROF 3 analítica (test 2b)', 'apu_any_level': True, 'line_ids': [
                Command.create({'sequence': 10, 'name': 'Especialidad (N1)', 'role': 'group',
                                'analytic_plan_id': cls.plan_specialty.id,
                                'analytic_mode': 'catalog'}),
                Command.create({'sequence': 20, 'name': 'Sub-especialidad (N2)', 'role': 'group',
                                'analytic_plan_id': cls.plan_subspecialty.id,
                                'analytic_mode': 'mixed'}),
                Command.create({'sequence': 30, 'name': 'Partida (N3)', 'role': 'space',
                                'analytic_plan_id': cls.plan_partida.id,
                                'analytic_mode': 'project'})]})
        cls.levels = cls.template.line_ids.sorted('sequence')
        cls.site = env['project.project'].create({
            'name': '096-26 Obra analítica (test 2b)', 'is_construction_site': True,
            'construction_level_template_id': cls.template.id})
        if not cls.site.account_id:
            cls.site._create_analytic_account()
        Task = env['project.task']
        cls.n1 = Task.create({'name': '3 ARQUITECTURA', 'project_id': cls.site.id,
                              'construction_level_line_id': cls.levels[0].id,
                              'construction_analytic_account_id': cls.architecture.id})
        cls.n2 = Task.create({'name': '3.01 TABIQUERÍA', 'project_id': cls.site.id,
                              'parent_id': cls.n1.id,
                              'construction_level_line_id': cls.levels[1].id})
        cls.n3 = Task.create({'name': '3.0101 Tabique drywall', 'project_id': cls.site.id,
                              'parent_id': cls.n2.id,
                              'construction_level_line_id': cls.levels[2].id,
                              'construction_has_apu': True})

    def _path_key(self, *accounts):
        accounts = self.env['account.analytic.account'].union(*accounts)
        return ','.join(str(i) for i in sorted(accounts.ids))

    # ------------------------------------------------------------------
    # Cuentas de los niveles
    # ------------------------------------------------------------------
    def test_level_accounts(self):
        self.assertEqual(self.n1.construction_analytic_account_id, self.architecture)
        self.assertFalse(self.n1.construction_analytic_own, 'el catálogo no es propio')
        own = self.n2.construction_analytic_account_id
        self.assertTrue(own and self.n2.construction_analytic_own,
                        'mixto sin catálogo: cuenta por obra')
        partida = self.n3.construction_analytic_account_id
        self.assertEqual(partida.plan_id, self.plan_partida)
        self.assertTrue(partida.code.endswith('-3.0101'))
        # La cuenta sigue el nombre de la tarea y se archiva con ella.
        self.n3.name = '3.0101 Tabique de drywall'
        self.assertEqual(partida.name, '3.0101 Tabique de drywall')
        self.n3.active = False
        self.assertFalse(partida.active)
        # Catálogo por código o por nombre, sin importar mayúsculas.
        Task = self.env['project.task']
        self.assertEqual(Task._construction_catalog_account(self.levels[0], 'arquitectura'),
                         self.architecture)
        self.assertEqual(Task._construction_catalog_account(self.levels[0], '03'),
                         self.architecture)
        self.assertFalse(Task._construction_catalog_account(self.levels[2], 'Arquitectura'))

    def test_plan_line_takes_path_accounts(self):
        plan = self.env['construction.resource.plan'].create({'project_id': self.site.id})
        line = self.env['construction.resource.plan.line'].create({
            'plan_id': plan.id, 'task_id': self.n3.id, 'resource_type': 'material',
            'product_id': self.p_screw.id, 'product_uom_id': self.unit.id,
            'qty_planned': 10, 'price_unit_planned': 2.0, 'stage': 'works_execution'})
        line._apply_analytic_rules()
        self.assertEqual(list(line.analytic_distribution), [self._path_key(
            self.site.account_id, self.execution, self.architecture,
            self.n2.construction_analytic_account_id, self.n3.construction_analytic_account_id)])

    def test_apply_analytics_to_loaded_sites(self):
        """Obra cargada antes de configurar la analítica: el botón crea las
        cuentas y recalcula la distribución y el presupuesto nativo."""
        template = self.env['construction.level.template'].create({
            'name': 'Sin analítica (test 2b)', 'line_ids': [
                Command.create({'sequence': 10, 'name': 'Especialidad', 'role': 'group'}),
                Command.create({'sequence': 20, 'name': 'Partida', 'role': 'space'})]})
        site = self.env['project.project'].create({
            'name': '018-26 Obra cargada (test 2b)', 'is_construction_site': True,
            'construction_level_template_id': template.id})
        if not site.account_id:
            site._create_analytic_account()
        levels = template.line_ids.sorted('sequence')
        Task = self.env['project.task']
        group = Task.create({'name': '1 ESTRUCTURAS', 'project_id': site.id,
                             'construction_level_line_id': levels[0].id})
        partida = Task.create({'name': '1.01 Concreto', 'project_id': site.id,
                               'parent_id': group.id, 'construction_level_line_id': levels[1].id})
        plan = self.env['construction.resource.plan'].create({'project_id': site.id})
        line = self.env['construction.resource.plan.line'].create({
            'plan_id': plan.id, 'task_id': partida.id, 'resource_type': 'material',
            'product_id': self.p_screw.id, 'product_uom_id': self.unit.id,
            'qty_planned': 10, 'price_unit_planned': 2.0, 'stage': 'works_execution'})
        plan.action_request_approval()
        self.assertEqual(plan.state, 'approved')
        self.assertFalse(partida.construction_analytic_account_id)
        levels[1].analytic_plan_id = self.plan_partida
        template.action_construction_apply_analytics()
        account = partida.construction_analytic_account_id
        self.assertTrue(account)
        self.assertIn(str(account.id), list(line.analytic_distribution)[0].split(','))
        budget_lines = plan.budget_analytic_id.budget_line_ids
        column = self.plan_partida._column_name()
        self.assertIn(account, budget_lines.mapped(column))

    def test_send_takes_catalog_accounts(self):
        """El envío de la hoja toma la cuenta del catálogo de la columna
        «Especialidad (catálogo)»; el título no crea cuentas de catálogo."""
        site = self.env['project.project'].create({
            'name': '181-26 Obra por catálogo (test 2b)', 'is_construction_site': True,
            'construction_level_template_id': self.template.id})
        customer = self.env['res.partner'].create({'name': 'Cliente 2b (test)'})
        order = self.env['sale.order'].create({'partner_id': customer.id, 'project_id': site.id})
        product = self.env['product.product'].create({'name': 'Partida (test 2b)',
                                                      'type': 'service'})
        self.env['sale.order.line'].create({
            'order_id': order.id, 'product_id': product.id, 'name': '3.0101 Tabique',
            'product_uom_qty': 1, 'construction_budget_item': '3.0101',
            'construction_budget_path': [['3', '3 ARQUITECTURA'], ['3.01', 'TABIQUERÍA']],
            'construction_budget_catalog': ['Arquitectura', False]})
        order.action_construction_create_levels()
        Task = self.env['project.task']
        specialty = Task.search([('project_id', '=', site.id),
                                 ('construction_level_line_id', '=', self.levels[0].id)])
        self.assertEqual(specialty.construction_analytic_account_id, self.architecture,
                         'la misma cuenta en las dos obras aunque el título sea otro')
        sub = specialty.child_ids
        self.assertTrue(sub.construction_analytic_own, 'mixto sin catálogo: por obra')

    # ------------------------------------------------------------------
    # D3
    # ------------------------------------------------------------------
    def test_control_plans_sum_matching_lines(self):
        plan = self.env['construction.resource.plan'].create({'project_id': self.site.id})
        other = self.env['project.task'].create({
            'name': '3.0102 Tabique de concreto', 'project_id': self.site.id,
            'parent_id': self.n2.id, 'construction_level_line_id': self.levels[2].id})
        lines = self.env['construction.resource.plan.line'].create([{
            'plan_id': plan.id, 'task_id': task.id, 'resource_type': 'material',
            'product_id': self.p_screw.id, 'product_uom_id': self.unit.id,
            'qty_planned': 10, 'price_unit_planned': 2.0, 'stage': 'works_execution'}
            for task in (self.n3, other)])
        lines._apply_analytic_rules()
        plan.action_request_approval()
        self.assertEqual(plan.state, 'approved')
        combo = {self.site.account_id.root_plan_id._column_name(): self.site.account_id.id,
                 self.plan_stage._column_name(): self.execution.id}
        # Sin planes de control: la compra con solo obra y etapa no calza con
        # ninguna línea (todas llevan la partida).
        self.assertFalse(plan._construction_control_budget_lines(combo))
        self.company.construction_budget_control_plan_ids = \
            self.site.account_id.root_plan_id | self.plan_stage
        matched = plan._construction_control_budget_lines(combo)
        self.assertEqual(len(matched), 2)
        self.assertEqual(sum(matched.mapped('budget_amount')), 40.0)


@tagged('post_install', '-at_install')
class TestPackage116Stage2bFurniture(PlannerCommon):
    """Rubro de mobiliario y consumo de la OF (D1)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        if not cls.project.account_id:
            cls.project._create_analytic_account()
        plan_rubro = env['account.analytic.plan'].create({'name': 'Rubro (test 2b)'})
        Account = env['account.analytic.account']
        cls.kitchen_rubro = Account.create({'name': 'Cocina (test 2b)', 'plan_id': plan_rubro.id})
        cls.closet_rubro = Account.create({'name': 'Closet (test 2b)', 'plan_id': plan_rubro.id})
        env['construction.rubro.account'].create([
            {'family': 'kitchen', 'account_id': cls.kitchen_rubro.id},
            {'family': 'closet', 'account_id': cls.closet_rubro.id}])
        cls.closet = cls.typology.copy({'code': '02', 'name': 'Closet 02', 'family': 'closet'})
        cls.space_502.construction_typology_id = cls.closet

    def test_rubro_on_plan_lines_and_production_shares(self):
        self._generate_and_approve()
        kitchen_line = self.plan.line_ids.filtered(
            lambda l: l.space_task_id == self.space_501 and l.resource_type == 'material')[:1]
        self.assertIn(str(self.kitchen_rubro.id),
                      list(kitchen_line.analytic_distribution)[0].split(','))
        production = self.env['mrp.production'].create({
            'product_id': self.p_white.id, 'product_qty': 1,
            'construction_plan_id': self.plan.id,
            'construction_space_task_ids': [Command.set((self.space_501 | self.space_502).ids)]})
        shares = production._construction_rubro_shares()
        self.assertEqual(set(shares), {self.kitchen_rubro, self.closet_rubro})
        self.assertAlmostEqual(sum(shares.values()), 1.0)
        # Una sola tipología: 100 % a su rubro.
        production.construction_space_task_ids = self.space_501
        self.assertEqual(production._construction_rubro_shares(), {self.kitchen_rubro: 1.0})


@tagged('post_install', '-at_install')
class TestPackage116Stage2bTransfer(PlannerCommon):
    """I-01: el traslado a la obra lleva la analítica del requerimiento."""

    def test_transfer_to_site_takes_request_distribution(self):
        self.company._al_construction_ensure_setup()
        if not self.project.account_id:
            self.project._create_analytic_account()
        request = self.env['construction.material.request'].create({'project_id': self.project.id})
        request.write({'line_ids': [Command.create({
            'product_id': self.p_screw.id, 'product_qty': 2, 'task_id': self.space_501.id})]})
        line = request.line_ids
        site = line._get_site_location()
        self.assertTrue(site)
        distribution = {'%s' % self.project.account_id.id: 100.0}
        Move = self.env['stock.move']
        move = Move.create({
            'product_id': self.p_screw.id, 'product_uom_qty': 2, 'product_uom': self.unit.id,
            'location_id': self.company.construction_src_location_id.id,
            'location_dest_id': site.id, 'construction_request_line_id': line.id,
            'construction_analytic_distribution': distribution})
        self.assertEqual(move._get_analytic_distribution(), distribution)
        # Otro destino (una devolución al almacén): lo de siempre.
        back = Move.create({
            'product_id': self.p_screw.id, 'product_uom_qty': 1, 'product_uom': self.unit.id,
            'location_id': site.id,
            'location_dest_id': self.company.construction_src_location_id.id,
            'construction_request_line_id': line.id,
            'construction_analytic_distribution': distribution})
        self.assertNotEqual(back._get_analytic_distribution(), distribution)
