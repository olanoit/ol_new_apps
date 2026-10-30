# -*- coding: utf-8 -*-
from datetime import timedelta
from decimal import Decimal

from lxml import etree

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
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

    # ------------------------------------------------------------------
    # Devoluciones y redondeo
    # ------------------------------------------------------------------
    def _refund(self, order, lines, payments, invoiced=False):
        """Devolución en caja de ``lines`` (línea de origen → cantidad)."""
        data = self.create_ui_order_data(
            [{'product': line.product_id, 'quantity': -qty, 'refunded_orderline_id': line.id}
             for line, qty in lines.items()],
            customer=self.patient, is_invoiced=invoiced, payments=payments)
        self.env['pos.order'].sync_from_ui([data])
        return self.env['pos.order'].search([('uuid', '=', data['uuid'])])

    def test_full_refund_in_same_period_nets_the_liquidation(self):
        self.open_new_session()
        order = self._sync([(self.insurance_pm, 19.24), (self.cash_pm1, 16.16)], invoiced=True)
        refund = self._refund(order, {line: 1 for line in order.lines},
                              [(self.insurance_pm, -19.24), (self.cash_pm1, -16.16)], invoiced=True)
        self.assertAlmostEqual(refund.pharmacy_insurance_amount, -19.24)
        self.assertEqual(refund.pharmacy_insurance_affiliate_id, self.affiliate)
        # La nota de crédito del paciente va solo por lo que él pagó.
        credit_note = refund.account_move
        self.assertEqual(credit_note.move_type, 'out_refund')
        self.assertAlmostEqual(credit_note.amount_total, 16.16)
        self.assertTrue(credit_note.currency_id.is_zero(credit_note.amount_residual))
        # El tope del mes queda libre otra vez.
        self.assertAlmostEqual(self._coverage()['amount'], 19.24)
        self.pos_session.action_pos_session_validate()
        self.assertEqual(self.pos_session.state, 'closed')
        liquidation = self.env['pharmacy.insurance.liquidation'].create({
            'agreement_id': self.agreement.id, 'date_from': self.today.replace(day=1),
            'date_to': self.today})
        liquidation.action_load_orders()
        self.assertEqual(liquidation.order_ids, order | refund)
        self.assertAlmostEqual(liquidation.amount_total, 0.0)
        liquidation.action_create_invoice()
        self.assertFalse(liquidation.invoice_id)
        self.assertFalse(liquidation.refund_invoice_ids)

    def test_refund_after_liquidation_is_a_credit_note_to_the_insurer(self):
        self.open_new_session()
        order = self._sync([(self.insurance_pm, 19.24), (self.cash_pm1, 16.16)])
        first = self._liquidate()
        losartan = order.lines.filtered(lambda line: line.product_id == self.losartan)
        covered = losartan.pharmacy_insurance_amount
        refund = self._refund(order, {losartan: 1},
                              [(self.insurance_pm, -covered), (self.cash_pm1, -(23.60 - covered))])
        self.assertAlmostEqual(refund.lines.pharmacy_insurance_amount, -covered)
        second = self.env['pharmacy.insurance.liquidation'].create({
            'agreement_id': self.agreement.id, 'date_from': self.today.replace(day=1),
            'date_to': self.today})
        second.action_load_orders()
        self.assertEqual(second.order_ids, refund)
        second.action_create_invoice()
        self.assertFalse(second.invoice_id)
        credit_note = second.refund_invoice_ids
        self.assertEqual(credit_note.move_type, 'out_refund')
        self.assertEqual(credit_note.reversed_entry_id, first.invoice_id)
        self.assertEqual(credit_note.partner_id, self.insurer)
        self.assertAlmostEqual(credit_note.amount_total, covered)
        self.assertAlmostEqual(credit_note.amount_untaxed, losartan.pharmacy_insurance_base)
        # Una devolución de una venta sin facturar a la aseguradora no se abona sola.
        second.action_cancel()
        first.invoice_id.button_draft()
        first.action_cancel()
        third = self.env['pharmacy.insurance.liquidation'].create({
            'agreement_id': self.agreement.id, 'date_from': self.today.replace(day=1),
            'date_to': self.today})
        third.order_ids = refund
        with self.assertRaises(UserError):
            third.action_create_invoice()

    def test_refund_must_return_covered_part_with_agreement(self):
        self.open_new_session()
        order = self._sync([(self.insurance_pm, 19.24), (self.cash_pm1, 16.16)])
        with self.assertRaises(ValidationError):
            self._refund(order, {line: 1 for line in order.lines}, [(self.cash_pm1, -35.40)])

    def test_cash_rounding_rounds_only_the_patient_invoice(self):
        rounding = self.env['account.cash.rounding'].create({
            'name': 'Redondeo 0,10', 'rounding': 0.10, 'strategy': 'add_invoice_line',
            'profit_account_id': self.company['default_cash_difference_income_account_id'].id,
            'loss_account_id': self.company['default_cash_difference_expense_account_id'].id,
            'rounding_method': 'HALF-UP'})
        self.config.write({'cash_rounding': True, 'rounding_method': rounding.id,
                           'only_round_cash_method': False})
        self.open_new_session()
        order = self._sync([(self.insurance_pm, 19.24), (self.cash_pm1, 16.20)], invoiced=True)
        invoice = order.account_move
        # 16,16 del paciente redondeado a 16,20; lo cubierto no entra al ajuste.
        self.assertAlmostEqual(invoice.amount_total, 16.20)
        rounding_line = invoice.line_ids.filtered(lambda line: line.display_type == 'rounding')
        self.assertAlmostEqual(rounding_line.balance, -0.04)
        self.assertTrue(invoice.currency_id.is_zero(invoice.amount_residual))

    def test_posted_invoice_needs_credit_note_to_cancel(self):
        self.open_new_session()
        self._sync([(self.insurance_pm, 19.24), (self.cash_pm1, 16.16)])
        liquidation = self._liquidate()
        with self.assertRaises(UserError):
            liquidation.action_cancel()


@tagged('post_install', '-at_install')
class TestPharmacyInsuranceTour(TestPointOfSaleHttpCommon):

    def start_tour(self, url_path, tour_name, step_delay=None, **kwargs):
        # Los pasos de los tours del núcleo usan los textos en inglés; la base
        # de migración está en es_PE y los usuarios de prueba lo heredan.
        if kwargs.get('login'):
            self.env['res.users'].search([('login', '=', kwargs['login'])]).lang = 'en_US'
        return super().start_tour(url_path, tour_name, step_delay=step_delay, **kwargs)

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


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestPharmacyInsurancePeXml(TestPoSCommon):
    """La boleta del paciente con los montos manuales de su parte, en una
    compañía peruana: el XML UBL cumple las reglas de cuadre de SUNAT y lleva
    el IGV de la parte del paciente."""

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        company = cls.company_data['company']
        # TestPoSCommon pisa el país de la compañía con uno ficticio.
        company.write({'country_id': cls.env.ref('base.pe').id, 'vat': '20557912879'})
        cls.config = cls.basic_config
        cls.config.journal_id.l10n_latam_use_documents = True
        cls.igv = cls.env['account.chart.template'].with_company(company).ref('sale_tax_igv_18')
        cls.analgesic = cls.create_product('Paracetamol 500 mg', cls.categ_basic, 10.0, tax_ids=cls.igv.ids)
        cls.losartan = cls.create_product('Losartán 50 mg', cls.categ_basic, 20.0, tax_ids=cls.igv.ids)
        cls.insurer = cls.env['res.partner'].create({
            'name': 'Salud Andina EPS S.A.', 'is_company': True, 'vat': '20100070970', 'country_id': cls.env.ref('base.pe').id})
        cls.patient = cls.env['res.partner'].create({
            'name': 'María Torres Quispe', 'additional_identifiers': {'PE_DNI': '44556677'}, 'country_id': cls.env.ref('base.pe').id})
        today = fields.Date.context_today(cls.env.user)
        cls.agreement = cls.env['pharmacy.insurance.agreement'].create({
            'name': 'Salud Andina · Plan regular', 'partner_id': cls.insurer.id,
            'coverage_percent': 80, 'copay_amount': 2, 'company_id': company.id,
            'date_start': today - timedelta(days=60),
            'journal_id': cls.company_data['default_journal_sale'].id})
        cls.env['pharmacy.insurance.affiliate'].create({
            'agreement_id': cls.agreement.id, 'partner_id': cls.patient.id, 'number': 'SA-001',
            'date_start': today - timedelta(days=30)})
        cls.agreement.action_create_pos_payment_method()
        cls.insurance_pm = cls.agreement.payment_method_id
        cls.config.write({'payment_method_ids': [Command.link(cls.insurance_pm.id)]})

    def test_patient_boleta_xml_follows_sunat_rules(self):
        try:
            from odoo.addons.al_l10n_pe_edi_downpayment_discount.tests.sunat_rules import NS, validar
        except ImportError:
            self.skipTest('Falta el validador de reglas SUNAT (al_l10n_pe_edi_downpayment_discount).')
        self.open_new_session()
        # 11,80 + 23,60 = 35,40. El convenio cubre 80 % menos 2,00 de copago: 26,32.
        data = self.create_ui_order_data([(self.analgesic, 1), (self.losartan, 1)],
                                         customer=self.patient, is_invoiced=True,
                                         payments=[(self.insurance_pm, 26.32), (self.cash_pm1, 9.08)])
        self.env['pos.order'].with_context(generate_pdf=False).sync_from_ui([data])
        order = self.env['pos.order'].search([('uuid', '=', data['uuid'])])
        boleta = order.account_move
        self.assertEqual(boleta.l10n_latam_document_type_id.code, '03')
        self.assertAlmostEqual(boleta.amount_total, 9.08)
        xml, errors = self.env['account.edi.xml.ubl_pe']._export_invoice(boleta)
        self.assertFalse(errors, errors)
        root = etree.fromstring(xml)
        self.assertEqual(validar(root), [])
        # El XML lleva la base y el IGV de la parte del paciente.
        self.assertEqual(Decimal(root.findtext('cac:LegalMonetaryTotal/cbc:PayableAmount', namespaces=NS)),
                         Decimal('9.08'))
        self.assertEqual(Decimal(root.findtext('cac:TaxTotal/cbc:TaxAmount', namespaces=NS)),
                         Decimal(str(boleta.amount_tax)).quantize(Decimal('0.01')))
        line_taxes = sum(Decimal(node.text) for node in root.findall(
            'cac:InvoiceLine/cac:TaxTotal/cbc:TaxAmount', NS))
        self.assertEqual(line_taxes, Decimal(str(boleta.amount_tax)).quantize(Decimal('0.01')))
