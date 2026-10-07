# -*- coding: utf-8 -*-
"""Escenarios de anticipos y descuentos contra las reglas de validación de
SUNAT (``sunat_rules``): los mismos E1-E16 del diagnóstico de
docs/anticipos/, ahora con el módulo instalado."""
from decimal import Decimal

from lxml import etree

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged

from .sunat_rules import NS, validar


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestSunatRules(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        company = cls.company_data['company']
        ruc = cls.env.ref('l10n_pe.it_RUC')
        company.partner_id.write({
            'vat': '20557912879', 'l10n_latam_identification_type_id': ruc.id,
            'country_id': cls.env.ref('base.pe').id})
        cls.journal = cls.company_data['default_journal_sale']
        cls.journal.l10n_latam_use_documents = True
        ref = cls.env['account.chart.template'].with_company(company).ref
        cls.igv = ref('sale_tax_igv_18')
        cls.exo = ref('sale_tax_exo')
        cls.ina = ref('sale_tax_ina')
        cls.igv_incl = cls.igv.copy({'name': 'IGV 18% incluido (prueba)', 'price_include_override': 'tax_included'})
        cls.customer = cls.env['res.partner'].create({
            'name': 'Cliente RUC', 'vat': '20100070970', 'l10n_latam_identification_type_id': ruc.id,
            'country_id': cls.env.ref('base.pe').id})
        cls.customer_dni = cls.env['res.partner'].create({
            'name': 'Cliente DNI', 'vat': '46027897',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_DNI').id,
            'country_id': cls.env.ref('base.pe').id})
        Product = cls.env['product.product']
        cls.p_a = Product.create({'name': 'Servicio A', 'type': 'service', 'invoice_policy': 'order',
                                  'taxes_id': [(6, 0, cls.igv.ids)]})
        cls.p_b = Product.create({'name': 'Servicio B', 'type': 'service', 'invoice_policy': 'order',
                                  'taxes_id': [(6, 0, cls.igv.ids)]})
        cls.p_exo = Product.create({'name': 'Servicio exonerado', 'type': 'service', 'invoice_policy': 'order',
                                    'taxes_id': [(6, 0, cls.exo.ids)]})
        cls.p_ina = Product.create({'name': 'Servicio inafecto', 'type': 'service', 'invoice_policy': 'order',
                                    'taxes_id': [(6, 0, cls.ina.ids)]})
        cls.Edi = cls.env['account.edi.xml.ubl_pe']
        # Los anticipos nacen de un pedido de venta.
        cls.env.user.group_ids |= cls.env.ref('sales_team.group_sale_salesman')

    # ------------------------------------------------------------------ ayuda
    def _sale(self, lines, partner=None, currency=None):
        vals = {'partner_id': (partner or self.customer).id, 'journal_id': self.journal.id,
                'order_line': [(0, 0, {'product_id': p.id, 'product_uom_qty': q, 'price_unit': pu,
                                       'discount': d, 'tax_ids': [(6, 0, t.ids)]})
                               for p, q, pu, d, t in lines]}
        if currency:
            vals['pricelist_id'] = self.env['product.pricelist'].create(
                {'name': currency.name, 'currency_id': currency.id}).id
        order = self.env['sale.order'].create(vals)
        order.action_confirm()
        return order

    def _wizard(self, order, method, amount=0.0):
        vals = {'advance_payment_method': method}
        if method == 'percentage':
            vals['amount'] = amount
        elif method == 'fixed':
            vals['fixed_amount'] = amount
        self.env['sale.advance.payment.inv'].with_context(
            active_model='sale.order', active_ids=order.ids, active_id=order.id).create(vals).create_invoices()
        return order.invoice_ids.sorted('id')[-1]

    def _post(self, move, boleta=False):
        if boleta:
            move.l10n_latam_document_type_id = self.env.ref('l10n_pe.document_type02')
        move.action_post()
        return move

    def _invoice(self, lines):
        return self._post(self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.customer.id, 'journal_id': self.journal.id,
            'invoice_line_ids': [(0, 0, {'name': n, 'product_id': p.id if p else False, 'quantity': q,
                                         'price_unit': pu, 'discount': d, 'tax_ids': [(6, 0, t.ids)]})
                                 for n, p, q, pu, d, t in lines]}))

    def _credit_note(self, move):
        wizard = self.env['account.move.reversal'].with_context(
            active_model='account.move', active_ids=move.ids).create({
                'reason': 'Anulación', 'journal_id': move.journal_id.id, 'l10n_pe_edi_refund_reason': '01'})
        return self._post(self.env['account.move'].browse(wizard.refund_moves()['res_id']))

    def _xml(self, move):
        xml, errors = self.Edi._export_invoice(move)
        self.assertFalse(errors, errors)
        return etree.fromstring(xml)

    def assertSunatValid(self, move):
        """Sin incumplimientos de las reglas SUNAT y con el mismo importe a
        pagar que el asiento."""
        root = self._xml(move)
        self.assertEqual(validar(root), [])
        payable = Decimal(root.findtext('cac:LegalMonetaryTotal/cbc:PayableAmount', namespaces=NS))
        self.assertEqual(payable, Decimal(str(move.currency_id.round(move.amount_total))).quantize(payable))
        return root

    def _codes(self, root, path='cac:AllowanceCharge/cbc:AllowanceChargeReasonCode'):
        return sorted(node.text for node in root.findall(path, NS))

    # ------------------------------------------------------- anticipos (nativo)
    def test_e1_one_downpayment(self):
        order = self._sale([(self.p_a, 1, 1000.0, 0, self.igv)])
        self._post(self._wizard(order, 'fixed', 118.0))
        root = self.assertSunatValid(self._post(self._wizard(order, 'delivered')))
        self.assertEqual(self._codes(root), ['04'])

    def test_e2_two_downpayments(self):
        order = self._sale([(self.p_a, 2, 1000.0, 0, self.igv)])
        first = self._post(self._wizard(order, 'percentage', 10))
        self.assertSunatValid(first)
        self._post(self._wizard(order, 'fixed', 236.0))
        root = self.assertSunatValid(self._post(self._wizard(order, 'delivered')))
        self.assertEqual(len(root.findall('cac:PrepaidPayment', NS)), 2)

    def test_e3_downpayment_with_line_discount(self):
        order = self._sale([(self.p_a, 3, 1000.0, 10, self.igv), (self.p_b, 7, 333.33, 0, self.igv)])
        self._post(self._wizard(order, 'percentage', 30))
        root = self.assertSunatValid(self._post(self._wizard(order, 'delivered')))
        self.assertIn('00', self._codes(root, 'cac:InvoiceLine/cac:AllowanceCharge/cbc:AllowanceChargeReasonCode'))

    def test_e5_downpayment_and_global_discount(self):
        order = self._sale([(self.p_a, 1, 1000.0, 0, self.igv)])
        self._post(self._wizard(order, 'fixed', 236.0))
        final = self._wizard(order, 'delivered')
        final.write({'invoice_line_ids': [(0, 0, {'name': 'Descuento global', 'quantity': 1,
                                                   'price_unit': -100.0, 'tax_ids': [(6, 0, self.igv.ids)]})]})
        root = self.assertSunatValid(self._post(final))
        self.assertEqual(self._codes(root), ['02', '04'])

    def test_e6_tax_included_with_cents(self):
        order = self._sale([(self.p_b, 3, 99.99, 0, self.igv_incl), (self.p_a, 1, 1180.0, 0, self.igv_incl)])
        self._post(self._wizard(order, 'percentage', 33))
        self.assertSunatValid(self._post(self._wizard(order, 'delivered')))

    def test_e7_usd(self):
        usd = self.setup_other_currency('USD', rounding=0.01)
        order = self._sale([(self.p_a, 1, 1000.0, 0, self.igv)], currency=usd)
        self._post(self._wizard(order, 'fixed', 118.0))
        final = self._post(self._wizard(order, 'delivered'))
        self.assertEqual(final.currency_id, usd)
        self.assertSunatValid(final)

    def test_e8_boleta(self):
        order = self._sale([(self.p_a, 1, 500.0, 0, self.igv)], partner=self.customer_dni)
        self._post(self._wizard(order, 'fixed', 118.0), boleta=True)
        root = self.assertSunatValid(self._post(self._wizard(order, 'delivered'), boleta=True))
        self.assertEqual(root.findtext('cac:AdditionalDocumentReference/cbc:DocumentTypeCode', namespaces=NS), '03')

    # ------------------------------------------------- anticipos (corregidos)
    def test_e9_mixed_exonerated_downpayment(self):
        """F1/F2: anticipo de una venta gravada + exonerada → 04 y 05, y una
        sola referencia al comprobante de anticipo."""
        order = self._sale([(self.p_a, 1, 1000.0, 0, self.igv), (self.p_exo, 1, 500.0, 0, self.exo)])
        downpayment = self._post(self._wizard(order, 'percentage', 20))
        root = self.assertSunatValid(self._post(self._wizard(order, 'delivered')))
        self.assertEqual(self._codes(root), ['04', '05'])
        references = root.findall('cac:AdditionalDocumentReference', NS)
        self.assertEqual([r.findtext('cbc:ID', namespaces=NS) for r in references], [downpayment.name.replace(' ', '')])
        self.assertEqual(root.findtext('cac:PrepaidPayment/cbc:PaidAmount', namespaces=NS), '336.00')

    def test_e11_mixed_unaffected_downpayment(self):
        order = self._sale([(self.p_a, 1, 1000.0, 0, self.igv), (self.p_ina, 1, 300.0, 0, self.ina)])
        self._post(self._wizard(order, 'percentage', 50))
        root = self.assertSunatValid(self._post(self._wizard(order, 'delivered')))
        self.assertEqual(self._codes(root), ['04', '06'])

    def test_downpayment_document_type_from_downpayment(self):
        """F3: el tipo del anticipo sale del propio comprobante de anticipo."""
        order = self._sale([(self.p_a, 1, 1000.0, 0, self.igv)])
        self._post(self._wizard(order, 'fixed', 118.0))
        root = self.assertSunatValid(self._post(self._wizard(order, 'delivered')))
        self.assertEqual(root.findtext('cac:AdditionalDocumentReference/cbc:DocumentTypeCode', namespaces=NS), '02')

    # -------------------------------------------------------- descuentos
    def test_e4_global_discount_taxed(self):
        root = self.assertSunatValid(self._invoice([
            ('Servicio A', self.p_a, 2, 1000.0, 0, self.igv),
            ('Descuento global', False, 1, -200.0, 0, self.igv)]))
        self.assertEqual(self._codes(root), ['02'])

    def test_e13_global_discount_exonerated(self):
        """F4: el descuento global exonerado pasa al ítem como descuento 00."""
        root = self.assertSunatValid(self._invoice([
            ('Servicio exonerado', self.p_exo, 2, 500.0, 0, self.exo),
            ('Descuento global', False, 1, -100.0, 0, self.exo)]))
        self.assertEqual(self._codes(root), [])
        self.assertEqual(self._codes(root, 'cac:InvoiceLine/cac:AllowanceCharge/cbc:AllowanceChargeReasonCode'), ['00'])
        self.assertEqual(len(root.findall('cac:InvoiceLine', NS)), 1)

    def test_e14_global_discount_mixed(self):
        root = self.assertSunatValid(self._invoice([
            ('Servicio A', self.p_a, 1, 1000.0, 0, self.igv),
            ('Servicio exonerado', self.p_exo, 1, 500.0, 0, self.exo),
            ('Servicio exonerado 2', self.p_exo, 3, 33.33, 0, self.exo),
            ('Descuento gravado', False, 1, -100.0, 0, self.igv),
            ('Descuento exonerado', False, 1, -50.0, 0, self.exo)]))
        self.assertEqual(self._codes(root), ['02'])

    def test_e15_global_discount_tax_included(self):
        self.assertSunatValid(self._invoice([
            ('Servicio B', self.p_b, 3, 33.33, 0, self.igv_incl),
            ('Servicio B', self.p_b, 7, 19.99, 0, self.igv_incl),
            ('Descuento global', False, 1, -10.01, 0, self.igv_incl)]))

    def test_global_discount_exceeding_lines_is_rejected(self):
        # Total positivo (lo gravado lo compensa), pero lo exonerado queda en negativo.
        with self.assertRaisesRegex(UserError, 'superan a las positivas'):
            self._invoice([('Servicio A', self.p_a, 1, 1000.0, 0, self.igv),
                           ('Servicio exonerado', self.p_exo, 1, 100.0, 0, self.exo),
                           ('Descuento global', False, 1, -150.0, 0, self.exo)])

    # -------------------------------------------------- notas de crédito
    def test_e10_credit_note_of_final_invoice(self):
        """F5: la NC de una factura con anticipo se publica y no lleva
        anticipos: la deducción se reparte entre los ítems."""
        order = self._sale([(self.p_a, 1, 1000.0, 0, self.igv)])
        self._post(self._wizard(order, 'fixed', 118.0))
        credit_note = self._credit_note(self._post(self._wizard(order, 'delivered')))
        root = self.assertSunatValid(credit_note)
        self.assertFalse(root.findall('cac:PrepaidPayment', NS))
        self.assertFalse(root.findall('cac:AllowanceCharge', NS))
        self.assertEqual(len(root.findall('cac:CreditNoteLine', NS)), 1)
        self.assertEqual(root.findtext('cac:CreditNoteLine/cbc:LineExtensionAmount', namespaces=NS), '900.00')

    def test_e12_credit_note_of_global_discount(self):
        invoice = self._invoice([('Servicio A', self.p_a, 2, 1000.0, 0, self.igv),
                                 ('Descuento global', False, 1, -200.0, 0, self.igv)])
        root = self.assertSunatValid(self._credit_note(invoice))
        self.assertEqual(root.findtext('cac:CreditNoteLine/cac:Price/cbc:PriceAmount', namespaces=NS), '900.0')

    def test_e16_credit_note_of_line_discount(self):
        """F6: la NC de una factura con descuento de línea informa el precio
        neto."""
        invoice = self._invoice([('Servicio A', self.p_a, 3, 1000.0, 10, self.igv)])
        root = self.assertSunatValid(self._credit_note(invoice))
        self.assertEqual(root.findtext('cac:CreditNoteLine/cac:Price/cbc:PriceAmount', namespaces=NS), '900.0')

    def test_credit_note_mixed_with_downpayment(self):
        order = self._sale([(self.p_a, 2, 1000.0, 5, self.igv), (self.p_exo, 1, 500.0, 0, self.exo)])
        self._post(self._wizard(order, 'percentage', 25))
        self.assertSunatValid(self._credit_note(self._post(self._wizard(order, 'delivered'))))

    def test_accounting_unchanged(self):
        """El asiento de la NC conserva la deducción del anticipo en su cuenta."""
        order = self._sale([(self.p_a, 1, 1000.0, 0, self.igv)])
        self._post(self._wizard(order, 'fixed', 118.0))
        final = self._post(self._wizard(order, 'delivered'))
        credit_note = self._credit_note(final)
        self.assertEqual(len(credit_note.invoice_line_ids), len(final.invoice_line_ids))
        self.assertEqual(credit_note.amount_total, final.amount_total)

    # ------------------------------------------------- auditoría 07/10/2026
    def test_downpayment_with_partial_credit_note_is_cited(self):
        """Anticipo con una NC parcial: sigue citado en el PrepaidPayment.

        Antes el filtro excluía todo anticipo con alguna reversión, el
        importe de la deducción se perdía y SUNAT rechazaba (2509/3220).
        """
        order = self._sale([(self.p_a, 1, 1000.0, 0, self.igv)])
        downpayment = self._post(self._wizard(order, 'fixed', 236.0))
        final = self._post(self._wizard(order, 'delivered'))
        wizard = self.env['account.move.reversal'].with_context(
            active_model='account.move', active_ids=downpayment.ids).create({
                'reason': 'Rebaja', 'journal_id': downpayment.journal_id.id,
                'l10n_pe_edi_refund_reason': '01'})
        refund = self.env['account.move'].browse(wizard.refund_moves()['res_id'])
        refund.invoice_line_ids.price_unit = refund.invoice_line_ids.price_unit / 2
        self._post(refund)
        self.assertTrue(downpayment.reversal_move_ids)
        root = self.assertSunatValid(final)
        references = root.findall('cac:AdditionalDocumentReference', NS)
        self.assertEqual([r.findtext('cbc:ID', namespaces=NS) for r in references],
                         [downpayment.name.replace(' ', '')])

    def test_credit_note_negative_quantity_is_blocked(self):
        move = self._invoice([('Servicio', self.p_a, 1, 100.0, 0, self.igv)])
        refund = self.env['account.move'].create({
            'move_type': 'out_refund', 'partner_id': self.customer.id,
            'journal_id': self.journal.id, 'reversed_entry_id': move.id,
            'l10n_pe_edi_refund_reason': '01',
            'invoice_line_ids': [(0, 0, {'name': 'Devolución', 'product_id': self.p_a.id,
                                         'quantity': -1, 'price_unit': -100.0,
                                         'tax_ids': [(6, 0, self.igv.ids)]})]})
        errors = self.env.ref('l10n_pe_edi.edi_pe_ubl_2_1')._check_move_configuration(refund)
        self.assertTrue(any('cantidades negativas' in str(error) for error in errors))
