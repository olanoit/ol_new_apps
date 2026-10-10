# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, new_test_user, tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestBaseline(PlannerCommon):
    """Fase 3, línea base: aprobación, presupuesto, versiones y W-12."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = new_test_user(
            cls.env, 'plan_jefatura', groups='al_construction_planner.group_planner_manager',
            name='Jefatura (test)')
        # Regla propia del test (PlannerCommon apaga las existentes).
        TierDefinition = cls.env['tier.definition']
        cls.tier_manager = TierDefinition.create({
            'name': 'Plan · jefatura (test)',
            'model_id': cls.env['ir.model']._get('construction.resource.plan').id,
            'review_type': 'group',
            'reviewer_group_id': cls.env.ref(
                'al_construction_planner.group_planner_manager').id,
            'definition_domain': "[('amount_total', '>', 0)]",
            'sequence': 20,
            'approve_sequence': True,
        })
        if not cls.project.account_id:
            cls.project._create_analytic_account()
        # Plan analítico adicional (partida) para probar las combinaciones.
        cls.analytic_plan = cls.env['account.analytic.plan'].create({'name': 'Partida (test)'})
        Account = cls.env['account.analytic.account']
        cls.acc_kitchen = Account.create({
            'name': 'Cocinas (test)', 'plan_id': cls.analytic_plan.id})
        cls.acc_closet = Account.create({
            'name': 'Closets (test)', 'plan_id': cls.analytic_plan.id})

    # ------------------------------------------------------------------
    # Ayudas
    # ------------------------------------------------------------------
    def _price_all(self, plan=None, price=10.0):
        """Aplica un costo manual (W-12) a cada producto sin costo."""
        plan = plan or self.plan
        products = plan.line_ids.filtered(lambda l: not l.price_unit_planned).product_id
        for product in products:
            wizard = self.env['construction.plan.price.wizard'].create({
                'plan_id': plan.id, 'product_id': product.id, 'basis': 'manual',
                'price_unit': price})
            wizard.action_apply()

    def _ready_plan(self):
        """Plan generado, con etapa y costo en todas sus líneas."""
        self._generate()
        self.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        self._price_all()
        return self.plan

    def _approve(self, plan):
        plan.with_user(self.planner).action_request_approval()
        self.assertEqual(plan.state, 'to_approve')
        self.assertTrue(plan.review_ids)
        plan.with_user(self.manager).validate_tier()
        self.assertEqual(plan.state, 'approved')

    def _budget_by_combo(self, budget):
        column = self.analytic_plan._column_name()
        return {(line.account_id.id, line[column].id): line.budget_amount
                for line in budget.budget_line_ids}

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------
    def test_request_blocked_without_stage_or_cost(self):
        self._generate()
        with self.assertRaises(UserError) as error:
            self.plan.with_user(self.planner).action_request_approval()
        message = str(error.exception)
        self.assertIn('Líneas sin etapa: 2', message)
        self.assertIn('Melamina blanco RH fantasía (test)', message)
        self.assertIn('Líneas sin costo', message)
        self.assertEqual(self.plan.state, 'draft')
        # P-03: «Sin etapa» aparece en el resumen mientras existan.
        self.assertIn('Sin etapa', self.plan.stage_summary_html)
        # Con etapa pero sin costo, sigue bloqueado y ya no lista etapas.
        self.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        with self.assertRaises(UserError) as error:
            self.plan.with_user(self.planner).action_request_approval()
        self.assertNotIn('sin etapa', str(error.exception))
        self.assertIn('Líneas sin costo', str(error.exception))
        # Una línea manual sin costo (vacío, no cero) también cuenta.
        unpriced = self.plan.unpriced_line_count
        self.env['construction.resource.plan.line'].create({
            'plan_id': self.plan.id, 'task_id': self.space_501.id, 'resource_type': 'material',
            'stage': 'assembly', 'product_id': self.p_cap.id, 'product_uom_id': self.unit.id,
            'qty_planned': 2})
        self.plan.invalidate_recordset(['unpriced_line_count'])
        self.assertEqual(self.plan.unpriced_line_count, unpriced + 1)

    def test_apply_cost_with_basis(self):
        """W-12: ponderado de las compras confirmadas, último precio, y el
        costo y su base quedan en las líneas en borrador."""
        self._generate()
        vendor = self.env['res.partner'].create({'name': 'Proveedor melamina (test)'})
        order = self.env['purchase.order'].create({
            'partner_id': vendor.id,
            'order_line': [
                (0, 0, {'product_id': self.p_white.id, 'product_qty': 10, 'price_unit': 100.0}),
                (0, 0, {'product_id': self.p_white.id, 'product_qty': 30, 'price_unit': 130.0}),
            ],
        })
        order.button_confirm()
        lines = self.plan.line_ids.filtered(lambda l: l.product_id == self.p_white)
        self.assertTrue(lines)
        form = Form(self.env['construction.plan.price.wizard'].with_context(
            default_plan_id=self.plan.id))
        form.product_id = self.p_white
        form.basis = 'weighted_6m'
        self.assertEqual(form.purchase_count, 2)
        self.assertAlmostEqual(form.price_weighted_6m, 122.5)
        self.assertAlmostEqual(form.price_last, 130.0)
        self.assertAlmostEqual(form.price_unit, 122.5)
        self.assertEqual(len(form.line_ids), len(lines))
        form.price_unit = 122.84  # el planificador escribe su costo
        wizard = form.save()
        wizard.action_apply()
        self.assertEqual(set(lines.mapped('price_unit_planned')), {122.84})
        self.assertIn('Ponderado de 6 meses', lines[0].price_basis)
        self.assertRegex(lines[0].price_basis, r'122[.,]84')
        self.assertEqual(lines[0].price_basis_date, wizard.basis_date)
        # Desde la lista de líneas: un solo producto por vez.
        with self.assertRaises(UserError):
            self.plan.line_ids.filtered('product_id')[:20].action_open_price_wizard()
        action = lines.action_open_price_wizard()
        self.assertEqual(action['context']['default_product_id'], self.p_white.id)
        # Plan no en borrador: ya no se aplica costo.
        self.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        self._price_all()
        self.plan.with_user(self.planner).action_request_approval()
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_approve_creates_budget_per_combination(self):
        plan = self._ready_plan()
        project_account = self.project.account_id
        materials = plan.line_ids.filtered(lambda l: l.resource_type == 'material')
        contracts = plan.line_ids - materials
        # Contratas: 60 % cocinas / 40 % closets; materiales: solo la obra.
        kitchen_key = '%s,%s' % (project_account.id, self.acc_kitchen.id)
        closet_key = '%s,%s' % (project_account.id, self.acc_closet.id)
        contracts.analytic_distribution = {kitchen_key: 60.0, closet_key: 40.0}
        materials.analytic_distribution = False
        self._approve(plan)
        budget = plan.budget_analytic_id
        self.assertTrue(budget)
        self.assertEqual(budget.state, 'confirmed')
        self.assertEqual(budget.company_id, plan.company_id)
        combos = self._budget_by_combo(budget)
        contract_total = sum(contracts.mapped('amount_planned'))
        material_total = sum(materials.mapped('amount_planned'))
        self.assertAlmostEqual(combos[(project_account.id, self.acc_kitchen.id)],
                               contract_total * 0.6, places=2)
        self.assertAlmostEqual(combos[(project_account.id, self.acc_closet.id)],
                               contract_total * 0.4, places=2)
        self.assertAlmostEqual(combos[(project_account.id, False)], material_total, places=2)
        self.assertAlmostEqual(sum(combos.values()), plan.amount_total, places=2)
        # Líneas congeladas: presupuesto = planificado y no se pueden editar.
        self.assertAlmostEqual(plan.amount_budgeted, plan.amount_total, places=2)
        self.assertIn('Presupuesto', plan.stage_summary_html)
        self.assertNotIn('Sin etapa', plan.stage_summary_html)
        with self.assertRaises(UserError):
            plan.line_ids[0].qty_planned = 99
        # Pasa a ejecución con el primer documento (gancho de las fases 4-6).
        plan._mark_in_progress()
        self.assertEqual(plan.state, 'in_progress')

    def test_reject_returns_to_draft(self):
        plan = self._ready_plan()
        plan.with_user(self.planner).action_request_approval()
        plan.with_user(self.manager).reject_tier()
        self.assertEqual(plan.state, 'draft')
        self.assertFalse(plan.budget_analytic_id)

    def test_approve_without_rules(self):
        self.tier_manager.active = False
        plan = self._ready_plan()
        plan.with_user(self.planner).action_request_approval()
        self.assertEqual(plan.state, 'approved')
        self.assertTrue(plan.budget_analytic_id)

    def test_replan_and_replace(self):
        plan_v1 = self._ready_plan()
        self._approve(plan_v1)
        budget_v1 = plan_v1.budget_analytic_id
        wizard = self.env['construction.plan.replan.wizard'].with_user(self.planner).create({
            'plan_id': plan_v1.id, 'reason': 'Cambio de melamina en el piso 05', 'mode': 'all'})
        action = wizard.action_create_version()
        plan_v2 = self.env['construction.resource.plan'].browse(action['res_id'])
        self.assertEqual(plan_v2.version, 2)
        self.assertEqual(plan_v2.state, 'draft')
        self.assertEqual(plan_v2.parent_id, plan_v1)
        self.assertEqual(len(plan_v2.line_ids), len(plan_v1.line_ids))
        self.assertEqual(plan_v2.line_ids.previous_line_id, plan_v1.line_ids)
        self.assertEqual(set(plan_v2.line_ids.mapped('source')), {'replan'})
        self.assertAlmostEqual(plan_v2.amount_total, plan_v1.amount_total, places=2)
        # Mientras la nueva no se aprueba, la anterior sigue vigente.
        self.assertEqual(plan_v1.state, 'approved')
        # Solo una versión en preparación por obra.
        with self.assertRaises(UserError):
            self.env['construction.plan.replan.wizard'].create({
                'plan_id': plan_v1.id, 'reason': 'Otra'}).action_create_version()
        # El motivo es obligatorio en una versión nueva.
        with self.assertRaises(ValidationError):
            plan_v2.replan_reason = ' '
        plan_v2.line_ids[0].qty_planned += 1
        self._approve(plan_v2)
        self.assertEqual(plan_v1.state, 'replaced')
        self.assertEqual(budget_v1.state, 'revised')
        self.assertEqual(plan_v2.budget_analytic_id.parent_id, budget_v1)
        self.assertEqual(plan_v2.version_count, 2)
        # Solo saldos: hoy sin consumos, copia las cantidades completas.
        wizard = self.env['construction.plan.replan.wizard'].create({
            'plan_id': plan_v2.id, 'reason': 'Saldos', 'mode': 'remaining'})
        plan_v3 = self.env['construction.resource.plan'].browse(
            wizard.action_create_version()['res_id'])
        self.assertEqual(len(plan_v3.line_ids), len(plan_v2.line_ids))

    def test_close(self):
        plan = self._ready_plan()
        self._approve(plan)
        with self.assertRaises(UserError):
            plan.with_user(self.planner).action_close()
        plan.with_user(self.manager).action_close()
        self.assertEqual(plan.state, 'closed')
        self.assertEqual(plan.budget_analytic_id.state, 'done')
        with self.assertRaises(UserError):
            plan.unlink()
        with self.assertRaises(UserError):
            plan.line_ids[0].price_unit_planned = 1

    def test_back_to_draft_restarts_reviews(self):
        plan = self._ready_plan()
        plan.with_user(self.planner).action_request_approval()
        plan.with_user(self.planner).action_draft()
        self.assertEqual(plan.state, 'draft')
        self.assertFalse(plan.review_ids)
        plan.line_ids[0].qty_planned += 1  # vuelve a ser editable

    def test_multicompany_budget(self):
        company_b = self.env['res.company'].create({'name': 'Compañía B (test)'})
        self.env.user.company_ids |= company_b
        env_b = self.env(context=dict(self.env.context, allowed_company_ids=company_b.ids))
        project_b = env_b['project.project'].create({
            'name': 'Obra B (test)', 'company_id': company_b.id, 'is_construction_site': True})
        if not project_b.account_id:
            project_b._create_analytic_account()
        plan_b = env_b['construction.resource.plan'].create({'project_id': project_b.id})
        env_b['construction.resource.plan.line'].create({
            'plan_id': plan_b.id, 'resource_type': 'material', 'stage': 'assembly',
            'product_id': self.p_cap.id, 'product_uom_id': self.unit.id,
            'qty_planned': 4, 'price_unit_planned': 2.5})
        self.tier_manager.active = False
        plan_b.action_request_approval()
        self.assertEqual(plan_b.state, 'approved')
        self.assertEqual(plan_b.budget_analytic_id.company_id, company_b)
        self.assertAlmostEqual(sum(plan_b.budget_analytic_id.budget_line_ids.mapped(
            'budget_amount')), 10.0)
        # El planificador de A no ve el plan de B.
        self.assertFalse(self.env['construction.resource.plan'].with_user(self.planner).search(
            [('id', '=', plan_b.id)]))
        # Un plan de A no puede apuntar al presupuesto de B.
        with self.assertRaises(UserError):
            self.plan.budget_analytic_id = plan_b.budget_analytic_id
