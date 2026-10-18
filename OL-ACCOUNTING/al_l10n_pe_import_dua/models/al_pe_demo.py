# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, api, fields, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_import_dua(self):
        """Importación de diez motobombas: recepción, factura del proveedor
        del exterior, gastos del agente de aduana y la DAM con sus derechos,
        publicada y con el costo en destino de la mercadería."""
        company = self._demo_company()
        if not company or self._demo_ref('al_l10n_pe_import_dua.demo_dua'):
            return
        env = self._demo_env(company)
        Journal = env['account.journal']
        journal = Journal.search([*Journal._check_company_domain(company), ('type', '=', 'purchase'),
                                  ('l10n_latam_use_documents', '=', True)], limit=1)
        picking_type = env['stock.picking.type'].search([('code', '=', 'incoming'),
                                                         ('company_id', '=', company.id)], limit=1)
        if not journal or not picking_type:
            return
        customs = self._demo_partner(env, 'al_l10n_pe_import_dua.demo_customs',
                                     'SUNAT - Superintendencia Nacional de Aduanas', '20131312955')
        offset = self._demo_account(env, 'al_l10n_pe_import_dua.demo_account_offset', '609190',
                                    'Valor en aduana por regularizar', 'expense')
        company.write({'l10n_pe_dua_partner_id': customs.id, 'l10n_pe_dua_offset_account_id': offset.id,
                       'l10n_pe_dua_journal_id': journal.id})
        category = self._demo_record('al_l10n_pe_import_dua.demo_category', env['product.category'], {
            'name': 'Productos importados', 'property_cost_method': 'average', 'property_valuation': 'real_time'})
        product = self._demo_record('al_l10n_pe_import_dua.demo_product', env['product.product'], {
            'name': 'Motobomba importada', 'is_storable': True, 'categ_id': category.id,
            'standard_price': 1000.0, 'weight': 45.0})
        supplier = self._demo_record('al_l10n_pe_import_dua.demo_supplier', env['res.partner'], {
            'name': 'Pumps Inc.', 'is_company': True, 'country_id': env.ref('base.us').id})
        agent = self._demo_partner(env, 'al_l10n_pe_import_dua.demo_agent', 'Agencia de Aduanas S.A.C.',
                                   self._demo_ruc('2060555444'))
        today = fields.Date.context_today(self)
        suppliers_location = env.ref('stock.stock_location_suppliers')
        destination = picking_type.default_location_dest_id
        picking = self._demo_record('al_l10n_pe_import_dua.demo_picking', env['stock.picking'], {
            'picking_type_id': picking_type.id, 'partner_id': supplier.id, 'origin': 'DUA 118-2026',
            'location_id': suppliers_location.id, 'location_dest_id': destination.id,
            'move_ids': [Command.create({'product_id': product.id, 'product_uom_qty': 10.0, 'price_unit': 1000.0,
                                         'location_id': suppliers_location.id, 'location_dest_id': destination.id})]})
        picking.action_confirm()
        picking.move_ids.quantity = 10.0
        picking.button_validate()
        foreign = self._demo_record('al_l10n_pe_import_dua.demo_foreign_invoice', env['account.move'], {
            'move_type': 'in_invoice', 'partner_id': supplier.id, 'ref': 'INV-118',
            'invoice_date': today - timedelta(days=11),
            'invoice_line_ids': [Command.create({'product_id': product.id, 'quantity': 10.0, 'price_unit': 1000.0,
                                                 'tax_ids': [Command.clear()]})]})
        plain = self._demo_journal(env, 'al_l10n_pe_import_dua.demo_journal_expenses',
                                   'Gastos de importación', 'DGIM', 'purchase')
        expense = self._demo_record('al_l10n_pe_import_dua.demo_agent_bill', env['account.move'], {
            'move_type': 'in_invoice', 'partner_id': agent.id, 'journal_id': plain.id,
            'invoice_date': today - timedelta(days=6), 'ref': 'Servicios de agenciamiento',
            'invoice_line_ids': [Command.create({'product_id': env.ref('al_l10n_pe_import_dua.product_dua_other').id,
                                                 'name': 'Comisión y gastos operativos del agente de aduana',
                                                 'price_unit': 350.0, 'tax_ids': [Command.clear()]})]})
        expense.action_post()
        dua = self._demo_record('al_l10n_pe_import_dua.demo_dua', env['account.move'], {
            'move_type': 'in_invoice', 'partner_id': customs.id, 'journal_id': journal.id,
            'l10n_latam_document_type_id': env.ref('l10n_pe.document_type50').id,
            'invoice_date': today - timedelta(days=7),
            'l10n_pe_dua_customs_code': '118', 'l10n_pe_dua_year': str(today.year), 'l10n_pe_dua_regime': '10',
            'l10n_pe_dua_sequence': '204518',
            'l10n_pe_dua_customs_value': 37450.0, 'l10n_pe_dua_ad_valorem': 2247.0,
            'l10n_pe_dua_other_duties': 120.0, 'l10n_pe_dua_perception': 1633.15,
            'l10n_pe_dua_picking_ids': [Command.set(picking.ids)],
            'l10n_pe_dua_expense_move_ids': [Command.set(expense.ids)],
            'l10n_pe_dua_split_method': 'by_quantity'})
        dua.l10n_pe_dua_foreign_invoice_ids = foreign
        dua.action_l10n_pe_dua_generate_lines()
        dua.action_post()
        dua.action_l10n_pe_dua_create_landed_costs()
