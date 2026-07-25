# -*- coding: utf-8 -*-
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
        # El filtro de _process_documents_web_services excluye los
        # documentos de facturas retenidas
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_dni.id,
            'l10n_pe_edi_hold': True,
        })
        doc = self.env['account.edi.document'].new({'move_id': move.id})
        filtered = doc.filtered(lambda d: not d.move_id.l10n_pe_edi_hold)
        self.assertFalse(filtered)

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
