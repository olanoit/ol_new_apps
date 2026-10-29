"""Transferencias gratuitas contra las reglas de validación de SUNAT (26.08.2026)."""
from datetime import timedelta
from decimal import Decimal

from lxml import etree

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.al_l10n_pe_edi_downpayment_discount.tests.sunat_rules import NS, validar
from odoo.exceptions import UserError
from odoo.tests import tagged


def free_rule_errors(root):
    """Reglas de las operaciones gratuitas que ``validar`` no revisa."""
    errors = []
    free_lea = Decimal('0')
    free_igv = Decimal('0')
    for line in root.findall('cac:InvoiceLine', NS):
        lid = line.findtext('cbc:ID', namespaces=NS)
        for sub in line.findall('cac:TaxTotal/cac:TaxSubtotal', NS):
            if sub.findtext('cac:TaxCategory/cac:TaxScheme/cbc:ID', namespaces=NS) != '9996':
                continue
            if Decimal(sub.findtext('cbc:TaxableAmount', namespaces=NS)) <= 0:
                continue
            reason = sub.findtext('cac:TaxCategory/cbc:TaxExemptionReasonCode', namespaces=NS)
            tax = Decimal(sub.findtext('cbc:TaxAmount', namespaces=NS))
            if Decimal(line.findtext('cac:Price/cbc:PriceAmount', namespaces=NS)) > 0:
                errors.append(('2640', f'línea {lid}: precio mayor a 0'))
            price_code = line.findtext(
                'cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceTypeCode', namespaces=NS)
            if price_code != '02':
                errors.append(('3234', f'línea {lid}: código de precio {price_code}'))
            if reason in ('11', '12', '13', '14', '15', '16') and tax == 0:
                errors.append(('3111', f'línea {lid}: retiro gravado sin IGV'))
            if reason in ('21', '31', '32', '33', '34', '35', '36', '37') and tax != 0:
                errors.append(('3110', f'línea {lid}: gratuita exonerada/inafecta con IGV'))
            free_lea += Decimal(line.findtext('cbc:LineExtensionAmount', namespaces=NS))
            free_igv += tax
    for sub in root.findall('cac:TaxTotal/cac:TaxSubtotal', NS):
        if sub.findtext('cac:TaxCategory/cac:TaxScheme/cbc:ID', namespaces=NS) != '9996':
            continue
        if abs(Decimal(sub.findtext('cbc:TaxableAmount', namespaces=NS)) - free_lea) > 1:
            errors.append(('3276', 'total gratuito distinto de la suma de los ítems'))
        if abs(Decimal(sub.findtext('cbc:TaxAmount', namespaces=NS)) - free_igv) > 1:
            errors.append(('3302', 'IGV gratuito distinto de la suma de los ítems'))
    legends = [note.get('languageLocaleID') for note in root.findall('cbc:Note', NS)]
    if '1002' in legends and not free_lea:
        errors.append(('2416', 'leyenda 1002 sin operaciones gratuitas'))
    return errors


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestFreeTransfer(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        company = cls.company_data['company']
        company.partner_id.write({
            'vat': '20557912879',
            'country_id': cls.env.ref('base.pe').id})
        cls.journal = cls.company_data['default_journal_sale']
        cls.journal.l10n_latam_use_documents = True
        ref = cls.env['account.chart.template'].with_company(company).ref
        cls.igv = ref('sale_tax_igv_18')
        cls.exo = ref('sale_tax_exo')
        cls.ina = ref('sale_tax_ina')
        cls.gra = ref('sale_tax_gra')
        cls.free_taxed = ref('tax_free_group')
        cls.free_exempt = ref('sale_tax_free_exempt_group')
        cls.customer = cls.env['res.partner'].create({
            'name': 'Cliente RUC', 'vat': '20100070970',
            'country_id': cls.env.ref('base.pe').id})
        Product = cls.env['product.product']
        cls.p_igv = Product.create({'name': 'Polo promocional', 'type': 'consu',
                                    'taxes_id': [(6, 0, cls.igv.ids)]})
        cls.p_exo = Product.create({'name': 'Libro', 'type': 'consu',
                                    'taxes_id': [(6, 0, cls.exo.ids)]})
        cls.p_ina = Product.create({'name': 'Muestra médica', 'type': 'consu',
                                    'taxes_id': [(6, 0, cls.ina.ids)]})
        cls.Edi = cls.env['account.edi.xml.ubl_pe']

    def _invoice(self, lines, **vals):
        return self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.customer.id, 'journal_id': self.journal.id,
            'invoice_date': '2026-10-15',
            'invoice_line_ids': [(0, 0, {'product_id': product.id, 'quantity': qty, 'price_unit': price,
                                         'tax_ids': [(6, 0, taxes.ids)]})
                                 for product, qty, price, taxes in lines],
            **vals})

    def _xml(self, move):
        xml, errors = self.Edi._export_invoice(move)
        self.assertFalse(errors, errors)
        return etree.fromstring(xml)

    def assertSunatValid(self, move):
        root = self._xml(move)
        self.assertEqual(validar(root) + free_rule_errors(root), [])
        payable = Decimal(root.findtext('cac:LegalMonetaryTotal/cbc:PayableAmount', namespaces=NS))
        self.assertEqual(payable, Decimal(str(move.currency_id.round(move.amount_total))).quantize(payable))
        return root

    def _payment_means(self, root):
        return [term.findtext('cbc:PaymentMeansID', namespaces=NS)
                for term in root.findall('cac:PaymentTerms', NS)
                if term.findtext('cbc:ID', namespaces=NS) == 'FormaPago']

    # ------------------------------------------------------------------
    # Impuestos
    # ------------------------------------------------------------------

    def test_exempt_group_leaves_the_item_at_zero(self):
        move = self._invoice([(self.p_ina, 2, 50.0, self.free_exempt)])
        line = move.invoice_line_ids
        self.assertEqual(line.l10n_pe_edi_affectation_reason, '37')
        self.assertEqual(line.price_subtotal, 100.0, 'el valor referencial se ve en la línea')
        self.assertEqual(move.amount_total, 0.0, 'no se cobra')
        move.action_post()
        self.assertEqual(move.l10n_pe_edi_legend, '1002')
        root = self.assertSunatValid(move)
        reference = root.findtext(
            'cac:InvoiceLine/cac:PricingReference/cac:AlternativeConditionPrice/cbc:PriceAmount',
            namespaces=NS)
        self.assertEqual(Decimal(reference), Decimal('50'), 'valor referencial unitario')
        self.assertEqual(self._payment_means(root), ['Contado'])

    def test_taxed_withdrawal_carries_igv(self):
        move = self._invoice([(self.p_igv, 1, 100.0, self.free_taxed)])
        self.assertEqual(move.invoice_line_ids.l10n_pe_edi_affectation_reason, '11')
        move.action_post()
        self.assertEqual(move.amount_total, 0.0)
        root = self.assertSunatValid(move)
        free = [sub for sub in root.findall('cac:TaxTotal/cac:TaxSubtotal', NS)
                if sub.findtext('cac:TaxCategory/cac:TaxScheme/cbc:ID', namespaces=NS) == '9996']
        self.assertEqual(free[0].findtext('cbc:TaxAmount', namespaces=NS), '18.00')

    def test_reason_37_is_free_in_the_xml(self):
        from odoo.addons.l10n_pe_edi.models.account_edi_xml_ubl_pe import FREE_AFFECTATION_REASONS
        self.assertIn('37', FREE_AFFECTATION_REASONS)

    # ------------------------------------------------------------------
    # Botón y factura mixta
    # ------------------------------------------------------------------

    def test_button_converts_the_whole_invoice(self):
        term = self.env['account.payment.term'].create({
            'name': '30 días', 'line_ids': [(0, 0, {'value': 'percent', 'value_amount': 100,
                                                    'nb_days': 30})]})
        move = self._invoice([
            (self.p_igv, 1, 100.0, self.igv),
            (self.p_exo, 1, 40.0, self.exo),
            (self.p_ina, 3, 10.0, self.ina),
        ], invoice_payment_term_id=term.id)
        move.action_l10n_pe_free_transfer()
        reasons = move.invoice_line_ids.mapped('l10n_pe_edi_affectation_reason')
        self.assertEqual(reasons, ['11', '21', '37'])
        self.assertEqual(move.invoice_line_ids.mapped('price_unit'), [100.0, 40.0, 10.0])
        self.assertEqual(move.amount_total, 0.0)
        move.action_post()
        self.assertFalse(move.invoice_payment_term_id)
        self.assertEqual(move.invoice_date_due, move.invoice_date)
        root = self.assertSunatValid(move)
        self.assertEqual(self._payment_means(root), ['Contado'])

    def test_paid_and_free_items(self):
        """Venta con bonificación inafecta: se cobra solo lo pagado."""
        move = self._invoice([
            (self.p_igv, 2, 50.0, self.igv),
            (self.p_ina, 1, 30.0, self.free_exempt),
        ])
        move.action_post()
        self.assertEqual(move.amount_total, 118.0)
        self.assertEqual(move.l10n_pe_edi_legend, '1002')
        self.assertSunatValid(move)

    def test_credit_term_survives_on_paid_invoices(self):
        """Con algo que cobrar, el plazo y el crédito se respetan."""
        term = self.env['account.payment.term'].create({
            'name': '15 días', 'line_ids': [(0, 0, {'value': 'percent', 'value_amount': 100,
                                                    'nb_days': 15})]})
        move = self._invoice([
            (self.p_igv, 1, 100.0, self.igv),
            (self.p_ina, 1, 30.0, self.free_exempt),
        ], invoice_payment_term_id=term.id)
        move.action_post()
        self.assertEqual(move.invoice_payment_term_id, term)
        self.assertEqual(move.invoice_date_due - move.invoice_date, timedelta(days=15))
        self.assertEqual(self._payment_means(self._xml(move))[0], 'Credito')

    # ------------------------------------------------------------------
    # Validaciones al publicar
    # ------------------------------------------------------------------

    def test_zero_reference_value_is_blocked(self):
        move = self._invoice([(self.p_ina, 1, 0.0, self.free_exempt)])
        with self.assertRaisesRegex(UserError, '2641'):
            move.action_post()

    def test_plain_free_tax_is_charged_and_blocked(self):
        move = self._invoice([(self.p_ina, 1, 30.0, self.gra)])
        move.invoice_line_ids.l10n_pe_edi_affectation_reason = '37'
        with self.assertRaisesRegex(UserError, 'se está cobrando'):
            move.action_post()

    def test_taxed_reason_without_igv_is_blocked(self):
        move = self._invoice([(self.p_ina, 1, 30.0, self.free_exempt)])
        move.invoice_line_ids.l10n_pe_edi_affectation_reason = '15'
        with self.assertRaisesRegex(UserError, '3111'):
            move.action_post()

    def test_exempt_reason_with_igv_is_blocked(self):
        move = self._invoice([(self.p_igv, 1, 30.0, self.free_taxed)])
        move.invoice_line_ids.l10n_pe_edi_affectation_reason = '31'
        with self.assertRaisesRegex(UserError, '3110'):
            move.action_post()

    def test_legend_follows_the_free_items(self):
        paid = self._invoice([(self.p_igv, 1, 100.0, self.igv)], l10n_pe_edi_legend='1002')
        paid.action_post()
        self.assertFalse(paid.l10n_pe_edi_legend, 'sin gratuitas no va la 1002 (2416)')
        other = self._invoice([(self.p_ina, 1, 30.0, self.free_exempt)], l10n_pe_edi_legend='2000')
        with self.assertRaisesRegex(UserError, '1002'):
            other.action_post()

    def test_button_only_on_drafts(self):
        move = self._invoice([(self.p_igv, 1, 100.0, self.igv)])
        move.action_post()
        with self.assertRaises(UserError):
            move.action_l10n_pe_free_transfer()
