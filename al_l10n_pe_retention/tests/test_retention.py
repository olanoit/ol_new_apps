# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestRetentionApplies(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        if not (cls.company.vat and len(cls.company.vat) == 11):
            cls.company.vat = '20512528458'
        cls.company.write({
            'l10n_pe_retention_agent': True,
            'l10n_pe_retention_rate': 3.0,
            'l10n_pe_retention_min_amount': 700.0,
        })
        Account = cls.env['account.account'].with_company(cls.company)
        cls.account_exp = Account.search(
            [('account_type', '=', 'expense')], limit=1)
        cls.tax_purchase = cls.env['account.tax'].search([
            ('company_id', '=', cls.company.id),
            ('type_tax_use', '=', 'purchase'), ('amount', '=', 18.0)],
            limit=1)
        cls.journal = cls.env['account.journal'].create({
            'name': 'RET Compras Test', 'code': 'RETC', 'type': 'purchase',
            'company_id': cls.company.id, 'l10n_latam_use_documents': False})
        cls.partner = cls.env['res.partner'].create({
            'name': 'Proveedor Retención SAC', 'vat': '20131312955'})

    def _bill(self, price, partner=None):
        return self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': (partner or self.partner).id,
            'journal_id': self.journal.id,
            'invoice_date': date(2025, 6, 10), 'date': date(2025, 6, 10),
            'ref': 'F00R-00000001',
            'invoice_line_ids': [(0, 0, {
                'name': 'Servicio', 'quantity': 1.0, 'price_unit': price,
                'account_id': self.account_exp.id,
                'tax_ids': [(6, 0, self.tax_purchase.ids)]})],
        })

    def test_applies_above_minimum(self):
        bill = self._bill(1000.0)  # total 1180 > 700
        self.assertTrue(bill.l10n_pe_retention_applies)
        # 3% de 1180 = 35.40 (estimación informativa)
        self.assertAlmostEqual(bill.l10n_pe_retention_amount, 35.40, 2)

    def test_not_applies_below_minimum(self):
        bill = self._bill(500.0)  # total 590 <= 700
        self.assertFalse(bill.l10n_pe_retention_applies)
        self.assertEqual(bill.l10n_pe_retention_amount, 0.0)

    def test_not_applies_between_agents(self):
        agent = self.env['res.partner'].create({
            'name': 'Proveedor Agente SAC', 'vat': '20512528458',
            'l10n_pe_retention_agent': True})
        bill = self._bill(1000.0, partner=agent)
        self.assertFalse(bill.l10n_pe_retention_applies)

    def test_not_applies_good_contributor(self):
        self.partner.l10n_pe_good_contributor = True
        bill = self._bill(1000.0)
        self.assertFalse(bill.l10n_pe_retention_applies)
        self.partner.l10n_pe_good_contributor = False

    def test_not_applies_company_not_agent(self):
        self.company.l10n_pe_retention_agent = False
        bill = self._bill(1000.0)
        self.assertFalse(bill.l10n_pe_retention_applies)
        self.company.l10n_pe_retention_agent = True

    def test_not_applies_customer_invoice(self):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner.id,
            'invoice_date': date(2025, 6, 10),
            'invoice_line_ids': [(0, 0, {
                'name': 'x', 'quantity': 1, 'price_unit': 5000.0,
                'account_id': self.account_exp.id})],
        })
        self.assertFalse(move.l10n_pe_retention_applies)

    def test_not_applies_with_detraction(self):
        if 'l10n_pe.detraction.type' not in self.env:
            self.skipTest('al_l10n_pe_detraction no instalado')
        dtype = self.env.ref('al_l10n_pe_detraction.detraction_037')
        product = self.env['product.product'].create({
            'name': 'Servicio SPOT Ret Test', 'type': 'service',
            'l10n_pe_detraction_type_id': dtype.id})
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': self.partner.id,
            'journal_id': self.journal.id,
            'invoice_date': date(2025, 6, 10), 'date': date(2025, 6, 10),
            'ref': 'F00R-00000002',
            'invoice_line_ids': [(0, 0, {
                'name': product.name, 'product_id': product.id,
                'quantity': 1.0, 'price_unit': 1000.0,
                'account_id': self.account_exp.id,
                'tax_ids': [(6, 0, self.tax_purchase.ids)]})],
        })
        self.assertTrue(bill.l10n_pe_detraction_applies)
        self.assertFalse(bill.l10n_pe_retention_applies)
