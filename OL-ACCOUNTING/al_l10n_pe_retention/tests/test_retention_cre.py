# -*- coding: utf-8 -*-
"""Comprobante de Retención Electrónico (auditoría del 07/10/2026).

Contrastado con el módulo oficial de Odoo ``l10n_pe_edi_withholding``
(Enterprise 19.4): el XML anterior usaba ``cbc:TotalPaid`` (SUNAT pide
``sac:SUNATTotalPaid``, el neto pagado), no llevaba el hueco de la firma ni
``cac:Signature``, ni ``Payment/cbc:ID``, y tomaba el RUC del contacto. El CRE
tampoco se firmaba ni se enviaba.
"""
from unittest.mock import patch

from lxml import etree

from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_retention import TestRetentionApplies

NS = {
    'r': 'urn:sunat:names:specification:ubl:peru:schema:xsd:Retention-1',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'sac': 'urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1',
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
}


@tagged('post_install', '-at_install')
class TestRetentionCre(TestRetentionApplies):

    def _paid(self, partner=None):
        self._setup_retention_tax()
        bill = self._bill(1000.0, partner=partner)
        bill.action_post()
        return self._register_payment(bill)._create_payments()

    def _tree(self, payment):
        return etree.fromstring(payment._l10n_pe_edi_generate_retention_bstr())

    def test_structure_like_sunat(self):
        payment = self._paid()
        tree = self._tree(payment)
        value = lambda path: tree.xpath(path, namespaces=NS)[0].text
        self.assertTrue(tree.xpath('//ds:Signature[@Id="placeholder"]', namespaces=NS),
                        'hueco de la firma para el servicio de firma')
        self.assertEqual(value('/r:Retention/cac:Signature/cbc:ID'), 'IDSignKG')
        self.assertEqual(value('/r:Retention/cbc:TotalInvoiceAmount'), '35.40')
        self.assertEqual(value('/r:Retention/sac:SUNATTotalPaid'), '1144.60',
                         'importe pagado neto de retención')
        self.assertFalse(tree.xpath('//cbc:TotalPaid', namespaces=NS))
        self.assertEqual(value('//sac:SUNATRetentionPercent'), '3.00')
        self.assertEqual(value('//cac:Payment/cbc:ID'), '1')
        self.assertEqual(value('//sac:SUNATRetentionDocumentReference/cbc:ID'), 'F00R-00000001')
        self.assertEqual(value('//cac:ReceiverParty/cac:PartyLegalEntity/cbc:RegistrationName'),
                         'Proveedor Retención SAC')

    def test_receiver_is_the_commercial_partner(self):
        contact = self.env['res.partner'].create({
            'name': 'Contacto pagos', 'parent_id': self.partner.id})
        payment = self._paid(partner=contact)
        tree = self._tree(payment)
        self.assertEqual(tree.xpath('//cac:ReceiverParty/cac:PartyIdentification/cbc:ID',
                                    namespaces=NS)[0].text, '20131312955')

    def test_send_success_stores_zip(self):
        payment = self._paid()
        edi = type(self.env['account.edi.format'])
        result = {'success': True, 'xml_document': b'<signed/>', 'cdr': b'<cdr/>'}
        with patch.object(edi, '_l10n_pe_edi_sign_service_iap', autospec=True,
                          return_value=result) as iap, \
                patch.object(edi, '_l10n_pe_edi_sign_service_sunat_digiflow_common',
                             autospec=True, return_value=result) as direct:
            payment.action_l10n_pe_edi_send_retention()
        sent_type = (iap.call_args or direct.call_args).args[-1]
        self.assertEqual(sent_type, '20', 'tipo de documento del CRE')
        self.assertEqual(payment.l10n_pe_edi_status, 'sent')
        self.assertTrue(payment.l10n_pe_edi_attachment_file)
        self.assertFalse(payment.l10n_pe_edi_is_required)
        with self.assertRaises(UserError, msg='no se reenvía un CRE aceptado'):
            payment.action_l10n_pe_edi_send_retention()

    def test_send_error_is_shown(self):
        payment = self._paid()
        edi = type(self.env['account.edi.format'])
        result = {'error': 'Certificado vencido'}
        with patch.object(edi, '_l10n_pe_edi_sign_service_iap', autospec=True,
                          return_value=result), \
                patch.object(edi, '_l10n_pe_edi_sign_service_sunat_digiflow_common',
                             autospec=True, return_value=result):
            payment.action_l10n_pe_edi_send_retention()
        self.assertEqual(payment.l10n_pe_edi_status, 'to_send')
        self.assertIn('Certificado vencido', payment.l10n_pe_edi_error_message)
        self.assertTrue(payment.l10n_pe_edi_is_required, 'se puede reintentar')

    def test_sunat_direct_uses_the_retention_service(self):
        payment = self._paid()
        self.company.l10n_pe_edi_provider = 'sunat'
        self.company.l10n_pe_edi_test_env = True
        edi = type(self.env['account.edi.format'])
        with patch.object(edi, '_l10n_pe_edi_sign_service_sunat_digiflow_common',
                          autospec=True, return_value={'error': 'x'}) as direct:
            payment.action_l10n_pe_edi_send_retention()
        credentials = direct.call_args.args[4]
        self.assertIn('ol-ti-itemision-otroscpe-gem-beta', credentials['wsdl'])

    def test_official_interface(self):
        """Misma interfaz que l10n_pe_edi_withholding (Enterprise 19.4/20)."""
        payment = self._paid()
        self.assertEqual(payment.l10n_pe_edi_status, 'to_send')
        self.assertTrue(payment.l10n_pe_edi_is_required)
        entry, = payment._l10n_pe_edi_get_retention_breakdown()
        self.assertEqual(set(entry), {'bill', 'bill_paid_currency', 'bill_paid_pen',
                                      'bill_retention_pen', 'net_total_paid_pen',
                                      'exchange_rate'})
        self.assertAlmostEqual(entry['bill_retention_pen'], 35.40, 2)
        self.assertEqual(payment._l10n_pe_edi_generate_retention_filename(),
                         '%s-20-%s' % (self.company.vat, payment.l10n_pe_edi_retention_number))
        self.assertIn('account.edi.xml.ubl_pe_withholding', self.env)

    def test_chart_template_creates_the_official_tax(self):
        company = self.env['res.company'].create({
            'name': 'Retenciones plantilla SAC', 'country_id': self.env.ref('base.pe').id,
            'currency_id': self.env.ref('base.PEN').id})
        self.env['account.chart.template'].try_loading('pe', company=company, install_demo=False)
        tax = self.env.ref('account.%s_purchase_tax_withholding_3' % company.id)
        self.assertEqual(company.l10n_pe_retention_tax_id, tax)
        self.assertTrue(tax.is_withholding_tax_on_payment)
        self.assertEqual(tax.amount, -3)
        self.assertEqual(tax.withholding_sequence_id,
                         self.env.ref('account.%s_l10n_pe_edi_withholding_sunat_sequence' % company.id))
        self.assertEqual(tax.invoice_repartition_line_ids.filtered(
            lambda l: l.repartition_type == 'tax').account_id.with_company(company).code[:5], '40114')

    def test_hook_binds_the_configured_tax(self):
        """Un impuesto ya configurado recibe el xmlid oficial: no se duplica."""
        from odoo.addons.al_l10n_pe_retention.hooks import _l10n_pe_retention_load_template
        tax, dummy = self._setup_retention_tax()
        self.company.chart_template = 'pe'
        self.env['ir.model.data'].search([
            ('module', '=', 'account'),
            ('name', '=', '%s_purchase_tax_withholding_3' % self.company.id)]).unlink()
        _l10n_pe_retention_load_template(self.env)
        self.assertEqual(self.env.ref('account.%s_purchase_tax_withholding_3' % self.company.id), tax)
        self.assertEqual(self.company.l10n_pe_retention_tax_id, tax)

    # ------------------------------------------------------------------
    # Norma (docs/retencion/INVESTIGACION_APPS_Y_NORMA.md)
    # ------------------------------------------------------------------
    def test_small_bills_paid_together_are_retained(self):
        """Dos facturas de S/ 472 pagadas juntas suman S/ 944 > 700: se retiene."""
        tax, dummy = self._setup_retention_tax()
        bills = self._bill(400.0) | self._bill(400.0)
        bills.action_post()
        self.assertFalse(any(bills.mapped('l10n_pe_retention_applies')))
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=bills.ids).create({'group_payment': True})
        line = wizard.withholding_line_ids.filtered(lambda l: l.tax_id == tax)
        self.assertAlmostEqual(line.amount, 28.32, 2)

    def test_perception_agent_is_excluded(self):
        self.partner.l10n_pe_is_perception_agent = True
        self.assertFalse(self._bill(1000.0).l10n_pe_retention_eligible)

    def test_purchase_settlement_is_excluded(self):
        """La liquidación de compra (04) no va en el CRE."""
        bill = self._bill(1000.0)
        bill.l10n_latam_document_type_id = self.env.ref('l10n_pe.document_type04', raise_if_not_found=False) \
            or self.env['l10n_latam.document.type'].search([('code', '=', '04'),
                                                             ('country_id.code', '=', 'PE')], limit=1)
        if bill.l10n_latam_document_type_id.code != '04':
            self.skipTest('sin tipo de documento 04')
        self.assertFalse(bill.l10n_pe_retention_eligible)

    def test_send_deadline(self):
        """R.S. 274-2015: 7 días calendario para enviar el CRE."""
        from datetime import timedelta
        payment = self._paid()
        self.assertEqual(payment.l10n_pe_edi_deadline, payment.date + timedelta(days=7))
        overdue = payment.date + timedelta(days=8)
        with patch('odoo.fields.Date.context_today', return_value=overdue):
            payment.invalidate_recordset(['l10n_pe_edi_overdue'])
            self.assertTrue(payment.l10n_pe_edi_overdue)
            self.assertIn(payment, self.env['account.payment'].search(
                [('l10n_pe_edi_overdue', '=', True)]))

    def test_printed_representation(self):
        payment = self._paid()
        html = self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_retention.report_retention', payment.ids)[0].decode()
        # el encabezado común lo pasa a mayúsculas por CSS
        self.assertIn('comprobante de retención electrónico', html.lower())
        self.assertIn(payment.l10n_pe_edi_retention_number, html)
        self.assertIn('F00R-00000001', html)
        self.assertIn('35.40', html.replace(',', '.'))


# Los tests heredados ya corren en su propia clase.
for _name in dir(TestRetentionApplies):
    if _name.startswith('test_') and _name not in TestRetentionCre.__dict__:
        setattr(TestRetentionCre, _name, None)
