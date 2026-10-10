# -*- coding: utf-8 -*-
"""Ciclo completo de un arrendamiento NIIF 16: subcuentas, cuotas, conciliación
con el libro, remedición, terminación, moneda extranjera y diferencias
temporales del impuesto a la renta.

Las fechas se fijan con ``freeze_time`` al 10/10/2026: el contrato empieza el
01/01/2026 y los asientos de enero a setiembre ya están contabilizados."""
from datetime import date

from freezegun import freeze_time

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
@freeze_time('2026-10-10')
class TestLeaseLifecycle(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.journal = cls.env['account.journal'].create({
            'name': 'Arrendamientos ciclo', 'code': 'ARRC', 'type': 'general', 'company_id': cls.company.id})
        cls.purchase = cls.env['account.journal'].create({
            'name': 'Compras arrendamientos', 'code': 'ARRP', 'type': 'purchase', 'company_id': cls.company.id,
            'l10n_latam_use_documents': False})
        cls.lessor = cls.env['res.partner'].create({'name': 'ARRENDADORA CICLO SAC', 'vat': '20100070970'})
        Account = cls.env['account.account'].with_company(cls.company)
        if not cls.company.gain_account_id:
            cls.company.gain_account_id = Account.search([('account_type', '=', 'income_other')], limit=1)
        if not cls.company.loss_account_id:
            cls.company.loss_account_id = Account.search([('account_type', '=', 'expense')], limit=1)

    def _lease(self, **vals):
        lease = self.env['l10n_pe.lease'].create(dict({
            'partner_id': self.lessor.id, 'property_description': 'Almacén Callao',
            'date_start': date(2026, 1, 1), 'term_months': 36, 'payment_amount': 1000.0,
            'payment_timing': 'advance', 'annual_rate': 12.0, 'journal_id': self.journal.id,
        }, **vals))
        lease.action_create_liability_accounts()
        return lease

    def _post_installments(self, lease, count):
        bills = self.env['account.move']
        for _i in range(count):
            bill = self.env['account.move'].browse(lease.action_register_installment()['res_id'])
            bill.journal_id = self.purchase
            bill.action_post()
            bills |= bill
        return bills

    # ------------------------------------------------------------------
    def test_liability_subaccounts_separate_terms(self):
        lease = self._lease()
        self.assertTrue(lease.liability_long_account_id.code.startswith('4521'))
        self.assertTrue(lease.liability_short_account_id.code.startswith('4522'))
        self.assertEqual(len(lease.liability_long_account_id.code), len(lease.liability_short_account_id.code))
        self.assertFalse(lease.same_liability_account)
        lease.action_confirm()
        reclass = lease.loan_id.line_ids.generated_move_ids.filtered(
            lambda m: not m.is_loan_payment_move and m.state == 'posted')
        self.assertTrue(reclass.line_ids.filtered(lambda l: l.account_id == lease.liability_short_account_id),
                        'la reclasificación pasa los próximos 12 meses al corto plazo')

    def test_book_matches_schedule(self):
        lease = self._lease()
        lease.action_confirm()
        self._post_installments(lease, 10)  # cuotas 1 a 10 (enero a octubre)
        self.assertEqual(lease.liability_difference, 0.0, 'en soles el libro cuadra con la tabla')
        self.assertGreater(lease.liability_balance, 0.0)
        self.assertEqual(lease.rou_book_value, lease.asset_id.book_value)

    def test_product_brings_taxes_and_keeps_liability_account(self):
        tax = self.company.account_purchase_tax_id
        product = self.env['product.product'].create({
            'name': 'Alquiler de inmueble', 'type': 'service', 'supplier_taxes_id': [Command.set(tax.ids)]})
        lease = self._lease(product_id=product.id)
        lease.action_confirm()
        lease.action_register_installment()
        second = self.env['account.move'].browse(lease.action_register_installment()['res_id'])
        line = second.invoice_line_ids
        self.assertEqual(line.product_id, product)
        self.assertEqual(line.tax_ids, tax, 'impuestos (y detracción) del producto')
        self.assertEqual(line.account_id, lease.liability_short_account_id)

    # ------------------------------------------------------------------
    def test_remeasurement_increase(self):
        lease = self._lease()
        lease.action_confirm()
        old_loan, rou_before = lease.loan_id, lease.asset_id.book_value
        carrying = lease._principal_before(date(2026, 10, 1))
        wizard = self.env['l10n_pe.lease.remeasure'].with_context(default_lease_id=lease.id).create({
            'date': date(2026, 10, 1), 'payment_amount': 1100.0, 'remaining_months': 27,
            'annual_rate': 12.0, 'reason': 'Reajuste de la renta'})
        self.assertEqual(wizard.carrying_amount, carrying)
        rate = 1.12 ** (1 / 12) - 1
        expected = round(1100.0 + sum(1100.0 / (1 + rate) ** k for k in range(1, 27)), 2)
        self.assertEqual(wizard.new_liability, expected, 'incluye la cuota de octubre (adelantada)')
        difference = wizard.difference
        wizard.action_apply()

        self.assertEqual(old_loan.state, 'closed')
        self.assertNotEqual(lease.loan_id, old_loan)
        self.assertEqual(lease.loan_id.amount_borrowed, expected)
        self.assertEqual(lease.term_months, 36)
        new_lines = lease.line_ids.filtered(lambda l: l.date >= date(2026, 10, 1))
        self.assertEqual((new_lines[0].number, new_lines[0].interest, new_lines[0].payment), (10, 0.0, 1100.0))
        self.assertEqual(new_lines[-1].balance, 0.0)
        increase = lease.asset_id.children_ids
        self.assertEqual(increase.original_value, difference, 'aumento bruto del derecho de uso')
        self.assertAlmostEqual(lease.asset_id.book_value, rou_before + difference, places=2)
        self.assertEqual(lease.event_ids.kind, 'remeasurement')
        self.assertEqual(lease.liability_difference, 0.0, 'el libro sigue cuadrando con la tabla')
        bill = self.env['account.move'].browse(lease.action_register_installment()['res_id'])
        self.assertEqual(bill.invoice_line_ids.price_unit, 1000.0, 'la cuota 1 es la de antes')

    def test_remeasurement_decrease(self):
        lease = self._lease()
        lease.action_confirm()
        rou_before = lease.asset_id.book_value
        wizard = self.env['l10n_pe.lease.remeasure'].with_context(default_lease_id=lease.id).create({
            'date': date(2026, 10, 1), 'payment_amount': 1000.0, 'remaining_months': 15,
            'annual_rate': 12.0, 'reason': 'Se acorta el plazo'})
        difference = wizard.difference
        self.assertLess(difference, 0.0)
        wizard.action_apply()
        self.assertEqual(lease.term_months, 24)
        self.assertEqual(lease.asset_id.method_number, 24, 'se deprecia en el plazo nuevo')
        self.assertAlmostEqual(lease.asset_id.book_value, rou_before + difference, places=2,
                               msg='el derecho de uso baja lo mismo que el pasivo')
        expense = lease.asset_id.account_depreciation_expense_id
        net_expense = sum(lease.event_ids.move_ids.line_ids.filtered(
            lambda l: l.account_id == expense).mapped('balance'))
        self.assertEqual(net_expense, 0.0, 'la disminución no pasa por resultados')
        self.assertEqual(lease.liability_difference, 0.0)

    def test_remeasurement_rejects_posted_period(self):
        lease = self._lease()
        lease.action_confirm()
        with self.assertRaises(UserError, msg='setiembre ya está contabilizado'):
            self.env['l10n_pe.lease.remeasure'].with_context(default_lease_id=lease.id).create({
                'date': date(2026, 9, 1), 'payment_amount': 1000.0, 'remaining_months': 28,
                'annual_rate': 12.0, 'reason': 'x'}).action_apply()
        with self.assertRaises(UserError, msg='rige desde el primer día de un mes'):
            self.env['l10n_pe.lease.remeasure'].with_context(default_lease_id=lease.id).create({
                'date': date(2026, 10, 15), 'payment_amount': 1000.0, 'remaining_months': 27,
                'annual_rate': 12.0, 'reason': 'x'}).action_apply()

    # ------------------------------------------------------------------
    def test_early_termination(self):
        lease = self._lease()
        lease.action_confirm()
        carrying = lease._principal_before(date(2026, 10, 1))
        book_value = lease.asset_id._get_residual_value_at_date(date(2026, 9, 30))
        self.env['l10n_pe.lease.terminate'].with_context(default_lease_id=lease.id).create({
            'date': date(2026, 10, 1), 'reason': 'Mudanza'}).action_apply()
        self.assertEqual(lease.state, 'closed')
        self.assertEqual(lease.termination_date, date(2026, 10, 1))
        self.assertEqual(lease.asset_id.state, 'close')
        self.assertEqual(lease.loan_id.state, 'closed')
        self.assertFalse(lease.line_ids.filtered(lambda l: l.date >= date(2026, 10, 1)))
        gain = self.company.gain_account_id
        moves = lease.event_ids.move_ids
        self.assertEqual(-sum(moves.line_ids.filtered(lambda l: l.account_id == gain).mapped('balance')),
                         carrying, 'el pasivo pendiente va a ganancia')
        loss = sum(moves.line_ids.filtered(lambda l: l.account_id == self.company.loss_account_id).mapped('balance'))
        self.assertAlmostEqual(loss, book_value, places=2, msg='el derecho de uso pendiente va a pérdida')

    # ------------------------------------------------------------------
    def test_foreign_currency_exchange_difference(self):
        usd = self.env.ref('base.USD')
        usd.active = True
        Rate = self.env['res.currency.rate']
        Rate.search([('currency_id', '=', usd.id), ('company_id', '=', self.company.id),
                     ('name', '>=', date(2025, 12, 1)), ('name', '<=', date(2026, 12, 31))]).unlink()
        Rate.create([
            {'name': date(2025, 12, 31), 'currency_id': usd.id, 'company_id': self.company.id,
             'inverse_company_rate': 3.70},
            {'name': date(2026, 6, 30), 'currency_id': usd.id, 'company_id': self.company.id,
             'inverse_company_rate': 3.80},
        ])
        lease = self._lease(currency_id=usd.id, date_start=date(2026, 1, 1), term_months=24)
        lease.action_confirm()
        self.assertAlmostEqual(lease.start_rate, 3.70, places=4)
        self.assertEqual(lease.rou_amount_company, round(lease.rou_amount * 3.70, 2))
        self.assertEqual(lease.asset_id.original_value, lease.rou_amount_company,
                         'el derecho de uso queda al tipo de cambio del inicio')

        moves = lease._exchange_difference(date(2026, 6, 30))
        self.assertTrue(moves)
        target = round(lease._liability_at(date(2026, 6, 30)) * 3.80, 2)
        self.assertEqual(lease._liability_book(date(2026, 6, 30)), target,
                         'el pasivo queda expresado al tipo de cambio de cierre')
        self.assertFalse(lease._exchange_difference(date(2026, 6, 30)), 'un segundo ajuste no hace nada')
        loss = self.company.expense_currency_exchange_account_id
        self.assertGreater(sum(moves.line_ids.filtered(lambda l: l.account_id == loss).mapped('balance')), 0,
                           'el dólar subió: pérdida por diferencia de cambio')
        bill = self.env['account.move'].browse(lease.action_register_installment()['res_id'])
        self.assertEqual(bill.currency_id, usd, 'el arrendador factura en dólares')

    # ------------------------------------------------------------------
    def test_tax_temporary_difference(self):
        lease = self._lease()
        lease.action_confirm()
        bills = self._post_installments(lease, 9)  # enero a setiembre
        report = self.env['l10n_pe.lease.tax.report'].create({'year': 2026, 'tax_rate': 29.5})
        report.action_compute()
        line = report.line_ids.filtered(lambda l: l.lease_id == lease)
        depreciation = sum(lease.asset_id.depreciation_move_ids.filtered(
            lambda m: m.state == 'posted' and m.date.year == 2026).mapped('depreciation_value'))
        self.assertAlmostEqual(line.depreciation, depreciation, places=2)
        self.assertEqual(line.tax_expense, sum(bills.mapped('amount_untaxed_signed')) * -1)
        self.assertEqual(line.tax_expense, 9000.0, 'nueve cuotas de 1 000 sin IGV')
        self.assertAlmostEqual(line.difference, line.depreciation + line.interest - 9000.0, places=2)
        self.assertAlmostEqual(line.deferred_tax, line.difference * 0.295, places=2)
