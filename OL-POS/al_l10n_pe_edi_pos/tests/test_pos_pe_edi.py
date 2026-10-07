# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestPosPeEdi(TestPoSCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        # TestPoSCommon pisa el país de la compañía con uno ficticio
        # ("PoS Land"); el flujo CPE depende de country_code == 'PE'.
        # El check EDI de l10n_pe_edi exige además el RUC de la compañía.
        cls.company_data['company'].write({
            'country_id': cls.env.ref('base.pe').id,
            'vat': '20512528458',
        })
        cls.config = cls.basic_config
        latam_journals = cls.env['account.journal'].search([
            ('company_id', '=', cls.company.id),
            ('type', '=', 'sale'),
            ('l10n_latam_use_documents', '=', True),
        ], limit=1)
        base_journal = latam_journals or cls.config.invoice_journal_id
        cls.journal_boleta = base_journal.copy({
            'name': 'Boletas TPV', 'code': 'BPOS',
            'l10n_latam_use_documents': True,
        })
        cls.journal_factura = base_journal.copy({
            'name': 'Facturas TPV', 'code': 'FPOS',
            'l10n_latam_use_documents': True,
        })
        cls.config.write({
            'l10n_pe_boleta_journal_id': cls.journal_boleta.id,
            'l10n_pe_factura_journal_id': cls.journal_factura.id,
        })
        cls.partner_ruc = cls.env['res.partner'].create({
            'name': 'Cliente con RUC',
            'vat': '20512528458',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
        })
        cls.partner_dni = cls.env['res.partner'].create({
            'name': 'Cliente con DNI',
            'vat': '44556677',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_DNI').id,
        })

    def test_cpe_enabled_flag(self):
        self.assertTrue(self.config.l10n_pe_cpe_enabled)
        self.config.l10n_pe_factura_journal_id = False
        self.assertFalse(self.config.l10n_pe_cpe_enabled)

    def test_journal_por_tipo_documento(self):
        """Boleta → diario de boletas; factura → diario de facturas."""
        self.open_new_session()
        session = self.pos_session
        order = self.env['pos.order'].create({
            'session_id': session.id,
            'partner_id': self.partner_dni.id,
            'l10n_pe_doc_type': 'boleta',
            'amount_tax': 0, 'amount_total': 0,
            'amount_paid': 0, 'amount_return': 0,
        })
        vals = order._prepare_invoice_vals()
        self.assertEqual(vals['journal_id'], self.journal_boleta.id)

        order.write({
            'partner_id': self.partner_ruc.id,
            'l10n_pe_doc_type': 'factura',
        })
        vals = order._prepare_invoice_vals()
        self.assertEqual(vals['journal_id'], self.journal_factura.id)

    def test_boleta_a_cliente_con_ruc_es_boleta(self):
        """Boleta elegida en caja para un cliente con RUC: tipo 03, no 01.

        l10n_pe pone por defecto la factura a un cliente con RUC; antes el
        comprobante salía como factura numerada en la serie de boletas."""
        self.open_new_session()
        order = self._order_with_line(self.partner_ruc, l10n_pe_doc_type='boleta')
        vals = order._prepare_invoice_vals()
        self.assertEqual(vals['journal_id'], self.journal_boleta.id)
        boleta = self.env.ref('l10n_pe.document_type02')
        self.assertEqual(vals['l10n_latam_document_type_id'], boleta.id)
        invoice = order._create_invoice(vals)
        self.assertEqual(invoice.l10n_latam_document_type_id.code, '03')
        self.assertEqual(invoice.journal_id, self.journal_boleta)

    def test_factura_lleva_tipo_01(self):
        self.open_new_session()
        order = self._order_with_line(self.partner_ruc, l10n_pe_doc_type='factura')
        invoice = order._create_invoice(order._prepare_invoice_vals())
        self.assertEqual(invoice.l10n_latam_document_type_id.code, '01')
        self.assertEqual(invoice.journal_id, self.journal_factura)

    def test_factura_requiere_ruc(self):
        self.open_new_session()
        order = self.env['pos.order'].create({
            'session_id': self.pos_session.id,
            'partner_id': self.partner_dni.id,
            'l10n_pe_doc_type': 'factura',
            'amount_tax': 0, 'amount_total': 0,
            'amount_paid': 0, 'amount_return': 0,
        })
        with self.assertRaises(UserError):
            order._prepare_invoice_vals()

    def test_factura_requiere_tipo_ruc(self):
        """11 dígitos con tipo «VAT» (código 0) no es RUC: SUNAT rechazaría la factura."""
        self.open_new_session()
        partner = self.env['res.partner'].create({
            'name': 'Cliente VAT 11', 'vat': '20557912879',
            'l10n_latam_identification_type_id': self.env.ref('l10n_latam_base.it_vat').id})
        order = self.env['pos.order'].create({
            'session_id': self.pos_session.id, 'partner_id': partner.id,
            'l10n_pe_doc_type': 'factura',
            'amount_tax': 0, 'amount_total': 0, 'amount_paid': 0, 'amount_return': 0,
        })
        with self.assertRaises(UserError):
            order._prepare_invoice_vals()

    def test_ticket_carga_todos_los_totales_del_xml(self):
        fields = self.env['account.move']._load_pos_data_fields(self.config)
        for name in ('l10n_pe_edi_amount_isc', 'l10n_pe_edi_amount_ivap', 'l10n_pe_edi_amount_free',
                     'l10n_pe_edi_amount_export', 'l10n_pe_pos_igv_label'):
            self.assertIn(name, fields)

    def test_qr_usa_la_entidad_comercial(self):
        self.open_new_session()
        contacto = self.env['res.partner'].create({
            'name': 'Contacto compras', 'parent_id': self.partner_ruc.id})
        igv = self.env['account.tax'].search([
            ('company_id', '=', self.env.company.id), ('type_tax_use', '=', 'sale'),
            ('l10n_pe_edi_tax_code', '=', '1000')], limit=1)
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': contacto.id,
            'journal_id': self.journal_factura.id,
            'l10n_latam_document_type_id': self.env.ref('l10n_pe.document_type01').id,
            'invoice_line_ids': [(0, 0, {'name': 'Venta', 'quantity': 1, 'price_unit': 100.0,
                                         'tax_ids': [(6, 0, igv.ids)]})]})
        invoice.action_post()
        self.assertIn(self.partner_ruc.vat, invoice.l10n_pe_pos_qr_str)

    def test_tipo_de_identificacion_lleva_el_codigo_sunat(self):
        fields = self.env['l10n_latam.identification.type']._load_pos_data_fields(self.config)
        self.assertIn('l10n_pe_vat_code', fields)

    def test_serie_cpe_en_factura(self):
        """La serie elegida en caja viaja a la factura generada."""
        serie = self.env['edi.invoice.series'].create({
            'name': 'F901',
            'l10n_latam_document_type_id': self.env.ref(
                'l10n_pe.document_type01').id,
            'name_nc': 'FC91', 'name_nd': 'FD91',
            'company_id': self.company.id,
        })
        serie.action_publish()
        self.journal_factura.write({
            'use_name_sequence': True,
            'edi_series_ids': [(6, 0, serie.ids)],
        })
        self.assertIn(serie, self.config.l10n_pe_factura_series_ids)
        self.open_new_session()
        order = self.env['pos.order'].create({
            'session_id': self.pos_session.id,
            'partner_id': self.partner_ruc.id,
            'l10n_pe_doc_type': 'factura',
            'edi_series_id': serie.id,
            'amount_tax': 0, 'amount_total': 0,
            'amount_paid': 0, 'amount_return': 0,
        })
        vals = order._prepare_invoice_vals()
        self.assertEqual(vals['journal_id'], self.journal_factura.id)
        self.assertEqual(vals['edi_series_id'], serie.id)

    def test_emision_sunat_retenida(self):
        """«Emitir a SUNAT: No» en caja → factura con la retención marcada
        y los documentos EDI excluidos del procesamiento."""
        self.open_new_session()
        order = self.env['pos.order'].create({
            'session_id': self.pos_session.id,
            'partner_id': self.partner_dni.id,
            'l10n_pe_doc_type': 'boleta',
            'l10n_pe_edi_send': False,
            'amount_tax': 0, 'amount_total': 0,
            'amount_paid': 0, 'amount_return': 0,
        })
        vals = order._prepare_invoice_vals()
        self.assertTrue(vals.get('l10n_pe_edi_hold'))

    def test_documentos_retenidos_no_se_procesan(self):
        """_process_documents_web_services (cron y botón «Procesar ahora»)
        no procesa los documentos EDI de facturas retenidas."""
        edi_format = self.env.ref('l10n_pe_edi.edi_pe_ubl_2_1')
        Doc = self.env['account.edi.document']
        docs = Doc
        for hold in (True, False):
            move = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': self.partner_dni.id,
                'l10n_pe_edi_hold': hold,
            })
            docs |= Doc.create({
                'move_id': move.id,
                'edi_format_id': edi_format.id,
                'state': 'to_send',
            })
        held = docs.filtered(lambda d: d.move_id.l10n_pe_edi_hold)
        prepared = []

        def fake_prepare_jobs(recs):
            prepared.append(recs)
            return []

        with patch.object(type(Doc), '_prepare_jobs', fake_prepare_jobs):
            docs._process_documents_web_services(with_commit=False)
        self.assertEqual(len(prepared), 1)
        self.assertNotIn(held, prepared[0])
        self.assertEqual(prepared[0], docs - held)

    def _order_with_line(self, partner, qty=1, **vals):
        """Orden con una línea: `refunded_order_id` es un compute que sale
        de `lines.refunded_orderline_id`, así que la devolución necesita
        líneas enlazadas a las del original."""
        if not hasattr(self, '_refund_product'):
            self._refund_product = self.create_product(
                'Producto devolución', self.categ_basic, 10.0)
        refunded_line = vals.pop('refunded_orderline_id', False)
        line = {
            'product_id': self._refund_product.id,
            'qty': qty, 'price_unit': 10.0,
            'price_subtotal': 10.0 * qty, 'price_subtotal_incl': 10.0 * qty,
        }
        if refunded_line:
            line['refunded_orderline_id'] = refunded_line.id
        return self.env['pos.order'].create({
            'session_id': self.pos_session.id,
            'partner_id': partner.id,
            'lines': [(0, 0, line)],
            'amount_tax': 0, 'amount_total': 10.0 * qty,
            'amount_paid': 0, 'amount_return': 0,
            **vals,
        })

    def _refund_for(self, original):
        refund = self._order_with_line(
            original.partner_id, qty=-1,
            refunded_orderline_id=original.lines[:1],
            # El frontend deja «boleta» por defecto en la devolución.
            l10n_pe_doc_type='boleta')
        self.assertEqual(refund.refunded_order_id, original)
        return refund

    def test_devolucion_de_factura_va_al_diario_de_facturas(self):
        """La NC de una factura se crea en el diario de la factura aunque la
        orden de devolución quede marcada como boleta."""
        self.open_new_session()
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_ruc.id,
            'journal_id': self.journal_factura.id,
        })
        original = self._order_with_line(
            self.partner_ruc, l10n_pe_doc_type='factura', account_move=invoice.id)
        vals = self._refund_for(original)._prepare_invoice_vals()
        self.assertEqual(vals['journal_id'], self.journal_factura.id)
        self.assertNotIn('edi_series_id', vals)

    def test_devolucion_de_recibo_sin_comprobante(self):
        """Devolver un «Recibo» (sin comprobante) no usa los diarios CPE."""
        self.open_new_session()
        original = self._order_with_line(self.partner_dni, l10n_pe_doc_type='recibo')
        vals = self._refund_for(original)._prepare_invoice_vals()
        self.assertNotIn(vals['journal_id'],
                         (self.journal_boleta | self.journal_factura).ids)

    def test_serie_de_otro_tipo_no_se_aplica(self):
        """Una serie de boletas no numera una factura aunque esté en el
        diario."""
        serie_b = self.env['edi.invoice.series'].create({
            'name': 'B901',
            'l10n_latam_document_type_id': self.env.ref(
                'l10n_pe.document_type03').id,
            'name_nc': 'BC91', 'name_nd': 'BD91',
            'company_id': self.company.id,
        })
        serie_b.action_publish()
        self.journal_factura.write({
            'use_name_sequence': True,
            'edi_series_ids': [(4, serie_b.id)],
        })
        self.open_new_session()
        order = self.env['pos.order'].create({
            'session_id': self.pos_session.id,
            'partner_id': self.partner_ruc.id,
            'l10n_pe_doc_type': 'factura',
            'edi_series_id': serie_b.id,
            'amount_tax': 0, 'amount_total': 0,
            'amount_paid': 0, 'amount_return': 0,
        })
        vals = order._prepare_invoice_vals()
        self.assertNotIn('edi_series_id', vals)

    def test_qr_representacion_impresa(self):
        product = self.create_product('Servicio QR', self.categ_basic, 100.0)
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_ruc.id,
            'journal_id': self.journal_factura.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'name': 'Servicio', 'quantity': 1, 'price_unit': 100.0,
                'tax_ids': [(6, 0, self.taxes['tax7'].ids)],
            })],
        })
        move.action_post()
        self.assertTrue(move.l10n_pe_pos_qr_str)
        parts = move.l10n_pe_pos_qr_str.split('|')
        self.assertEqual(len(parts), 9)
        self.assertEqual(parts[0], self.company.vat or '')
        self.assertEqual(parts[8], self.partner_ruc.vat)
        self.assertTrue(move.l10n_pe_pos_amount_text)
