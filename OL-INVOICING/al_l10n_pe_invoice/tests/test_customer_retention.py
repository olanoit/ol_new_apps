# -*- coding: utf-8 -*-
"""Cliente agente de retención: el «Monto neto pendiente de pago» y las
cuotas no incluyen la retención del IGV (R.S. 193-2020/SUNAT, numeral 2.1),
en el XML y en el comprobante impreso, con el mismo reparto."""
from datetime import date

from lxml import etree

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestCustomerRetention(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        if 'is_retention_agent' not in cls.env['res.partner']._fields:
            cls.skipTest(cls, 'requiere l10n_pe_vat_sunat (agente de retención)')
        cls.company = cls.company_data['company']
        cls.company.vat = '20512528458'
        cls.company.partner_id.write({'is_retention_agent': False, 'is_good_taxpayer': False})
        if 'l10n_pe_retention_agent' in cls.company._fields:
            cls.company.l10n_pe_retention_agent = False
        cls.partner_a.write({
            'name': 'CLIENTE AGENTE SAC', 'is_company': True, 'vat': '20557912879',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
            'is_retention_agent': True,
        })
        cls.igv = cls.env['account.tax'].search([
            ('l10n_pe_edi_tax_code', '=', '1000'), ('type_tax_use', '=', 'sale'),
            ('amount', '=', 18), ('company_id', '=', cls.company.id)], limit=1)
        cls.two_dues = cls.env['account.payment.term'].create({
            'name': '30/60 días test', 'line_ids': [
                Command.create({'value': 'percent', 'value_amount': 50, 'nb_days': 30}),
                Command.create({'value': 'percent', 'value_amount': 50, 'nb_days': 60})]})

    def _invoice(self, price=1000.0, currency=None, move_type='out_invoice', **kw):
        vals = {
            'move_type': move_type, 'partner_id': self.partner_a.id,
            'invoice_date': date(2026, 3, 15), 'date': date(2026, 3, 15),
            'invoice_payment_term_id': self.two_dues.id,
            'invoice_line_ids': [Command.create({
                'name': 'Servicio', 'quantity': 1, 'price_unit': price,
                'tax_ids': [Command.set(self.igv.ids)]})],
        }
        if currency:
            vals['currency_id'] = currency.id
        vals.update(kw)
        move = self.env['account.move'].create(vals)
        move.action_post()
        return move

    def _terms(self, move):
        node = {}
        self.env['account.edi.xml.ubl_pe']._add_invoice_payment_terms_nodes(node, {'invoice': move})
        terms = node['cac:PaymentTerms']
        credit = next(t for t in terms if t['cbc:PaymentMeansID']['_text'] == 'Credito')
        cuotas = [float(t['cbc:Amount']['_text']) for t in terms
                  if str(t['cbc:PaymentMeansID']['_text']).startswith('Cuota')]
        return float(credit['cbc:Amount']['_text']), cuotas

    def test_agent_above_minimum(self):
        move = self._invoice()  # 1,180.00: retención 35.40
        self.assertEqual(move._l10n_pe_customer_retention(), 35.40)
        self.assertEqual(move._l10n_pe_report_net_pending(), 1144.60)
        net, cuotas = self._terms(move)
        self.assertEqual(net, 1144.60)
        self.assertEqual(cuotas, [572.30, 572.30])
        self.assertEqual([due['amount'] for due in move.get_data_dues()], cuotas,
                         'el PDF reparte igual que el XML')
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_invoice.report_cpe_invoice_a4_main', move.ids)[0].decode()
        self.assertTrue('1.144,60' in html or '1,144.60' in html, 'neto pendiente en el PDF')

    def test_agent_not_above_minimum(self):
        move = self._invoice(price=500.0)  # 590.00
        self.assertEqual(move._l10n_pe_customer_retention(), 0.0)
        self.assertEqual(self._terms(move)[0], 590.0)

    def test_customer_not_agent(self):
        self.partner_a.is_retention_agent = False
        move = self._invoice()
        self.assertEqual(move._l10n_pe_report_net_pending(), 1180.0)
        self.partner_a.is_retention_agent = True

    def test_foreign_currency(self):
        usd = self.setup_other_currency('USD', rates=[('2026-01-01', 0.25)])  # 1 USD = 4 PEN
        move = self._invoice(price=200.0, currency=usd)  # USD 236 = S/ 944
        self.assertEqual(move._l10n_pe_customer_retention(), 7.08)
        net, cuotas = self._terms(move)
        self.assertEqual(net, 228.92)
        self.assertAlmostEqual(sum(cuotas), 228.92, 2)

    def test_detraction_excludes_retention(self):
        if 'l10n_pe_detraction_applies' not in self.env['account.move']._fields:
            self.skipTest('requiere al_l10n_pe_detraction')
        move = self._invoice()
        move.button_draft()
        move.l10n_pe_edi_operation_type = '1001'
        move.l10n_pe_detraction_percent = 12.0
        move.action_post()
        if not move._l10n_pe_edi_get_spot():
            self.skipTest('sin detracción en la factura de prueba')
        self.assertEqual(move._l10n_pe_customer_retention(), 0.0)

    def test_company_agent_is_not_retained(self):
        self.company.partner_id.is_retention_agent = True
        move = self._invoice()
        self.assertEqual(move._l10n_pe_customer_retention(), 0.0)
        self.company.partner_id.is_retention_agent = False

    def test_credit_note_has_no_retention(self):
        invoice = self._invoice()
        refund = self._invoice(move_type='out_refund', reversed_entry_id=invoice.id)
        self.assertEqual(refund._l10n_pe_customer_retention(), 0.0)

    # ------------------------------------------------------------------
    # Catálogo 53, código 62 «Retención del IGV» en el XML de la factura
    # ------------------------------------------------------------------
    def _retention_charges(self, move):
        xml = self.env['account.edi.xml.ubl_pe']._export_invoice(move)[0]
        tree = etree.fromstring(xml)
        return [charge for charge in tree.findall('{*}AllowanceCharge')
                if charge.findtext('{*}AllowanceChargeReasonCode') == '62']

    def test_xml_retention_code_62(self):
        move = self._invoice()
        charges = self._retention_charges(move)
        self.assertEqual(len(charges), 1)
        charge = charges[0]
        self.assertEqual(charge.findtext('{*}ChargeIndicator'), 'false')
        self.assertEqual(charge.findtext('{*}MultiplierFactorNumeric'), '0.03000')
        self.assertEqual(charge.findtext('{*}Amount'), '35.40')
        self.assertEqual(charge.findtext('{*}BaseAmount'), '1180.00')

    def test_xml_without_retention_has_no_code_62(self):
        self.assertFalse(self._retention_charges(self._invoice(price=500.0)))
        self.partner_a.is_retention_agent = False
        self.assertFalse(self._retention_charges(self._invoice()))
        self.partner_a.is_retention_agent = True
