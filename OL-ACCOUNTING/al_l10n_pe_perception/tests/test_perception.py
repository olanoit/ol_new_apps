# -*- coding: utf-8 -*-
"""Percepciones del IGV (R.S. 058-2006/SUNAT, Ley 29173; combustibles,
R.S. 128-2002/SUNAT): régimen y tasa en la factura, XML de la factura,
comprobante de percepción (tipo 40) y percepciones que nos cobran."""
from datetime import date
from unittest.mock import patch

from lxml import etree
from psycopg2 import IntegrityError

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..models.perception import perception_factor

NS = {
    'p': 'urn:sunat:names:specification:ubl:peru:schema:xsd:Perception-1',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'sac': 'urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1',
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
}


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestPerception(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.company.vat = '20512528458'
        cls.company.write({
            'l10n_pe_perception_agent': True,
            'l10n_pe_perception_fuel_agent': True,
        })
        Account = cls.env['account.account'].with_company(cls.company)
        cls.perception_account = Account.create({
            'code': '401130', 'name': 'IGV percibido por pagar test',
            'account_type': 'liability_current'})
        cls.received_account = Account.create({
            'code': '401140', 'name': 'IGV percepciones por aplicar test',
            'account_type': 'asset_current'})
        cls.company.write({
            'l10n_pe_perception_account_id': cls.perception_account.id,
            'l10n_pe_perception_received_account_id': cls.received_account.id,
        })
        cls.customer = cls.env['res.partner'].create({
            'name': 'FERRETERÍA CLIENTE SAC', 'is_company': True, 'vat': '20557912879', 'country_id': cls.env.ref('base.pe').id})
        cls.person = cls.env['res.partner'].create({
            'name': 'Juan Pérez', 'additional_identifiers': {'PE_DNI': '45678912'},
            'country_id': cls.env.ref('base.pe').id})
        cls.supplier = cls.env['res.partner'].create({
            'name': 'DISTRIBUIDORA AGENTE SAC', 'is_company': True, 'vat': '20100070970'})
        cls.igv = cls.env['account.tax'].search([
            ('l10n_pe_edi_tax_code', '=', '1000'), ('type_tax_use', '=', 'sale'),
            ('amount', '=', 18), ('company_id', '=', cls.company.id)], limit=1)
        cls.cement = cls.env['product.product'].create({
            'name': 'Cemento portland', 'type': 'consu', 'lst_price': 100.0,
            'l10n_pe_perception_type': 'internal', 'taxes_id': [Command.set(cls.igv.ids)]})
        cls.beer = cls.env['product.product'].create({
            'name': 'Cerveza', 'type': 'consu', 'lst_price': 10.0,
            'l10n_pe_perception_type': 'internal_low', 'taxes_id': [Command.set(cls.igv.ids)]})
        cls.diesel = cls.env['product.product'].create({
            'name': 'Diésel B5', 'type': 'consu', 'lst_price': 10.0,
            'l10n_pe_perception_type': 'fuel', 'taxes_id': [Command.set(cls.igv.ids)]})
        cls.service = cls.env['product.product'].create({
            'name': 'Flete', 'type': 'service', 'lst_price': 100.0,
            'taxes_id': [Command.set(cls.igv.ids)]})

    def _invoice(self, lines, partner=None, post=True, currency=None):
        vals = {
            'move_type': 'out_invoice', 'partner_id': (partner or self.customer).id,
            'invoice_date': date(2026, 3, 15), 'date': date(2026, 3, 15),
            'invoice_line_ids': [Command.create({
                'product_id': product.id, 'quantity': qty, 'price_unit': price,
                'tax_ids': [Command.set(self.igv.ids)]}) for product, qty, price in lines],
        }
        if currency:
            vals['currency_id'] = currency.id
        move = self.env['account.move'].create(vals)
        if post:
            move.action_post()
        return move

    # ------------------------------------------------------------------
    # Régimen y tasa en la factura
    # ------------------------------------------------------------------
    def test_internal_two_percent(self):
        move = self._invoice([(self.cement, 10, 100.0)])
        self.assertEqual(move.l10n_pe_perception_code, '51')
        self.assertEqual(move.l10n_pe_perception_rate, 2.0)
        self.assertAlmostEqual(move.l10n_pe_perception_base_pen, 1180.0, 2)
        self.assertAlmostEqual(move.l10n_pe_perception_amount, 23.60, 2)
        self.assertEqual(move.l10n_pe_edi_operation_type, '2001', 'operación sujeta a percepción')

    def test_mixed_invoice_only_subject_goods(self):
        move = self._invoice([(self.cement, 1, 100.0), (self.service, 1, 100.0)])
        self.assertAlmostEqual(move.l10n_pe_perception_base, 118.0, 2)
        self.assertAlmostEqual(move.l10n_pe_perception_amount, 2.36, 2)

    def test_customer_perception_agent_half_percent(self):
        self.customer.l10n_pe_is_perception_agent = True
        move = self._invoice([(self.cement, 10, 100.0)])
        self.assertEqual(move.l10n_pe_perception_code, '53')
        self.assertAlmostEqual(move.l10n_pe_perception_amount, 5.90, 2)
        self.customer.l10n_pe_is_perception_agent = False

    def test_customer_retention_agent_excluded(self):
        self.customer.is_retention_agent = True
        move = self._invoice([(self.cement, 10, 100.0)])
        self.assertFalse(move.l10n_pe_perception_code)
        self.assertIn('agente de retención', move.l10n_pe_perception_note)
        self.customer.is_retention_agent = False

    def test_exempt_entity_excluded(self):
        self.customer.l10n_pe_perception_excluded = True
        move = self._invoice([(self.cement, 10, 100.0)])
        self.assertFalse(move.l10n_pe_perception_code)
        self.customer.l10n_pe_perception_excluded = False

    def test_final_consumer_limits(self):
        """Boleta a persona natural: no se percibe hasta S/ 1 500 (S/ 100 en los
        numerales 1, 2 y 3); por encima, 2 %."""
        small = self._invoice([(self.cement, 12, 100.0)], partner=self.person, post=False)
        self.assertEqual(small.l10n_latam_document_type_id.code, '03')
        self.assertFalse(small.l10n_pe_perception_code, '1 416 ≤ 1 500')
        self.assertIn('Consumidor final', small.l10n_pe_perception_note)
        big = self._invoice([(self.cement, 13, 100.0)], partner=self.person, post=False)
        self.assertEqual(big.l10n_pe_perception_code, '51', '1 534 > 1 500')
        low = self._invoice([(self.beer, 10, 10.0)], partner=self.person, post=False)
        self.assertEqual(low.l10n_pe_perception_code, '51', '118 > 100 en los numerales 1-3')

    def test_fuel_one_percent_and_exclusions(self):
        move = self._invoice([(self.diesel, 100, 10.0)], post=False)
        self.assertEqual(move.l10n_pe_perception_code, '52')
        self.assertAlmostEqual(move.l10n_pe_perception_amount, 11.80, 2)
        self.customer.l10n_pe_is_perception_agent = True
        move.invalidate_recordset()
        move._compute_l10n_pe_perception()
        self.assertFalse(move.l10n_pe_perception_code, 'combustible a otro agente')
        self.customer.l10n_pe_is_perception_agent = False

    def test_company_not_agent(self):
        self.company.l10n_pe_perception_agent = False
        move = self._invoice([(self.cement, 10, 100.0)], post=False)
        self.assertFalse(move.l10n_pe_perception_code)
        self.company.l10n_pe_perception_agent = True

    # ------------------------------------------------------------------
    # XML de la factura
    # ------------------------------------------------------------------
    def test_invoice_xml_charge_and_total(self):
        move = self._invoice([(self.cement, 10, 100.0)])
        tree = etree.fromstring(self.env['account.edi.xml.ubl_pe']._export_invoice(move)[0])
        charge = next(c for c in tree.findall('{*}AllowanceCharge')
                      if c.findtext('{*}AllowanceChargeReasonCode') == '51')
        self.assertEqual(charge.findtext('{*}ChargeIndicator'), 'true')
        self.assertEqual(charge.findtext('{*}MultiplierFactorNumeric'), '0.020')
        self.assertEqual(charge.findtext('{*}Amount'), '23.60')
        self.assertEqual(charge.findtext('{*}BaseAmount'), '1180.00')
        self.assertEqual(charge.find('{*}Amount').get('currencyID'), 'PEN')
        term = next(t for t in tree.findall('{*}PaymentTerms') if t.findtext('{*}ID') == 'Percepcion')
        self.assertEqual(term.findtext('{*}Amount'), '1203.60')
        self.assertEqual(tree.find('{*}InvoiceTypeCode').get('listID'), '2001')

    def test_invoice_xml_without_perception(self):
        move = self._invoice([(self.service, 1, 100.0)])
        tree = etree.fromstring(self.env['account.edi.xml.ubl_pe']._export_invoice(move)[0])
        self.assertFalse([c for c in tree.findall('{*}AllowanceCharge')
                          if c.findtext('{*}AllowanceChargeReasonCode') in ('51', '52', '53')])
        self.assertFalse([t for t in tree.findall('{*}PaymentTerms')
                          if t.findtext('{*}ID') == 'Percepcion'])

    # ------------------------------------------------------------------
    # Comprobante de percepción
    # ------------------------------------------------------------------
    def test_factor(self):
        self.assertEqual(perception_factor(2.0), 0.019608)
        self.assertEqual(perception_factor(0.5), 0.004975)
        self.assertEqual(perception_factor(1.0), 0.009901)

    def _collect(self, invoice, amount):
        """Cobro de la factura más su percepción (sin conciliar el exceso)."""
        payment = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids).create({
                'payment_date': date(2026, 3, 20), 'amount': amount,
                'payment_difference_handling': 'open',
            })._create_payments()
        return payment

    def test_cpe_from_payment(self):
        invoice = self._invoice([(self.cement, 10, 100.0)])
        payment = self._collect(invoice, 1203.60)
        self.assertEqual(invoice.payment_state in ('paid', 'in_payment'), True)
        action = payment.action_l10n_pe_create_perception()
        perception = self.env['l10n_pe.perception'].browse(action['res_id'])
        self.assertEqual(perception.perception_code, '01')
        line = perception.line_ids
        self.assertAlmostEqual(line.paid_amount, 1180.0, 2)
        self.assertAlmostEqual(line.collected_pen, 1203.60, 2)
        self.assertAlmostEqual(line.perception_pen, 23.60, 2, 'factor 0.019608 × 1 203.60')
        perception.action_post()
        self.assertEqual(perception.l10n_pe_edi_perception_number, 'P001-00000001')
        self.assertEqual(perception.state, 'posted')
        self.assertEqual(perception.l10n_pe_edi_status, 'to_send')
        move = perception.move_id
        self.assertEqual(move.state, 'posted')
        credit = move.line_ids.filtered(lambda l: l.account_id == self.perception_account)
        self.assertAlmostEqual(credit.credit, 23.60, 2)
        debit = move.line_ids - credit
        self.assertTrue(debit.reconciled, 'el cargo al cliente se concilia con el exceso del cobro')
        self.assertAlmostEqual(invoice.l10n_pe_perception_collected, 23.60, 2)
        self.assertEqual(payment.l10n_pe_perception_count, 1)

    def _posted_cpe(self):
        invoice = self._invoice([(self.cement, 10, 100.0)])
        self._collect(invoice, 1203.60)
        perception = self.env['l10n_pe.perception'].create({
            'partner_id': self.customer.id, 'company_id': self.company.id,
            'date': date(2026, 3, 20), 'perception_code': '01',
            'line_ids': [Command.create({'invoice_id': invoice.id, 'paid_amount': 1180.0})],
        })
        perception.action_post()
        return perception

    def test_cpe_xml(self):
        perception = self._posted_cpe()
        tree = etree.fromstring(perception._l10n_pe_edi_generate_retention_bstr())
        value = lambda path: tree.xpath(path, namespaces=NS)[0].text
        self.assertEqual(etree.QName(tree).localname, 'Perception')
        self.assertTrue(tree.xpath('//ds:Signature[@Id="placeholder"]', namespaces=NS))
        self.assertEqual(value('/p:Perception/cbc:ID'), 'P001-00000001')
        self.assertEqual(value('//sac:SUNATPerceptionSystemCode'), '01')
        self.assertEqual(value('//sac:SUNATPerceptionPercent'), '2.00')
        self.assertEqual(value('/p:Perception/cbc:TotalInvoiceAmount'), '23.60')
        self.assertEqual(value('/p:Perception/sac:SUNATTotalCashed'), '1203.60')
        self.assertEqual(value('//cac:Payment/cbc:ID'), '1')
        self.assertEqual(value('//cac:Payment/cbc:PaidAmount'), '1180.00')
        self.assertEqual(value('//sac:SUNATPerceptionInformation/sac:SUNATNetTotalCashed'),
                         '1203.60')
        reference = tree.xpath('//sac:SUNATPerceptionDocumentReference/cbc:ID', namespaces=NS)[0]
        self.assertEqual(reference.get('schemeID'), '01')
        self.assertEqual(value('//cac:ReceiverParty/cac:PartyIdentification/cbc:ID'), '20557912879')
        self.assertEqual(perception._l10n_pe_edi_generate_retention_filename(),
                         '20512528458-40-P001-00000001')

    def test_cpe_send_uses_type_40(self):
        perception = self._posted_cpe()
        edi = type(self.env['account.edi.format'])
        result = {'success': True, 'xml_document': b'<signed/>', 'cdr': b'<cdr/>'}
        with patch.object(edi, '_l10n_pe_edi_sign_service_iap', autospec=True,
                          return_value=result) as iap, \
                patch.object(edi, '_l10n_pe_edi_sign_service_sunat_digiflow_common',
                             autospec=True, return_value=result) as direct:
            perception.action_l10n_pe_edi_send_retention()
        self.assertEqual((iap.call_args or direct.call_args).args[-1], '40')
        self.assertEqual(perception.l10n_pe_edi_status, 'sent')
        with self.assertRaises(UserError):
            perception.action_cancel()

    def test_cpe_reversal_summary_type_40(self):
        perception = self._posted_cpe()
        xml = perception._l10n_pe_edi_generate_reversal_bstr(
            {'number': 'RR-20260320-1', 'issue_date': date(2026, 3, 21)})
        tree = etree.fromstring(xml)
        self.assertEqual(tree.xpath('//*[local-name()="DocumentTypeCode"]')[0].text, '40')
        self.assertEqual(tree.xpath('//*[local-name()="DocumentSerialID"]')[0].text, 'P001')
        perception._l10n_pe_edi_after_reversal()
        self.assertEqual(perception.state, 'cancel')
        self.assertEqual(perception.move_id.state, 'cancel')

    def test_second_payment_index(self):
        invoice = self._invoice([(self.cement, 10, 100.0)])
        first = self.env['l10n_pe.perception'].create({
            'partner_id': self.customer.id, 'date': date(2026, 3, 20), 'perception_code': '01',
            'line_ids': [Command.create({'invoice_id': invoice.id, 'paid_amount': 500.0})]})
        first.action_post()
        second = self.env['l10n_pe.perception'].create({
            'partner_id': self.customer.id, 'date': date(2026, 3, 25), 'perception_code': '01',
            'line_ids': [Command.create({'invoice_id': invoice.id, 'paid_amount': 680.0})]})
        second.action_post()
        self.assertEqual(first._l10n_pe_perception_payment_index(invoice), 1)
        self.assertEqual(second._l10n_pe_perception_payment_index(invoice), 2)
        self.assertEqual(second.l10n_pe_edi_perception_number, 'P001-00000002')

    def test_branch_shares_the_ruc_series(self):
        branch = self.env['res.company'].create({'name': 'Sucursal Arequipa',
                                                 'parent_id': self.company.id})
        self.assertTrue(branch.l10n_pe_perception_agent, 'la designación es del RUC')
        self.assertEqual(branch._l10n_pe_perception_sequence(),
                         self.company._l10n_pe_perception_sequence(),
                         'una sola serie P001 por RUC')

    def test_cpe_rate_mismatch_rejected(self):
        invoice = self._invoice([(self.cement, 10, 100.0)])
        perception = self.env['l10n_pe.perception'].create({
            'partner_id': self.customer.id, 'perception_code': '03',
            'line_ids': [Command.create({'invoice_id': invoice.id, 'paid_amount': 1180.0})]})
        with self.assertRaises(UserError):
            perception.action_post()

    def test_cpe_from_invoices_action(self):
        invoice = self._invoice([(self.cement, 10, 100.0)])
        action = self.env['l10n_pe.perception'].with_context(
            active_ids=invoice.ids).action_create_from_invoices()
        perception = self.env['l10n_pe.perception'].browse(action['res_id'])
        self.assertEqual(perception.partner_id, self.customer)
        self.assertAlmostEqual(perception.amount_perception, 23.60, 2)

    def test_cpe_foreign_currency_uses_collection_rate(self):
        usd = self.setup_other_currency('USD', rates=[('2026-03-15', 1 / 3.70),
                                                      ('2026-03-20', 1 / 3.80)])
        invoice = self._invoice([(self.cement, 10, 100.0)], currency=usd)
        perception = self.env['l10n_pe.perception'].create({
            'partner_id': self.customer.id, 'date': date(2026, 3, 20), 'perception_code': '01',
            'line_ids': [Command.create({'invoice_id': invoice.id, 'paid_amount': 1180.0})]})
        line = perception.line_ids
        self.assertAlmostEqual(line.exchange_rate, 3.80, 4)
        self.assertAlmostEqual(line.subject_paid_pen, 4484.0, 2)
        self.assertAlmostEqual(line.collected_pen, 4573.68, 2)
        self.assertAlmostEqual(line.perception_pen, 89.68, 2)

    def test_pdf(self):
        perception = self._posted_cpe()
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_perception.report_perception', perception.ids)[0]
        self.assertIn(b'P001-00000001', html)
        invoice = perception.line_ids.invoice_id
        invoice_html = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_invoice.report_cpe_invoice_a4_main', invoice.ids)[0]
        self.assertIn('Operación sujeta a percepción del IGV'.encode(), invoice_html)

    # ------------------------------------------------------------------
    # Percepciones que nos cobran
    # ------------------------------------------------------------------
    def test_received_from_bill(self):
        expense = self.company_data['default_account_expense']
        purchase_igv = self.env['account.tax'].search([
            ('type_tax_use', '=', 'purchase'), ('amount', '=', 18),
            ('company_id', '=', self.company.id)], limit=1)
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': self.supplier.id,
            'invoice_date': date(2026, 3, 10), 'date': date(2026, 3, 10),
            'l10n_latam_document_number': 'F001-00000077',
            'invoice_line_ids': [Command.create({
                'name': 'Cemento', 'quantity': 1, 'price_unit': 1000.0, 'account_id': expense.id,
                'tax_ids': [Command.set(purchase_igv.ids)]})],
        })
        bill.action_post()
        action = bill.action_l10n_pe_register_perception()
        received = self.env['l10n_pe.perception.received'].browse(action['res_id'])
        self.assertEqual(received.name, 'F001-00000077')
        self.assertAlmostEqual(received.amount, 23.60, 2)
        received.action_post()
        self.assertEqual(received.state, 'posted')
        debit = received.move_id.line_ids.filtered(lambda l: l.account_id == self.received_account)
        self.assertAlmostEqual(debit.debit, 23.60, 2)
        self.assertEqual(bill.l10n_pe_perception_received_line_ids.received_id, received)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.cr.savepoint():
            received.copy()  # mismo documento: único
        received.action_cancel()
        self.assertEqual(received.move_id.state, 'cancel')

    def test_received_import_dua(self):
        aduana = self.env['res.partner'].create({'name': 'SUNAT - Aduanas'})
        received = self.env['l10n_pe.perception.received'].create({
            'partner_id': aduana.id, 'kind': 'import', 'document_kind': 'dua',
            'name': '118-2026-10-012345', 'date': date(2026, 3, 5),
            'line_ids': [Command.create({'reference': 'DAM 118-2026-10-012345',
                                         'base_amount': 50000.0, 'amount': 1750.0})],
        })
        received.action_post()
        self.assertEqual(received.state, 'posted')
        self.assertAlmostEqual(received.move_id.amount_total, 1750.0, 2)
