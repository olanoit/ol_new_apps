# -*- coding: utf-8 -*-
from unittest.mock import patch

from lxml import etree

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_pe_edi.tests.common import TestPeEdiCommon
from .test_factory_hka import FakeHkaClient

NS = {'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
      'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
      'sac': 'urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1'}


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestFactoryHkaRetention(TestPeEdiCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.company.write({
            'l10n_pe_edi_provider': 'factory_hka',
            'l10n_pe_edi_factory_hka_username': '20557912879HKA',
            'l10n_pe_edi_factory_hka_password': 'secreto',
        })
        FakeHkaClient.edi_format = cls.edi_format

    def setUp(self):
        super().setUp()
        FakeHkaClient.calls = []
        patcher = patch('odoo.addons.l10n_pe_edi.models.account_edi_format.Client', FakeHkaClient)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _sent_cre(self):
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier',
            'partner_id': self.partner_a.id, 'amount': 35.40, 'date': '2026-10-01',
            'journal_id': self.company_data['default_journal_bank'].id,
        })
        payment.write({'l10n_pe_edi_retention_number': 'R001-00000005', 'l10n_pe_edi_status': 'sent'})
        return payment

    # ------------------------------------------------------------------
    # Envío del CRE
    # ------------------------------------------------------------------

    def _sign(self, payment):
        edi = type(self.env['account.edi.format'])
        with patch.object(edi, '_l10n_pe_edi_sign_service_sunat_digiflow_common', autospec=True,
                          return_value={'success': True}) as common:
            payment._l10n_pe_edi_sign_retention(self.edi_format, '20557912879-20-R001-5', b'<cre/>')
        return common.call_args.args

    def test_cre_goes_to_factory_hka(self):
        _self, company, filename, _edi_str, credentials, doc_type = self._sign(self._sent_cre())
        self.assertEqual(company, self.company)
        self.assertEqual(doc_type, '20', 'tipo de documento del CRE')
        self.assertEqual(filename, '20557912879-20-R001-00000005', 'número en 8 dígitos')
        self.assertEqual(credentials['wsdl'], self.company.l10n_pe_edi_factory_hka_wsdl_demo)
        self.assertEqual(credentials['token'].username, '20557912879HKA')

    def test_cre_disabled_goes_to_sunat(self):
        self.company.l10n_pe_edi_factory_hka_retention = False
        credentials = self._sign(self._sent_cre())[4]
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
        edi = type(self.env['account.edi.format'])
        with patch.object(edi, '_l10n_pe_edi_cancel_invoices_step_1_factory_hka', autospec=True,
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
