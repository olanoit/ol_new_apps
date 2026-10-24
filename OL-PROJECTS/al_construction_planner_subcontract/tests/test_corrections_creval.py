# -*- coding: utf-8 -*-
"""Correcciones de la prueba del 24-oct-2026 (requerimiento CREVAL v1.0,
capítulo 12): re-trabajo en la valorización (CR-08) y deductivos al
actualizar (CR-09). Datos ficticios."""
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
