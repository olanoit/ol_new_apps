# -*- coding: utf-8 -*-
"""Gasto pagado con la caja chica (requerimiento CREVAL v1.0, CR-14): la
factura del proveedor con su comprobante y la rendición que la paga."""
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.al_l10n_pe_cash_fund.tests.test_cash_fund import TestCashFund


@tagged('post_install', '-at_install')
class TestCashFundExpense(TestCashFund):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('hr_expense.group_hr_expense_manager')
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Rosa Quispe (test)', 'work_contact_id': cls.worker.id})
        cls.meal = cls.env['product.product'].create({
            'name': 'Almuerzo del personal (test)', 'type': 'service', 'can_be_expensed': True,
            'standard_price': 0.0, 'supplier_taxes_id': [(5, 0, 0)],
            'property_account_expense_id': cls.expense.id})
        cls.receipt_type = cls.env.ref('l10n_pe.document_type03')
        cls.journal = cls.company._l10n_pe_expense_journal()

    def _expense(self, fund, **vals):
        return self.env['hr.expense'].create(dict({
            'name': 'Almuerzo del personal', 'employee_id': self.employee.id,
            'product_id': self.meal.id, 'total_amount_currency': 32.0,
            'date': date(2026, 10, 7), 'payment_mode': 'own_account',
            'l10n_pe_cash_fund_id': fund.id, 'vendor_id': self.supplier.id,
            'l10n_latam_document_type_id': self.receipt_type.id,
            'l10n_pe_document_number': 'B010-00005725'}, **vals))

    def test_expense_as_supplier_bill(self):
        self.assertTrue(self.journal, 'falta un diario de compras con documentos')
        fund = self._fund(500.0, 'petty_cash')
        expense = self._expense(fund)
        other = self._expense(fund, total_amount_currency=24.65,
                              l10n_pe_document_number='B010-00005726')
        (expense | other).action_submit()
        (expense | other).action_approve()
        (expense | other).action_post()
        bill = expense.account_move_id
        self.assertEqual(bill.move_type, 'in_invoice')
        self.assertEqual(bill.journal_id, self.journal)
        self.assertEqual(bill.partner_id, self.supplier)
        self.assertEqual(bill.l10n_latam_document_type_id, self.receipt_type)
        self.assertIn('B010-00005725', bill.name)
        self.assertEqual(bill.amount_total, 32.0)
        self.assertEqual(bill.payment_state, 'paid')
        self.assertEqual(expense.state, 'paid')
        self.assertIn('B010-00005726', other.account_move_id.name)
        self.assertNotEqual(bill, other.account_move_id)
        self.assertAlmostEqual(fund.amount_balance, 500.0 - 32.0 - 24.65)
        settlement = fund.settlement_ids
        self.assertEqual(len(settlement), 1)
        self.assertEqual(settlement.state, 'posted')
        self.assertEqual(settlement.document_line_ids.move_id, bill | other.account_move_id)

    def test_expense_needs_document(self):
        fund = self._fund(100.0, 'petty_cash')
        expense = self._expense(fund, l10n_pe_document_number=False)
        expense.action_submit()
        expense.action_approve()
        with self.assertRaisesRegex(UserError, 'número de comprobante'):
            expense.action_post()


# Las pruebas heredadas ya corren en su clase.
for _name in dir(TestCashFund):
    if _name.startswith('test_') and callable(getattr(TestCashFund, _name)) \
            and _name not in vars(TestCashFundExpense):
        setattr(TestCashFundExpense, _name, None)
