# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# Tasa efectiva anual equivalente al 1 % mensual: 1,01^12 − 1.
RATE_1_PCT_MONTHLY = (1.01 ** 12 - 1) * 100


@tagged('post_install', '-at_install')
class TestLease(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.journal = cls.env['account.journal'].create({
            'name': 'Arrendamientos test', 'code': 'ARRT', 'type': 'general', 'company_id': cls.company.id})
        cls.lessor = cls.env['res.partner'].create({'name': 'INMOBILIARIA ARRENDADORA SAC', 'vat': '20100070970'})

    def _lease(self, **vals):
        return self.env['l10n_pe.lease'].create(dict({
            'partner_id': self.lessor.id, 'property_description': 'Oficina piso 5',
            'date_start': date(2026, 1, 1), 'term_months': 36, 'payment_amount': 1000.0,
            'payment_timing': 'advance', 'annual_rate': 12.0, 'journal_id': self.journal.id,
        }, **vals))

    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    def test_present_value_checked_by_hand(self):
        """Dos cuotas vencidas de 1 000 al 1 % mensual:
        1 000 / 1,01 + 1 000 / 1,01² = 990,10 + 980,30 = 1 970,40.
        Cuota 1: interés 19,70 (1 970,40 × 1 %), capital 980,30, saldo 990,10.
        Cuota 2: capital 990,10 e interés 9,90."""
        lease = self._lease(term_months=2, exemption='none', payment_timing='arrears',
                            annual_rate=RATE_1_PCT_MONTHLY)
        self.assertAlmostEqual(lease.monthly_rate, 1.0, places=6)
        self.assertEqual(lease.liability_amount, 1970.40)
        self.assertEqual(lease.rou_amount, 1970.40, 'sin cuota adelantada ni costos')
        lease.action_compute()
        self.assertEqual([(l.number, l.date, l.interest, l.principal, l.balance) for l in lease.line_ids], [
            (1, date(2026, 1, 31), 19.70, 980.30, 990.10),
            (2, date(2026, 2, 28), 9.90, 990.10, 0.0),
        ])
        self.assertEqual(lease.total_interest, 29.60, 'cuotas 2 000 − pasivo 1 970,40')

    def test_advance_payment_is_not_part_of_the_liability(self):
        lease = self._lease(initial_direct_costs=500.0, incentives=200.0)
        rate = 1.12 ** (1 / 12) - 1
        expected = round(sum(1000.0 / (1 + rate) ** k for k in range(1, 36)), 2)
        self.assertEqual(lease.liability_amount, expected, '35 cuotas: la primera se paga al inicio')
        self.assertEqual(lease.rou_amount, round(expected + 1000.0 + 500.0 - 200.0, 2))
        lease.action_compute()
        self.assertEqual(len(lease.line_ids), 35)
        self.assertEqual(lease.line_ids[0].number, 2, 'la primera cuota de la tabla es la segunda del contrato')
        self.assertAlmostEqual(sum(lease.line_ids.mapped('principal')), lease.liability_amount, places=2)
        self.assertEqual(lease.line_ids[-1].balance, 0.0)

    # ------------------------------------------------------------------
    # Confirmación
    # ------------------------------------------------------------------
    def test_confirm_creates_asset_and_loan(self):
        lease = self._lease(initial_direct_costs=500.0)
        lease.action_confirm()
        self.assertEqual(lease.state, 'running')

        move = lease.initial_move_id
        self.assertEqual(move.state, 'posted')
        rou = move.line_ids.filtered(lambda l: l.account_id == lease.rou_account_id)
        liability = move.line_ids.filtered(lambda l: l.account_id == lease.liability_long_account_id)
        clearing = move.line_ids.filtered(lambda l: l.account_id == lease.clearing_account_id)
        self.assertEqual(rou.debit, lease.rou_amount)
        self.assertEqual(liability.credit, lease.liability_amount)
        self.assertEqual(clearing.credit, 1500.0, 'cuota adelantada 1 000 + costos 500')

        asset = lease.asset_id
        self.assertEqual(asset.state, 'open')
        self.assertEqual(asset.original_value, lease.rou_amount)
        self.assertEqual((asset.method, asset.method_number, asset.method_period), ('linear', 36, '1'))
        self.assertAlmostEqual(sum(asset.depreciation_move_ids.mapped('depreciation_value')), lease.rou_amount, 2)

        loan = lease.loan_id
        self.assertEqual(loan.state, 'running')
        self.assertEqual(loan.amount_borrowed, lease.liability_amount)
        self.assertEqual(loan.duration, 35)
        self.assertAlmostEqual(sum(loan.line_ids.mapped('principal')), lease.liability_amount, 2)
        self.assertEqual(loan.asset_group_id, lease.asset_group_id)
        self.assertIn(asset, loan.linked_assets_ids, 'activo y pasivo enlazados por el grupo')

    def test_installments(self):
        lease = self._lease()
        lease.action_confirm()
        first = self.env['account.move'].browse(lease.action_register_installment()['res_id'])
        self.assertEqual(first.invoice_line_ids.account_id, lease.clearing_account_id,
                         'la cuota adelantada ya está en el activo: salda la transitoria')
        self.assertEqual(first.invoice_date, date(2026, 1, 1))
        second = self.env['account.move'].browse(lease.action_register_installment()['res_id'])
        self.assertEqual(second.invoice_line_ids.account_id, lease.liability_short_account_id)
        self.assertEqual(second.invoice_date, date(2026, 2, 1))
        self.assertEqual((lease.bill_count, lease.next_period), (2, 3))

    def test_short_term_is_exempt(self):
        lease = self._lease(term_months=12)
        self.assertEqual(lease.exemption, 'short_term')
        self.assertFalse(lease.liability_amount)
        lease.action_confirm()
        self.assertEqual(lease.state, 'exempt')
        self.assertFalse(lease.asset_id or lease.loan_id or lease.initial_move_id)
        bill = self.env['account.move'].browse(lease.action_register_installment()['res_id'])
        self.assertEqual(bill.invoice_line_ids.account_id, lease.rent_expense_account_id)

    def test_rate_is_required(self):
        lease = self._lease(annual_rate=0.0)
        with self.assertRaises(UserError):
            lease.action_confirm()

    def test_multicompany(self):
        other = self.env['res.company'].create({'name': 'Otra compañía arrendamientos'})
        foreign = self.env['l10n_pe.lease'].with_company(other).create({
            'company_id': other.id, 'partner_id': self.lessor.id, 'property_description': 'Almacén',
            'term_months': 24, 'payment_amount': 500.0, 'annual_rate': 10.0})
        visible = self.env['l10n_pe.lease'].with_user(self.env.ref('base.user_admin')).with_context(
            allowed_company_ids=[self.company.id]).search([('id', '=', foreign.id)])
        self.assertFalse(visible, 'un contrato de otra compañía no se ve')
