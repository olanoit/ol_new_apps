# -*- coding: utf-8 -*-
"""Mejoras 4 a 6 del análisis de retenciones v16 (docs/md/analisis_retenciones_v16.md).

4. Reversión del CRE (resumen RR, R.S. 274-2015/SUNAT) con todos los
   operadores de ``l10n_pe_edi``: SUNAT directo, IAP y Digiflow.
5. CRE sin pago de Odoo (letras, compensaciones, pagos fuera de Odoo).
6. Retención de notas de crédito descontada en el siguiente CRE al mismo
   proveedor (art. 2 de la R.S. 037-2002/SUNAT).
"""
from unittest.mock import patch

from lxml import etree

from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_retention import TestRetentionApplies
from .test_retention_cre import NS


@tagged('post_install', '-at_install')
class TestRetentionV16Improvements(TestRetentionApplies):

    def _paid(self, price=1000.0):
        self._setup_retention_tax()
        bill = self._bill(price)
        bill.action_post()
        return self._register_payment(bill)._create_payments()

    # ------------------------------------------------------------------
    # 4. Reversión con todos los operadores
    # ------------------------------------------------------------------
    def _reverse(self, document, provider):
        """Envía y consulta la reversión con los servicios de baja de
        ``l10n_pe_edi`` simulados. Devuelve lo que recibieron."""
        self.company.l10n_pe_edi_provider = provider
        document.invalidate_recordset(['l10n_pe_edi_reversal_available'])
        document.write({'l10n_pe_edi_status': 'sent', 'l10n_pe_edi_reversal_reason': 'Duplicado'})
        edi = type(self.env['account.edi.format'])
        calls = {}

        def step_1(_self, company, invoices, filename, edi_str, *args):
            calls.update(filename=filename, xml=edi_str, credentials=args and args[0])
            return {'xml_document': edi_str, 'cdr_number': '202610110001'}

        def step_2(_self, company, edi_values, cdr_number, *args):
            calls['ticket'] = cdr_number
            return {'success': True, 'cdr': b'<ApplicationResponse/>'}

        suffix = 'iap' if provider == 'iap' else 'sunat_digiflow_common'
        with patch.object(edi, '_l10n_pe_edi_cancel_invoices_step_1_%s' % suffix, step_1), \
                patch.object(edi, '_l10n_pe_edi_cancel_invoices_step_2_%s' % suffix, step_2), \
                patch.object(edi, '_l10n_pe_edi_get_sunat_credentials', lambda s, c: {'wsdl': 'x'}), \
                patch.object(edi, '_l10n_pe_edi_get_digiflow_credentials',
                             lambda s, c: {'wsdl': 'digiflow'}):
            document.action_l10n_pe_edi_reverse_retention()
            self.assertEqual(document.l10n_pe_edi_status, 'reversing')
            document.action_l10n_pe_edi_check_reversal()
        self.assertEqual(document.l10n_pe_edi_status, 'cancelled')
        return calls

    def test_reversal_sunat_direct(self):
        payment = self._paid()
        calls = self._reverse(payment, 'sunat')
        self.assertTrue(calls['filename'].startswith('%s-RR-' % self.company.vat))
        self.assertIn('otroscpe', calls['credentials']['wsdl'], 'servicio de retenciones de SUNAT')
        self.assertEqual(calls['ticket'], '202610110001')
        tree = etree.fromstring(calls['xml'])
        self.assertEqual(etree.QName(tree).localname, 'SummaryDocuments')

    def test_reversal_iap_and_digiflow(self):
        for provider in ('iap', 'digiflow'):
            with self.subTest(provider=provider):
                payment = self._paid()
                calls = self._reverse(payment, provider)
                self.assertEqual(calls['ticket'], '202610110001')
                if provider == 'digiflow':
                    self.assertEqual(calls['credentials']['wsdl'], 'digiflow')

    def test_reversal_still_processing(self):
        payment = self._paid()
        self.company.l10n_pe_edi_provider = 'sunat'
        payment.write({'l10n_pe_edi_status': 'reversing',
                       'l10n_pe_edi_reversal_ticket': '202610110002'})
        edi = type(self.env['account.edi.format'])
        with patch.object(edi, '_l10n_pe_edi_cancel_invoices_step_2_sunat_digiflow_common',
                          lambda *a: {'error': 'En proceso (98)', 'blocking_level': 'info'}), \
                patch.object(edi, '_l10n_pe_edi_get_sunat_credentials', lambda s, c: {}):
            payment.action_l10n_pe_edi_check_reversal()
        self.assertEqual(payment.l10n_pe_edi_status, 'reversing', 'se vuelve a consultar')

    def test_accepted_cre_locks_the_payment(self):
        payment = self._paid()
        payment.l10n_pe_edi_status = 'sent'
        with self.assertRaises(UserError):
            payment.action_draft()
        with self.assertRaises(UserError):
            payment.action_cancel()

    def test_reversed_payment_gets_a_new_number(self):
        payment = self._paid()
        number = payment.l10n_pe_edi_retention_number
        self._reverse(payment, 'sunat')
        payment.action_draft()
        self.assertFalse(payment.l10n_pe_edi_status)
        payment.action_post()
        self.assertTrue(payment.l10n_pe_edi_retention_number)
        self.assertNotEqual(payment.l10n_pe_edi_retention_number, number, 'número nuevo')
        self.assertEqual(payment.l10n_pe_edi_status, 'to_send')

    # ------------------------------------------------------------------
    # 5. CRE sin pago de Odoo
    # ------------------------------------------------------------------
    def _document(self, bills, paid=None, **values):
        general = self.env['account.journal'].search([
            ('company_id', '=', self.company.id), ('type', '=', 'general')], limit=1)
        return self.env['l10n_pe.retention.document'].create({
            'partner_id': self.partner.id,
            'date': '2025-06-20',
            'journal_id': general.id,
            'origin': 'letter',
            'reference': 'LT-0001',
            'line_ids': [(0, 0, {'bill_id': bill.id,
                                 'paid_amount': paid if paid is not None else bill.amount_total})
                         for bill in bills],
            **values,
        })

    def test_document_post_entry_and_xml(self):
        tax, account = self._setup_retention_tax()
        bill = self._bill(1000.0)
        bill.action_post()
        document = self._document(bill)
        self.assertEqual(document.amount_retention, 35.40)
        document.action_post()
        self.assertEqual(document.state, 'posted')
        self.assertEqual(document.l10n_pe_edi_status, 'to_send')
        self.assertTrue(document.l10n_pe_edi_retention_number.startswith('R001-'))
        move = document.move_id
        self.assertEqual(move.state, 'posted')
        retention_line = move.line_ids.filtered(lambda l: l.account_id == account)
        self.assertEqual(retention_line.credit, 35.40)
        self.assertEqual(bill.amount_residual, 1180.0 - 35.40, 'la retención rebaja la factura')
        tree = etree.fromstring(document._l10n_pe_edi_generate_retention_bstr())
        value = lambda path: tree.xpath(path, namespaces=NS)[0].text
        self.assertEqual(value('/r:Retention/cbc:TotalInvoiceAmount'), '35.40')
        self.assertEqual(value('/r:Retention/sac:SUNATTotalPaid'), '1144.60')
        self.assertEqual(value('//cbc:Note'), 'Referencia: LT-0001')
        self.assertEqual(value('//cac:Payment/cbc:ID'), '1')
        # informado en el resumen 626
        wizard = self.env['l10n_pe.retention.summary.wizard'].create({
            'company_id': self.company.id, 'year': 2025, 'month': '06'})
        wizard.action_export()
        self.assertAlmostEqual(wizard.retention_total, 35.40, 2)
        # el PDF sale con el mismo reparto
        self.env['ir.actions.report']._render_qweb_html(
            'al_l10n_pe_retention.action_report_retention_document', document.ids)

    def test_document_payment_index_counts_payments(self):
        """Un pago parcial con CRE y luego una letra por el resto: la letra es el pago 2."""
        tax, _account = self._setup_retention_tax()
        bill = self._bill(1000.0)
        bill.action_post()
        wizard = self._register_payment(bill)
        wizard.payment_date = '2025-06-15'
        wizard.amount = 800.0
        wizard._create_payments()
        self.assertEqual(bill.amount_residual, 380.0)
        document = self._document(bill, paid=380.0)
        document.action_post()
        self.assertEqual(document._l10n_pe_edi_retention_payment_index(bill), 2)

    def test_document_validations(self):
        self._setup_retention_tax()
        small = self._bill(500.0)  # 590 <= 700
        small.action_post()
        with self.assertRaises(UserError, msg='monto mínimo'):
            self._document(small).action_post()
        bill = self._bill(1000.0)
        bill.action_post()
        with self.assertRaises(UserError, msg='no paga más que el total'):
            self._document(bill, paid=2000.0).action_post()
        draft = self._bill(1000.0)
        with self.assertRaises(UserError, msg='factura sin publicar'):
            self._document(draft).action_post()

    def test_document_cancel_and_reversal(self):
        self._setup_retention_tax()
        bill = self._bill(1000.0)
        bill.action_post()
        document = self._document(bill)
        document.action_post()
        document.l10n_pe_edi_status = 'sent'
        with self.assertRaises(UserError, msg='aceptado: hay que revertirlo'):
            document.action_cancel()
        self._reverse(document, 'sunat')
        self.assertEqual(document.state, 'cancel')
        self.assertEqual(document.move_id.state, 'cancel', 'el asiento se anula con la reversión')
        self.assertEqual(bill.amount_residual, 1180.0)
        self.assertFalse(bill._l10n_pe_retention_cre_history(), 'el CRE anulado no cuenta')

    def test_document_from_bills_action(self):
        self._setup_retention_tax()
        bills = self._bill(1000.0) | self._bill(200.0)
        bills.action_post()
        action = self.env['l10n_pe.retention.document'].with_context(
            active_ids=bills.ids).action_create_from_bills()
        document = self.env['l10n_pe.retention.document'].browse(action['res_id'])
        self.assertEqual(document.line_ids.bill_id, bills)
        self.assertEqual(sum(document.line_ids.mapped('paid_amount')), 1416.0)

    # ------------------------------------------------------------------
    # 6. Notas de crédito descontadas en el siguiente CRE
    # ------------------------------------------------------------------
    def _credit_note(self, bill, price):
        refund = self.env['account.move'].create({
            'move_type': 'in_refund', 'partner_id': self.partner.id,
            'journal_id': self.journal.id, 'reversed_entry_id': bill.id,
            'invoice_date': '2025-06-15', 'date': '2025-06-15', 'ref': 'FC01-00000009',
            'invoice_line_ids': [(0, 0, {
                'name': 'Descuento', 'quantity': 1.0, 'price_unit': price,
                'account_id': self.account_exp.id,
                'tax_ids': [(6, 0, self.tax_purchase.ids)]})],
        })
        refund.action_post()
        return refund

    def test_credit_note_deducted_in_next_payment(self):
        self.company.l10n_pe_retention_deduct_credit_notes = True
        tax, _account = self._setup_retention_tax()
        first = self._paid()  # factura de 1180 con CRE
        bill = first.reconciled_bill_ids | first.invoice_ids
        refund = self._credit_note(bill, 100.0)  # 118: retención 3.54
        self.assertEqual(refund.l10n_pe_retention_credit_amount, 3.54)
        self.assertEqual(refund.l10n_pe_retention_credit_pending, 3.54)

        second_bill = self._bill(1000.0)
        second_bill.action_post()
        wizard = self._register_payment(second_bill)
        line = wizard.withholding_line_ids.filtered(lambda l: l.tax_id == tax)
        self.assertAlmostEqual(line.amount, 35.40 - 3.54, 2, msg='retiene menos')
        payment = wizard._create_payments()
        self.assertEqual(payment.l10n_pe_retention_deduction_ids.credit_note_id, refund)
        self.assertEqual(payment.l10n_pe_retention_deduction_ids.amount, 3.54)
        refund.invalidate_recordset(['l10n_pe_retention_credit_pending'])
        self.assertEqual(refund.l10n_pe_retention_credit_pending, 0.0)

        tree = etree.fromstring(payment._l10n_pe_edi_generate_retention_bstr())
        value = lambda path: tree.xpath(path, namespaces=NS)[0].text
        self.assertEqual(value('/r:Retention/cbc:TotalInvoiceAmount'), '31.86')
        self.assertEqual(value('/r:Retention/sac:SUNATTotalPaid'), '1148.14')
        references = tree.xpath('//sac:SUNATRetentionDocumentReference/cbc:ID', namespaces=NS)
        self.assertEqual([r.get('schemeID') for r in references], ['01', '07'])
        amounts = [a.text for a in tree.xpath('//sac:SUNATRetentionAmount', namespaces=NS)]
        self.assertEqual(amounts, ['35.40', '-3.54'], 'la factura con su 3 % y la nota en negativo')

        # cancelar el pago libera la nota para el siguiente CRE
        payment.action_cancel()
        refund.invalidate_recordset(['l10n_pe_retention_credit_pending'])
        self.assertEqual(refund.l10n_pe_retention_credit_pending, 3.54)

    def test_credit_note_option_off_by_default(self):
        self.assertFalse(self.company.l10n_pe_retention_deduct_credit_notes)
        tax, _account = self._setup_retention_tax()
        first = self._paid()
        refund = self._credit_note(first.reconciled_bill_ids | first.invoice_ids, 100.0)
        self.assertEqual(refund.l10n_pe_retention_credit_amount, 0.0)
        bill = self._bill(1000.0)
        bill.action_post()
        line = self._register_payment(bill).withholding_line_ids.filtered(lambda l: l.tax_id == tax)
        self.assertAlmostEqual(line.amount, 35.40, 2)

    def test_credit_note_deducted_in_document(self):
        self.company.l10n_pe_retention_deduct_credit_notes = True
        self._setup_retention_tax()
        first = self._paid()
        refund = self._credit_note(first.reconciled_bill_ids | first.invoice_ids, 100.0)
        bill = self._bill(1000.0)
        bill.action_post()
        document = self._document(bill)
        document.action_post()
        self.assertEqual(document.deduction_ids.credit_note_id, refund)
        self.assertEqual(document.amount_retention, 31.86)
        self.assertEqual(document.move_id.amount_total, 31.86)
