# -*- coding: utf-8 -*-
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestMoveNameSequence(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('pe')
    def setUpClass(cls):
        super().setUpClass()
        # El check EDI de l10n_pe_edi exige RUC de compañía y del cliente
        # al publicar en diarios latam.
        cls.company_data['company'].vat = '20512528458'
        cls.partner_a.write({
            'vat': '20557912879',
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
        })
        cls.journal_seq = cls.company_data['default_journal_sale'].copy({
            'name': 'Ventas por secuencia', 'code': 'VSEQ',
            'l10n_latam_use_documents': False,
            'use_name_sequence': True,
        })
        cls.journal_seq.name_sequence_id.write({
            'prefix': 'TST-', 'padding': 4,
        })

    def _invoice(self, journal, move_type='out_invoice'):
        move = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': self.partner_a.id,
            'journal_id': journal.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product_a.id,
                'quantity': 1, 'price_unit': 100.0,
                'tax_ids': [(6, 0, self.tax_sale_a.ids)],
            })],
        })
        move.action_post()
        return move

    def test_auto_sequence_created(self):
        """Al activar la casilla sin secuencia se crea una automáticamente."""
        journal = self.company_data['default_journal_sale'].copy({
            'name': 'Auto seq', 'code': 'ASEQ',
            'l10n_latam_use_documents': False,
        })
        self.assertFalse(journal.name_sequence_id)
        journal.use_name_sequence = True
        self.assertTrue(journal.name_sequence_id)
        self.assertEqual(journal.name_sequence_id.implementation, 'no_gap')
        self.assertEqual(journal.name_sequence_id.padding, 8)

    def test_prefix_driven_auto_creation(self):
        """Con casilla + prefijos, las secuencias se crean solas al guardar."""
        journal = self.company_data['default_journal_sale'].copy({
            'name': 'Boletas seq', 'code': 'BSEQ',
            'l10n_latam_use_documents': False,
            'use_name_sequence': True,
            'name_sequence_prefix': 'B001-',
            'refund_name_sequence_prefix': 'BC01-',
        })
        self.assertEqual(journal.name_sequence_id.prefix, 'B001-')
        self.assertEqual(journal.refund_name_sequence_id.prefix, 'BC01-')
        self.assertEqual(journal.name_sequence_id.company_id, journal.company_id)

    def test_generate_buttons(self):
        """El botón Generar crea la secuencia con el prefijo indicado."""
        journal = self.company_data['default_journal_sale'].copy({
            'name': 'Botón seq', 'code': 'GSEQ',
            'l10n_latam_use_documents': False,
        })
        journal.name_sequence_prefix = 'G001-'
        journal.refund_name_sequence_prefix = 'GC01-'
        self.assertFalse(journal.name_sequence_id)
        journal.action_al_generate_name_sequence()
        journal.action_al_generate_refund_name_sequence()
        self.assertEqual(journal.name_sequence_id.prefix, 'G001-')
        self.assertEqual(journal.refund_name_sequence_id.prefix, 'GC01-')

    def test_name_from_sequence(self):
        m1 = self._invoice(self.journal_seq)
        m2 = self._invoice(self.journal_seq)
        self.assertEqual(m1.name, 'TST-0001')
        self.assertEqual(m2.name, 'TST-0002')

    def test_refund_sequence(self):
        refund_seq = self.env['ir.sequence'].create({
            'name': 'NC seq', 'prefix': 'RTST-', 'padding': 4,
            'implementation': 'no_gap',
            'company_id': self.journal_seq.company_id.id,
        })
        self.journal_seq.refund_name_sequence_id = refund_seq
        refund = self._invoice(self.journal_seq, move_type='out_refund')
        self.assertEqual(refund.name, 'RTST-0001')

    def test_journal_without_flag_keeps_core_naming(self):
        journal = self.company_data['default_journal_sale']
        move = self._invoice(journal)
        self.assertNotEqual(move.name, '/')
        self.assertFalse(move.name.startswith('TST-'))

    def test_edi_series_flow(self):
        """Serie CPE: publicar crea las 3 secuencias; la factura numera con
        la serie y la NC con la serie rectificativa del origen."""
        serie = self.env['edi.invoice.series'].create({
            'name': 'F001',
            'l10n_latam_document_type_id': self.env.ref(
                'l10n_pe.document_type01').id,
            'name_nc': 'FC01', 'name_nd': 'FD01',
            'company_id': self.env.company.id,
        })
        serie.action_publish()
        self.assertEqual(serie.state, 'publish')
        self.assertEqual(serie.invoice_seq_id.prefix, 'F001-')
        self.assertEqual(serie.credit_note_seq_id.prefix, 'FC01-')
        self.assertEqual(serie.debit_note_seq_id.prefix, 'FD01-')

        journal = self.company_data['default_journal_sale'].copy({
            'name': 'CPE series', 'code': 'CPES',
            'l10n_latam_use_documents': True,
            'use_name_sequence': True,
            'edi_series_ids': [(6, 0, serie.ids)],
        })
        invoice = self._invoice(journal)
        self.assertEqual(invoice.edi_series_id, serie)
        self.assertEqual(invoice.name, 'F001-00000001')
        self.assertEqual(invoice.l10n_latam_document_number, 'F001-00000001')

        reversal = self.env['account.move.reversal'].with_context(
            active_model='account.move', active_ids=invoice.ids).create({
                'journal_id': journal.id,
                'reason': 'Prueba NC',
            })
        action = reversal.reverse_moves()
        refund = self.env['account.move'].browse(action['res_id'])
        refund.action_post()
        self.assertTrue(refund.name.startswith('FC01-'),
                        f'NC numerada como {refund.name}')

    def test_edi_series_journal_change(self):
        """Una sola serie candidata → autoasignada; varias → elección
        manual; al cambiar de diario la serie se limpia/reasigna."""
        doc01 = self.env.ref('l10n_pe.document_type01')
        Serie = self.env['edi.invoice.series']
        s1 = Serie.create({
            'name': 'F101', 'l10n_latam_document_type_id': doc01.id,
            'name_nc': 'FC91', 'name_nd': 'FD91',
            'company_id': self.env.company.id})
        s2 = Serie.create({
            'name': 'F102', 'l10n_latam_document_type_id': doc01.id,
            'name_nc': 'FC92', 'name_nd': 'FD92',
            'company_id': self.env.company.id})
        (s1 | s2).action_publish()
        j_una = self.company_data['default_journal_sale'].copy({
            'name': 'Una serie', 'code': 'JUNA',
            'l10n_latam_use_documents': True,
            'use_name_sequence': True,
            'edi_series_ids': [(6, 0, s1.ids)]})
        j_dos = self.company_data['default_journal_sale'].copy({
            'name': 'Dos series', 'code': 'JDOS',
            'l10n_latam_use_documents': True,
            'use_name_sequence': True,
            'edi_series_ids': [(6, 0, (s1 | s2).ids)]})

        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'journal_id': j_una.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product_a.id,
                'quantity': 1, 'price_unit': 100.0,
                'tax_ids': [(6, 0, self.tax_sale_a.ids)]})],
        })
        # Una candidata → autoasignada
        self.assertEqual(move.edi_series_id, s1)
        # Cambio a diario con dos candidatas → se limpia (elección manual)
        move.journal_id = j_dos
        self.assertFalse(move.edi_series_id)
        move.edi_series_id = s2
        # Vuelta al diario de una sola serie → se reasigna la única válida
        move.journal_id = j_una
        self.assertEqual(move.edi_series_id, s1)

    def test_latam_journal_only_series(self):
        """Diario con documentos latam: las secuencias simples NO se crean
        ni se consideran — solo numeran las Series CPE; sin serie, el
        comprobante numera de forma nativa."""
        latam_journal = self.company_data['default_journal_sale'].copy({
            'name': 'Facturas seq', 'code': 'FSEQ',
            'l10n_latam_use_documents': True,
            'use_name_sequence': True,
            'name_sequence_prefix': 'F001-',
        })
        # No se autocrea la secuencia simple en diarios latam
        self.assertFalse(latam_journal.name_sequence_id)
        move = self._invoice(latam_journal)
        # Sin series CPE asignadas → numeración nativa latam
        self.assertTrue(move.name)
        self.assertNotEqual(move.name, 'F001-00000001')
