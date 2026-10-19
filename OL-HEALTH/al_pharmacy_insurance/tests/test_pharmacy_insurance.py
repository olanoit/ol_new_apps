# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, fields
from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestPharmacyInsurance(TestPoSCommon):
    """Venta de 2 productos con IGV 18 %: Paracetamol 10,00 + 1,80 y Losartán
    20,00 + 3,60 = 35,40. El convenio cubre 80 % del paracetamol (9,44) y 50 %
    del losartán (11,80) menos el copago de 2,00: 19,24. El paciente paga 16,16."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        cls.igv = cls.env['account.tax'].create({
            'name': 'IGV 18 % (convenio)', 'amount': 18, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'price_include_override': 'tax_excluded',
            'company_id': cls.env.company.id})
        cls.chronic_categ = cls.env['product.category'].create({
            'name': 'Crónicos', 'parent_id': cls.categ_basic.id})
        cls.analgesic = cls.create_product('Paracetamol 500 mg', cls.categ_basic, 10.0,
                                           tax_ids=cls.igv.ids)
        cls.losartan = cls.create_product('Losartán 50 mg', cls.chronic_categ, 20.0,
                                          tax_ids=cls.igv.ids)
        cls.insurer = cls.env['res.partner'].create({'name': 'Salud Andina EPS S.A.', 'is_company': True})
        cls.patient = cls.env['res.partner'].create({'name': 'María Torres Quispe', 'vat': '44556677'})
        cls.today = fields.Date.context_today(cls.env.user)
        cls.sale_journal = cls.env['account.journal'].search([
            ('type', '=', 'sale'), ('company_id', '=', cls.env.company.id)], limit=1)
        cls.agreement = cls.env['pharmacy.insurance.agreement'].create({
            'name': 'Salud Andina · Plan regular', 'partner_id': cls.insurer.id,
            'coverage_percent': 80, 'copay_amount': 2, 'max_per_sale': 100, 'max_per_month': 30,
            'date_start': cls.today - timedelta(days=60), 'journal_id': cls.sale_journal.id,
            'line_ids': [Command.create({'categ_id': cls.chronic_categ.id, 'coverage_percent': 50})],
        })
        cls.affiliate = cls.env['pharmacy.insurance.affiliate'].create({
            'agreement_id': cls.agreement.id, 'partner_id': cls.patient.id, 'number': 'SA-001',
            'date_start': cls.today - timedelta(days=30)})
        cls.agreement.action_create_pos_payment_method()
        cls.insurance_pm = cls.agreement.payment_method_id
        cls.config.write({'payment_method_ids': [Command.link(cls.insurance_pm.id)]})

    def _lines(self, *pairs):
        return [{'product': product, 'price_unit': price, 'qty': qty, 'discount': 0.0,
                 'taxes': product.taxes_id} for product, price, qty in pairs]

    def _coverage(self, lines=None, prescription=False, date=None):
        lines = lines or self._lines((self.analgesic, 10.0, 1), (self.losartan, 20.0, 1))
        return self.agreement._compute_coverage(self.patient, lines, date or self.today, prescription)

    def _sync(self, payments, invoiced=False):
        data = self.create_ui_order_data(
            [(self.analgesic, 1), (self.losartan, 1)], customer=self.patient,
            is_invoiced=invoiced, payments=payments)
        result = self.env['pos.order'].sync_from_ui([data])
        return self.env['pos.order'].browse(result['pos.order'][0]['id'])

    def _liquidate(self):
        liquidation = self.env['pharmacy.insurance.liquidation'].create({
            'agreement_id': self.agreement.id, 'date_from': self.today.replace(day=1),
            'date_to': self.today})
        liquidation.action_load_orders()
        liquidation.action_create_invoice()
        liquidation.invoice_id.action_post()
        return liquidation

    # ------------------------------------------------------------------
    # Cobertura
    # ------------------------------------------------------------------
    def test_payment_method_is_customer_account(self):
        self.assertEqual(self.insurance_pm.type, 'pay_later')
        self.assertFalse(self.insurance_pm.split_transactions)
        self.assertTrue(self.insurance_pm.pharmacy_is_insurance)

    def test_coverage_by_category_with_copay(self):
        coverage = self._coverage()
        self.assertFalse(coverage['error'])
        self.assertEqual(coverage['affiliate'], self.affiliate)
        self.assertAlmostEqual(coverage['amount'], 19.24)
        # Lo cubierto por línea suma lo cubierto de la venta.
        self.assertAlmostEqual(sum(a['amount'] for a in coverage['allocations']), 19.24)

    def test_product_line_wins_over_category(self):
        self.agreement.line_ids = [Command.create({'product_id': self.losartan.id, 'coverage_percent': 100})]
        coverage = self._coverage(self._lines((self.losartan, 20.0, 1)))
        self.assertAlmostEqual(coverage['amount'], 21.60)

    def test_cap_per_sale(self):
        self.agreement.write({'max_per_sale': 10, 'max_per_month': 0})
        self.assertAlmostEqual(self._coverage(self._lines((self.analgesic, 10.0, 10)))['amount'], 10.0)

    def test_monthly_cap_counts_previous_sales(self):
        self.open_new_session()
        order = self._sync([(self.insurance_pm, 19.24), (self.cash_pm1, 16.16)])
        self.assertAlmostEqual(order.pharmacy_insurance_amount, 19.24)
        self.assertEqual(order.pharmacy_insurance_affiliate_id, self.affiliate)
        self.assertAlmostEqual(sum(order.lines.mapped('pharmacy_insurance_amount')), 19.24)
        # Quedan 30 − 19,24 = 10,76 del tope mensual.
        self.assertAlmostEqual(self._coverage()['amount'], 10.76)

    def test_validity_of_agreement_and_affiliate(self):
        before = self.today - timedelta(days=45)
        self.assertTrue(self._coverage(date=before)['error'])
        self.affiliate.date_end = self.today - timedelta(days=1)
        self.assertTrue(self._coverage()['error'])
        self.agreement.date_end = self.today - timedelta(days=1)
        self.assertIn('no está vigente', self._coverage()['error'])

    def test_prescription_required(self):
        self.agreement.require_prescription = True
        self.assertTrue(self._coverage()['error'])
        self.assertAlmostEqual(self._coverage(prescription=True)['amount'], 19.24)

    def test_reimbursement_mode_is_not_applied_in_pos(self):
        self.agreement.billing_mode = 'reimbursement'
        self.assertIn('reembolso', self._coverage()['error'])
        other = self.agreement.copy({'name': 'Reembolso', 'payment_method_id': False})
        with self.assertRaises(UserError):
            other.action_create_pos_payment_method()

    def test_pos_rpc_for_cashier(self):
        line = {'product_id': self.analgesic.id, 'price_unit': 10.0, 'qty': 1, 'discount': 0,
                'tax_ids': self.igv.ids}
        result = self.env['pharmacy.insurance.agreement'].get_pos_coverage(
            self.insurance_pm.id, self.patient.id, [line], False)
        # 80 % de 11,80 − 2,00 = 7,44.
        self.assertAlmostEqual(result['amount'], 7.44)
        self.assertEqual(result['affiliate'], 'SA-001')
        other = self.env['res.partner'].create({'name': 'Sin convenio'})
        result = self.env['pharmacy.insurance.agreement'].get_pos_coverage(
            self.insurance_pm.id, other.id, [line], False)
        self.assertIn('no es afiliado', result['error'])

    def test_order_rejects_more_than_covered(self):
        self.open_new_session()
        with self.assertRaises(ValidationError):
            self._sync([(self.insurance_pm, 25.0), (self.cash_pm1, 10.40)])

    # ------------------------------------------------------------------
    # Comprobantes y asientos
    # ------------------------------------------------------------------
    def test_patient_invoice_and_insurer_invoice_add_up_to_the_sale(self):
        self.open_new_session()
        order = self._sync([(self.insurance_pm, 19.24), (self.cash_pm1, 16.16)], invoiced=True)
        patient_invoice = order.account_move
        # El comprobante del paciente va solo por su parte, con su IGV, y queda pagado.
        self.assertAlmostEqual(patient_invoice.amount_total, 16.16)
        self.assertTrue(patient_invoice.currency_id.is_zero(patient_invoice.amount_residual))
        self.assertEqual(patient_invoice.partner_id, self.patient)
        self.pos_session.action_pos_session_validate()

        liquidation = self._liquidate()
        insurer_invoice = liquidation.invoice_id
        self.assertEqual(insurer_invoice.move_type, 'out_invoice')
        self.assertEqual(insurer_invoice.partner_id, self.insurer)
        self.assertAlmostEqual(insurer_invoice.amount_total, 19.24)
        self.assertAlmostEqual(liquidation.amount_total, 19.24)
        self.assertIn('DNI 44556677', insurer_invoice.invoice_line_ids[0].name)
        self.assertIn('SA-001', insurer_invoice.invoice_line_ids[0].name)
        # Ingreso e IGV de los dos comprobantes = los de la venta (30,00 y 5,40).
        self.assertAlmostEqual(patient_invoice.amount_untaxed + insurer_invoice.amount_untaxed, 30.0)
        self.assertAlmostEqual(patient_invoice.amount_tax + insurer_invoice.amount_tax, 5.40)
        # Cuenta por cobrar: el paciente en cero, la aseguradora por lo cubierto.
        receivable = insurer_invoice.line_ids.filtered(lambda l: l.display_type == 'payment_term')
        self.assertAlmostEqual(receivable.balance, 19.24)
        self.assertEqual(receivable.partner_id, self.insurer)
        # El método «Convenio» no deja cuenta por cobrar en el cierre de caja.
        session_lines = self.pos_session.move_id.line_ids
        self.assertFalse(session_lines.filtered(
            lambda l: self.insurance_pm.name in (l.name or '')))
        self.assertEqual(self.pos_session.move_id.state, 'posted')

    def test_sale_without_invoice_books_only_patient_part(self):
        self.open_new_session()
        order = self._sync([(self.insurance_pm, 19.24), (self.cash_pm1, 16.16)])
        self.assertFalse(order.account_move)
        self.pos_session.action_pos_session_validate()
        move = self.pos_session.move_id
        income = move.line_ids.filtered(lambda l: self.igv in l.tax_ids)
        taxes = move.line_ids.filtered(lambda l: l.tax_line_id == self.igv)
        patient_untaxed = -sum(income.mapped('balance'))
        patient_tax = -sum(taxes.mapped('balance'))
        self.assertAlmostEqual(patient_untaxed + patient_tax, 16.16)
        self.assertFalse(move.line_ids.filtered(lambda l: self.insurance_pm.name in (l.name or '')))

        liquidation = self._liquidate()
        insurer_invoice = liquidation.invoice_id
        self.assertAlmostEqual(insurer_invoice.amount_total, 19.24)
        self.assertAlmostEqual(patient_untaxed + insurer_invoice.amount_untaxed, 30.0)
        self.assertAlmostEqual(patient_tax + insurer_invoice.amount_tax, 5.40)

    def test_order_is_liquidated_once_and_cancel_frees_it(self):
        self.open_new_session()
        order = self._sync([(self.insurance_pm, 19.24), (self.cash_pm1, 16.16)])
        liquidation = self.env['pharmacy.insurance.liquidation'].create({
            'agreement_id': self.agreement.id, 'date_from': self.today.replace(day=1),
            'date_to': self.today})
        liquidation.action_load_orders()
        self.assertEqual(liquidation.order_ids, order)
        liquidation.action_create_invoice()
        second = self.env['pharmacy.insurance.liquidation'].create({
            'agreement_id': self.agreement.id, 'date_from': self.today.replace(day=1),
            'date_to': self.today})
        second.action_load_orders()
        self.assertFalse(second.order_ids)
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_pharmacy_insurance.report_pharmacy_insurance_liquidation', liquidation.ids)[0]
        self.assertIn(b'SA-001', html)
        liquidation.action_cancel()
        self.assertFalse(order.pharmacy_insurance_liquidation_id)
        self.assertEqual(liquidation.invoice_id.state, 'cancel')

    def test_posted_invoice_needs_credit_note_to_cancel(self):
        self.open_new_session()
        self._sync([(self.insurance_pm, 19.24), (self.cash_pm1, 16.16)])
        liquidation = self._liquidate()
        with self.assertRaises(UserError):
            liquidation.action_cancel()


@tagged('post_install', '-at_install')
class TestPharmacyInsuranceTour(TestPointOfSaleHttpCommon):

    def test_pos_pays_covered_part_with_agreement(self):
        product = self.env['product.product'].create({
            'name': 'Losartán 50 mg', 'type': 'consu', 'available_in_pos': True,
            'list_price': 20.0, 'taxes_id': [Command.set([])]})
        insurer = self.env['res.partner'].create({'name': 'Salud Andina EPS S.A.', 'is_company': True})
        patient = self.env['res.partner'].create({'name': 'María Torres Quispe'})
        agreement = self.env['pharmacy.insurance.agreement'].create({
            'name': 'Salud Andina', 'partner_id': insurer.id, 'coverage_percent': 80,
            'copay_amount': 2, 'company_id': self.main_pos_config.company_id.id,
            'date_start': fields.Date.today() - timedelta(days=10)})
        self.env['pharmacy.insurance.affiliate'].create({
            'agreement_id': agreement.id, 'partner_id': patient.id, 'number': 'SA-777',
            'date_start': fields.Date.today() - timedelta(days=10)})
        agreement.action_create_pos_payment_method()
        self.main_pos_config.write({'payment_method_ids': [Command.link(agreement.payment_method_id.id)]})
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.start_pos_tour('al_pharmacy_insurance_pay')
        order = self.env['pos.order'].search(
            [('session_id', '=', self.main_pos_config.current_session_id.id)], limit=1)
        # 80 % de 20 − copago 2 = 14 el convenio; 6 el paciente.
        self.assertEqual(order.pharmacy_insurance_amount, 14.0)
        self.assertEqual(order.pharmacy_insurance_agreement_id, agreement)
        self.assertEqual(order.lines.pharmacy_insurance_amount, 14.0)
        self.assertEqual(sum(order.payment_ids.filtered(
            lambda p: p.payment_method_id != agreement.payment_method_id).mapped('amount')), 6.0)
