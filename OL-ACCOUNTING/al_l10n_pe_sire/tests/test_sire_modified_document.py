# -*- coding: utf-8 -*-
"""Comprobante modificado de una nota cuyo original no está en Odoo (R5)."""
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestSireModifiedDocument(TransactionCase):

    def test_manual_origin_in_sire_columns(self):
        doc_01 = self.env['l10n_latam.document.type'].search(
            [('code', '=', '01'), ('country_id.code', '=', 'PE')], limit=1)
        partner = self.env['res.partner'].create({'name': 'Cliente SIRE R5'})
        note = self.env['account.move'].create({
            'move_type': 'out_refund', 'partner_id': partner.id,
            'invoice_date': date(2026, 3, 16),
            'l10n_pe_origin_document_type_id': doc_01.id,
            'l10n_pe_origin_serie': 'F001', 'l10n_pe_origin_number': '815',
            'l10n_pe_origin_date': date(2024, 11, 20),
        })
        vals = self.env['l10n_pe.sire.rvie']._sire_reversed_doc_vals(note)
        self.assertEqual(vals, {
            'fecha_emision_mod': date(2024, 11, 20), 'tipo_cp_mod': '01',
            'serie_cp_mod': 'F001', 'nro_cp_mod': '815'})

    def test_without_origin_returns_nothing(self):
        partner = self.env['res.partner'].create({'name': 'Cliente SIRE R5 bis'})
        note = self.env['account.move'].create({
            'move_type': 'out_refund', 'partner_id': partner.id,
            'invoice_date': date(2026, 3, 16)})
        self.assertEqual(self.env['l10n_pe.sire.rvie']._sire_reversed_doc_vals(note), {})

    def test_customs_declaration_total(self):
        """DAM: el total es base + IGV (+ otros), no el amount_total de la
        factura, que excluye el valor en aduana llevado a la cuenta puente."""
        doc_50 = self.env['l10n_latam.document.type'].search(
            [('code', '=', '50'), ('country_id.code', '=', 'PE')], limit=1)
        igv = self.env['account.tax'].search(
            [('type_tax_use', '=', 'purchase'), ('amount', '=', 18.0),
             ('company_id', '=', self.env.company.id)], limit=1)
        if not doc_50 or not igv:
            self.skipTest('sin tipo 50 o IGV de compras')
        partner = self.env['res.partner'].create({'name': 'Aduana SIRE R5'})
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': partner.id,
            'invoice_date': date(2026, 3, 16),
            'l10n_latam_document_type_id': doc_50.id,
            'l10n_latam_document_number': '118-2026-10-204518',
            'invoice_line_ids': [
                (0, 0, {'name': 'Ad valorem', 'price_unit': 300.0, 'tax_ids': False}),
                (0, 0, {'name': 'Base', 'price_unit': 1000.0, 'tax_ids': [(6, 0, igv.ids)]}),
                (0, 0, {'name': 'Compensación', 'price_unit': -1000.0, 'tax_ids': False}),
            ],
        })
        igv_amount = sum(abs(line.balance) for line in bill.line_ids if line.tax_line_id)
        self.assertEqual(self.env['l10n_pe.sire.rce']._sire_total(bill), 1000.0 + igv_amount)
