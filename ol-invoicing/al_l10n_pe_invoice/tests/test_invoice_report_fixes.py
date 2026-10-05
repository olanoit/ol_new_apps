# -*- coding: utf-8 -*-
"""Correcciones de la auditoría de septiembre de 2026 en el comprobante.

* Exportación (9995) y operaciones gratuitas (9996) tienen su propia
  casilla: antes el 9996 caía en «otros» y el 9995 no se contaba.
* El descuento se imprime en base imponible y suma tanto el porcentaje
  por línea como las líneas negativas.
* Las NC/ND imprimen el documento que modifican (la ND lo guarda en
  ``debit_origin_id``) y el motivo.
* Las cuotas salen de los apuntes de vencimiento: siguen ahí después de
  pagar la factura.
* La moneda y la tasa del IGV ya no son textos fijos.
"""
from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestInvoiceReportFixes(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.company.vat = '20512528458'
        cls.company_data['default_journal_sale'].l10n_latam_use_documents = True
        cls.partner_a.write({
            'vat': '20557912879',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
        })
        cls.a4 = 'al_l10n_pe_invoice.report_cpe_invoice_a4_main'
        cls.ticket = 'al_l10n_pe_invoice.report_cpe_ticket_main'

    @classmethod
    def _tax(cls, code):
        return cls.env['account.tax'].search([
            ('l10n_pe_edi_tax_code', '=', code),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', cls.company.id),
        ], limit=1)

    def _invoice(self, lines, post=True, **kw):
        vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2026-03-15',
            'date': '2026-03-15',
            'invoice_line_ids': [Command.create({
                'name': name,
                'quantity': 1,
                'price_unit': price,
                'discount': discount,
                'tax_ids': [Command.set(tax.ids if tax else [])],
            }) for name, price, tax, discount in lines],
        }
        vals.update(kw)
        move = self.env['account.move'].create(vals)
        if post:
            move.action_post()
        return move

    def _html(self, report, move):
        return self.env['ir.actions.report']._render_qweb_html(
            report, move.ids)[0].decode()

    # ------------------------------------------------------------------
    # Desglose tributario
    # ------------------------------------------------------------------
    def test_export_goes_to_export_bucket(self):
        """9995: la base va a «Op. exportación», no se pierde."""
        exp = self._tax('9995')
        if not exp:
            self.skipTest('el plan PE no trae impuesto de exportación de venta')
        move = self._invoice([('Exportación', 800.0, exp, 0.0)], post=False)
        self.assertAlmostEqual(move.l10n_pe_edi_amount_export, 800.0, 2)
        self.assertAlmostEqual(move.l10n_pe_edi_amount_others, 0.0, 2)
        self.assertAlmostEqual(move.l10n_pe_edi_amount_base, 0.0, 2)
        self.assertIn('Op. exportación', self._html(self.a4, move))
        self.assertIn('Op. exportación', self._html(self.ticket, move))

    def test_free_goes_to_free_bucket(self):
        """9996 (gratuito) va a «Op. gratuitas», no a «otros tributos»."""
        gra = self._tax('9996')
        if not gra:
            self.skipTest('el plan PE no trae impuesto gratuito de venta')
        move = self._invoice([('Muestra gratuita', 50.0, gra, 0.0)], post=False)
        self.assertAlmostEqual(move.l10n_pe_edi_amount_free, 50.0, 2)
        self.assertAlmostEqual(move.l10n_pe_edi_amount_others, 0.0, 2)
        self.assertIn('Op. gratuitas', self._html(self.a4, move))

    # ------------------------------------------------------------------
    # Descuento
    # ------------------------------------------------------------------
    def test_line_discount_is_printed_in_base(self):
        """Un 10 % en la línea imprime la fila «Descuento» con 100.00 (sin
        IGV); antes salía 0.00."""
        move = self._invoice([('Servicio', 1000.0, self._tax('1000'), 10.0)])
        self.assertAlmostEqual(move.get_amount_discount(), 100.0, 2)
        html = self._html(self.a4, move)
        # El importe sale en el formato del idioma del cliente (100,00 en
        # es_419): se comprueba el valor de la propia fila «Descuento».
        self.assertRegex(
            html, r'Descuento</td>\s*<td[^>]*>\s*<span[^>]*>[^<]*'
                  r'<span class="oe_currency_value">100[.,]00</span>')

    def test_global_discount_row_is_printed(self):
        """Un descuento global (línea negativa) sí imprime la fila."""
        igv = self._tax('1000')
        move = self._invoice([('Servicio', 1000.0, igv, 0.0),
                              ('Descuento global', -200.0, igv, 0.0)])
        self.assertAlmostEqual(move.get_amount_discount(), 200.0, 2)
        self.assertIn('Descuento', self._html(self.a4, move))

    def test_no_discount_no_row(self):
        move = self._invoice([('Servicio', 1000.0, self._tax('1000'), 0.0)])
        self.assertEqual(move.get_amount_discount(), 0.0)
        self.assertNotIn('>Descuento<', self._html(self.a4, move))

    # ------------------------------------------------------------------
    # NC / ND: documento que modifica
    # ------------------------------------------------------------------
    def test_credit_note_prints_origin_and_reason(self):
        invoice = self._invoice([('Servicio', 1000.0, self._tax('1000'), 0.0)])
        refund = invoice._reverse_moves([{
            'invoice_date': invoice.invoice_date,
            'date': invoice.date,
            'l10n_latam_document_type_id': self.env.ref('l10n_pe.document_type07').id,
            'l10n_pe_edi_refund_reason': '01',
        }])
        self.assertEqual(refund._l10n_pe_report_origin_move(), invoice)
        origin_number = invoice.l10n_latam_document_number or invoice.name
        for report in (self.a4, self.ticket):
            html = self._html(report, refund)
            self.assertIn(origin_number, html)
            self.assertIn('Motivo', html)

    def test_debit_note_prints_origin_from_debit_origin(self):
        """La ND guarda el origen en ``debit_origin_id``: antes el ticket
        solo miraba ``reversed_entry_id`` y el A4 no lo imprimía."""
        invoice = self._invoice([('Servicio', 1000.0, self._tax('1000'), 0.0)])
        debit = self._invoice(
            [('Intereses', 50.0, self._tax('1000'), 0.0)], post=False,
            debit_origin_id=invoice.id,
            l10n_latam_document_type_id=self.env.ref('l10n_pe.document_type08').id,
            l10n_pe_edi_charge_reason='01')
        self.assertEqual(debit._l10n_pe_report_origin_move(), invoice)
        origin_number = invoice.l10n_latam_document_number or invoice.name
        for report in (self.a4, self.ticket):
            html = self._html(report, debit)
            self.assertIn('Documento que modifica' if report == self.a4 else 'Modifica a', html)
            self.assertIn(origin_number, html)

    # ------------------------------------------------------------------
    # Cuotas
    # ------------------------------------------------------------------
    def test_dues_survive_payment(self):
        """Tras pagar, la factura se reimprime con sus dos cuotas (antes una
        sola de 0.00)."""
        term = self.env['account.payment.term'].create({
            'name': 'Dos cuotas 30/60 fix',
            'company_id': self.company.id,
            'line_ids': [
                Command.create({'value': 'percent', 'value_amount': 50.0, 'nb_days': 30}),
                Command.create({'value': 'percent', 'value_amount': 50.0, 'nb_days': 60}),
            ],
        })
        move = self._invoice([('Servicio', 1000.0, self._tax('1000'), 0.0)],
                             invoice_payment_term_id=term.id)
        before = move.get_data_dues()
        self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=move.ids,
        ).create({})._create_payments()
        self.assertNotIn(move.payment_state, ('not_paid', 'partial'))
        after = move.get_data_dues()
        self.assertEqual(after, before)
        self.assertEqual([d['nro'] for d in after], [1, 2])
        self.assertAlmostEqual(sum(d['amount'] for d in after), move.amount_total, 2)
        self.assertRegex(after[0]['date'], r'^\d{2}/\d{2}/\d{4}$')

    # ------------------------------------------------------------------
    # Textos que eran fijos
    # ------------------------------------------------------------------
    def test_currency_label_follows_document_currency(self):
        eur = self.setup_other_currency('EUR')
        move = self._invoice([('Servicio', 100.0, self._tax('1000'), 0.0)],
                             post=False, currency_id=eur.id)
        self.assertEqual(move._l10n_pe_report_currency_label(), 'EUROS')
        self.assertNotIn('SOLES', self._html(self.a4, move))
        pen = self._invoice([('Servicio', 100.0, self._tax('1000'), 0.0)], post=False)
        self.assertEqual(pen._l10n_pe_report_currency_label(), 'SOLES')

    def test_igv_label_uses_applied_rate(self):
        igv = self._tax('1000')
        move = self._invoice([('Servicio', 100.0, igv, 0.0)], post=False)
        self.assertEqual(move._l10n_pe_report_igv_label(), 'IGV (18%)')
        igv10 = igv.copy({'name': 'IGV 10% test', 'amount': 10.0})
        move10 = self._invoice([('Menú', 100.0, igv10, 0.0)], post=False)
        self.assertEqual(move10._l10n_pe_report_igv_label(), 'IGV (10%)')
        self.assertIn('IGV (10%)', self._html(self.ticket, move10))
