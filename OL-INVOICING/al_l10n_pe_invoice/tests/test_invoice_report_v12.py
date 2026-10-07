# -*- coding: utf-8 -*-
"""Auditoría del 07/10/2026: la representación impresa debe decir lo mismo
que el XML enviado a SUNAT.

* El adquirente es la entidad comercial (``commercial_partner_id``), como en
  el XML y en el QR: facturando a un contacto de la empresa, el A4 imprimía
  el nombre del contacto y su documento (vacío).
* Las notas de crédito no llevan forma de pago ni cuotas en el XML; el PDF
  imprimía «CRÉDITO» y un cuadro de cuotas si la nota tenía vencimiento.
* A crédito, la R.S. 193-2020/SUNAT exige el monto neto pendiente de pago
  y las cuotas; el ticket no mostraba ninguno y el A4 no mostraba el neto.
"""
from datetime import date

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestInvoiceReportV12(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.company.vat = '20512528458'
        cls.company_data['default_journal_sale'].l10n_latam_use_documents = True
        cls.partner_a.write({
            'name': 'EMPRESA CLIENTE SAC', 'is_company': True,
            'vat': '20557912879',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
        })
        cls.contact = cls.env['res.partner'].create({
            'name': 'Juana Compras', 'parent_id': cls.partner_a.id, 'type': 'invoice'})
        cls.a4 = 'al_l10n_pe_invoice.report_cpe_invoice_a4_main'
        cls.ticket = 'al_l10n_pe_invoice.report_cpe_ticket_main'
        cls.igv = cls.env['account.tax'].search([
            ('l10n_pe_edi_tax_code', '=', '1000'), ('type_tax_use', '=', 'sale'),
            ('amount', '=', 18), ('company_id', '=', cls.company.id)], limit=1)
        cls.term_30 = cls.env['account.payment.term'].create({
            'name': '30 días test', 'line_ids': [Command.create({
                'value': 'percent', 'value_amount': 100, 'nb_days': 30})]})

    def _invoice(self, partner=None, move_type='out_invoice', **kw):
        vals = {
            'move_type': move_type,
            'partner_id': (partner or self.partner_a).id,
            'invoice_date': date(2026, 3, 15), 'date': date(2026, 3, 15),
            'invoice_line_ids': [Command.create({
                'name': 'Servicio', 'quantity': 1, 'price_unit': 1000.0,
                'tax_ids': [Command.set(self.igv.ids)]})],
        }
        vals.update(kw)
        move = self.env['account.move'].create(vals)
        move.action_post()
        return move

    def _html(self, report, move):
        return self.env['ir.actions.report']._render_qweb_html(report, move.ids)[0].decode()

    def test_buyer_is_the_commercial_partner(self):
        move = self._invoice(partner=self.contact)
        for report in (self.a4, self.ticket):
            html = self._html(report, move)
            self.assertIn('EMPRESA CLIENTE SAC', html, report)
            self.assertIn('20557912879', html, report)
            self.assertNotIn('Juana Compras', html, report)

    def test_credit_note_has_no_payment_means(self):
        invoice = self._invoice(invoice_payment_term_id=self.term_30.id)
        refund = self._invoice(move_type='out_refund', reversed_entry_id=invoice.id,
                               invoice_payment_term_id=self.term_30.id)
        self.assertTrue(refund.is_credit, 'la nota vence después de emitirse')
        for report in (self.a4, self.ticket):
            html = self._html(report, refund)
            self.assertNotIn('CRÉDITO', html, report)
            self.assertNotIn('Información del crédito', html, report)

    def test_credit_shows_net_pending_and_dues(self):
        move = self._invoice(invoice_payment_term_id=self.term_30.id)
        self.assertEqual(move._l10n_pe_report_net_pending(), 1180.0)
        for report in (self.a4, self.ticket):
            html = self._html(report, move)
            self.assertIn('Monto neto pendiente de pago', html, report)
            self.assertIn('14/04/2026', html, report)
