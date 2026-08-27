# -*- coding: utf-8 -*-
"""Detalle tributario SUNAT y bloques auxiliares del comprobante.

El pie del comprobante no es decorativo: SUNAT exige que el desglose
(gravado, exonerado, inafecto, ICBPER, ISC, otros) cuadre con el XML
enviado. Aquí se comprueba la clasificación por código de tributo
(catálogo 5), el caso de la factura en moneda extranjera —el desglose
debe ir en la moneda del documento, no en soles— y los datos que arman
las cuotas de crédito, el descuento global y la cuenta de detracción.
"""
from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestInvoiceTaxBreakdown(AccountTestInvoicingCommon):

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
        cls.usd = cls.setup_other_currency('USD')

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    @classmethod
    def _tax(cls, code):
        """Impuesto de venta con un código de tributo SUNAT concreto."""
        return cls.env['account.tax'].search([
            ('l10n_pe_edi_tax_code', '=', code),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', cls.company.id),
        ], limit=1)

    def _invoice(self, lines, currency=None, post=True, **kw):
        vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2026-03-15',
            'date': '2026-03-15',
            'invoice_line_ids': [Command.create({
                'name': name,
                'quantity': 1,
                'price_unit': price,
                'tax_ids': [Command.set(tax.ids if tax else [])],
            }) for name, price, tax in lines],
        }
        if currency:
            vals['currency_id'] = currency.id
        vals.update(kw)
        move = self.env['account.move'].create(vals)
        if post:
            move.action_post()
        return move

    # ------------------------------------------------------------------
    # Clasificación por código de tributo
    # ------------------------------------------------------------------
    def test_igv_line_feeds_base_and_igv(self):
        """Una línea gravada suma a base imponible e IGV (18 %)."""
        igv = self._tax('1000')
        move = self._invoice([('Servicio gravado', 1000.0, igv)])
        self.assertAlmostEqual(move.l10n_pe_edi_amount_base, 1000.0, 2)
        self.assertAlmostEqual(move.l10n_pe_edi_amount_igv, 180.0, 2)
        self.assertAlmostEqual(move.amount_total, 1180.0, 2)

    def test_exonerated_tax_goes_to_exonerated_base(self):
        """El tributo 9997 va a exonerado, no a base gravada."""
        exo = self._tax('9997')
        if not exo:
            self.skipTest('el plan PE no trae impuesto exonerado de venta')
        move = self._invoice([('Servicio exonerado', 500.0, exo)])
        self.assertAlmostEqual(move.l10n_pe_edi_amount_exonerated, 500.0, 2)
        self.assertAlmostEqual(move.l10n_pe_edi_amount_igv, 0.0, 2)
        self.assertAlmostEqual(move.l10n_pe_edi_amount_base, 0.0, 2)

    def test_unaffected_tax_goes_to_unaffected_base(self):
        """El tributo 9998 va a inafecto."""
        ina = self._tax('9998')
        if not ina:
            self.skipTest('el plan PE no trae impuesto inafecto de venta')
        move = self._invoice([('Servicio inafecto', 300.0, ina)])
        self.assertAlmostEqual(move.l10n_pe_edi_amount_unaffected, 300.0, 2)
        self.assertAlmostEqual(move.l10n_pe_edi_amount_igv, 0.0, 2)

    def test_line_without_tax_counts_as_exonerated(self):
        """Sin impuesto, SUNAT lo trata como operación exonerada.

        Sin publicar: el control EDI del core exige impuesto en todas las
        líneas, y lo que se comprueba aquí es la clasificación.
        """
        move = self._invoice([('Sin impuesto', 250.0, None)], post=False)
        self.assertAlmostEqual(move.l10n_pe_edi_amount_exonerated, 250.0, 2)

    def test_mixed_invoice_splits_each_bucket(self):
        """Factura mixta: cada línea cae en su casilla y nada se solapa."""
        igv, exo = self._tax('1000'), self._tax('9997')
        if not exo:
            self.skipTest('el plan PE no trae impuesto exonerado de venta')
        move = self._invoice([
            ('Gravado', 1000.0, igv),
            ('Exonerado', 400.0, exo),
        ])
        self.assertAlmostEqual(move.l10n_pe_edi_amount_base, 1000.0, 2)
        self.assertAlmostEqual(move.l10n_pe_edi_amount_igv, 180.0, 2)
        self.assertAlmostEqual(move.l10n_pe_edi_amount_exonerated, 400.0, 2)
        self.assertAlmostEqual(move.amount_total, 1580.0, 2)

    def test_icbper_amount(self):
        """El ICBPER (bolsas) se acumula en su propia casilla."""
        icbper = self._tax('7152')
        if not icbper:
            self.skipTest('el plan PE no trae ICBPER de venta')
        igv = self._tax('1000')
        move = self._invoice([('Bolsa', 100.0, igv | icbper)])
        self.assertGreater(move.l10n_pe_edi_amount_icbper, 0.0)

    # ------------------------------------------------------------------
    # Moneda extranjera
    # ------------------------------------------------------------------
    def test_breakdown_in_document_currency(self):
        """Factura en USD: el desglose va en dólares, no convertido a soles.

        Con las claves en moneda de compañía, el pie mostraba el IGV en
        soles junto a un total en dólares.
        """
        igv = self._tax('1000')
        move = self._invoice([('Servicio gravado', 1000.0, igv)],
                             currency=self.usd)
        self.assertEqual(move.currency_id, self.usd)
        self.assertAlmostEqual(move.l10n_pe_edi_amount_base, 1000.0, 2)
        self.assertAlmostEqual(move.l10n_pe_edi_amount_igv, 180.0, 2)
        self.assertAlmostEqual(
            move.l10n_pe_edi_amount_base + move.l10n_pe_edi_amount_igv,
            move.amount_total, 2,
            'el desglose debe cuadrar con el total del documento')

    # ------------------------------------------------------------------
    # Tipos de documento que no llevan desglose
    # ------------------------------------------------------------------
    def test_journal_entry_has_no_breakdown(self):
        """Un asiento manual no arrastra desglose tributario."""
        journal = self.company_data['default_journal_misc']
        account = self.company_data['default_account_revenue']
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': '2026-03-15',
            'line_ids': [
                Command.create({'account_id': account.id, 'name': 'D',
                                'debit': 100.0, 'credit': 0.0}),
                Command.create({'account_id': account.id, 'name': 'H',
                                'debit': 0.0, 'credit': 100.0}),
            ],
        })
        self.assertAlmostEqual(move.l10n_pe_edi_amount_base, 0.0, 2)
        self.assertAlmostEqual(move.l10n_pe_edi_amount_igv, 0.0, 2)

    def test_credit_note_keeps_breakdown(self):
        """La nota de crédito conserva su propio desglose."""
        igv = self._tax('1000')
        invoice = self._invoice([('Servicio gravado', 1000.0, igv)])
        # El tipo de documento tiene que ser de nota de crédito: copiar el
        # de la factura viola la restricción de l10n_latam.
        nc_type = self.env['l10n_latam.document.type'].search([
            ('country_id', '=', self.env.ref('base.pe').id),
            ('internal_type', '=', 'credit_note'),
        ], limit=1)
        reversal = invoice._reverse_moves([{
            'invoice_date': invoice.invoice_date,
            'date': invoice.date,
            'l10n_latam_document_type_id': nc_type.id,
        }])
        # No se publica: la NC necesita su propio tipo de documento SUNAT
        # (catálogo 01, código 07) y eso es cosa del flujo EDI, no del
        # desglose que se prueba aquí.
        self.assertEqual(reversal.move_type, 'out_refund')
        self.assertAlmostEqual(reversal.l10n_pe_edi_amount_base, 1000.0, 2)
        self.assertAlmostEqual(reversal.l10n_pe_edi_amount_igv, 180.0, 2)

    # ------------------------------------------------------------------
    # Bloques auxiliares del reporte
    # ------------------------------------------------------------------
    def test_is_credit_flag(self):
        """``is_credit`` distingue contado de crédito por el plazo de pago."""
        igv = self._tax('1000')
        term = self.env['account.payment.term'].create({
            'name': 'Crédito 30 días',
            'company_id': self.company.id,
            'line_ids': [Command.create({'value': 'percent',
                                         'value_amount': 100.0,
                                         'nb_days': 30})],
        })
        move = self._invoice([('Servicio', 1000.0, igv)], post=False)
        move.invoice_payment_term_id = False
        self.assertFalse(move.is_credit, 'sin plazo de pago es contado')
        move.invoice_payment_term_id = term
        self.assertTrue(move.is_credit)

    def test_get_data_dues_single_due(self):
        """Sin detalle de cuotas se muestra una sola con el saldo pendiente."""
        igv = self._tax('1000')
        move = self._invoice([('Servicio', 1000.0, igv)])
        dues = move.get_data_dues()
        self.assertTrue(dues)
        self.assertEqual(dues[0]['nro'], 1)

    def test_get_data_dues_multiple_installments(self):
        """Con un plazo de varias cuotas se numeran correlativas."""
        igv = self._tax('1000')
        term = self.env['account.payment.term'].create({
            'name': 'Dos cuotas 30/60',
            'company_id': self.company.id,
            'line_ids': [
                Command.create({'value': 'percent', 'value_amount': 50.0,
                                'nb_days': 30}),
                Command.create({'value': 'percent', 'value_amount': 50.0,
                                'nb_days': 60}),
            ],
        })
        move = self._invoice([('Servicio', 1000.0, igv)], post=False)
        move.invoice_payment_term_id = term
        move.action_post()
        dues = move.get_data_dues()
        self.assertEqual([d['nro'] for d in dues], [1, 2])
        self.assertAlmostEqual(sum(d['amount'] for d in dues),
                               move.amount_total, 2)

    def test_get_amount_discount(self):
        """El descuento global se toma de las líneas en negativo, en positivo."""
        igv = self._tax('1000')
        move = self._invoice([
            ('Servicio', 1000.0, igv),
            ('Descuento', -100.0, igv),
        ])
        self.assertAlmostEqual(move.get_amount_discount(), 118.0, 2)

    def test_report_filename_includes_partner(self):
        """El PDF se nombra con el documento y el cliente."""
        igv = self._tax('1000')
        move = self._invoice([('Servicio', 1000.0, igv)])
        filename = move._get_report_base_filename_custom()
        self.assertIn(self.partner_a.name, filename)

    def test_national_bank_account_empty_without_bank(self):
        """Sin cuenta del Banco de la Nación el bloque de detracción va vacío."""
        igv = self._tax('1000')
        move = self._invoice([('Servicio', 1000.0, igv)])
        self.company.partner_id.bank_ids.filtered(
            lambda b: b.bank_id == self.env.ref('l10n_pe.peruvian_national_bank')
        ).unlink()
        self.assertEqual(move._l10n_pe_get_national_bank_account_number(), '')

    def test_action_print_pdf_returns_report_action(self):
        """El botón de imprimir devuelve el reporte A4 propio."""
        igv = self._tax('1000')
        move = self._invoice([('Servicio', 1000.0, igv)])
        action = move.action_print_pdf()
        report = self.env.ref('al_l10n_pe_invoice.report_cpe_invoice_a4')
        if action['type'] == 'ir.actions.report':
            self.assertEqual(action['report_name'], report.report_name)
        else:
            # Sin formato de documento configurado, Odoo interpone el
            # asistente de diseño antes de imprimir.
            self.assertEqual(action['res_model'], 'base.document.layout')
