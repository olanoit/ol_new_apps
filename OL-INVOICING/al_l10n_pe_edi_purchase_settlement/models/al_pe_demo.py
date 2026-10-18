# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, api, fields, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_purchase_settlement(self):
        """Una productora de café sin RUC y dos liquidaciones de compra:
        café pergamino por S/ 11 875 (retiene IGV y 1,5 % de renta,
        confirmada y por enviar) y una compra menor en borrador. No se envía
        nada a SUNAT."""
        company = self._demo_company()
        if not company or self._demo_ref('al_l10n_pe_edi_purchase_settlement.demo_settlement_2'):
            return
        env = self._demo_env(company)
        Journal = env['account.journal']
        journal = Journal.search([*Journal._check_company_domain(company), ('l10n_pe_lce_journal', '=', True)],
                                 limit=1)
        igv = self._demo_tax(env, 'purchase')
        if not journal or not igv:
            return
        kg = env.ref('uom.product_uom_kgm')
        district = env.ref('l10n_pe.district_pe_100103')
        seller = self._demo_partner(
            env, 'al_l10n_pe_edi_purchase_settlement.demo_seller', 'Quispe Mamani Juana', '45612378',
            street='Caserío Santa Rosa, parcela 14', state_id=district.city_id.state_id.id,
            city_id=district.city_id.id, l10n_pe_district=district.id)
        Product = env['product.product']
        coffee = self._demo_record('al_l10n_pe_edi_purchase_settlement.demo_product_coffee', Product, {
            'name': 'Café pergamino', 'default_code': 'CAFE-PERG', 'type': 'consu', 'uom_id': kg.id,
            'supplier_taxes_id': [Command.set(igv.ids)]})
        self._demo_record('al_l10n_pe_edi_purchase_settlement.demo_product_gold', Product, {
            'name': 'Oro en bruto', 'default_code': 'ORO-BRUTO', 'type': 'consu', 'l10n_pe_lce_gold': True,
            'supplier_taxes_id': [Command.set(igv.ids)]})
        day = fields.Date.context_today(self) - timedelta(days=7)
        for key, quantity, price, post in (('1', 1250.0, 9.5, True), ('2', 60.0, 10.0, False)):
            move = self._demo_record('al_l10n_pe_edi_purchase_settlement.demo_settlement_%s' % key,
                                     env['account.move'], {
                'move_type': 'in_invoice', 'journal_id': journal.id, 'partner_id': seller.id,
                'invoice_date': day, 'date': day, 'ref': 'LC-%s' % key,
                'l10n_pe_lce_place_type': '02', 'l10n_pe_lce_partner_address_type': '02',
                'l10n_pe_lce_license_plate': 'B2C845' if post else False,
                'invoice_line_ids': [Command.create({
                    'product_id': coffee.id, 'name': 'Café pergamino seco, humedad 12 %', 'quantity': quantity,
                    'product_uom_id': kg.id, 'price_unit': price, 'tax_ids': [Command.set(igv.ids)]})],
            })
            move._l10n_pe_lce_sync_taxes()
            if post and move.state == 'draft':
                move.action_post()
