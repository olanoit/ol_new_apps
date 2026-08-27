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
            'is_retention_agent': True})
        bill = self._bill(1000.0, partner=agent)
        self.assertFalse(bill.l10n_pe_retention_applies)

    def test_not_applies_good_contributor(self):
        self.partner.is_good_taxpayer = True
        bill = self._bill(1000.0)
        self.assertFalse(bill.l10n_pe_retention_applies)
        self.partner.is_good_taxpayer = False

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

    # ------------------------------------------------------------------
    # Fase 1: retención en el pago (marco nativo)
    # ------------------------------------------------------------------
    def _setup_retention_tax(self):
        Account = self.env['account.account'].with_company(self.company)
        account = Account.search([('code', '=', '401141')], limit=1) or \
            Account.create({'code': '401141',
                            'name': 'IGV Retenciones por pagar Test',
                            'account_type': 'liability_current'})
        sequence = self.env['ir.sequence'].search(
            [('code', '=', 'l10n_pe.cre.test')], limit=1) or \
            self.env['ir.sequence'].create({
                'name': 'CRE Test', 'code': 'l10n_pe.cre.test',
                'prefix': 'R001-', 'padding': 8,
                'company_id': self.company.id})
        tax = self.env['account.tax'].search(
            [('company_id', '=', self.company.id),
             ('name', '=', 'Retención IGV 3% Test')], limit=1)
        if not tax:
            tax = self.env['account.tax'].create({
                'name': 'Retención IGV 3% Test', 'amount': -3.0,
                'amount_type': 'percent', 'type_tax_use': 'purchase',
                'is_withholding_tax_on_payment': True,
                'withholding_sequence_id': sequence.id,
                'company_id': self.company.id})
            tax.invoice_repartition_line_ids.filtered(
                lambda l: l.repartition_type == 'tax'
            ).account_id = account
            tax.refund_repartition_line_ids.filtered(
                lambda l: l.repartition_type == 'tax'
            ).account_id = account
        self.company.l10n_pe_retention_tax_id = tax
        return tax, account

    def _register_payment(self, bill, amount=None):
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=bill.ids).create({})
        if amount is not None:
            wizard.amount = amount
        return wizard

    def test_payment_full_retention(self):
        tax, _account = self._setup_retention_tax()
        bill = self._bill(1000.0)  # total 1180
        bill.action_post()
        # el impuesto se inyectó sin alterar el total
        self.assertIn(tax, bill.invoice_line_ids.tax_ids)
        self.assertEqual(bill.amount_total, 1180.0)
        wizard = self._register_payment(bill)
        self.assertEqual(len(wizard.withholding_line_ids), 1)
        # 3% del pago completo
        self.assertAlmostEqual(
            wizard.withholding_line_ids.amount, 35.40, 2)
        payments = wizard._create_payments()
        self.assertAlmostEqual(
            payments._l10n_pe_retention_lines().amount, 35.40, 2)
        self.assertTrue(payments.l10n_pe_retention_number)
        self.assertTrue(
            payments.l10n_pe_retention_number.startswith('R001-'))

    def test_payment_partial_retention(self):
        self._setup_retention_tax()
        bill = self._bill(1000.0)
        bill.action_post()
        wizard = self._register_payment(bill, amount=590.0)  # 50%
        # 3% de cada pago parcial (590 × 3% = 17.70)
        self.assertAlmostEqual(
            wizard.withholding_line_ids.amount, 17.70, 2)

    def test_post_without_tax_raises(self):
        from odoo.exceptions import UserError
        self.company.l10n_pe_retention_tax_id = False
        bill = self._bill(1000.0)
        with self.assertRaises(UserError):
            bill.action_post()

    def test_no_tax_injected_below_minimum(self):
        tax, _account = self._setup_retention_tax()
        bill = self._bill(500.0)
        bill.action_post()
        self.assertNotIn(tax, bill.invoice_line_ids.tax_ids)

    def test_outstanding_account_default(self):
        self._setup_retention_tax()
        Account = self.env['account.account'].with_company(self.company)
        outstanding = Account.search(
            [('code', '=', '104901')], limit=1) or Account.create({
                'code': '104901', 'name': 'Pagos pendientes Test',
                'account_type': 'asset_current', 'reconcile': True})
        self.company.l10n_pe_retention_outstanding_account_id = outstanding
        bill = self._bill(1000.0)
        bill.action_post()
        wizard = self._register_payment(bill)
        if not wizard.withholding_payment_account_id:
            self.assertEqual(
                wizard.withholding_outstanding_account_id, outstanding)

    def test_wizard_amount_edit_recomputes(self):
        self._setup_retention_tax()
        bill = self._bill(1000.0)
        bill.action_post()
        wizard = self._register_payment(bill, amount=295.0)  # 25%
        self.assertAlmostEqual(
            wizard.withholding_line_ids.amount, 8.85, 2)  # 3% de 295
        wizard.amount = 1180.0
        self.assertAlmostEqual(
            wizard.withholding_line_ids.amount, 35.40, 2)

    def test_wizard_line_removable(self):
        self._setup_retention_tax()
        bill = self._bill(1000.0)
        bill.action_post()
        wizard = self._register_payment(bill)
        wizard.withholding_line_ids = [(5, 0, 0)]
        payments = wizard._create_payments()
        self.assertFalse(payments.l10n_pe_retention_number)

    def test_sequence_increments(self):
        self._setup_retention_tax()
        numbers = []
        for _i in range(2):
            bill = self._bill(1000.0)
            bill.action_post()
            payments = self._register_payment(bill)._create_payments()
            numbers.append(payments.l10n_pe_retention_number)
        self.assertTrue(all(n and n.startswith('R001-') for n in numbers))
        self.assertNotEqual(numbers[0], numbers[1])

    def test_applies_recomputes_on_partner_flag(self):
        bill = self._bill(1000.0)
        self.assertTrue(bill.l10n_pe_retention_applies)
        self.partner.is_retention_agent = True
        self.assertFalse(bill.l10n_pe_retention_applies)
        self.partner.is_retention_agent = False
        self.assertTrue(bill.l10n_pe_retention_applies)

    def test_not_applies_boleta(self):
        bill = self._bill(1000.0)
        doc_type = self.env['l10n_latam.document.type'].search(
            [('code', '=', '03'), ('country_id.code', '=', 'PE')], limit=1)
        if not doc_type:
            self.skipTest('sin tipo de documento 03')
        bill.l10n_latam_document_type_id = doc_type
        self.assertFalse(bill.l10n_pe_retention_applies)

    def test_cre_xml_content(self):
        self._setup_retention_tax()
        bill = self._bill(1000.0)
        bill.action_post()
        payments = self._register_payment(bill)._create_payments()
        payments.action_l10n_pe_generate_cre_xml()
        attachment = self.env['ir.attachment'].search(
            [('res_model', '=', 'account.payment'),
             ('res_id', '=', payments.id),
             ('mimetype', '=', 'application/xml')],
            limit=1, order='id desc')
        xml = attachment.raw.decode()
        self.assertIn(self.company.vat, xml)
        self.assertIn(self.partner.vat, xml)
        self.assertIn(payments.l10n_pe_retention_number, xml)
        self.assertIn('<sac:SUNATRetentionPercent>3', xml)
        self.assertIn('35.40', xml)

    def test_summary_excludes_other_months(self):
        self._setup_retention_tax()
        bill = self._bill(1000.0)
        bill.action_post()
        wizard = self._register_payment(bill)
        wizard.payment_date = date(2025, 6, 15)
        wizard._create_payments()
        summary = self.env['l10n_pe.retention.summary.wizard'].create({
            'year': 2025, 'month': '07'})
        summary.action_export()
        import base64
        content = base64.b64decode(summary.file_data or b'').decode()
        self.assertNotIn(str(date(2025, 6, 15)), content)

    def test_retention_received_reset_draft(self):
        self.test_retention_received()
        received = self.env['l10n_pe.retention.received'].search(
            [('name', '=', 'R002-00000077')], limit=1)
        invoice = received.move_id
        received.action_draft()
        self.assertEqual(received.state, 'draft')
        self.assertFalse(received.entry_id)
        self.assertAlmostEqual(invoice.amount_residual, 2360.0, 2)

    # ------------------------------------------------------------------
    # Fase 2: retenciones sufridas (ventas)
    # ------------------------------------------------------------------
    def test_retention_received(self):
        Account = self.env['account.account'].with_company(self.company)
        account = Account.search([('code', '=', '401142')], limit=1) or \
            Account.create({'code': '401142',
                            'name': 'IGV Retenciones sufridas Test',
                            'account_type': 'asset_current',
                            'reconcile': False})
        self.company.l10n_pe_retention_received_account_id = account
        acc_inc = Account.search([('account_type', '=', 'income')], limit=1)
        journal_sale = self.env['account.journal'].create({
            'name': 'RET Ventas Test', 'code': 'RETV', 'type': 'sale',
            'company_id': self.company.id,
            'l10n_latam_use_documents': False})
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner.id,
            'journal_id': journal_sale.id,
            'invoice_date': date(2025, 6, 10),
            'invoice_line_ids': [(0, 0, {
                'name': 'Venta', 'quantity': 1, 'price_unit': 2000.0,
                'account_id': acc_inc.id,
                'tax_ids': [(6, 0, self.env['account.tax'].search(
                    [('company_id', '=', self.company.id),
                     ('type_tax_use', '=', 'sale'),
                     ('amount', '=', 18.0)], limit=1).ids)]})],
        })
        invoice.action_post()
        residual_before = invoice.amount_residual
        received = self.env['l10n_pe.retention.received'].create({
            'name': 'R002-00000077', 'date': date(2025, 6, 20),
            'partner_id': self.partner.id, 'move_id': invoice.id,
            'amount': 70.80})
        received.action_post()
        self.assertEqual(received.state, 'posted')
        self.assertTrue(received.entry_id)
        self.assertEqual(received.entry_id.state, 'posted')
        self.assertAlmostEqual(
            invoice.amount_residual, residual_before - 70.80, 2)
        debit_line = received.entry_id.line_ids.filtered(
            lambda l: l.debit > 0)
        self.assertEqual(debit_line.account_id, account)

    # ------------------------------------------------------------------
    # Fase 4: resumen 626
    # ------------------------------------------------------------------
    def test_summary_626(self):
        self._setup_retention_tax()
        bill = self._bill(1000.0)
        bill.action_post()
        wizard = self._register_payment(bill)
        wizard.payment_date = date(2025, 6, 15)
        wizard._create_payments()
        summary = self.env['l10n_pe.retention.summary.wizard'].create({
            'year': 2025, 'month': '06'})
        summary.action_export()
        import base64
        content = base64.b64decode(summary.file_data).decode()
        row = next(l.split('|') for l in content.split('\r\n')
                   if self.partner.vat in l)
        self.assertEqual(len(row), 7)
        self.assertEqual(row[6], '35.40')

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
