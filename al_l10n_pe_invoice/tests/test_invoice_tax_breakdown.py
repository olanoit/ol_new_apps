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
        """``is_credit`` sigue al XML: crédito solo si vence después de emitir."""
        igv = self._tax('1000')
        term = self.env['account.payment.term'].create({
            'name': 'Crédito 30 días',
            'company_id': self.company.id,
            'line_ids': [Command.create({'value': 'percent',
                                         'value_amount': 100.0,
                                         'nb_days': 30})],
        })
        immediate = self.env['account.payment.term'].create({
            'name': 'Pago inmediato test',
            'company_id': self.company.id,
            'line_ids': [Command.create({'value': 'percent',
                                         'value_amount': 100.0,
                                         'nb_days': 0})],
        })
        move = self._invoice([('Servicio', 1000.0, igv)], post=False)
        move.invoice_payment_term_id = False
        move.invoice_date_due = move.invoice_date
        self.assertFalse(move.is_credit, 'vencer el día de emisión es contado')
        move.invoice_payment_term_id = immediate
        self.assertFalse(move.is_credit,
                         'un plazo con una línea a 0 días es contado, como en el XML')
        self.assertEqual(move._l10n_pe_edi_get_payment_means(), 'Contado')
        move.invoice_payment_term_id = term
        self.assertTrue(move.is_credit)
        self.assertEqual(move._l10n_pe_edi_get_payment_means(), 'Credito')

    def test_report_exchange_rate_is_the_invoice_rate(self):
        """El T.C. del reporte es el que usó la factura, aunque ese día no
        tenga una tasa cargada con fecha idéntica."""
        igv = self._tax('1000')
        pen_move = self._invoice([('Servicio', 1000.0, igv)], post=False)
        self.assertEqual(pen_move._l10n_pe_report_exchange_rate(), 0.0)
        usd_move = self._invoice([('Servicio', 1000.0, igv)], currency=self.usd,
                                 post=False, invoice_date='2026-03-17')
        rate = usd_move._l10n_pe_report_exchange_rate()
        self.assertTrue(rate)
        self.assertAlmostEqual(rate, 1.0 / usd_move.invoice_currency_rate, 6)

    def test_report_company_address_without_name(self):
        self.company.partner_id.write({
            'street': 'Av. Test 123', 'city': 'San Isidro', 'zip': '15046'})
        move = self._invoice([('Servicio', 1000.0, self._tax('1000'))], post=False)
        address = move._l10n_pe_report_company_address()
        self.assertNotIn(self.company.name, address)
        self.assertIn('Av. Test 123', address)
        self.assertIn('San Isidro', address)
        self.assertIn('15046', address)
        self.assertNotIn('15046San Isidro', address)
        self.assertNotIn('\n', address)
        # Distrito y ciudad iguales no se repiten.
        self.assertEqual(move._l10n_pe_report_address(self.env['res.partner'].new({
            'street': 'Calle 1', 'city': 'Lima', 'zip': '15001',
            'state_id': False})), 'Calle 1, Lima, 15001')
        self.assertNotIn(move.partner_id.name, move._l10n_pe_report_partner_address())

    def test_slogan_only_with_the_signature_setting(self):
        self.company.write({'company_eslogan_pdf': 'ESLOGAN DE PRUEBA',
                            'active_fep_signatures': False})
        move = self._invoice([('Servicio', 1000.0, self._tax('1000'))])
        report = 'al_l10n_pe_invoice.report_cpe_invoice_a4_main'
        html = self.env['ir.actions.report']._render_qweb_html(report, move.ids)[0]
        self.assertNotIn(b'ESLOGAN DE PRUEBA', html)
        self.company.active_fep_signatures = True
        html = self.env['ir.actions.report']._render_qweb_html(report, move.ids)[0]
        self.assertIn(b'ESLOGAN DE PRUEBA', html)

    def test_invoice_from_sale_order_keeps_external_purchase(self):
        """Facturar un pedido con «OC. externa» fallaba: la factura no tenía
        el campo."""
        self.env.user.group_ids = [Command.link(self.env.ref('sales_team.group_sale_manager').id)]
        product = self.env['product.product'].create({
            'name': 'Producto OC', 'invoice_policy': 'order',
            'taxes_id': [Command.set(self._tax('1000').ids)]})
        order = self.env['sale.order'].create({
            'partner_id': self.partner_a.id,
            'external_purchase': 'OC-2026-0045',
            'order_line': [Command.create({'product_id': product.id,
                                           'product_uom_qty': 1,
                                           'price_unit': 500.0})],
        })
        order.action_confirm()
        invoice = order._create_invoices()
        self.assertEqual(invoice.external_purchase, 'OC-2026-0045')
        self.assertEqual(invoice.sale_id, order)

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
