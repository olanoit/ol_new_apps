# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo.tests import new_test_user, tagged

from .common import PlannerCommon


@tagged('post_install', '-at_install')
class TestSupply(PlannerCommon):
    """Fase 4, asignaciones y compras: compra masiva (W-02), requerimiento de
    obra con control de plan (W-03, W-10), OF desde la BOM (W-04), estado de
    la línea, traspaso al replanificar y multicompañía."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # La jefatura revisa el exceso de los requerimientos: necesita verlos.
        cls.manager = new_test_user(
            cls.env, 'plan_jefatura_f4', name='Jefatura (test)',
            groups='al_construction_planner.group_planner_manager,'
                   'al_construction_material_request.group_construction_approver')
        cls.buyer = new_test_user(
            cls.env, 'plan_compras_f4', name='Planificador comprador (test)',
            groups='al_construction_planner.group_planner_planner,'
                   'purchase_request.group_purchase_request_user,'
                   'al_construction_material_request.group_construction_requester,'
                   'mrp.group_mrp_user')
        # Solo la regla de exceso del módulo: las demás reglas del
        # requerimiento (p. ej. las demo) se apagan.
        cls.tier_exceed = cls.env.ref('al_construction_planner.tier_material_request_exceed')
        cls.env['tier.definition'].search([
            ('model', '=', 'construction.material.request'),
            ('id', '!=', cls.tier_exceed.id)]).active = False
        cls.tier_exceed.active = True
        cls.company._al_construction_ensure_setup()
        if not cls.project.account_id:
            cls.project._create_analytic_account()
        # El residente (comprador del test) ve los requerimientos de las obras
        # que sigue.
        cls.project.message_subscribe(partner_ids=cls.buyer.partner_id.ids)

        cls._generate_and_approve()

    @classmethod
    def _generate_and_approve(cls):
        wizard = cls.env['construction.plan.generate.wizard'].create({'plan_id': cls.plan.id})
        wizard.action_generate()
        cls.plan.line_ids.filtered(lambda l: not l.stage).stage = 'production'
        for line in cls.plan.line_ids.filtered(lambda l: not l.price_unit_planned):
            line.price_unit_planned = 10.0
        cls.plan.action_request_approval()
        assert cls.plan.state == 'approved', cls.plan.state

    def _lines(self, product, plan=None):
        return (plan or self.plan).line_ids.filtered(
            lambda l: l.product_id == product).sorted(lambda l: (l.date_needed, l.id))

    def _set_policy(self, policy, tolerance=0.0):
        self.plan.write({'exceed_policy': policy, 'exceed_tolerance': tolerance})

    def _request(self, product, qty, task=None):
        return self.env['construction.material.request'].with_user(self.buyer).create({
            'project_id': self.project.id,
            'task_id': (task or self.floor).id,
            'line_ids': [(0, 0, {'product_id': product.id, 'product_qty': qty})],
        })

    # ------------------------------------------------------------------
    # W-02 compra masiva
    # ------------------------------------------------------------------
    def test_purchase_project_mode(self):
        wizard = self.env['construction.plan.purchase.wizard'].with_user(self.buyer).with_context(
            default_plan_id=self.plan.id, construction_selection_project=True).create({})
        self.assertTrue(wizard.whole_project)
        white = wizard.line_ids.filtered(lambda l: l.product_id == self.p_white)
        self.assertAlmostEqual(white.qty_need, 3.92)
        # Unidades: se redondea a entero hacia arriba (P-10, planchas).
        self.assertEqual(white.qty_to_buy, 4.0)
        action = wizard.action_create()
        request = self.env['purchase.request'].browse(action['res_id'])
        self.assertEqual(request.construction_plan_id, self.plan)
        pr_line = request.line_ids.filtered(lambda l: l.product_id == self.p_white)
        self.assertEqual(pr_line.construction_plan_mode, 'project')
        self.assertEqual(pr_line.analytic_distribution,
                         {str(self.project.account_id.id): 100.0})
        lines = self._lines(self.p_white)
        # Primero la línea que se necesita antes; el redondeo, a la última.
        self.assertEqual(sum(pr_line.construction_allocation_ids.mapped('qty_allocated')), 4.0)
        self.assertAlmostEqual(sum(lines.mapped('qty_purchased')), 4.0)
        self.assertEqual(set(lines.mapped('line_state')), {'purchasing'})
        self.assertEqual(lines[0].qty_requested, 0.0)
        self.assertEqual(self.plan.state, 'in_progress')
        self.assertEqual(self.plan.allocation_count,
                         len(request.line_ids.construction_allocation_ids))
        # Comprometido: lo comprado al costo del plan.
        self.assertAlmostEqual(sum(lines.mapped('amount_committed')), 40.0)
        # Una segunda compra masiva ya no ve necesidad de melamina blanca.
        again = self.env['construction.plan.purchase.wizard'].with_context(
            default_plan_id=self.plan.id).create({})
        self.assertFalse(again.line_ids.filtered(lambda l: l.product_id == self.p_white))

    def test_purchase_general_mode(self):
        self.p_white.is_storable = True
        wizard = self.env['construction.plan.purchase.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=[self.apt_501.id],
        ).create({'mode': 'general'})
        self.assertFalse(wizard.whole_project)
        central = wizard.picking_type_id.default_location_dest_id
        self.env['stock.quant']._update_available_quantity(self.p_white, central, 1.0)
        wizard.mode = 'project'
        wizard.mode = 'general'
        white = wizard.line_ids.filtered(lambda l: l.product_id == self.p_white)
        # Solo el Dpto 501: 1.96 de necesidad, 1 libre → 0.96 → 1 plancha.
        self.assertAlmostEqual(white.qty_need, 1.96)
        self.assertEqual(white.qty_free, 1.0)
        self.assertEqual(white.qty_to_buy, 1.0)
        # Sin etapas de instalación: no hay tornillos.
        wizard.stage_installation = False
        self.assertFalse(wizard.line_ids.filtered(lambda l: l.product_id == self.p_screw))
        action = wizard.action_create()
        request = self.env['purchase.request'].browse(action['res_id'])
        pr_line = request.line_ids.filtered(lambda l: l.product_id == self.p_white)
        self.assertFalse(pr_line.analytic_distribution)
        self.assertEqual(pr_line.construction_plan_mode, 'general')
        line_501 = self._lines(self.p_white).filtered(lambda l: l.space_task_id == self.space_501)
        self.assertEqual(line_501.qty_purchased, 1.0)
        self.assertFalse(self._lines(self.p_white).filtered(
            lambda l: l.space_task_id == self.space_502).allocation_ids)
        # El requerimiento cancelado deja la línea sin comprado.
        pr_line.do_cancel()
        self.assertEqual(line_501.qty_purchased, 0.0)
        self.assertEqual(line_501.allocation_ids.state, 'cancel')
        self.assertEqual(line_501.line_state, 'planned')

    # ------------------------------------------------------------------
    # W-03 requerimiento de obra y control de plan
    # ------------------------------------------------------------------
    def test_request_wizard_grouped_by_floor(self):
        wizard = self.env['construction.plan.request.wizard'].with_user(self.buyer).with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=[self.floor.id],
        ).create({'group_by': 'floor'})
        screws = wizard.line_ids.filtered(lambda l: l.product_id == self.p_screw)
        self.assertEqual(screws.group_task_id, self.floor)
        self.assertEqual(screws.qty_planned, 242.0)
        self.assertEqual(screws.qty_to_request, 242.0)
        wizard.group_by = 'space'
        self.assertEqual(len(wizard.line_ids.filtered(lambda l: l.product_id == self.p_screw)), 2)
        wizard.group_by = 'floor'
        action = wizard.action_create()
        request = self.env['construction.material.request'].browse(action['res_id'])
        self.assertEqual(request.construction_plan_id, self.plan)
        self.assertEqual(request.task_id, self.floor)
        line = request.line_ids.filtered(lambda l: l.product_id == self.p_screw)
        self.assertEqual(line.task_id, self.floor)
        self.assertEqual(len(line.construction_allocation_ids), 2)
        self.assertEqual(set(line.construction_allocation_ids.plan_line_id.space_task_id.ids),
                         {self.space_501.id, self.space_502.id})
        self.assertEqual(line.construction_plan_control, 'En plan')
        self.assertEqual(line.construction_plan_remaining, 242.0)
        plan_lines = self._lines(self.p_screw)
        self.assertEqual(plan_lines.mapped('qty_requested'), [121.0, 121.0])
        self.assertEqual(plan_lines.mapped('qty_remaining'), [0.0, 0.0])
        self.assertEqual(set(plan_lines.mapped('line_state')), {'partial'})
        # Al pedir la aprobación (sin exceso) se aprueba y se reparte igual.
        request.with_user(self.buyer).action_request_approval()
        self.assertEqual(request.state, 'approved')
        self.assertEqual(request.construction_exceed_state, 'ok')
        self.assertEqual(plan_lines.mapped('qty_requested'), [121.0, 121.0])
        # Nada más que pedir: el asistente ya no propone tornillos.
        again = self.env['construction.plan.request.wizard'].with_context(
            default_plan_id=self.plan.id).create({})
        self.assertFalse(again.line_ids.filtered(lambda l: l.product_id == self.p_screw))

    def test_request_policy_warn(self):
        self._set_policy('warn')
        request = self._request(self.p_screw, 300)
        line = request.line_ids
        self.assertIn('Excede 58', line.construction_plan_control)
        self.assertTrue(line.construction_plan_exceeded)
        action = request.with_user(self.buyer).action_request_approval()
        self.assertEqual(action['res_model'], 'construction.plan.exceed.wizard')
        wizard = self.env['construction.plan.exceed.wizard'].browse(action['res_id'])
        self.assertEqual(wizard.policy, 'warn')
        self.assertEqual(wizard.line_ids.qty_excess, 58.0)
        wizard.with_user(self.buyer).action_confirm()
        self.assertEqual(request.state, 'approved')
        self.assertEqual(request.construction_exceed_state, 'exceeded')
        self.assertFalse(request.review_ids)
        plan_lines = self._lines(self.p_screw)
        self.assertEqual(plan_lines.mapped('qty_requested'), [121.0, 179.0])
        self.assertEqual(plan_lines.mapped('line_state'), ['partial', 'exceeded'])
        self.assertEqual(self.plan.state, 'in_progress')

    def test_request_policy_approval(self):
        self._set_policy('approval')
        request = self._request(self.p_screw, 300)
        action = request.with_user(self.buyer).action_request_approval()
        wizard = self.env['construction.plan.exceed.wizard'].browse(action['res_id'])
        with self.assertRaises(UserError):
            wizard.with_user(self.buyer).action_confirm()
        wizard.reason = 'Se rompieron tornillos en el armado'
        wizard.with_user(self.buyer).action_confirm()
        self.assertEqual(request.state, 'to_approve')
        self.assertEqual(request.construction_exceed_state, 'exceeded')
        self.assertEqual(request.construction_exceed_reason, 'Se rompieron tornillos en el armado')
        self.assertEqual(request.review_ids.definition_id, self.tier_exceed)
        request.with_user(self.manager).validate_tier()
        self.assertEqual(request.state, 'approved')
        self.assertEqual(request.construction_exceed_state, 'approved')

    def test_request_policy_block_and_tolerance(self):
        self._set_policy('block')
        request = self._request(self.p_screw, 300)
        with self.assertRaises(UserError):
            request.with_user(self.buyer).action_request_approval()
        self.assertEqual(request.state, 'draft')
        # Con 30 % de tolerancia (242 × 1.3 = 314.6) los 300 caben.
        self._set_policy('block', 30.0)
        request.invalidate_recordset()
        request.with_user(self.buyer).action_request_approval()
        self.assertEqual(request.state, 'approved')
        self.assertEqual(request.construction_exceed_state, 'ok')
        # Un material que el plan no tiene bajo ese nivel: fuera de plan.
        other = self.env['product.product'].create({'name': 'Silicona (test)', 'type': 'consu'})
        outside = self._request(other, 1)
        self.assertTrue(outside.line_ids.construction_out_of_plan)
        self.assertEqual(outside.line_ids.construction_plan_control, 'Fuera de plan')
        with self.assertRaises(UserError):
            outside.with_user(self.buyer).action_request_approval()

    # ------------------------------------------------------------------
    # W-04 orden de fabricación
    # ------------------------------------------------------------------
    def test_production_from_bom(self):
        wizard = self.env['construction.plan.production.wizard'].with_user(self.buyer).with_context(
            default_plan_id=self.plan.id, construction_selection_project=True).create({})
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids.group_task_id, self.floor)
        self.assertEqual(wizard.line_ids.space_count, 2)
        action = wizard.action_create()
        production = self.env['mrp.production'].browse(action['res_id'])
        self.assertEqual(production.product_id, self.kitchen.product_variant_id)
        self.assertEqual(production.product_qty, 2)
        self.assertEqual(production.construction_space_task_ids, self.space_501 | self.space_502)
        self.assertEqual(set(production.move_raw_ids.product_id.ids), {
            p.id for p in (self.p_white, self.p_cognac, self.p_rh, self.p_hinge,
                           self.p_screw, self.p_cap)})
        # Asignaciones solo a producción y armado (los tornillos van a obra).
        allocated = production.construction_allocation_ids.plan_line_id.product_id
        self.assertEqual(allocated, self.p_white | self.p_cognac | self.p_rh | self.p_hinge)
        hinges = self._lines(self.p_hinge)
        self.assertEqual(hinges.mapped('qty_requested'), [10.0, 10.0])
        # Ya en una OF: el asistente no vuelve a proponer esos ambientes.
        again = self.env['construction.plan.production.wizard'].with_context(
            default_plan_id=self.plan.id).create({})
        self.assertFalse(again.line_ids)
        self.assertIn('Ya en una OF', again.note)
        production.with_user(self.buyer).action_confirm()
        self.assertEqual(production.state, 'confirmed')
        self.assertEqual(production.construction_exceed_state, 'ok')
        # Cerrar la OF sube lo consumido.
        production.qty_producing = 2
        for move in production.move_raw_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        production.button_mark_done()
        self.assertEqual(production.state, 'done')
        self.assertEqual(hinges.mapped('qty_consumed'), [10.0, 10.0])
        self.assertEqual(set(hinges.mapped('line_state')), {'done'})
        self.assertAlmostEqual(sum(hinges.mapped('amount_actual')), 200.0)

    def test_production_confirm_control(self):
        self._set_policy('block')
        wizard = self.env['construction.plan.production.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=[self.apt_501.id],
        ).create({'group_by': 'selection'})
        self.assertFalse(wizard.line_ids.group_task_id)
        self.assertEqual(wizard.line_ids.space_count, 1)
        production = self.env['mrp.production'].browse(wizard.action_create()['res_id'])
        hinge_move = production.move_raw_ids.filtered(lambda m: m.product_id == self.p_hinge)
        hinge_move.product_uom_qty = 25  # el plan del Dpto 501 tiene 10
        with self.assertRaises(UserError):
            production.with_user(self.buyer).action_confirm()
        self._set_policy('approval')
        action = production.with_user(self.buyer).action_confirm()
        exceed = self.env['construction.plan.exceed.wizard'].browse(action['res_id'])
        self.assertEqual(exceed.line_ids.product_id, self.p_hinge)
        self.assertEqual(exceed.line_ids.qty_excess, 15.0)
        exceed.reason = 'Bisagras de repuesto'
        # El exceso de una OF lo aprueba la jefatura.
        with self.assertRaises(UserError):
            exceed.with_user(self.buyer).action_confirm()
        exceed.with_user(self.manager).action_confirm()
        self.assertEqual(production.state, 'confirmed')
        self.assertEqual(production.construction_exceed_state, 'approved')
        line_501 = self._lines(self.p_hinge).filtered(
            lambda l: l.space_task_id == self.space_501)
        self.assertEqual(line_501.qty_requested, 25.0)
        self.assertEqual(line_501.line_state, 'exceeded')

    # ------------------------------------------------------------------
    # Versiones, cierre y multicompañía
    # ------------------------------------------------------------------
    def test_replan_transfers_open_allocations(self):
        request_wizard = self.env['construction.plan.request.wizard'].with_context(
            default_plan_id=self.plan.id).create({})
        request_wizard.line_ids.filtered(lambda l: l.product_id != self.p_screw).unlink()
        request = self.env['construction.material.request'].browse(
            request_wizard.action_create()['res_id'])
        request.action_request_approval()
        old_lines = self._lines(self.p_screw)
        self.assertEqual(old_lines.mapped('qty_requested'), [121.0, 121.0])
        self.assertEqual(old_lines[0]._get_consumed_qty(), 0.0)  # aún abierta
        # Cierre bloqueado con documentos abiertos.
        with self.assertRaises(UserError) as error:
            self.plan.with_user(self.manager).action_close()
        self.assertIn(request.name, str(error.exception))
        replan = self.env['construction.plan.replan.wizard'].create({
            'plan_id': self.plan.id, 'reason': 'Cambio de tipología', 'mode': 'remaining'})
        new_plan = self.env['construction.resource.plan'].browse(
            replan.action_create_version()['res_id'])
        new_plan.action_request_approval()
        self.assertEqual(new_plan.state, 'approved')
        self.assertEqual(self.plan.state, 'replaced')
        new_lines = self._lines(self.p_screw, new_plan)
        self.assertEqual(new_lines.allocation_ids, request.line_ids.construction_allocation_ids)
        self.assertEqual(new_lines.mapped('qty_requested'), [121.0, 121.0])
        self.assertFalse(old_lines.allocation_ids)
        self.assertEqual(new_lines.mapped('previous_line_id'), old_lines)

    def test_multicompany(self):
        other = self.env['res.company'].create({'name': 'Otra constructora (test)'})
        self.env.user.company_ids |= other
        pr = self.env['purchase.request'].with_company(other).create({
            'company_id': other.id,
            'line_ids': [(0, 0, {'product_id': self.p_white.id, 'product_qty': 1,
                                 'company_id': other.id})],
        })
        with self.assertRaises(UserError):  # check_company
            self.env['construction.resource.plan.allocation'].create({
                'plan_line_id': self._lines(self.p_white)[0].id,
                'kind': 'purchase_request',
                'purchase_request_line_id': pr.line_ids.id,
                'qty_allocated': 1,
            })
        wizard = self.env['construction.plan.purchase.wizard'].with_context(
            default_plan_id=self.plan.id).create({})
        own_pr = self.env['purchase.request'].browse(wizard.action_create()['res_id'])
        # El tipo debe coincidir con el documento enlazado.
        with self.assertRaises(ValidationError):
            self.env['construction.resource.plan.allocation'].create({
                'plan_line_id': self._lines(self.p_white)[0].id,
                'kind': 'production',
                'purchase_request_line_id': own_pr.line_ids[:1].id,
                'qty_allocated': 1,
            })
        # Un usuario de la otra compañía no ve las asignaciones de esta.
        outsider = new_test_user(
            self.env, 'plan_otra_cia', groups='al_construction_planner.group_planner_planner',
            company_id=other.id, company_ids=[(6, 0, [other.id])], name='Otra compañía (test)')
        self.assertFalse(self.env['construction.resource.plan.allocation'].with_user(
            outsider).search([('plan_id', '=', self.plan.id)]))
