# -*- coding: utf-8 -*-
"""Regresiones de la revisión de contabilidad de planillas (octubre 2026).

* «Generar asiento» por cesado abre el asistente (antes se llamaba a sí
  mismo: RecursionError).
* Doble contabilización de BBSS: la boleta no carga el gasto que el
  asiento de BBSS ya registra.
* Reparto por centro de costo con distribuciones parciales o multiplan.
* Anular una boleta no deja el lote bloqueado con el asiento revertido.
"""
from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.al_hr_pe_account.tests.test_fase5_account import \
    AccountCaseBase


@tagged('post_install', '-at_install')
class TestAccountReviewFixes(AccountCaseBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Account = cls.env['account.account']
        cls.acc_liq_payable = Account.create({
            'code': '415900', 'name': 'Liquidaciones por pagar',
            'account_type': 'liability_current'})
        cls.param.liquidation_payable_account_id = cls.acc_liq_payable
        Plan = cls.env['account.analytic.plan']
        Analytic = cls.env['account.analytic.account']
        plan = Plan.create({'name': 'Obras revisión'})
        other_plan = Plan.create({'name': 'Proyectos revisión'})
        cls.obra_a = Analytic.create({
            'name': 'Obra A rev', 'plan_id': plan.id,
            'company_id': cls.company.id})
        cls.obra_b = Analytic.create({
            'name': 'Obra B rev', 'plan_id': plan.id,
            'company_id': cls.company.id})
        cls.proyecto = Analytic.create({
            'name': 'Proyecto X rev', 'plan_id': other_plan.id,
            'company_id': cls.company.id})
        cls.acc_obra_a = Account.create({
            'code': '621390', 'name': 'Sueldos obra A rev',
            'account_type': 'expense'})

    # ------------------------------------------------------------------
    # A1: botón por cesado
    # ------------------------------------------------------------------
    def test_liquidation_row_opens_the_wizard(self):
        liquidation = self.env['hr.liquidation'].create({
            'company_id': self.company.id, 'year': 2026,
            'gratification_type': '07', 'cts_type': '11',
            'payslip_run_id': self.batch.id,
        })
        row = self.env['hr.liquidation.move'].create({
            'liquidation_id': liquidation.id,
            'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id,
        })
        lines = [
            row._make_line(self.acc_cts_debe, 'CTS trunca', debit=100.0),
            row._make_line(self.acc_liq_payable, 'Por pagar', credit=100.0),
        ]
        with patch.object(type(row), '_get_move_lines', return_value=lines):
            action = row.action_open_move_wizard()
        self.assertEqual(action['res_model'], 'hr.benefits.move.wizard')
        self.assertEqual(action['context']['benefits_model'],
                         'hr.liquidation.move')
        self.assertEqual(action['context']['default_debit'], 100.0)

    # ------------------------------------------------------------------
    # A4: doble contabilización de BBSS
    # ------------------------------------------------------------------
    def _pay_cts_in_slip(self, debit_account):
        """La CTS se paga por la boleta del lote con el input del motor."""
        rule = self.param.cts_input_id.with_company(self.company)
        rule.account_debit = debit_account
        rule.account_credit = self.acc_neto
        slip = self.batch.slip_ids
        self.env['hr.payslip.line'].create({
            'slip_id': slip.id, 'salary_rule_id': rule.id,
            'name': rule.name, 'code': rule.code,
            'amount': 500.0, 'quantity': 1.0, 'rate': 100.0,
            'total': 500.0,
            'version_id': slip.version_id.id,
            'employee_id': slip.employee_id.id,
        })
        self.assertTrue(slip.line_ids.filtered(
            lambda line: line.salary_rule_id == rule and line.total))
        return rule

    def _cts(self):
        cts = self.env['hr.cts'].create({
            'company_id': self.company.id, 'year': 2026, 'type': '05',
            'payslip_run_id': self.batch.id,
            'deposit_date': date(2026, 5, 15),
        })
        cts.action_process()
        return cts

    def test_benefits_move_after_slip_expense_is_blocked(self):
        """La boleta ya cargó el gasto de CTS: el asiento de CTS no se
        genera."""
        self._pay_cts_in_slip(self.acc_cts_debe)
        self.batch._pe_generate_batch_move(adjust_account=self.acc_ajuste)
        with self.assertRaises(UserError):
            self._cts().action_open_move_wizard()

    def test_batch_move_after_benefits_move_is_blocked(self):
        cts = self._cts()
        cts.account_move_id = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': self.journal.id})
        self._pay_cts_in_slip(self.acc_cts_debe)
        with self.assertRaises(UserError):
            self.batch._pe_generate_batch_move(
                adjust_account=self.acc_ajuste)
        self.assertFalse(self.batch.move_id)

    def test_slip_clearing_the_payable_is_allowed(self):
        """Con el pasivo como cuenta de cargo de la regla no hay doble
        gasto: los dos asientos se generan."""
        self._pay_cts_in_slip(self.acc_cts_payable)
        self.batch._pe_generate_batch_move(adjust_account=self.acc_ajuste)
        action = self._cts().action_open_move_wizard()
        self.assertEqual(action['res_model'], 'hr.benefits.move.wizard')

    # ------------------------------------------------------------------
    # M2: reparto por centro de costo
    # ------------------------------------------------------------------
    def _cost_center_rule(self):
        self.env['l10n_pe.hr.salary.rule.account'].create({
            'salary_rule_id': self.rule_bas.id, 'company_id': self.company.id,
            'analytic_account_id': self.obra_a.id,
            'account_debit_id': self.acc_obra_a.id})

    def test_partial_distribution_keeps_the_rest_without_analytic(self):
        self._cost_center_rule()
        parts = self.batch._pe_split_by_cost_center(
            self.rule_bas, 1000.0, {str(self.obra_a.id): 60.0})
        self.assertEqual(
            [(amount, dist) for amount, dist, _ids in parts],
            [(600.0, {str(self.obra_a.id): 100.0}), (400.0, False)])

    def test_distribution_under_100_is_not_inflated(self):
        self._cost_center_rule()
        parts = self.batch._pe_split_by_cost_center(
            self.rule_bas, 1000.0,
            {str(self.obra_a.id): 30.0, str(self.obra_b.id): 30.0})
        self.assertEqual([amount for amount, _d, _i in parts],
                         [300.0, 300.0, 400.0])

    def test_other_plan_travels_with_each_part(self):
        self._cost_center_rule()
        a, b, x = (str(self.obra_a.id), str(self.obra_b.id),
                   str(self.proyecto.id))
        parts = self.batch._pe_split_by_cost_center(
            self.rule_bas, 1000.0, {x: 100.0, a: 70.0, b: 30.0})
        self.assertEqual(
            [(amount, dist) for amount, dist, _ids in parts],
            [(700.0, {x: 100.0, a: 100.0}), (300.0, {x: 100.0, b: 100.0})])
        self.assertEqual(parts[0][2], {self.obra_a.id, self.proyecto.id})
        self.assertEqual(sum(amount for amount, _d, _i in parts), 1000.0)

    # ------------------------------------------------------------------
    # M3: anular una boleta con el asiento del lote
    # ------------------------------------------------------------------
    def test_cancel_slip_unlocks_the_batch(self):
        move = self.batch._pe_generate_batch_move(
            adjust_account=self.acc_ajuste)
        slip = self.batch.slip_ids
        slip.action_payslip_cancel()
        # Según el diario, el nativo elimina, anula o revierte el asiento.
        self.assertTrue(not move.exists() or move.state == 'cancel'
                        or move.reversal_move_ids)
        self.assertFalse(self.batch.move_id)
        # El asistente ya no se niega por «el lote ya tiene asiento».
        action = self.batch.action_pe_open_batch_move_wizard()
        self.assertEqual(action['res_model'], 'hr.payslip.run.move.wizard')
