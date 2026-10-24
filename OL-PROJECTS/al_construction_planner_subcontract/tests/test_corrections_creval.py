# -*- coding: utf-8 -*-
"""Correcciones de la prueba del 24-oct-2026 (requerimiento CREVAL v1.0,
capítulo 12): re-trabajo en la valorización (CR-08), deductivos al
actualizar (CR-09) y una sola semana para el avance y la valorización
(CR-10). Datos ficticios."""
from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from .test_contract_terms_creval import PHOTO, ContractTermsCommon


@tagged('post_install', '-at_install')
class TestCorrectionsCreval(ContractTermsCommon):

    def _order(self):
        _wizard, order = self._assign()
        order.button_confirm()
        action = order.action_construction_register_advance()
        self._post(self.env['account.move'].browse(action['res_id']), date(2026, 11, 2))
        return order

    def _prepare(self):
        return self.env['construction.contract.settlement']._prepare_terms_settlements(
            today=date(2026, 11, 20))

    # CR-09
    def test_refresh_keeps_deductions(self):
        order = self._order()
        self._report(self.partida, self.act_wall, 500.0, date(2026, 11, 4))
        first = self._deduction(order, 800.0)
        second = self._deduction(order, 220.0)
        settlement = self._prepare()
        self.assertEqual(settlement.deduction_ids, first | second)
        self.assertEqual(settlement.amount_deductions, 1020.0)
        settlement.action_refresh()
        settlement.action_refresh()
        self.assertEqual(settlement.deduction_ids, first | second)
        self.assertEqual(set((first | second).mapped('state')), {'in_valuation'})
        self.assertEqual(settlement.amount_deductions, 1020.0)
        # Uno nuevo del periodo entra; uno anulado sale.
        third = self._deduction(order, 100.0)
        first.action_cancel()
        settlement.action_refresh()
        self.assertEqual(settlement.deduction_ids, second | third)
        self.assertEqual(settlement.amount_deductions, 320.0)

    # CR-08
    def test_rework_not_paid(self):
        order = self._order()
        self._report(self.partida, self.act_wall, 500.0, date(2026, 11, 4))
        rework = self.env['construction.task.progress'].create({
            'task_id': self.partida.id, 'activity_id': self.act_wall.id,
            'date': date(2026, 11, 4), 'qty': 6.0, 'is_rework': True,
            'rework_reason': 'bad_assembly',
            'attachment_ids': [Command.create({'name': 'foto.jpg', 'datas': PHOTO})]})
        rework.action_validate()
        settlement = self._prepare()
        line = settlement.line_ids.filtered('is_rework')
        self.assertEqual(line.qty_period, 6.0)
        self.assertEqual(line.qty_settle, 0.0)
        self.assertEqual(line.amount, 0.0)
        self.assertEqual(settlement.amount_direct, 500.0 * 38.20)
        self.assertEqual(settlement.review_rework_count, 1)
        # Lo decide quien valida la ejecución, con motivo.
        reporter = new_test_user(self.env, 'cr08_reporta',
                                 groups='al_construction_planner.group_planner_user')
        with self.assertRaises(UserError):
            line.with_user(reporter).write({'rework_paid': True, 'rework_pay_reason': 'Error'})
        with self.assertRaises(UserError):
            line.rework_paid = True
        with self.assertRaises(UserError):
            settlement.line_ids.filtered(lambda l: not l.is_rework).write(
                {'rework_paid': True, 'rework_pay_reason': 'No es re-trabajo'})
        line.write({'rework_paid': True,
                    'rework_pay_reason': 'El plano cambió después del armado'})
        self.assertEqual(line.rework_paid_by, self.env.user)
        self.assertEqual(line.qty_settle, 6.0)
        self.assertEqual(line.amount, 229.2)
        line.write({'rework_paid': False})
        self.assertEqual(line.qty_settle, 0.0)
        # Sin pagar, la factura no lo lleva y la bitácora lo registra.
        settlement.action_submit()
        settlement.action_validate()
        self.assertEqual(settlement.state, 'approved')
        names = settlement.invoice_id.invoice_line_ids.mapped('name')
        self.assertFalse(any('Re-trabajo' in (name or '') for name in names))
        log = self.env['construction.exceed.log'].search([
            ('res_id', '=', settlement.id), ('kind', '=', 'rework')])
        self.assertEqual(log.qty, 6.0)
        self.assertEqual(log.amount, 0.0)

    # CR-10
    def test_one_week_for_progress_and_valuation(self):
        weekly = self.condition.copy({'name': 'Contrato de obra semanal (test)',
                                      'cutoff_weekday': '3'})  # jueves
        self.assertEqual(self.project.construction_week_start_day, '3')
        _wizard, order = self._assign(weekly)
        # El corte del jueves fija la semana de la obra: de viernes a jueves.
        self.assertEqual(self.project.construction_week_start_day, '4')
        self.assertIn('cierra el jueves', self.project.message_ids[0].body)
        order.order_line.filtered(
            lambda l: l.construction_activity_id == self.act_seal).construction_is_additional = True
        order.button_confirm()
        action = order.action_construction_register_advance()
        self._post(self.env['account.move'].browse(action['res_id']), date(2026, 11, 2))
        first_progress = self._report(self.partida, self.act_wall, 100.0, date(2026, 11, 4))
        self.assertEqual(first_progress.period_start, date(2026, 10, 30))
        Settlement = self.env['construction.contract.settlement']
        first = Settlement._prepare_terms_settlements(today=date(2026, 11, 6))
        self.assertEqual((first.period_start, first.period_end),
                         (date(2026, 10, 30), date(2026, 11, 5)))
        first.action_submit()
        first.action_validate()
        # Una semana sin avances (6 al 12) no corta la serie: el adicional
        # del miércoles 18 entra en la del 13 al 19.
        extra = self._report(self.extra_task, self.act_seal, 10.0, date(2026, 11, 18))
        self.assertEqual(extra.period_start, date(2026, 11, 13))
        second = Settlement._prepare_terms_settlements(today=date(2026, 11, 20))
        self.assertEqual((second.period_start, second.period_end),
                         (date(2026, 11, 13), date(2026, 11, 19)))
        self.assertEqual(second.progress_ids, extra)
        self.assertEqual(second.amount_additional, 180.0)
        # Con valorizaciones, otro corte no mueve la semana.
        with self.assertRaisesRegex(UserError, 'semanas distintas'):
            order.construction_terms_id.sudo().cutoff_weekday = '0'

    # CR-07 y CR-11
    def test_price_from_plan_and_rounding(self):
        self.act_wall.default_price = 0.0
        wizard = self.env['construction.plan.contract.wizard'].with_context(
            default_plan_id=self.plan.id, construction_selection_project=True,
        ).create({'stage': 'creval_tab', 'partner_id': self.contractor.id,
                  'condition_id': self.condition.id, 'date_start': date(2026, 11, 2)})
        self.assertEqual(wizard.price_source, 'plan')
        wall = wizard.line_ids.filtered(lambda r: r.activity_id == self.act_wall)
        self.assertEqual(wall.price_unit, 38.20)
        wizard.price_source = 'rate'
        wall = wizard.line_ids.filtered(lambda r: r.activity_id == self.act_wall)
        self.assertEqual(wall.price_unit, 0.0)
        wizard.price_source = 'plan'
        wall = wizard.line_ids.filtered(lambda r: r.activity_id == self.act_wall)
        # El precio se corrige en la línea, con cuatro decimales.
        self.env.ref('product.decimal_price').digits = 4
        wall.price_unit = 12.3456
        self.assertEqual(wall.amount, 24691.20)
        self.assertEqual(wizard.amount_total, 24691.20 + 1800.0)
        wizard.action_assign()
        order = self.env['purchase.order'].search([
            ('partner_id', '=', self.contractor.id),
            ('construction_project_id', '=', self.project.id)], order='id desc', limit=1)
        po_wall = order.order_line.filtered(lambda l: l.construction_activity_id == self.act_wall)
        self.assertEqual(po_wall.price_unit, 12.3456)
        order.button_confirm()
        action = order.action_construction_register_advance()
        self._post(self.env['account.move'].browse(action['res_id']), date(2026, 11, 2))
        self._report(self.partida, self.act_wall, 333.33, date(2026, 11, 4))
        settlement = self._prepare()
        line = settlement.line_ids.filtered(lambda l: l.activity_id == self.act_wall)
        self.assertEqual(line.price_unit, 12.3456)
        # 333.33 × 12.3456 = 4,115.1585: se redondea una vez.
        self.assertEqual(line.amount, 4115.16)
        settlement.action_submit()
        settlement.action_validate()
        invoice_line = settlement.invoice_id.invoice_line_ids.filtered(
            lambda l: l.purchase_line_id == po_wall)
        self.assertEqual(invoice_line.price_subtotal, line.amount)

    # CR-13
    def test_advance_without_analytic(self):
        order, advance, settlement = self._scenario()
        self.assertTrue(self.project.account_id)
        self.assertFalse(advance.invoice_line_ids.analytic_distribution)
        settlement.action_submit()
        settlement.action_validate()
        invoice = settlement.invoice_id
        regularization = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.advance_product)
        self.assertTrue(regularization)
        self.assertFalse(regularization.analytic_distribution)
        services = invoice.invoice_line_ids.filtered('purchase_line_id')
        self.assertTrue(all(services.mapped('analytic_distribution')))

    # CR-02: una cuenta por pagar en el producto de anticipo se avisa antes.
    def test_advance_account_payable(self):
        _wizard, order = self._assign()
        order.button_confirm()
        payable = self.env['account.account'].create({
            'name': 'Anticipos otorgados por pagar (test)', 'code': '422199',
            'account_type': 'liability_payable', 'reconcile': True})
        self.advance_product.property_account_expense_id = payable
        with self.assertRaisesRegex(UserError, 'necesita una cuenta de activo'):
            order.action_construction_register_advance()
