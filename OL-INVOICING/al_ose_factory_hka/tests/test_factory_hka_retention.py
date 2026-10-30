# -*- coding: utf-8 -*-
from unittest.mock import patch

from lxml import etree

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_factory_hka import FactoryHkaCommon, FakeHkaClient

NS = {'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
      'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
      'sac': 'urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1'}


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestFactoryHkaRetention(FactoryHkaCommon):

    def _sent_cre(self):
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier',
            'partner_id': self.partner_a.id, 'amount': 35.40, 'date': '2026-10-01',
            'journal_id': self.company_data['default_journal_bank'].id,
        })
        # Odoo 20: el número del CRE es el de la línea de retención del pago.
        tax = self.env.company.l10n_pe_retention_tax_id
        payment.write({
            'withholding_line_ids': [Command.create({
                'tax_id': tax.id, 'name': 'R001-00000005', 'base_amount': 1180.0, 'amount': 35.40})],
            'l10n_pe_edi_status': 'sent',
        })
        self.assertEqual(payment.l10n_pe_edi_retention_number, 'R001-00000005')
        return payment

    # ------------------------------------------------------------------
    # Envío del CRE
    # ------------------------------------------------------------------

    def _sign(self, payment):
        """Envía el CRE y devuelve (archivo, credenciales usadas). Odoo 20:
        el envío pasa por l10n_pe.edi.cpe.service."""
        service = type(self.env['l10n_pe.edi.cpe.service'])
        sent = {}

        def send_bill(_self, company, filename, edi_str, cpe_type, sunat_wsdl):
            sent.update(company=company, filename=filename, cpe_type=cpe_type,
                        credentials=company._l10n_pe_edi_get_credentials(sunat_wsdl=sunat_wsdl))
            return {'success': True}

        with patch.object(service, '_send_bill', send_bill):
            payment._l10n_pe_edi_sign_retention('20557912879-20-R001-5', b'<cre/>')
        return sent

    def test_cre_goes_to_factory_hka(self):
        sent = self._sign(self._sent_cre())
        self.assertEqual(sent['company'], self.company)
        self.assertEqual(sent['cpe_type'], '20', 'tipo de documento del CRE')
        self.assertEqual(sent['filename'], '20557912879-20-R001-00000005', 'número en 8 dígitos')
        self.assertEqual(sent['credentials']['wsdl'], self.company.l10n_pe_edi_factory_hka_wsdl_demo)
        self.assertEqual(sent['credentials']['token'].username, '20557912879HKA')

    def test_cre_disabled_goes_to_sunat(self):
        self.company.l10n_pe_edi_factory_hka_retention = False
        credentials = self._sign(self._sent_cre())['credentials']
        self.assertIn('otroscpe', credentials['wsdl'], 'directo a SUNAT por el servicio de otros CPE')

    # ------------------------------------------------------------------
    # Reversión
    # ------------------------------------------------------------------

    def test_reversal_xml(self):
        payment = self._sent_cre()
        values = payment._l10n_pe_edi_reversal_values()
        tree = etree.fromstring(payment._l10n_pe_edi_generate_reversal_bstr(values))
        value = lambda path: tree.xpath(path, namespaces=NS)[0].text
        self.assertEqual(etree.QName(tree).localname, 'SummaryDocuments', 'RR, no VoidedDocuments (error 2308)')
        self.assertRegex(value('/*/cbc:ID'), r'^RR-\d{8}-\d+$', 'el ID va sin RUC (error 2220)')
        self.assertTrue(values['filename'].startswith('20557912879-RR-'), 'el archivo sí lleva el RUC')
        self.assertEqual(value('/*/cbc:ReferenceDate'), '2026-10-01', 'fecha del CRE')
        self.assertEqual(value('//sac:SummaryDocumentsLine/cbc:DocumentTypeCode'), '20')
        self.assertEqual(value('//sac:DocumentSerialID'), 'R001')
        self.assertEqual(value('//sac:DocumentNumberID'), '5')
        self.assertEqual(value('//sac:TotalAmount'), '0.00')
        self.assertEqual(value('//cac:Status/cbc:ConditionCode'), '3', 'estado 3: anulación')

    def test_reversal_flow(self):
        payment = self._sent_cre()
        with self.assertRaises(UserError, msg='el motivo es obligatorio'):
            payment.action_l10n_pe_edi_reverse_retention()

        payment.l10n_pe_edi_reversal_reason = 'Retención mal calculada'
        payment.action_l10n_pe_edi_reverse_retention()
        self.assertRecordValues(payment, [{
            'l10n_pe_edi_status': 'reversing', 'l10n_pe_edi_reversal_ticket': '202610090001',
            'l10n_pe_edi_is_required': False}])

        payment.action_l10n_pe_edi_check_reversal()
        self.assertRecordValues(payment, [{'l10n_pe_edi_status': 'cancelled', 'l10n_pe_edi_reversal_message': False}])
        self.assertEqual([c['operation'] for c in FakeHkaClient.calls], ['sendSummary', 'getStatus'])
        self.assertEqual(FakeHkaClient.calls[0]['args'][0], '%s.zip' % payment.l10n_pe_edi_reversal_filename)

    def test_reversal_retry_keeps_the_number(self):
        payment = self._sent_cre()
        payment.l10n_pe_edi_reversal_reason = 'Duplicado'
        service = type(self.env['l10n_pe.edi.cpe.service'])
        with patch.object(service, '_send_summary', autospec=True,
                          return_value={'error': 'Servicio no disponible', 'blocking_level': 'warning'}):
            payment.action_l10n_pe_edi_reverse_retention()
        first = payment.l10n_pe_edi_reversal_filename
        self.assertEqual(payment.l10n_pe_edi_status, 'sent')
        self.assertIn('Servicio no disponible', payment.l10n_pe_edi_reversal_message)

        payment.action_l10n_pe_edi_reverse_retention()
        self.assertEqual(payment.l10n_pe_edi_reversal_filename, first, 'mismo correlativo en el reintento')
        self.assertEqual(payment.l10n_pe_edi_status, 'reversing')

    def test_reversal_can_be_disabled(self):
        payment = self._sent_cre()
        self.assertTrue(payment.l10n_pe_edi_reversal_available)
        self.company.l10n_pe_edi_factory_hka_reversal = False
        payment.invalidate_recordset(['l10n_pe_edi_reversal_available'])
        self.assertFalse(payment.l10n_pe_edi_reversal_available)
        payment.l10n_pe_edi_reversal_reason = 'Duplicado'
        with self.assertRaises(UserError):
            payment.action_l10n_pe_edi_reverse_retention()

    def test_reversal_goes_to_sunat_when_cre_did(self):
        """CRE enviado directo a SUNAT (función de CRE apagada): la reversión
        también va a SUNAT, aunque la función de reversión siga activa."""
        self.company.l10n_pe_edi_factory_hka_retention = False
        payment = self._sent_cre()
        payment.invalidate_recordset(['l10n_pe_edi_reversal_available'])
        self.assertTrue(payment.l10n_pe_edi_reversal_available)
        payment.l10n_pe_edi_reversal_reason = 'Duplicado'
        service = type(self.env['l10n_pe.edi.cpe.service'])
        used = {}

        def send_summary(_self, company, filename, edi_str, sunat_wsdl):
            used['credentials'] = company._l10n_pe_edi_get_credentials(sunat_wsdl=sunat_wsdl)
            return {'xml_document': b'<x/>', 'cdr_number': '202610110009'}

        with patch.object(service, '_send_summary', send_summary):
            payment.action_l10n_pe_edi_reverse_retention()
        self.assertIn('otroscpe', used['credentials']['wsdl'])
        self.assertFalse(FakeHkaClient.calls, 'nada pasa por HKA')
        self.assertEqual(payment.l10n_pe_edi_reversal_ticket, '202610110009')
