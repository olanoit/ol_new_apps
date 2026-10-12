# -*- coding: utf-8 -*-
"""DUA de importación: liquidación, número de la DAM, percepción aduanera y
costos en destino (criterios de R4 en docs/md/analisis_integral_proyecto.md)."""
from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestImportDua(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customs = cls.env['res.partner'].create({
            'name': 'SUNAT - Aduanas (test)', 'is_company': True,
            'country_id': cls.env.ref('base.pe').id,
            'l10n_latam_identification_type_id': cls.env.ref('l10n_pe.it_RUC').id,
            'vat': '20131312955'})
        # Código propio de la prueba (la demo ya crea la 609190 en la base).
        cls.offset = cls.env['account.account'].create({
            'name': 'Valor en aduana por regularizar (test)', 'code': '609199',
            'account_type': 'expense', 'reconcile': False})
        cls.company.write({'l10n_pe_dua_partner_id': cls.customs.id,
                           'l10n_pe_dua_offset_account_id': cls.offset.id})
        cls.journal = cls.env['account.journal'].search([
            *cls.env['account.journal']._check_company_domain(cls.company),
            ('type', '=', 'purchase'), ('l10n_latam_use_documents', '=', True)], limit=1)
        cls.dua_type = cls.env.ref('l10n_pe.document_type50')
        cls.igv = cls.env['account.chart.template'].ref('purchase_tax_igv_18')

    def _dua(self, **vals):
        return self.env['account.move'].create(dict({
            'move_type': 'in_invoice',
            'partner_id': self.customs.id,
            'journal_id': self.journal.id,
            'l10n_latam_document_type_id': self.dua_type.id,
            'invoice_date': fields.Date.from_string('2026-10-05'),
            'l10n_pe_dua_customs_code': '118',
            'l10n_pe_dua_year': '2026',
            'l10n_pe_dua_regime': '10',
            'l10n_pe_dua_sequence': '12345',
            'l10n_pe_dua_customs_value': 10000.0,
            'l10n_pe_dua_ad_valorem': 600.0,
            'l10n_pe_dua_other_duties': 100.0,
        }, **vals))

    def test_liquidation_lines_and_totals(self):
        dua = self._dua()
        self.assertTrue(dua.l10n_pe_dua_is_dua)
        self.assertEqual(dua.l10n_latam_document_number, '118-2026-10-012345')
        dua.action_l10n_pe_dua_generate_lines()
        self.assertEqual(dua.l10n_pe_dua_igv_tax_id, self.igv)
        self.assertAlmostEqual(dua.l10n_pe_dua_tax_base, 10700.0)
        # Base 10 700 × 18 % = 1 926 de IGV (crédito fiscal); la DUA suma lo
        # que se paga a la Aduana: derechos 700 + IGV 1 926.
        self.assertAlmostEqual(dua.amount_tax, 1926.0)
        self.assertAlmostEqual(dua.amount_total, 2626.0)
        tax_line = dua.line_ids.filtered('tax_line_id')
        self.assertAlmostEqual(abs(tax_line.tax_base_amount), 10700.0)
        duties = dua.invoice_line_ids.filtered('is_landed_costs_line')
        self.assertEqual(set(duties.mapped('l10n_pe_dua_line_kind')), {'ad_valorem', 'other'})
        # Regenerar no duplica.
        dua.action_l10n_pe_dua_generate_lines()
        self.assertEqual(len(dua.invoice_line_ids.filtered('l10n_pe_dua_line_kind')), 4)

    def test_dam_number_validation(self):
        with self.assertRaises(ValidationError):
            self._dua(l10n_pe_dua_customs_code='11A')

    def test_generate_requires_offset_account(self):
        self.company.l10n_pe_dua_offset_account_id = False
        with self.assertRaises(UserError):
            self._dua().action_l10n_pe_dua_generate_lines()

    def test_customs_perception_registered(self):
        if 'l10n_pe.perception.received' not in self.env:
            self.skipTest('al_l10n_pe_perception no está instalado')
        if not self.company.l10n_pe_perception_received_account_id:
            self.company.l10n_pe_perception_received_account_id = self.env['account.account'].create({
                'name': 'Percepciones por aplicar (test)', 'code': '401190',
                'account_type': 'asset_current'})
        dua = self._dua(l10n_pe_dua_perception=441.11)
        dua.action_l10n_pe_dua_generate_lines()
        dua.action_post()
        self.assertEqual(dua.l10n_pe_dua_perception_count, 1)
        perception = dua._l10n_pe_dua_perceptions()
        self.assertEqual((perception.kind, perception.document_kind, perception.state),
                         ('import', 'dua', 'posted'))
        self.assertAlmostEqual(perception.amount, 441.11)
        # Volver a publicar (p. ej. tras pasar a borrador) no la duplica.
        dua.button_draft()
        dua.action_post()
        self.assertEqual(len(dua._l10n_pe_dua_perceptions()), 1)

    def test_foreign_invoice_link(self):
        supplier = self.env['res.partner'].create({
            'name': 'Proveedor del exterior (test)', 'country_id': self.env.ref('base.us').id})
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': supplier.id,
            'invoice_date': fields.Date.from_string('2026-10-01'),
            'invoice_line_ids': [Command.create({'name': 'Mercadería', 'price_unit': 2800.0,
                                                 'tax_ids': [Command.clear()]})]})
        dua = self._dua()
        dua.l10n_pe_dua_foreign_invoice_ids = invoice
        self.assertEqual(invoice.l10n_pe_dua_invoice_id, dua)
        dua.l10n_pe_dua_foreign_invoice_ids = False
        self.assertFalse(invoice.l10n_pe_dua_invoice_id)

    def test_landed_costs_from_dua_and_customs_expense(self):
        category = self.env['product.category'].create({
            'name': 'Importados (test)', 'property_cost_method': 'average',
            'property_valuation': 'real_time'})
        product = self.env['product.product'].create({
            'name': 'Equipo importado (test)', 'is_storable': True, 'categ_id': category.id,
            'standard_price': 100.0})
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'), ('company_id', '=', self.company.id)], limit=1)
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': self.env.ref('stock.stock_location_suppliers').id,
            'location_dest_id': picking_type.default_location_dest_id.id,
            'move_ids': [Command.create({
                'product_id': product.id, 'product_uom_qty': 10.0, 'price_unit': 100.0,
                'location_id': self.env.ref('stock.stock_location_suppliers').id,
                'location_dest_id': picking_type.default_location_dest_id.id})]})
        picking.action_confirm()
        picking.move_ids.quantity = 10.0
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        agent = self.env['res.partner'].create({'name': 'Agente de aduana (test)'})
        plain_journal = self.env['account.journal'].create({
            'name': 'Gastos de importación (test)', 'code': 'GIMT', 'type': 'purchase',
            'l10n_latam_use_documents': False})
        expense = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': agent.id, 'journal_id': plain_journal.id,
            'invoice_date': fields.Date.from_string('2026-10-06'),
            'invoice_line_ids': [Command.create({
                'product_id': self.env.ref('al_l10n_pe_import_dua.product_dua_other').id,
                'name': 'Comisión del agente de aduana', 'price_unit': 200.0,
                'tax_ids': [Command.clear()]})]})
        expense.action_post()
        dua = self._dua(l10n_pe_dua_picking_ids=[Command.set(picking.ids)],
                        l10n_pe_dua_expense_move_ids=[Command.set(expense.ids)],
                        l10n_pe_dua_split_method='by_quantity')
        dua.action_l10n_pe_dua_generate_lines()
        dua.action_post()
        action = dua.action_l10n_pe_dua_create_landed_costs()
        landed = self.env['stock.landed.cost'].browse(action['res_id'])
        self.assertEqual(landed.vendor_bill_id, dua)
        self.assertEqual(landed.picking_ids, picking)
        # 600 ad valorem + 100 otros derechos + 200 agente = 900 al costo.
        self.assertAlmostEqual(landed.amount_total, 900.0)
        self.assertAlmostEqual(
            sum(landed.valuation_adjustment_lines.mapped('additional_landed_cost')), 900.0)
        self.assertEqual(set(landed.cost_lines.mapped('split_method')), {'by_quantity'})

    def test_landed_costs_require_posted_dua_and_pickings(self):
        dua = self._dua()
        with self.assertRaises(UserError):
            dua.action_l10n_pe_dua_create_landed_costs()

    def test_form_onchange_builds_number(self):
        form = Form(self.env['account.move'].with_context(default_move_type='in_invoice'))
        form.partner_id = self.customs
        form.journal_id = self.journal
        form.l10n_latam_document_type_id = self.dua_type
        form.invoice_date = fields.Date.from_string('2026-10-05')
        form.l10n_pe_dua_customs_code = '235'
        form.l10n_pe_dua_year = '2026'
        form.l10n_pe_dua_regime = '10'
        form.l10n_pe_dua_sequence = '987'
        self.assertEqual(form.l10n_latam_document_number, '235-2026-10-000987')
