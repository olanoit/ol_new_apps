# -*- coding: utf-8 -*-
"""Liquidación de compra electrónica: numeración, retenciones, asiento, XML
(anexo 6), envío y reversión simulados (nunca se llama a SUNAT ni a un OSE)."""
from datetime import date, timedelta
from unittest.mock import patch

from lxml import etree

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase

NS = {
    'i': 'urn:oasis:names:specification:ubl:schema:xsd:SelfBilledInvoice-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
    'v': 'urn:sunat:names:specification:ubl:peru:schema:xsd:VoidedDocuments-1',
    'sac': 'urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1',
}
SIGNED = {'success': True, 'xml_document': b'<signed/>', 'cdr': b'<cdr/>'}


@tagged('post_install', '-at_install')
class TestPurchaseSettlement(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        if not (cls.company.vat and len(cls.company.vat) == 11):
            cls.company.vat = '20512528458'
        cls.company.write({
            'l10n_pe_edi_provider': 'sunat',
            'l10n_pe_edi_test_env': True,
            'l10n_pe_lce_send_on_post': False,
        })
        cls.journal = cls.env['account.journal'].search([
            *cls.env['account.journal']._check_company_domain(cls.company),
            ('l10n_pe_lce_journal', '=', True)], limit=1)
        cls.igv = cls.env['account.tax'].search([
            *cls.env['account.tax']._check_company_domain(cls.company),
            ('type_tax_use', '=', 'purchase'), ('l10n_pe_edi_tax_code', '=', '1000'),
            ('amount', '=', 18.0)], limit=1)
        cls.exo = cls.env['account.tax'].search([
            *cls.env['account.tax']._check_company_domain(cls.company),
            ('type_tax_use', '=', 'purchase'), ('l10n_pe_edi_tax_code', '=', '9997')], limit=1)
        cls.account_exp = cls.env['account.account'].with_company(cls.company).search(
            [('account_type', '=', 'expense')], limit=1)
        cls.district = cls.env.ref('l10n_pe.district_pe_150131')
        cls.seller = cls.env['res.partner'].create({
            'name': 'Quispe Mamani Juana',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_DNI').id,
            'vat': '40404040',
            'street': 'Jr. Los Olivos 123, caserío Santa Rosa',
            'country_id': cls.env.ref('base.pe').id,
            'l10n_pe_district': cls.district.id,
            'city_id': cls.district.city_id.id,
            'state_id': cls.district.city_id.state_id.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Café pergamino', 'default_code': 'CAFE-01',
            'supplier_taxes_id': [Command.set(cls.igv.ids)]})
        cls.gold = cls.env['product.product'].create({
            'name': 'Oro en bruto', 'l10n_pe_lce_gold': True,
            'supplier_taxes_id': [Command.set(cls.igv.ids)]})

    def _settlement(self, price=1000.0, product=None, taxes=None, partner=None, **values):
        product = product or self.product
        return self.env['account.move'].create({
            'move_type': 'in_invoice',
            'journal_id': self.journal.id,
            'partner_id': (partner or self.seller).id,
            'invoice_date': fields.Date.context_today(self.env.user),
            'invoice_line_ids': [Command.create({
                'product_id': product.id, 'name': product.name, 'quantity': 10.0,
                'price_unit': price / 10.0, 'account_id': self.account_exp.id,
                'tax_ids': [Command.set((taxes or self.igv).ids)]})],
            **values,
        })

    def _xml(self, move):
        return etree.fromstring(move._l10n_pe_lce_generate_xml())

    def _patched(self, result=SIGNED):
        edi = type(self.env['account.edi.format'])
        return patch.object(edi, '_l10n_pe_edi_sign_service_sunat_digiflow_common',
                            autospec=True, return_value=result)

    # ------------------------------------------------------------------
    # Configuración
    # ------------------------------------------------------------------
    def test_chart_template_loads_taxes_and_journal(self):
        company = self.company
        self.assertTrue(self.journal, 'diario de liquidaciones creado por la plantilla')
        self.assertEqual(self.journal.l10n_pe_lce_serie, 'L001')
        self.assertEqual(company.l10n_pe_lce_igv_tax_id.amount, -18.0)
        self.assertEqual(company.l10n_pe_lce_ir_tax_id.amount, -1.5)
        self.assertEqual(company.l10n_pe_lce_ir_gold_tax_id.amount, -4.0)
        self.assertTrue(company.l10n_pe_lce_ir_tax_id.invoice_repartition_line_ids.account_id.code
                        .startswith('40175'), 'cuenta de retenciones de renta (art. 9, R.S. 234-2005)')

    def test_serie_must_start_with_l(self):
        with self.assertRaises(Exception):
            self.journal.l10n_pe_lce_serie = 'F001'

    # ------------------------------------------------------------------
    # Numeración y tipo de documento
    # ------------------------------------------------------------------
    def test_document_type_and_numbering(self):
        move = self._settlement()
        self.assertTrue(move.l10n_pe_lce_required)
        self.assertEqual(move.l10n_latam_document_type_id.code, '04')
        self.assertFalse(move.l10n_latam_manual_document_number)
        move.action_post()
        serie, folio = move._l10n_pe_lce_serie_folio()
        self.assertEqual(serie, 'L001')
        self.assertTrue(folio.isdigit() and len(folio) == 8)
        self.assertEqual(move.l10n_pe_lce_status, 'to_send')
        self.assertEqual(move._l10n_pe_lce_filename(), '%s-04-L001-%s' % (self.company.vat, folio))
        second = self._settlement()
        second.action_post()
        self.assertEqual(int(second._l10n_pe_lce_serie_folio()[1]), int(folio) + 1)

    def test_normal_bills_do_not_default_to_the_settlement_journal(self):
        bill = self.env['account.move'].create({'move_type': 'in_invoice'})
        self.assertFalse(bill.journal_id.l10n_pe_lce_journal)
        settlement = self.env['account.move'].with_context(l10n_pe_lce_default_journal=True).create(
            {'move_type': 'in_invoice'})
        self.assertTrue(settlement.journal_id.l10n_pe_lce_journal)

    # ------------------------------------------------------------------
    # Retenciones y asiento
    # ------------------------------------------------------------------
    def test_withholdings_and_journal_entry(self):
        move = self._settlement(1000.0)
        move.action_post()
        self.assertAlmostEqual(move.amount_untaxed, 1000.0)
        self.assertAlmostEqual(move.l10n_pe_lce_igv_amount, 180.0)
        self.assertAlmostEqual(move.l10n_pe_lce_ir_amount, 15.0, msg='1,5 % del valor de venta')
        self.assertAlmostEqual(move.l10n_pe_lce_subtotal, 1180.0)
        self.assertAlmostEqual(move.amount_total, 985.0, msg='importe total neto')
        payable = move.line_ids.filtered(lambda line: line.display_type == 'payment_term')
        self.assertAlmostEqual(sum(payable.mapped('credit')), 985.0)
        igv_withheld = move.line_ids.filtered(
            lambda line: line.tax_line_id == self.company.l10n_pe_lce_igv_tax_id)
        self.assertAlmostEqual(igv_withheld.credit, 180.0)
        ir_withheld = move.line_ids.filtered(
            lambda line: line.tax_line_id == self.company.l10n_pe_lce_ir_tax_id)
        self.assertAlmostEqual(ir_withheld.credit, 15.0)
        self.assertTrue(ir_withheld.account_id.code.startswith('40175'))

    def test_no_income_tax_up_to_700(self):
        move = self._settlement(700.0)
        move.action_post()
        self.assertAlmostEqual(move.l10n_pe_lce_ir_amount, 0.0)
        self.assertAlmostEqual(move.amount_total, 700.0)
        above = self._settlement(700.10)
        above.action_post()
        self.assertAlmostEqual(above.l10n_pe_lce_ir_amount, 10.5)

    def test_gold_withholds_four_percent(self):
        move = self._settlement(2000.0, product=self.gold)
        move.action_post()
        self.assertAlmostEqual(move.l10n_pe_lce_ir_amount, 80.0)
        self.assertIn(self.company.l10n_pe_lce_ir_gold_tax_id, move.invoice_line_ids.tax_ids)

    def test_exempt_operation_has_no_income_tax(self):
        move = self._settlement(5000.0, l10n_pe_lce_ir_exempt=True)
        move.action_post()
        self.assertAlmostEqual(move.l10n_pe_lce_ir_amount, 0.0)

    def test_exonerated_line_keeps_igv_out(self):
        if not self.exo:
            self.skipTest('sin impuesto exonerado en el plan')
        move = self._settlement(1000.0, taxes=self.exo)
        move.action_post()
        self.assertAlmostEqual(move.l10n_pe_lce_igv_amount, 0.0)
        self.assertNotIn(self.company.l10n_pe_lce_igv_tax_id, move.invoice_line_ids.tax_ids)
        self.assertAlmostEqual(move.amount_total, 985.0)

    def test_form_onchange_adds_withholdings(self):
        with Form(self.env['account.move'].with_context(
                default_move_type='in_invoice', l10n_pe_lce_default_journal=True)) as form:
            form.partner_id = self.seller
            form.invoice_date = date.today()
            with form.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = 1000.0
        move = form.save()
        self.assertTrue(move.journal_id.l10n_pe_lce_journal)
        self.assertIn(self.company.l10n_pe_lce_igv_tax_id, move.invoice_line_ids.tax_ids)
        self.assertIn(self.company.l10n_pe_lce_ir_tax_id, move.invoice_line_ids.tax_ids)
        self.assertAlmostEqual(move.amount_total, 985.0)

    def test_seller_with_ruc_is_rejected(self):
        company_seller = self.env['res.partner'].create({
            'name': 'Agro SAC', 'vat': '20131312955',
            'l10n_latam_identification_type_id': self.env.ref('l10n_pe.it_RUC').id,
            'street': 'Av. 1', 'l10n_pe_district': self.district.id})
        move = self._settlement(partner=company_seller)
        with self.assertRaisesRegex(UserError, 'persona natural sin RUC'):
            move.action_post()

    def test_place_of_operation_defaults_to_seller_address(self):
        move = self._settlement()
        self.assertEqual(move.l10n_pe_lce_place_district_id, self.district)
        self.assertEqual(move.l10n_pe_lce_place_street, self.seller.street)
        self.assertEqual(move.l10n_pe_lce_place_type, '01')

    def test_place_is_proposed_when_conditions_are_given(self):
        """Con las condiciones en los valores de creación, la dirección y el
        distrito se siguen proponiendo (cálculos separados)."""
        move = self._settlement(l10n_pe_lce_place_type='02', l10n_pe_lce_partner_address_type='03')
        self.assertEqual(move.l10n_pe_lce_place_district_id, self.district)
        self.assertEqual(move.l10n_pe_lce_place_street, self.seller.street)
        self.assertEqual((move.l10n_pe_lce_place_type, move.l10n_pe_lce_partner_address_type),
                         ('02', '03'))
        move.action_post()

    def test_seller_warning_above_75_uit(self):
        uit = self.company._l10n_pe_lce_uit(date.today().year)
        move = self._settlement(75 * uit + 100.0)
        self.assertIn('75 UIT', move.l10n_pe_lce_seller_warning or '')
        small = self._settlement(1000.0, partner=self.seller.copy({'vat': '41414141'}))
        self.assertFalse(small.l10n_pe_lce_seller_warning)

    # ------------------------------------------------------------------
    # XML (anexo 6)
    # ------------------------------------------------------------------
    def test_xml_structure(self):
        move = self._settlement(1000.0, l10n_pe_lce_license_plate='ABC123')
        move.action_post()
        tree = self._xml(move)
        value = lambda path: tree.xpath(path, namespaces=NS)[0].text
        self.assertEqual(etree.QName(tree).localname, 'SelfBilledInvoice')
        self.assertTrue(tree.xpath('//ds:Signature[@Id="placeholder"]', namespaces=NS))
        self.assertEqual(value('/i:SelfBilledInvoice/cbc:UBLVersionID'), '2.1')
        type_code = tree.xpath('/i:SelfBilledInvoice/cbc:InvoiceTypeCode', namespaces=NS)[0]
        self.assertEqual(type_code.text, '04')
        self.assertEqual(type_code.get('listID'), '0501')
        self.assertEqual(value('/i:SelfBilledInvoice/cbc:ID'), move._l10n_pe_lce_number())
        # El comprador (emisor) es AccountingCustomerParty; el vendedor, Supplier.
        children = [etree.QName(child).localname for child in tree]
        self.assertLess(children.index('AccountingCustomerParty'), children.index('AccountingSupplierParty'))
        self.assertLess(children.index('Delivery'), children.index('DeliveryTerms'))
        self.assertLess(children.index('TaxTotal'), children.index('LegalMonetaryTotal'))
        self.assertEqual(value('//cac:AccountingCustomerParty//cbc:ID[@schemeID="6"]'), self.company.vat)
        seller_id = tree.xpath('//cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID',
                               namespaces=NS)[0]
        self.assertEqual((seller_id.text, seller_id.get('schemeID')), ('40404040', '1'))
        self.assertEqual(value('//cac:AccountingSupplierParty//cac:RegistrationAddress/cbc:ID'), '150131')
        self.assertEqual(value('//cac:AccountingSupplierParty//cbc:AddressTypeCode'), '01')
        self.assertEqual(value('//cac:DeliveryTerms/cac:DeliveryLocation/cbc:LocationTypeCode'), '01')
        self.assertEqual(value('//cac:DeliveryTerms//cac:Address/cbc:District'), 'San Isidro')
        self.assertEqual(value('//cac:Delivery/cac:Shipment/cbc:ID'), '02')
        self.assertEqual(value('//cbc:LicensePlateID'), 'ABC123')
        # Totales (anexo 27): neto = sub total - IGV - IR.
        self.assertEqual(value('/i:SelfBilledInvoice/cac:TaxTotal/cbc:TaxAmount'), '180.00')
        self.assertEqual(value('//cac:LegalMonetaryTotal/cbc:LineExtensionAmount'), '1000.00')
        self.assertEqual(value('//cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount'), '1180.00')
        self.assertEqual(value('//cac:LegalMonetaryTotal/cbc:PayableAmount'), '985.00')
        ir_total = tree.xpath('/i:SelfBilledInvoice/cac:TaxTotal/cac:TaxSubtotal'
                              '[cac:TaxCategory/cac:TaxScheme/cbc:ID="3000"]', namespaces=NS)[0]
        self.assertEqual(ir_total.find('cbc:TaxAmount', NS).text, '15.00')
        self.assertEqual(ir_total.find('.//cbc:TaxTypeCode', NS).text, 'TOX')
        line = tree.xpath('//cac:InvoiceLine', namespaces=NS)[0]
        self.assertEqual(line.find('cbc:InvoicedQuantity', NS).text, '10')
        self.assertEqual(line.find('cbc:LineExtensionAmount', NS).text, '1000.00')
        self.assertEqual(line.find('cac:Price/cbc:PriceAmount', NS).text, '100')
        self.assertEqual(line.find('cac:PricingReference//cbc:PriceAmount', NS).text, '118')
        line_ir = line.xpath('cac:TaxTotal/cac:TaxSubtotal[cac:TaxCategory/cac:TaxScheme/cbc:ID="3000"]',
                             namespaces=NS)[0]
        self.assertEqual(line_ir.find('cac:TaxCategory/cbc:Percent', NS).text, '1.50')
        self.assertEqual(line.find('cac:TaxTotal/cbc:TaxAmount', NS).text, '180.00',
                         'los tributos del ítem no incluyen la retención de renta')
        self.assertEqual(line.find('cac:Item/cac:SellersItemIdentification/cbc:ID', NS).text, 'CAFE-01')

    def test_xml_matches_ubl_schema_order(self):
        """Orden de AddressType y de InvoiceLine del esquema OASIS."""
        move = self._settlement()
        move.action_post()
        tree = self._xml(move)
        address = tree.xpath('//cac:AccountingSupplierParty//cac:RegistrationAddress', namespaces=NS)[0]
        self.assertEqual([etree.QName(c).localname for c in address],
                         ['ID', 'AddressTypeCode', 'CityName', 'CountrySubentity', 'District',
                          'AddressLine', 'Country'])
        line = tree.xpath('//cac:InvoiceLine', namespaces=NS)[0]
        self.assertEqual([etree.QName(c).localname for c in line],
                         ['ID', 'InvoicedQuantity', 'LineExtensionAmount', 'PricingReference',
                          'TaxTotal', 'Item', 'Price'])

    # ------------------------------------------------------------------
    # Envío (simulado)
    # ------------------------------------------------------------------
    def test_send_success_with_sunat_invoice_service(self):
        move = self._settlement()
        move.action_post()
        with self._patched() as direct:
            move.action_l10n_pe_lce_send()
        args = direct.call_args.args
        self.assertEqual(args[-1], '04', 'tipo de documento')
        self.assertIn('ol-ti-itcpfegem-beta', args[4]['wsdl'], 'servicio de facturas (anexo 6)')
        self.assertTrue(args[2].endswith('-04-%s' % move._l10n_pe_lce_number()))
        self.assertEqual(move.l10n_pe_lce_status, 'sent')
        self.assertTrue(move.l10n_pe_lce_accepted_date)
        self.assertTrue(move._l10n_pe_lce_xml_attachment())
        with self.assertRaises(UserError, msg='no se reenvía una liquidación aceptada'):
            move.action_l10n_pe_lce_send()
        with self.assertRaises(UserError, msg='aceptada: no vuelve a borrador'):
            move.button_draft()

    def test_send_error_is_shown(self):
        move = self._settlement()
        move.action_post()
        with self._patched({'error': 'Certificado vencido', 'blocking_level': 'error'}):
            move.action_l10n_pe_lce_send()
        self.assertEqual(move.l10n_pe_lce_status, 'to_send')
        self.assertIn('Certificado vencido', move.l10n_pe_lce_message)

    def test_iap_provider_uses_its_service(self):
        self.company.l10n_pe_edi_provider = 'iap'
        move = self._settlement()
        move.action_post()
        edi = type(self.env['account.edi.format'])
        with patch.object(edi, '_l10n_pe_edi_sign_service_iap', autospec=True,
                          return_value=SIGNED) as iap:
            move.action_l10n_pe_lce_send()
        self.assertEqual(iap.call_args.args[-1], '04')
        self.assertEqual(move.l10n_pe_lce_status, 'sent')

    def test_send_on_post(self):
        self.company.l10n_pe_lce_send_on_post = True
        move = self._settlement()
        with self._patched():
            move.action_post()
        self.assertEqual(move.l10n_pe_lce_status, 'sent')

    def test_late_send_is_warned(self):
        move = self._settlement(invoice_date=date.today() - timedelta(days=5))
        move.action_post()
        with self._patched():
            move.action_l10n_pe_lce_send()
        self.assertTrue(any('fuera de plazo' in (message.body or '')
                            for message in move.message_ids))

    # ------------------------------------------------------------------
    # Reversión (resumen diario de reversiones, simulada)
    # ------------------------------------------------------------------
    def _sent(self):
        move = self._settlement()
        move.action_post()
        with self._patched():
            move.action_l10n_pe_lce_send()
        return move

    def test_reversal_summary_xml(self):
        move = self._sent()
        move.l10n_pe_lce_reversal_reason = 'Error en el DNI del vendedor'
        values = move._l10n_pe_lce_reversal_values()
        self.assertTrue(values['number'].startswith('RR-'))
        tree = etree.fromstring(move._l10n_pe_lce_generate_reversal_xml(values))
        value = lambda path: tree.xpath(path, namespaces=NS)[0].text
        self.assertEqual(value('/v:VoidedDocuments/cbc:ID'), values['number'])
        self.assertEqual(value('//sac:VoidedDocumentsLine/cbc:DocumentTypeCode'), '04')
        self.assertEqual(value('//sac:VoidedDocumentsLine/sac:DocumentSerialID'), 'L001')
        self.assertEqual(value('//sac:VoidReasonDescription'), 'Error en el DNI del vendedor')
        self.assertEqual(value('/v:VoidedDocuments/cbc:ReferenceDate'), str(move.invoice_date))
        self.assertEqual(move._l10n_pe_lce_reversal_values()['filename'], values['filename'],
                         'los reintentos reutilizan el correlativo')

    def test_reversal_flow(self):
        move = self._sent()
        number = move.name
        with self.assertRaisesRegex(UserError, 'motivo'):
            move.action_l10n_pe_lce_reverse()
        move.l10n_pe_lce_reversal_reason = 'Error en la cantidad'
        edi = type(self.env['account.edi.format'])
        with patch.object(edi, '_l10n_pe_edi_cancel_invoices_step_1_sunat_digiflow_common',
                          autospec=True, return_value={'xml_document': b'<rr/>', 'cdr': b'',
                                                       'cdr_number': '123456'}) as step_1:
            move.action_l10n_pe_lce_reverse()
        self.assertIn('ol-ti-itemision-otroscpe-gem-beta', step_1.call_args.args[5]['wsdl'],
                      'servicio de retenciones, percepciones y reversiones (anexo 22)')
        self.assertEqual(move.l10n_pe_lce_status, 'reversing')
        self.assertEqual(move.l10n_pe_lce_reversal_ticket, '123456')
        with patch.object(edi, '_l10n_pe_edi_cancel_invoices_step_2_sunat_digiflow_common',
                          autospec=True, return_value={'error': 'En proceso', 'blocking_level': 'info'}):
            move.action_l10n_pe_lce_check_reversal()
        self.assertEqual(move.l10n_pe_lce_status, 'reversing')
        with patch.object(edi, '_l10n_pe_edi_cancel_invoices_step_2_sunat_digiflow_common',
                          autospec=True, return_value={'success': True, 'cdr': b'<cdr/>'}):
            move.action_l10n_pe_lce_check_reversal()
        self.assertEqual(move.l10n_pe_lce_status, 'reversed')
        self.assertEqual(move.state, 'cancel')
        self.assertEqual(move.name, number, 'la liquidación revertida conserva su número')

    def test_rejected_reversal_keeps_the_settlement(self):
        move = self._sent()
        move.l10n_pe_lce_reversal_reason = 'Error en la cantidad'
        edi = type(self.env['account.edi.format'])
        with patch.object(edi, '_l10n_pe_edi_cancel_invoices_step_1_sunat_digiflow_common',
                          autospec=True, return_value={'xml_document': b'<rr/>', 'cdr': b'',
                                                       'cdr_number': '9'}), \
                patch.object(edi, '_l10n_pe_edi_cancel_invoices_step_2_sunat_digiflow_common',
                             autospec=True, return_value={'error': 'Tiene pagos registrados',
                                                          'blocking_level': 'error'}):
            move.action_l10n_pe_lce_reverse()
            move.action_l10n_pe_lce_check_reversal()
        self.assertEqual(move.l10n_pe_lce_status, 'sent')
        self.assertEqual(move.state, 'posted')
        self.assertFalse(move.l10n_pe_lce_reversal_filename, 'un nuevo intento usa otro RR')

    def test_reversal_deadline(self):
        move = self._sent()
        move.write({'l10n_pe_lce_reversal_reason': 'Error en el producto',
                    'l10n_pe_lce_accepted_date': date.today() - timedelta(days=10)})
        with self.assertRaisesRegex(UserError, 'siete días'):
            move.action_l10n_pe_lce_reverse()

    # ------------------------------------------------------------------
    # Representación impresa y registros
    # ------------------------------------------------------------------
    def test_report_renders(self):
        move = self._sent()
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_edi_purchase_settlement.report_purchase_settlement', move.ids)[0].decode()
        for text in ('Liquidación de compra electrónica', move._l10n_pe_lce_number(),
                     'IMPORTE TOTAL NETO', 'IR - Retención', 'IGV - Crédito', 'Quispe Mamani Juana',
                     'San Isidro', 'Punto de venta'):
            self.assertIn(text, html)
        with self.assertRaises(UserError):
            self.env['account.move'].create({'move_type': 'in_invoice'}).action_l10n_pe_lce_print()

    def test_registers_report_the_gross_total(self):
        """RCE (PLE y SIRE): el total del comprobante es el sub total, no el
        neto que recibe el vendedor."""
        move = self._settlement(1000.0)
        move.action_post()
        if 'l10n_pe.rce.extractor' in self.env:
            self.assertAlmostEqual(self.env['l10n_pe.rce.extractor']._rce_total(move), 1180.0)
        if 'l10n_pe.sire.rce' in self.env:
            self.assertAlmostEqual(self.env['l10n_pe.sire.rce']._sire_total(move), 1180.0)
