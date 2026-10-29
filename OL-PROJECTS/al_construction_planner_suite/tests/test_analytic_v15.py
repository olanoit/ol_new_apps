# -*- coding: utf-8 -*-
"""v1.5, fase 15: producto de servicio por actividad, tramos de pago,
reglas analíticas y presupuesto por obra › etapa › partida."""

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestAnalyticV15(PlannerCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Plan = cls.env['account.analytic.plan']
        Account = cls.env['account.analytic.account']
        cls.plan_stage = Plan.create({'name': 'Etapa (test)'})
        cls.plan_cost = Plan.create({'name': 'Partida (test)'})
        cls.prd = Account.create({'name': 'PRD', 'plan_id': cls.plan_stage.id})
        cls.ins = Account.create({'name': 'INS', 'plan_id': cls.plan_stage.id})
        cls.modv = Account.create({'name': 'MODV', 'plan_id': cls.plan_cost.id})
        cls.mptab = Account.create({'name': 'MP-TAB', 'plan_id': cls.plan_cost.id})
        cls.mpacc = Account.create({'name': 'MP-ACC', 'plan_id': cls.plan_cost.id})
        cls.categ_board = cls.env['product.category'].create({'name': 'Tableros (test)'})
        (cls.p_white | cls.p_cognac | cls.p_rh).categ_id = cls.categ_board
        if not cls.project.account_id:
            cls.project._create_analytic_account()
        Rule = cls.env['construction.analytic.rule']
        Rule.create([
            {'sequence': 10, 'stage': 'production', 'stage_account_id': cls.prd.id},
            {'sequence': 11, 'stage': 'assembly', 'stage_account_id': cls.prd.id},
            {'sequence': 12, 'stage': 'installation', 'stage_account_id': cls.ins.id},
            {'sequence': 13, 'stage': 'finishing', 'stage_account_id': cls.ins.id},
            {'sequence': 20, 'resource_type': 'contract', 'stage': 'assembly',
             'stage_account_id': cls.prd.id, 'cost_account_id': cls.modv.id},
            {'sequence': 21, 'resource_type': 'contract', 'stage': 'installation',
             'stage_account_id': cls.ins.id, 'cost_account_id': cls.modv.id},
            {'sequence': 30, 'resource_type': 'material', 'stage': 'production',
             'product_categ_id': cls.categ_board.id,
             'stage_account_id': cls.prd.id, 'cost_account_id': cls.mptab.id},
            {'sequence': 31, 'resource_type': 'material', 'cost_account_id': cls.mpacc.id},
        ])

    def _accounts(self, line):
        key = next(iter(line.analytic_distribution or {}), '')
        return self.env['account.analytic.account'].browse(int(a) for a in key.split(',') if a)

    def test_rule_specificity(self):
        Rule = self.env['construction.analytic.rule']
        board = Rule._accounts_for(self.env.company, 'material', 'production', self.categ_board)
        self.assertEqual(board, self.prd | self.mptab, 'la más específica')
        hinge = Rule._accounts_for(self.env.company, 'material', 'assembly', self.p_hinge.categ_id)
        self.assertEqual(hinge, self.prd | self.mpacc, 'etapa de una regla y partida de otra')

    def test_generated_lines_carry_stage_and_partida(self):
        self._generate()
        lines = self.plan.line_ids
        assembly = lines.filtered(lambda l: l.resource_type == 'contract' and l.stage == 'assembly')[0]
        self.assertEqual(self._accounts(assembly), self.project.account_id | self.prd | self.modv)
        board = lines.filtered(lambda l: l.product_id == self.p_white)[0]
        self.assertEqual(self._accounts(board), self.project.account_id | self.prd | self.mptab)
        unstaged = lines.filtered(lambda l: l.product_id == self.p_rh)[0]
        self.assertEqual(self._accounts(unstaged), self.project.account_id | self.mpacc,
                         'sin etapa, solo la partida de material')
        # Presupuesto por obra › etapa › partida.
        values = self.plan._get_budget_line_values()
        self.assertTrue(len(values) >= 4)
        stage_column = self.prd.root_plan_id._column_name()
        cost_column = self.modv.root_plan_id._column_name()
        self.assertTrue(any(v.get(stage_column) == self.ins.id and v.get(cost_column) == self.modv.id
                            for v in values))
        self.assertAlmostEqual(sum(v['budget_amount'] for v in values),
                               sum(lines.mapped('amount_planned')), 2)

    def test_apply_rules_button_only_in_draft(self):
        self._generate()
        self.plan.line_ids.analytic_distribution = False
        self.plan.action_apply_analytic_rules()
        self.assertTrue(all(self.plan.line_ids.mapped('analytic_distribution')))

    def test_service_products(self):
        assembly_categ = self.env['product.category'].create({'name': '601 (test)'})
        install_categ = self.env['product.category'].create({'name': '602 (test)'})
        self.env.company.write({'construction_categ_assembly_id': assembly_categ.id,
                                'construction_categ_installation_id': install_categ.id})
        activities = self.act_screw | self.act_inst_low
        products = activities.action_create_service_products()
        self.assertEqual(len(products), 2)
        self.assertEqual(self.act_screw.product_id.categ_id, assembly_categ)
        self.assertEqual(self.act_inst_low.product_id.categ_id, install_categ)
        self.assertEqual(self.act_inst_low.product_id.type, 'service')
        self.assertFalse(activities.action_create_service_products(), 'no duplica')

    def test_tranches(self):
        delivery = self.act_doors
        delivery.tranche_ids = [Command.create({'sequence': 1, 'name': 'Limpieza', 'pct': 45}),
                                Command.create({'sequence': 2, 'name': 'Acabado', 'pct': 50}),
                                Command.create({'sequence': 3, 'name': 'R1', 'pct': 10})]
        self.assertEqual(delivery.tranche_total_pct, 105, 'avisa, no bloquea')
        with self.assertRaises(ValidationError):
            delivery.tranche_ids[0].pct = 0
        self._generate_and_approve()
        # Con la política «Bloquear» (la aprobación del exceso se prueba en
        # test_progress_exceed_approval).
        self.plan.exceed_policy = 'block'
        line = self.plan.line_ids.filtered(lambda l: l.activity_id == delivery)[0]
        cleaning = delivery.tranche_ids[0]
        photo = self.env['ir.attachment'].create({'name': 'foto.png', 'raw': b'x'})

        def progress_vals(qty, tranche):
            return {'task_id': line.task_id.id, 'activity_id': delivery.id, 'plan_line_id': line.id,
                    'qty': qty, 'tranche_id': tranche.id,
                    'attachment_ids': [Command.set(photo.copy().ids)]}
        progress = self.env['construction.task.progress'].create(
            progress_vals(line.qty_planned, cleaning))
        # Ponderada con la precisión de la unidad del producto.
        self.assertAlmostEqual(progress.qty_weighted, line.qty_planned * 0.45, 2)
        self.assertAlmostEqual(progress.amount,
                               round(progress.qty_weighted * line.price_unit_planned, 2))
        # El tramo admite lo presupuestado de la línea; otro tramo, también.
        self.env['construction.task.progress'].create(
            progress_vals(line.qty_planned, delivery.tranche_ids[1]))
        with self.assertRaises(ValidationError):
            self.env['construction.task.progress'].create(
                progress_vals(line.qty_planned * 2, cleaning))
