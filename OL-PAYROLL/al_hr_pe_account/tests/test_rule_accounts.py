# -*- coding: utf-8 -*-
"""Cuentas por condición de la regla y reparto por centro de costo en el
asiento de planilla por lote."""
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.al_hr_pe_account.tests.test_fase5_account import AccountCaseBase


@tagged('post_install', '-at_install')
class TestRuleAccounts(AccountCaseBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Account = cls.env['account.account']
        cls.acc_obrero = Account.create({'code': '621100', 'name': 'Sueldos obreros', 'account_type': 'expense'})
        cls.acc_obra = Account.create({'code': '621200', 'name': 'Sueldos de obra', 'account_type': 'expense'})
        cls.acc_obra_a = Account.create({'code': '621300', 'name': 'Sueldos obra A', 'account_type': 'expense'})
        WorkerType = cls.env['hr.worker.type']
        cls.obrero, cls.empleado = WorkerType.search([], limit=2)
        cls.department = cls.env['hr.department'].create({'name': 'Producción', 'company_id': cls.company.id})
        plan = cls.env['account.analytic.plan'].create({'name': 'Obras (cuentas)'})
        Analytic = cls.env['account.analytic.account']
        cls.obra_a = Analytic.create({'name': 'Obra A', 'plan_id': plan.id, 'company_id': cls.company.id})
        cls.obra_b = Analytic.create({'name': 'Obra B', 'plan_id': plan.id, 'company_id': cls.company.id})
        cls.version = cls.employee.version_id

    def _row(self, **vals):
        return self.env['l10n_pe.hr.salary.rule.account'].create(dict(
            {'salary_rule_id': self.rule_bas.id, 'company_id': self.company.id}, **vals))

    def _bas_debits(self, with_analytic=False):
        lines = self.batch._pe_prepare_batch_move_lines(with_analytic=with_analytic)
        return [(line['account_id'], round(line['debit'], 2), line['analytic_distribution'] or False)
                for line in lines if line['salary_rule_id'] == self.rule_bas.id and line['debit']]

    def _balanced(self, with_analytic=False):
        lines = self.batch._pe_prepare_batch_move_lines(with_analytic=with_analytic)
        self.assertAlmostEqual(sum(l['debit'] for l in lines), sum(l['credit'] for l in lines), places=2)

    # ------------------------------------------------------------------
    # Cuentas por condición
    # ------------------------------------------------------------------
    def test_without_rows_uses_rule_account(self):
        self.assertEqual(self._bas_debits(), [(self.acc_gasto.id, self.wage, False)])

    def test_row_by_worker_type(self):
        self.version.worker_type_id = self.obrero
        self._row(worker_type_id=self.obrero.id, account_debit_id=self.acc_obrero.id)
        self.assertEqual(self._bas_debits(), [(self.acc_obrero.id, self.wage, False)])
        self._balanced()

    def test_row_for_other_worker_type_does_not_apply(self):
        self.version.worker_type_id = self.empleado
        self._row(worker_type_id=self.obrero.id, account_debit_id=self.acc_obrero.id)
        self.assertEqual(self._bas_debits(), [(self.acc_gasto.id, self.wage, False)])

    def test_most_specific_row_wins(self):
        self.version.worker_type_id = self.obrero
        self.version.department_id = self.department
        self._row(worker_type_id=self.obrero.id, account_debit_id=self.acc_obrero.id, sequence=1)
        self._row(worker_type_id=self.obrero.id, department_id=self.department.id,
                  account_debit_id=self.acc_obra.id, sequence=20)
        self.assertEqual(self._bas_debits(), [(self.acc_obra.id, self.wage, False)],
                         'dos condiciones ganan a una, aunque tenga menor secuencia')

    def test_empty_account_keeps_the_rule_account(self):
        self.version.worker_type_id = self.obrero
        self._row(worker_type_id=self.obrero.id, account_credit_id=self.acc_obrero.id)
        self.assertEqual(self._bas_debits(), [(self.acc_gasto.id, self.wage, False)])

    def test_row_needs_condition_and_account(self):
        with self.assertRaises(ValidationError):
            self._row(account_debit_id=self.acc_obrero.id)
        with self.assertRaises(ValidationError):
            self._row(worker_type_id=self.obrero.id)

    def test_cost_center_row_splits_the_amount(self):
        self.version.analytic_distribution = {str(self.obra_a.id): 60.0, str(self.obra_b.id): 40.0}
        self._row(analytic_account_id=self.obra_a.id, account_debit_id=self.acc_obra_a.id)
        debits = sorted(self._bas_debits(with_analytic=True))
        self.assertEqual(debits, sorted([
            (self.acc_obra_a.id, 1800.0, {str(self.obra_a.id): 100.0}),
            (self.acc_gasto.id, 1200.0, {str(self.obra_b.id): 100.0}),
        ]))
        self._balanced(with_analytic=True)

    # ------------------------------------------------------------------
    # Reparto por el tareaje (hook de al_hr_pe)
    # ------------------------------------------------------------------
    def test_tareaje_distribution_reaches_the_move(self):
        distribution = {str(self.obra_a.id): 60.0, str(self.obra_b.id): 40.0}
        with patch.object(type(self.env['hr.payslip']), '_l10n_pe_tareaje_distribution',
                          return_value=distribution):
            debits = self._bas_debits(with_analytic=True)
            move = self.batch._pe_generate_batch_move(adjust_account=self.acc_ajuste,
                                                      with_analytic=True)
        self.assertEqual(debits, [(self.acc_gasto.id, self.wage, distribution)])
        expense = move.line_ids.filtered(lambda line: line.account_id == self.acc_gasto)
        self.assertEqual(expense.analytic_distribution, distribution)

    def test_rule_distribution_wins_over_tareaje(self):
        self.rule_bas.analytic_distribution = {str(self.obra_b.id): 100.0}
        with patch.object(type(self.env['hr.payslip']), '_l10n_pe_tareaje_distribution',
                          return_value={str(self.obra_a.id): 100.0}):
            debits = self._bas_debits(with_analytic=True)
        self.rule_bas.analytic_distribution = False
        self.assertEqual(debits, [(self.acc_gasto.id, self.wage, {str(self.obra_b.id): 100.0})])

    def test_without_tareaje_uses_the_employee_file(self):
        self.version.analytic_distribution = {str(self.obra_b.id): 100.0}
        self.assertEqual(self._bas_debits(with_analytic=True),
                         [(self.acc_gasto.id, self.wage, {str(self.obra_b.id): 100.0})])

    # ------------------------------------------------------------------
    # Asiento por centro de costo
    # ------------------------------------------------------------------
    def _analytic_amount(self, analytic):
        column = analytic.plan_id._column_name()
        return sum(self.env['account.analytic.line'].search(
            [(column, '=', analytic.id)]).mapped('amount'))

    def test_payable_lines_do_not_cancel_the_center_cost(self):
        """El pasivo no lleva analítica: el centro queda con todo el gasto."""
        self.rule_neto.employee_move_line = False
        self.version.analytic_distribution = {str(self.obra_a.id): 100.0}
        move = self.batch._pe_generate_batch_move(
            adjust_account=self.acc_ajuste, with_analytic=True)
        payable = move.line_ids.filtered(lambda line: line.account_id == self.acc_neto)
        self.assertTrue(payable)
        self.assertFalse(payable.analytic_distribution)
        self.assertEqual(self._analytic_amount(self.obra_a), -self.wage)

    def test_one_expense_line_per_center(self):
        self.param.move_split_by_cost_center = True
        self.version.analytic_distribution = {str(self.obra_a.id): 60.0, str(self.obra_b.id): 40.0}
        debits = sorted(self._bas_debits(with_analytic=True), key=lambda line: line[1])
        self.assertEqual(debits, [
            (self.acc_gasto.id, round(self.wage * 0.4, 2), {str(self.obra_b.id): 100.0}),
            (self.acc_gasto.id, round(self.wage * 0.6, 2), {str(self.obra_a.id): 100.0}),
        ])
        self._balanced(with_analytic=True)

    def test_split_ignored_when_plans_are_in_separate_keys(self):
        """Dos planes en claves separadas suman 200 %: no se parte el importe."""
        self.param.move_split_by_cost_center = True
        other_plan = self.env['account.analytic.plan'].create({'name': 'Áreas (cuentas)'})
        area = self.env['account.analytic.account'].create(
            {'name': 'Área', 'plan_id': other_plan.id, 'company_id': self.company.id})
        distribution = {str(self.obra_a.id): 100.0, str(area.id): 100.0}
        self.version.analytic_distribution = distribution
        self.assertEqual(self._bas_debits(with_analytic=True),
                         [(self.acc_gasto.id, self.wage, distribution)])

    def _cost_center_rule(self):
        self.env['l10n_pe.hr.salary.rule.account'].create({
            'salary_rule_id': self.rule_bas.id, 'company_id': self.company.id,
            'analytic_account_id': self.obra_a.id,
            'account_debit_id': self.acc_gasto.id})

    def test_partial_distribution_keeps_the_rest_without_analytic(self):
        self._cost_center_rule()
        parts = self.batch._pe_split_by_cost_center(
            self.rule_bas, 1000.0, {str(self.obra_a.id): 60.0})
        self.assertEqual([(amount, dist) for amount, dist, _ids in parts],
                         [(600.0, {str(self.obra_a.id): 100.0}), (400.0, False)])

    def test_distribution_under_100_is_not_inflated(self):
        self._cost_center_rule()
        parts = self.batch._pe_split_by_cost_center(
            self.rule_bas, 1000.0,
            {str(self.obra_a.id): 30.0, str(self.obra_b.id): 30.0})
        self.assertEqual([amount for amount, _d, _i in parts], [300.0, 300.0, 400.0])

    def test_other_plan_travels_with_each_part(self):
        self._cost_center_rule()
        other_plan = self.env['account.analytic.plan'].create({'name': 'Proyectos'})
        proyecto = self.env['account.analytic.account'].create(
            {'name': 'Proyecto X', 'plan_id': other_plan.id, 'company_id': self.company.id})
        a, b, x = str(self.obra_a.id), str(self.obra_b.id), str(proyecto.id)
        parts = self.batch._pe_split_by_cost_center(
            self.rule_bas, 1000.0, {x: 100.0, a: 70.0, b: 30.0})
        self.assertEqual([(amount, dist) for amount, dist, _ids in parts],
                         [(700.0, {x: 100.0, a: 100.0}), (300.0, {x: 100.0, b: 100.0})])
        self.assertEqual(parts[0][2], {self.obra_a.id, proyecto.id})

    def test_require_cost_center_blocks_and_warns(self):
        self.param.move_require_cost_center = True
        self.version.analytic_distribution = False
        wizard = self.env['hr.payslip.run.move.wizard'].create(
            {'payslip_run_id': self.batch.id, 'with_analytic': True})
        self.assertIn(self.employee.name, wizard.cost_center_warning)
        with self.assertRaises(UserError):
            self.batch._pe_generate_batch_move(
                adjust_account=self.acc_ajuste, with_analytic=True)
        self.version.analytic_distribution = {str(self.obra_a.id): 100.0}
        self.assertTrue(self.batch._pe_generate_batch_move(
            adjust_account=self.acc_ajuste, with_analytic=True))
