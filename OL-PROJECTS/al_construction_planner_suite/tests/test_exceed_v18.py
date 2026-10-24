# -*- coding: utf-8 -*-
"""Control de consumo sin repetición (v1.8, M18-05), pago repetido y
re-trabajo de contratas (M18-21) y porcentaje manual en la liquidación
(M18-09, parte de contratas)."""
from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_contracts import PHOTO, TestContracts
from .test_supply import TestSupply


@tagged('post_install', '-at_install')
class TestConsumptionControl(TestSupply):

    def test_policy_defaults_from_company_and_types(self):
        self.company.write({'construction_exceed_policy': 'block',
                            'construction_exceed_policy_labor': 'warn'})
        site = self.env['project.project'].create({'name': 'Obra con política (test)',
                                                   'is_construction_site': True})
        self.assertEqual(site.construction_exceed_policy, 'block')
        plan = self.env['construction.resource.plan'].create({'project_id': site.id})
        self.assertEqual(plan.exceed_policy, 'block')
        self.assertEqual(plan._exceed_policy_for('labor'), 'warn')
        self.assertEqual(plan._exceed_policy_for('contract'), 'block')
        plan.exceed_policy_material = 'approval'
        self.assertEqual(plan._exceed_policy_for('equipment'), 'approval')

    def test_second_request_waits_for_head_and_is_logged(self):
        """Criterio: con «aprobación adicional», un segundo requerimiento de
        melamina para un nivel cuya producción de piezas ya se pidió entera
        espera a la jefatura y la autorización queda registrada."""
        self._set_policy('approval')
        plan_lines = self.plan.line_ids.filtered(
            lambda l: l.space_task_id == self.space_501 and l.stage == 'production'
            and l.resource_type == 'material' and l.product_id)
        products = {}
        for line in plan_lines:
            products[line.product_id] = products.get(line.product_id, 0.0) + line.qty_planned
        first = self.env['construction.material.request'].with_user(self.buyer).create({
            'project_id': self.project.id, 'task_id': self.space_501.id,
            'line_ids': [Command.create({'product_id': product.id, 'product_qty': qty})
                         for product, qty in products.items()]})
        first.with_user(self.buyer).action_request_approval()
        self.assertEqual(first.state, 'approved')
        white = self.plan.line_ids.filtered(
            lambda l: l.space_task_id == self.space_501 and l.product_id == self.p_white)[:1]
        second = self._request(self.p_white, 1.0, self.space_501)
        self.assertTrue(second.line_ids.sudo()._construction_is_repeat())
        action = second.with_user(self.buyer).action_request_approval()
        wizard = self.env['construction.plan.exceed.wizard'].browse(action['res_id'])
        self.assertEqual(wizard.policy, 'approval')
        wizard.reason = 'Plancha dañada en el corte'
        wizard.with_user(self.buyer).action_confirm()
        self.assertEqual(second.state, 'to_approve')
        second.with_user(self.manager).validate_tier()
        self.assertEqual(second.state, 'approved')
        log = self.env['construction.exceed.log'].search([('res_id', '=', second.id),
                                                          ('res_model', '=', second._name)])
        self.assertEqual(len(log), 1)
        self.assertEqual(log.user_id, self.manager)
        self.assertEqual(log.reason, 'Plancha dañada en el corte')
        self.assertEqual(log.product_id, self.p_white)
        self.assertEqual(log.plan_line_id, white)
        self.assertAlmostEqual(log.qty, 1.0)
        self.assertIn(log, self.plan.exceed_log_ids)


@tagged('post_install', '-at_install')
class TestRepeatAndRework(TestContracts):

    def _settle(self, day):
        Settlement = self.env['construction.contract.settlement']
        settlement = Settlement._prepare_settlements(day, self.project)
        settlement.with_user(self.planner).action_submit()
        return settlement

    def _approve(self, settlement):
        settlement.with_user(self.planner).action_validate()
        settlement.with_user(self.manager).validate_tier()
        self.assertEqual(settlement.state, 'approved')

    def test_repeat_payment_waits_for_head(self):
        """Criterio: una segunda liquidación del mismo módulo y actividad
        espera la autorización de la jefatura."""
        self.plan.exceed_tolerance = 100.0
        self._assign_installation()
        self._confirm_order()
        line = self._line('Dpto 501', 'INB')
        self._report('Dpto 501', 'INB', line.qty_planned, date(2026, 11, 3)).with_user(
            self.planner).action_validate()
        first = self._settle(date(2026, 11, 5))
        self.assertFalse(first.needs_head_authorization)
        self._approve(first)
        self._report('Dpto 501', 'INB', 1.0, date(2026, 11, 10)).with_user(
            self.planner).action_validate()
        second = self._settle(date(2026, 11, 12))
        repeated = second.line_ids.filtered('is_repeat')
        self.assertAlmostEqual(repeated.qty_repeat, 1.0)
        self.assertTrue(second.needs_head_authorization)
        with self.assertRaises(UserError):
            second.with_user(self.planner).action_validate()
        with self.assertRaises(UserError):
            second.with_user(self.planner).action_head_authorize()
        second.with_user(self.manager).action_head_authorize()
        self.assertFalse(second.needs_head_authorization)
        log = self.env['construction.exceed.log'].search([('res_id', '=', second.id),
                                                          ('kind', '=', 'repeat_payment')])
        self.assertEqual(log.user_id, self.manager)
        self._approve(second)

    def test_rework_paid_apart(self):
        """Criterio: un re-trabajo con motivo «mal armado» entra con 0 a liquidar
        (CREVAL v1.0, CR-08); si el validador decide pagarlo, se liquida sin
        bloqueo y queda separado en el análisis de control."""
        self._assign_installation()
        self._confirm_order()
        line = self._line('Dpto 501', 'INB')
        self._report('Dpto 501', 'INB', line.qty_planned, date(2026, 11, 3)).with_user(
            self.planner).action_validate()
        rework = self.env['construction.task.progress'].with_user(self.reporter).create({
            'task_id': line.task_id.id, 'activity_id': line.activity_id.id,
            'date': date(2026, 11, 3), 'qty': 1.0, 'is_rework': True,
            'rework_reason': 'bad_assembly',
            'attachment_ids': [Command.create({'name': 'foto.jpg', 'datas': PHOTO})]})
        rework.with_user(self.planner).action_validate()
        self.assertAlmostEqual(line.qty_executed, line.qty_planned)
        settlement = self._settle(date(2026, 11, 5))
        rework_line = settlement.line_ids.filtered('is_rework')
        self.assertEqual(rework_line.rework_reason, 'bad_assembly')
        self.assertAlmostEqual(rework_line.qty_settle, 0.0)
        rework_line.with_user(self.planner).write({
            'rework_paid': True, 'rework_pay_reason': 'Cambio del cliente después del armado'})
        self.assertAlmostEqual(rework_line.qty_settle, 1.0)
        self.assertFalse(settlement.needs_head_authorization)
        self._approve(settlement)
        log = self.env['construction.exceed.log'].search([('res_id', '=', settlement.id),
                                                          ('kind', '=', 'rework')])
        self.assertEqual(log.rework_reason, 'bad_assembly')
        self.assertAlmostEqual(log.amount, rework_line.amount)
        names = settlement.invoice_id.invoice_line_ids.mapped('name')
        self.assertTrue(any('Re-trabajo' in (name or '') for name in names))

    def test_manual_pct_over_validated(self):
        """Criterio de M18-09 (contratas): la línea propone el % validado y se
        liquida a un % escrito con motivo y aprobación, marcado como manual."""
        self._assign_installation()
        self._confirm_order()
        self._report_example().with_user(self.planner).action_validate()
        settlement = self._settle(date(2026, 11, 5))
        low = settlement.line_ids.filtered(lambda l: l.activity_id == self.act['INB'])
        self.assertAlmostEqual(low.pct_validated, round(10.14 / 21.27 * 100, 2))
        with self.assertRaises(UserError):
            low.with_user(self.planner).write({'pct_manual': 50.0})
        low.with_user(self.planner).write({'pct_manual': 50.0,
                                           'manual_reason': 'Adelanto pactado por el piso'})
        self.assertTrue(low.is_manual)
        self.assertTrue(low.manual_over)
        self.assertEqual(low.manual_user_id, self.planner)
        self.assertAlmostEqual(low.qty_settle, 21.27 * 0.5, delta=0.01)
        self.assertTrue(settlement.needs_head_authorization)
        with self.assertRaises(UserError):
            settlement.with_user(self.planner).action_validate()
        settlement.with_user(self.manager).action_head_authorize()
        self._approve(settlement)
        self.assertAlmostEqual(low.purchase_line_id.qty_received, low.qty_settle, places=2)
        log = self.env['construction.exceed.log'].search([('res_id', '=', settlement.id),
                                                          ('kind', '=', 'manual_pct')])
        self.assertEqual(log.reason, 'Adelanto pactado por el piso')


for _base, _cls in ((TestSupply, TestConsumptionControl), (TestContracts, TestRepeatAndRework)):
    for _name in dir(_base):
        if _name.startswith('test_') and callable(getattr(_base, _name)) \
                and _name not in vars(_cls):
            setattr(_cls, _name, None)
