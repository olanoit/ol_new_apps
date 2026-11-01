# -*- coding: utf-8 -*-
"""Intervenir una contrata en ejecución (paquete 3 de CREVAL, CR-20) sin
comprometer dos veces (paquete 1.16, I-13). Datos ficticios."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_contract_terms_creval import PHOTO, ContractTermsCommon


@tagged('post_install', '-at_install')
class TestContractIntervention(ContractTermsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.contractor_b = cls.env['res.partner'].create({'name': 'Drywall Sur SAC (test)'})
        cls.defect_type = cls.env.ref(
            'al_construction_planner_subcontract.deduction_type_intervened_defect')

    def _first_valuation(self):
        """Orden A confirmada, sin adelanto: 1,000 m² de tabique valorizados
        y facturados (con su cuota de fondo) y 200 m² validados después."""
        _wizard, order = self._assign()
        order.button_confirm()
        self._report(self.partida, self.act_wall, 1000.0, date(2026, 11, 4))
        settlement = self.env['construction.contract.settlement']._prepare_terms_settlements(
            today=date(2026, 11, 20)).filtered(lambda s: s.purchase_order_id == order)
        settlement.action_submit()
        settlement.action_validate()
        self.assertEqual(settlement.state, 'approved')
        self._post(settlement.invoice_id, date(2026, 11, 21))
        self._report(self.partida, self.act_wall, 200.0, date(2026, 11, 24))
        return order

    def _wizard(self, order=None, **context):
        Wizard = self.env['construction.contract.intervention.wizard'].with_context(**context)
        values = {'date': date(2026, 11, 25), 'reason': 'Abandono de la obra'}
        if order:
            values['purchase_order_id'] = order.id
        return Wizard.create(values)

    def test_intervene_reassign_and_liquidate(self):
        order = self._first_valuation()
        fund = order.construction_guarantee_fund_ids
        self.assertEqual(len(fund), 1)
        wall_po = order.order_line.filtered(lambda l: l.construction_task_id == self.partida)
        plan_wall = self.plan.line_ids.filtered(lambda l: l.task_id == self.partida)
        old_progress = self.env['construction.task.progress'].search(
            [('plan_line_id', '=', plan_wall.id)])
        self.assertEqual(old_progress.partner_id, self.contractor)

        # Preliquidación por partida, sin asiento.
        moves_before = self.env['account.move'].search_count([])
        wizard = self._wizard(order)
        wall = wizard.line_ids.filtered(lambda r: r.purchase_line_id == wall_po)
        self.assertEqual(wall.qty_contracted, 2000.0)
        self.assertEqual(wall.qty_validated, 1200.0)
        self.assertEqual(wall.qty_valued, 1000.0)
        self.assertEqual(wall.qty_new, 1200.0)
        self.assertEqual(wall.qty_released, 800.0)
        self.assertAlmostEqual(wall.amount_released, 800 * 38.20)
        self.assertEqual(wizard.fund_amount, fund.amount_residual)
        action = wizard.action_confirm()
        self.assertEqual(self.env['account.move'].search_count([]), moves_before)
        intervention = self.env['construction.contract.intervention'].browse(action['res_id'])
        self.assertEqual(intervention.purchase_order_id, order)
        self.assertEqual(intervention.name, '%s-INT01' % order.name)

        # La OC baja a lo ejecutado y no se cancela; el plan queda sin
        # contrata y con el saldo libre.
        self.assertTrue(order.construction_intervened)
        self.assertEqual(order.state, 'purchase')
        self.assertEqual(wall_po.product_qty, 1200.0)
        self.assertEqual(wall_po.construction_intervention_date, date(2026, 11, 25))
        self.assertFalse(plan_wall.partner_id)
        self.assertEqual(plan_wall.qty_requested, 1200.0)
        # El avance anterior sigue siendo de la contrata que sale.
        self.assertEqual(old_progress.partner_id, self.contractor)
        # Fondo retenido con el motivo.
        self.assertTrue(fund.hold)
        self.assertTrue(fund.hold_by_intervention)
        self.assertEqual(fund.state, 'retained')
        self.assertIn('Contrata intervenida', fund.hold_reason)

        # El saldo va a la contrata que entra.
        assign = self.env['construction.plan.contract.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_task_ids=self.partida.ids,
        ).create({'stage': 'creval_tab', 'partner_id': self.contractor_b.id,
                  'condition_id': self.condition.id, 'date_start': date(2026, 11, 26)})
        self.assertEqual(sum(assign.line_ids.mapped('qty')), 800.0)
        assign.action_assign()
        order_b = self.env['purchase.order'].search([
            ('partner_id', '=', self.contractor_b.id),
            ('construction_project_id', '=', self.project.id)])
        self.assertEqual(order_b.order_line.product_qty, 800.0)
        self.assertEqual(plan_wall.partner_id, self.contractor_b)
        self.assertEqual(plan_wall.qty_requested, 2000.0)
        order_b.button_confirm()
        new_progress = self._report(self.partida, self.act_wall, 100.0, date(2026, 11, 27))
        self.assertEqual(new_progress.partner_id, self.contractor_b)
        self.assertEqual(old_progress.partner_id, self.contractor)
        # Historial de contratas de la partida.
        history = self.partida.construction_contract_history_ids
        self.assertEqual(history.mapped('contract_partner_id'), self.contractor | self.contractor_b)
        status = {a.contract_partner_id: (a.contract_status, a.contract_date_to) for a in history}
        self.assertEqual(status[self.contractor], ('intervened', date(2026, 11, 25)))
        self.assertEqual(status[self.contractor_b][0], 'open')
        # La orden intervenida no entra a la nueva valorización de B.
        self.assertFalse(self.env['construction.contract.settlement'].search(
            [('purchase_order_id', '=', order_b.id)]).progress_ids & old_progress)

        # Deductivo por defecto de la contrata que sale, mayor que lo que
        # queda por pagar: la diferencia va contra el fondo.
        self._deduction(order, 8000.0, type_id=self.defect_type.id, date=date(2026, 11, 24),
                        description='Tabique mal anclado, rehecho por la contrata que entra')
        liquidation = self.env['construction.contract.settlement'].browse(
            order.action_construction_liquidate()['res_id'])
        self.assertEqual(liquidation.amount_direct, 7640.0)
        self.assertGreaterEqual(liquidation.amount_to_pay, 0.0)
        self.assertLess(liquidation.amount_to_pay, 1.0)
        self.assertGreater(liquidation.amount_fund_charge, 0.0)
        self.assertAlmostEqual(liquidation.amount_deductions + liquidation.amount_fund_charge,
                               8000.0, places=2)
        liquidation.action_submit()
        liquidation.action_validate()
        self.assertEqual(liquidation.state, 'approved')
        invoice = liquidation.invoice_id
        self.assertGreaterEqual(invoice.amount_total, 0.0)
        deduction_lines = invoice.invoice_line_ids.filtered(lambda l: 'Deductivo' in (l.name or ''))
        self.assertAlmostEqual(-sum(deduction_lines.mapped('price_subtotal')),
                               liquidation.amount_deductions, places=2)
        refund = liquidation.fund_charge_move_id
        self.assertEqual(refund.move_type, 'in_refund')
        self.assertEqual(refund.state, 'draft')
        self.assertAlmostEqual(refund.amount_untaxed, liquidation.amount_fund_charge, places=2)
        # Sin publicar la nota, el fondo sigue retenido.
        self.assertTrue(fund.hold)
        self._post(invoice, date(2026, 11, 29))
        residual = fund.amount_residual
        self._post(refund, date(2026, 11, 29))
        self.assertAlmostEqual(fund.amount_charged, refund.amount_total, places=2)
        self.assertAlmostEqual(fund.amount_residual, residual - refund.amount_total, places=2)
        self.assertFalse(fund.hold)
        self.assertNotEqual(fund.state, 'retained')
        self.assertEqual(refund.payment_state, 'paid')

    def test_from_schedule_and_checks(self):
        order = self._first_valuation()
        # Desde el Cronograma: la orden de las partidas marcadas, solo esas.
        wizard = self._wizard(construction_selection_task_ids=self.partida.ids)
        self.assertEqual(wizard.purchase_order_id, order)
        chosen = wizard.line_ids.filtered('intervene')
        self.assertEqual(chosen.purchase_line_id.construction_task_id, self.partida)
        self.assertEqual(len(wizard.line_ids), 2)
        # Un avance reportado sin validar detiene la intervención.
        pending = self.env['construction.task.progress'].create({
            'task_id': self.partida.id, 'activity_id': self.act_wall.id,
            'date': date(2026, 11, 25), 'qty': 10.0,
            'attachment_ids': [(0, 0, {'name': 'foto.jpg', 'datas': PHOTO})]})
        with self.assertRaises(UserError):
            wizard.action_confirm()
        pending.unlink()
        # La intervención no puede ser anterior al último avance validado.
        wizard.date = date(2026, 11, 23)
        with self.assertRaises(UserError):
            wizard.action_confirm()
        wizard.date = date(2026, 11, 25)
        # Solo quien aprueba la ejecución.
        user = self.env['res.users'].create({
            'name': 'Residente (test)', 'login': 'residente_int_test',
            'group_ids': [(6, 0, [self.env.ref('al_construction_planner.group_planner_user').id,
                                  self.env.ref('purchase.group_purchase_user').id])]})
        with self.assertRaises(UserError):
            wizard.with_user(user).action_confirm()
        wizard.action_confirm()
        seal_po = order.order_line.filtered(lambda l: l.construction_task_id == self.extra_task)
        self.assertFalse(seal_po.construction_intervention_line_id)
        # Sin deductivos que superen lo pendiente, la liquidación final levanta
        # la retención del fondo.
        liquidation = self.env['construction.contract.settlement'].browse(
            order.action_construction_liquidate()['res_id'])
        self.assertFalse(liquidation.amount_fund_charge)
        liquidation.action_submit()
        liquidation.action_validate()
        self.assertFalse(liquidation.fund_charge_move_id)
        fund = order.construction_guarantee_fund_ids.filtered('move_line_id')[:1]
        self.assertFalse(fund.hold)
