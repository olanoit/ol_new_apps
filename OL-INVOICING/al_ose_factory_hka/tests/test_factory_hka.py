# -*- coding: utf-8 -*-
import base64
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.l10n_pe_edi.tests.common import TestPeEdiCommon

CDR_OK = (b'<ar:ApplicationResponse xmlns:ar="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2" '
          b'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
          b'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">'
          b'<cac:DocumentResponse><cac:Response><cbc:ResponseCode>0</cbc:ResponseCode>'
          b'<cbc:Description>El comprobante ha sido aceptado</cbc:Description></cac:Response>'
          b'</cac:DocumentResponse></ar:ApplicationResponse>')
SOAP = ('<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"><S:Body>'
        '<ns2:%s xmlns:ns2="http://service.sunat.gob.pe">%s</ns2:%s></S:Body></S:Envelope>')


class FakeResponse:
    def __init__(self, content, status_code=200):
        self.content = content.encode()
        self.status_code = status_code

    def raise_for_status(self):
        return None


class FakeHkaClient:
    """Imita el billService de Factory HKA y guarda cada llamada."""
    calls = []
    cdr = CDR_OK

    def __init__(self, wsdl, wsse, **kwargs):
        self.wsdl, self.username = wsdl, wsse.username
        self.service = self

    def _log(self, operation, *args):
        FakeHkaClient.calls.append({'wsdl': self.wsdl, 'username': self.username,
                                    'operation': operation, 'args': args})

    def _cdr_b64(self, edi_format):
        return base64.b64encode(edi_format._l10n_pe_edi_zip_edi_document([('R-cdr.xml', FakeHkaClient.cdr)])).decode()

    def sendBill(self, filename, content):
        self._log('sendBill', filename)
        edi_format = FakeHkaClient.edi_format
        return FakeResponse(SOAP % ('sendBillResponse', '<applicationResponse>%s</applicationResponse>'
                                    % self._cdr_b64(edi_format), 'sendBillResponse'))

    def sendSummary(self, filename, content):
        self._log('sendSummary', filename, content)
        return FakeResponse(SOAP % ('sendSummaryResponse', '<ticket>202610090001</ticket>', 'sendSummaryResponse'))

    def getStatus(self, ticket):
        self._log('getStatus', ticket)
        return FakeResponse(SOAP % ('getStatusResponse', '<status><statusCode>0</statusCode><content>%s</content></status>'
                                    % self._cdr_b64(FakeHkaClient.edi_format), 'getStatusResponse'))

    def getStatusCdr(self, ruc, doc_type, serie, folio):
        self._log('getStatusCdr', ruc, doc_type, serie, folio)
        return FakeResponse(SOAP % ('getStatusCdrResponse',
                                    '<statusCdr><statusCode>0004</statusCode><statusMessage>CDR existe</statusMessage>'
                                    '<content>%s</content></statusCdr>' % self._cdr_b64(FakeHkaClient.edi_format),
                                    'getStatusCdrResponse'))


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestFactoryHka(TestPeEdiCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.company.write({
            'l10n_pe_edi_provider': 'factory_hka',
            'l10n_pe_edi_factory_hka_username': '20557912879HKA',
            'l10n_pe_edi_factory_hka_password': 'secreto',
            'l10n_pe_edi_factory_hka_wsdl_prod': 'https://ose.example/billService?wsdl',
        })
        FakeHkaClient.edi_format = cls.edi_format

    def setUp(self):
        super().setUp()
        FakeHkaClient.calls = []
        FakeHkaClient.cdr = CDR_OK
        patcher = patch('odoo.addons.l10n_pe_edi.models.account_edi_format.Client', FakeHkaClient)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_provider_available(self):
        selection = dict(self.env['res.company']._fields['l10n_pe_edi_provider']._description_selection(self.env))
        self.assertIn('factory_hka', selection)

    def test_filename_number_with_8_digits(self):
        fn = self.edi_format._l10n_pe_edi_factory_hka_filename
        self.assertEqual(fn('20524531861-01-F001-11'), '20524531861-01-F001-00000011')
        self.assertEqual(fn('20524531861-20-R001-00000005'), '20524531861-20-R001-00000005')
        self.assertEqual(fn('20524531861-RA-20261009-1-X'), '20524531861-RA-20261009-1-X')

    def test_wsdl_by_environment(self):
        self.assertEqual(self.company._l10n_pe_edi_factory_hka_wsdl(),
                         self.company.l10n_pe_edi_factory_hka_wsdl_demo)
        self.company.l10n_pe_edi_test_env = False
        self.assertEqual(self.company._l10n_pe_edi_factory_hka_wsdl(), 'https://ose.example/billService?wsdl')
        # Sin WSDL de producción no se cae al de demostración.
        self.company.l10n_pe_edi_factory_hka_wsdl_prod = False
        res = self.edi_format._l10n_pe_edi_get_factory_hka_credentials(self.company)
        self.assertIn('WSDL de producción', res['error'])

    def test_invoice_sent_through_factory_hka(self):
        move = self._create_invoice(name='F FFI-11')
        move.action_post()
        doc = move.edi_document_ids.filtered(lambda d: d.state == 'to_send')
        move.action_process_edi_web_services(with_commit=False)

        self.assertRecordValues(doc, [{'error': False}])
        self.assertRecordValues(move, [{'edi_state': 'sent'}])
        call = FakeHkaClient.calls[-1]
        self.assertEqual(call['operation'], 'sendBill')
        self.assertEqual(call['wsdl'], self.company.l10n_pe_edi_factory_hka_wsdl_demo)
        self.assertEqual(call['username'], '20557912879HKA')
        self.assertTrue(call['args'][0].endswith('-01-FFFI-00000011.zip'), call['args'][0])

    def test_missing_credentials_keep_document_pending(self):
        self.company.l10n_pe_edi_factory_hka_password = False
        move = self._create_invoice(name='F FFI-12')
        move.action_post()
        doc = move.edi_document_ids.filtered(lambda d: d.state == 'to_send')
        move.action_process_edi_web_services(with_commit=False)

        self.assertIn('Factory HKA', doc.error)
        self.assertRecordValues(move, [{'edi_state': 'to_send'}])
        self.assertFalse(FakeHkaClient.calls)

    def test_cancellation_two_steps(self):
        move = self._create_invoice(name='F FFI-13')
        move.action_post()
        move.action_process_edi_web_services(with_commit=False)

        move.l10n_pe_edi_cancel_reason = 'Error en el importe'
        move.button_cancel_posted_moves()
        move.action_process_edi_web_services(with_commit=False)
        self.assertEqual(move.l10n_pe_edi_cancel_cdr_number, '202610090001')
        move.action_process_edi_web_services(with_commit=False)

        self.assertRecordValues(move, [{'edi_state': 'cancelled'}])
        self.assertEqual([c['operation'] for c in FakeHkaClient.calls], ['sendBill', 'sendSummary', 'getStatus'])

    def test_status_cdr_service(self):
        res = self.edi_format._l10n_pe_edi_get_status_cdr_factory_hka_service(
            self.company, {'serie': 'F001', 'folio': '11'}, '01')
        self.assertEqual(res['code'], '0004')
        self.assertEqual(FakeHkaClient.calls[-1]['args'], (self.company.vat, '01', 'F001', '11'))

    # ------------------------------------------------------------------
    # Boletas: baja por resumen diario
    # ------------------------------------------------------------------

    def _summary_tree(self):
        """XML del resumen enviado con sendSummary (dentro del ZIP)."""
        import io, zipfile
        from lxml import etree
        call = [c for c in FakeHkaClient.calls if c['operation'] == 'sendSummary'][-1]
        with zipfile.ZipFile(io.BytesIO(call['args'][1])) as zf:
            return call['args'][0], etree.fromstring(zf.read(zf.namelist()[0]))

    def _boleta_with_credit_note(self, number):
        boleta = self._create_invoice(name='B BOL-%s' % number,
                                      l10n_latam_document_type_id=self.env.ref('l10n_pe.document_type02').id)
        note = self.env['account.move'].create({
            'name': 'B BNC-%s' % number, 'move_type': 'out_refund', 'ref': 'devolución',
            'partner_id': self.partner_a.id, 'invoice_date': '2017-01-01', 'date': '2017-01-01',
            'currency_id': self.other_currency.id, 'reversed_entry_id': boleta.id,
            'l10n_latam_document_type_id': self.env.ref('l10n_pe.document_type07b').id,
            'l10n_pe_edi_refund_reason': '01',
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id, 'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                'price_unit': 1600.0, 'quantity': 5, 'tax_ids': [(6, 0, self.tax_18.ids)]})],
        })
        (boleta + note).action_post()
        (boleta + note).action_process_edi_web_services(with_commit=False)
        return boleta, note

    def test_boleta_note_cancelled_with_daily_summary(self):
        """La nota de una boleta se da de baja en un resumen diario (RC), no en
        una comunicación de baja (RA). La boleta misma solo se anula con nota de
        crédito, como ya exige l10n_pe_edi."""
        boleta, note = self._boleta_with_credit_note(21)
        self.assertRecordValues(boleta + note, [{'edi_state': 'sent'}, {'edi_state': 'sent'}])
        self.assertTrue(self.edi_format._l10n_pe_edi_factory_hka_goes_in_summary(boleta))
        self.assertTrue(self.edi_format._l10n_pe_edi_factory_hka_goes_in_summary(note))

        note.l10n_pe_edi_cancel_reason = 'Nota emitida por error'
        note.button_cancel_posted_moves()
        note.action_process_edi_web_services(with_commit=False)
        filename, tree = self._summary_tree()
        ns = {'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
              'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
              'sac': 'urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1'}
        value = lambda path: tree.xpath(path, namespaces=ns)[0].text
        self.assertTrue(filename.startswith('%s-RC-20170101-' % self.company.vat), 'RC con la fecha de emisión')
        self.assertEqual(tree.tag.split('}')[1], 'SummaryDocuments', 'no es una comunicación de baja (RA)')
        self.assertEqual(value('/*/cbc:CustomizationID'), '1.1')
        self.assertEqual(value('/*/cbc:ReferenceDate'), '2017-01-01')
        self.assertEqual(value('//sac:SummaryDocumentsLine/cbc:DocumentTypeCode'), '07')
        self.assertEqual(value('//sac:SummaryDocumentsLine/cbc:ID'), 'BBNC-21')
        self.assertEqual(value('//cac:InvoiceDocumentReference/cbc:ID'), 'BBOL-21')
        self.assertEqual(value('//cac:InvoiceDocumentReference/cbc:DocumentTypeCode'), '03')
        self.assertEqual(value('//cac:Status/cbc:ConditionCode'), '3', 'estado 3: anulado')
        self.assertEqual(value('//sac:TotalAmount'), '9440.00')
        self.assertEqual(value('//sac:BillingPayment[cbc:InstructionID="01"]/cbc:PaidAmount'), '8000.00')
        self.assertEqual(value('//cac:TaxTotal[.//cbc:ID="1000"]/cbc:TaxAmount'), '1440.00')
        self.assertTrue(note.l10n_pe_edi_cancel_cdr_number)

        note.action_process_edi_web_services(with_commit=False)
        self.assertRecordValues(note, [{'edi_state': 'cancelled'}])

    def test_boleta_and_factura_cancelled_separately(self):
        edi = self.edi_format
        _boleta, note = self._boleta_with_credit_note(22)
        factura = self._create_invoice(name='F FFI-23')
        FakeHkaClient.calls = []
        res = edi._l10n_pe_edi_cancel_invoices_step_1_factory_hka(self.company, note + factura, 'x', b'<x/>')
        self.assertIn('por separado', res['error'])
        self.assertFalse(FakeHkaClient.calls)

    def test_factura_goes_in_voided_documents(self):
        factura = self._create_invoice(name='F FFI-24')
        self.assertFalse(self.edi_format._l10n_pe_edi_factory_hka_goes_in_summary(factura))

    # ------------------------------------------------------------------
    # Plazo de envío y observaciones del CDR
    # ------------------------------------------------------------------

    def test_late_factura_and_cdr_notes_in_chatter(self):
        FakeHkaClient.cdr = CDR_OK.replace(
            b'</cac:DocumentResponse>',
            b'<cbc:Note>4252 - El dato ingresado como atributo @listName es incorrecto.</cbc:Note></cac:DocumentResponse>')
        move = self._create_invoice(name='F FFI-25')  # emitida el 01/01/2017
        move.action_post()
        move.action_process_edi_web_services(with_commit=False)
        self.assertRecordValues(move, [{'edi_state': 'sent'}])
        bodies = ' '.join(move.message_ids.mapped('body'))
        self.assertIn('fuera de plazo', bodies)
        self.assertIn('observaciones', bodies)
        self.assertIn('4252', bodies)
