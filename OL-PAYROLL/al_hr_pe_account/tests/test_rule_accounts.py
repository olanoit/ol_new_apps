# -*- coding: utf-8 -*-
"""Cuentas por condición de la regla y reparto por centro de costo en el
asiento de planilla por lote."""
from unittest.mock import patch

from odoo.exceptions import ValidationError
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
