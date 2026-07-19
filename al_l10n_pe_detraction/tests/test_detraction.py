# -*- coding: utf-8 -*-
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestDetraction(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        if not (cls.company.vat and len(cls.company.vat) == 11):
            cls.company.vat = '20512528458'
        cls.dtype_12 = cls.env.ref('al_l10n_pe_detraction.detraction_037')
        cls.dtype_4 = cls.env.ref('al_l10n_pe_detraction.detraction_030')
        Account = cls.env['account.account'].with_company(cls.company)
        cls.account_inc = Account.search(
            [('account_type', '=', 'income')], limit=1)
        cls.account_exp = Account.search(
            [('account_type', '=', 'expense')], limit=1)
        cls.tax_sale = cls.env['account.tax'].search([
            ('company_id', '=', cls.company.id),
            ('type_tax_use', '=', 'sale'), ('amount', '=', 18.0)], limit=1)
        cls.tax_purchase = cls.env['account.tax'].search([
            ('company_id', '=', cls.company.id),
            ('type_tax_use', '=', 'purchase'), ('amount', '=', 18.0)],
            limit=1)
        cls.journal_sale = cls.env['account.journal'].create({
            'name': 'DET Ventas Test', 'code': 'DTV', 'type': 'sale',
            'company_id': cls.company.id, 'l10n_latam_use_documents': False})
        cls.journal_purchase = cls.env['account.journal'].create({
            'name': 'DET Compras Test', 'code': 'DTC', 'type': 'purchase',
            'company_id': cls.company.id, 'l10n_latam_use_documents': False})
        cls.journal_bank = cls.env['account.journal'].search(
            [('company_id', '=', cls.company.id), ('type', '=', 'bank')],
            limit=1) or cls.env['account.journal'].create({
                'name': 'DET Banco Test', 'code': 'DTB', 'type': 'bank',
                'company_id': cls.company.id})
        cls.partner = cls.env['res.partner'].create({
            'name': 'Detracción Test SAC', 'vat': '20131312955'})
        cls.service = cls.env['product.product'].create({
            'name': 'Servicio Detracción Test', 'type': 'service',
            'l10n_pe_detraction_type_id': cls.dtype_12.id})
        cls.service_4 = cls.env['product.product'].create({
            'name': 'Construcción Test', 'type': 'service',
            'l10n_pe_detraction_type_id': cls.dtype_4.id})

    def _invoice(self, move_type, price, products=None):
        products = products or [self.service]
        journal = (self.journal_sale if move_type == 'out_invoice'
                   else self.journal_purchase)
        tax = (self.tax_sale if move_type == 'out_invoice'
               else self.tax_purchase)
        account = (self.account_inc if move_type == 'out_invoice'
                   else self.account_exp)
        move = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': self.partner.id,
            'journal_id': journal.id,
            'invoice_date': date(2025, 6, 10),
            'date': date(2025, 6, 10),
            'ref': 'F001-00000555' if move_type == 'in_invoice' else False,
            'invoice_line_ids': [(0, 0, {
                'name': product.name,
                'product_id': product.id,
                'quantity': 1.0,
                'price_unit': price,
                'account_id': account.id,
                'tax_ids': [(6, 0, tax.ids)] if tax else False,
            }) for product in products],
        })
        return move

    # ------------------------------------------------------------------
    # Catálogo y productos
    # ------------------------------------------------------------------
    def test_catalog_percentage_constraint(self):
        with self.assertRaises(ValidationError):
            self.env['l10n_pe.detraction.type'].create({
                'code': '998', 'name': 'Inválido', 'percentage': 150.0})

    def test_product_sync_native_fields(self):
        self.assertEqual(self.service.l10n_pe_withhold_code, '037')
        self.assertEqual(self.service.l10n_pe_withhold_percentage, 12.0)
        # cambio de tipo re-sincroniza
        self.service.l10n_pe_detraction_type_id = self.dtype_4
        self.assertEqual(self.service.l10n_pe_withhold_code, '030')
        self.assertEqual(self.service.l10n_pe_withhold_percentage, 4.0)
        self.service.l10n_pe_detraction_type_id = self.dtype_12

    def test_catalog_sync_action(self):
        self.dtype_12.percentage = 13.0
        self.dtype_12.action_sync_products()
        self.assertEqual(self.service.l10n_pe_withhold_percentage, 13.0)
        self.dtype_12.percentage = 12.0
        self.dtype_12.action_sync_products()

    # ------------------------------------------------------------------
    # Cálculo en factura
    # ------------------------------------------------------------------
    def test_invoice_detraction_applies(self):
        move = self._invoice('out_invoice', 1000.0)  # total 1180 > 700
        self.assertTrue(move.l10n_pe_detraction_applies)
        self.assertEqual(move.l10n_pe_detraction_type_id, self.dtype_12)
        self.assertEqual(move.l10n_pe_detraction_percent, 12.0)
        # 1180 * 12% = 141.6 → redondeo a soles enteros = 142
        self.assertEqual(move.l10n_pe_detraction_amount, 142.0)
        self.assertEqual(move.l10n_pe_detraction_net, 1180.0 - 142.0)

    def test_invoice_below_minimum(self):
        move = self._invoice('out_invoice', 500.0)  # total 590 <= 700
        self.assertFalse(move.l10n_pe_detraction_applies)
        self.assertEqual(move.l10n_pe_detraction_amount, 0.0)

    def test_invoice_dominant_percentage(self):
        move = self._invoice('out_invoice', 1000.0,
                             products=[self.service_4, self.service])
        self.assertEqual(move.l10n_pe_detraction_type_id, self.dtype_12)
        self.assertEqual(move.l10n_pe_detraction_percent, 12.0)

    def test_post_sets_operation_type(self):
        move = self._invoice('out_invoice', 1000.0)
        self.assertNotIn(move.l10n_pe_edi_operation_type,
                         ('1001', '1002', '1003', '1004'))
        move.action_post()
        self.assertEqual(move.l10n_pe_edi_operation_type, '1001')

    def test_purchase_no_operation_type_change(self):
        move = self._invoice('in_invoice', 1000.0)
        self.assertTrue(move.l10n_pe_detraction_applies)
        operation_before = move.l10n_pe_edi_operation_type
        move.action_post()
        self.assertEqual(move.l10n_pe_edi_operation_type, operation_before)

    # ------------------------------------------------------------------
    # Reparto en el asiento de la factura (opción de Ajustes)
    # ------------------------------------------------------------------
    def _enable_split(self):
        Account = self.env['account.account'].with_company(self.company)
        receivable = Account.create({
            'code': '121901', 'name': 'Detracciones por cobrar Test',
            'account_type': 'asset_receivable', 'reconcile': True})
        payable = Account.create({
            'code': '424901', 'name': 'Detracciones por pagar Test',
            'account_type': 'liability_payable', 'reconcile': True})
        self.company.write({
            'l10n_pe_detraction_split': True,
            'l10n_pe_detraction_receivable_account_id': receivable.id,
            'l10n_pe_detraction_payable_account_id': payable.id,
        })
        return receivable, payable

    def test_split_customer_invoice(self):
        receivable, _payable = self._enable_split()
        move = self._invoice('out_invoice', 1000.0)  # total 1180, det 142
        move.action_post()
        term_lines = move.line_ids.filtered(
            lambda l: l.display_type == 'payment_term')
        self.assertEqual(len(term_lines), 2)
        det_line = term_lines.filtered(lambda l: l.account_id == receivable)
        main_line = term_lines - det_line
        self.assertEqual(det_line.balance, 142.0)     # detracción al debe
        self.assertEqual(main_line.balance, 1038.0)   # neto en la cuenta 12
        # mismo asiento: total, balance y residual intactos
        self.assertEqual(move.amount_total, 1180.0)
        self.assertEqual(move.amount_residual, 1180.0)
        self.assertEqual(sum(move.line_ids.mapped('balance')), 0.0)

    def test_split_vendor_bill(self):
        _receivable, payable = self._enable_split()
        move = self._invoice('in_invoice', 1000.0)
        move.action_post()
        term_lines = move.line_ids.filtered(
            lambda l: l.display_type == 'payment_term')
        self.assertEqual(len(term_lines), 2)
        det_line = term_lines.filtered(lambda l: l.account_id == payable)
        main_line = term_lines - det_line
        self.assertEqual(det_line.balance, -142.0)    # detracción al haber
        self.assertEqual(main_line.balance, -1038.0)  # neto al proveedor
        self.assertEqual(move.amount_residual, 1180.0)

    def test_split_requires_accounts(self):
        from odoo.exceptions import UserError
        self.company.l10n_pe_detraction_split = True
        self.company.l10n_pe_detraction_receivable_account_id = False
        move = self._invoice('out_invoice', 1000.0)
        with self.assertRaises(UserError):
            move.action_post()

    def test_split_disabled_keeps_single_line(self):
        self.company.l10n_pe_detraction_split = False
        move = self._invoice('out_invoice', 1000.0)
        move.action_post()
        term_lines = move.line_ids.filtered(
            lambda l: l.display_type == 'payment_term')
        self.assertEqual(len(term_lines), 1)

    def test_split_not_applied_below_minimum(self):
        self._enable_split()
        move = self._invoice('out_invoice', 500.0)  # 590 <= 700: no aplica
        move.action_post()
        term_lines = move.line_ids.filtered(
            lambda l: l.display_type == 'payment_term')
        self.assertEqual(len(term_lines), 1)

    # ------------------------------------------------------------------
    # Depósito y constancia
    # ------------------------------------------------------------------
    def test_deposit_wizard_purchase(self):
        move = self._invoice('in_invoice', 1000.0)
        move.action_post()
        wizard = self.env['l10n_pe.detraction.deposit.wizard'].create({
            'move_id': move.id,
            'journal_id': self.journal_bank.id,
            'payment_date': date(2025, 6, 15),
            'constancy_number': '2025-000123',
        })
        self.assertEqual(wizard.amount, move.l10n_pe_detraction_amount)
        wizard.action_confirm()
        self.assertEqual(move.l10n_pe_detraction_number, '2025-000123')
        self.assertEqual(move.l10n_pe_detraction_date, date(2025, 6, 15))
        # v19: el pago queda registrado y vinculado (el asiento contable
        # nace al conciliar el extracto); la factura pasa a "En proceso de
        # pago" por el parcial de la detracción
        self.assertIn(move.payment_state, ('in_payment', 'paid', 'partial'))
        payment = self.env['account.payment'].search(
            [('partner_id', '=', self.partner.id),
             ('amount', '=', move.l10n_pe_detraction_amount)], limit=1)
        self.assertTrue(payment)
        self.assertIn(payment.state, ('in_process', 'paid'))
        self.assertEqual(payment.payment_type, 'outbound')
