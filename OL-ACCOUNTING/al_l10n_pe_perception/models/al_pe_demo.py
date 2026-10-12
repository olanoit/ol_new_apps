# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, api, fields, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_perception(self):
        """Agente de percepción con tres ventas de cemento y fierro, dos
        cobradas con su comprobante de percepción, y dos percepciones
        sufridas: la de un proveedor agente y la de una importación (DAM)."""
        company = self._demo_company()
        if not company or self._demo_ref('al_l10n_pe_perception.demo_received_import'):
            return
        env = self._demo_env(company)
        misc = env['account.journal'].search([*env['account.journal']._check_company_domain(company),
                                              ('type', '=', 'general')], limit=1)
        igv, igv_p = self._demo_tax(env, 'sale'), self._demo_tax(env, 'purchase')
        if not misc or not igv or not igv_p:
            return
        payable = self._demo_account(env, 'al_l10n_pe_perception.demo_account_payable', '401132',
                                     'IGV percepciones por pagar', 'liability_current')
        to_apply = self._demo_account(env, 'al_l10n_pe_perception.demo_account_to_apply', '401131',
                                      'IGV percepciones por aplicar', 'asset_current')
        company.write({
            'l10n_pe_perception_agent': True, 'l10n_pe_perception_fuel_agent': False,
            'l10n_pe_perception_account_id': payable.id, 'l10n_pe_perception_journal_id': misc.id,
            'l10n_pe_perception_received_account_id': to_apply.id,
            'l10n_pe_perception_received_journal_id': misc.id,
        })
        address = {'street': 'Av. Industrial 123', 'city': 'Lima'}
        customer = self._demo_partner(env, 'al_l10n_pe_perception.demo_customer',
                                      'DEMO PER Ferretería Los Andes S.A.C.', self._demo_ruc('2060123459'), **address)
        agent_customer = self._demo_partner(env, 'al_l10n_pe_perception.demo_agent_customer',
                                            'DEMO PER Distribuidora Agente S.A.C.', self._demo_ruc('2060123460'),
                                            l10n_pe_is_perception_agent=True, **address)
        supplier = self._demo_partner(env, 'al_l10n_pe_perception.demo_supplier', 'DEMO PER Cementos del Sur S.A.C.',
                                      self._demo_ruc('2060123461'), l10n_pe_is_perception_agent=True, **address)
        customs = self._demo_partner(env, 'al_l10n_pe_perception.demo_customs', 'DEMO PER SUNAT Aduanas',
                                     is_company=True)
        Product = env['product.product']

        def product(key, name, price):
            return self._demo_record('al_l10n_pe_perception.demo_product_%s' % key, Product, {
                'name': name, 'type': 'consu', 'lst_price': price, 'l10n_pe_perception_type': 'internal',
                'taxes_id': [Command.set(igv.ids)], 'supplier_taxes_id': [Command.set(igv_p.ids)]})

        cement = product('cement', 'DEMO PER Cemento Portland tipo I (bolsa 42,5 kg)', 28.0)
        rod = product('rod', 'DEMO PER Fierro corrugado 1/2"', 45.0)
        sale = self._demo_journal(env, 'al_l10n_pe_perception.demo_journal_sale', 'DEMO PER Ventas', 'DPEV', 'sale')
        purchase = self._demo_journal(env, 'al_l10n_pe_perception.demo_journal_purchase', 'DEMO PER Compras', 'DPEC',
                                      'purchase')
        today = fields.Date.context_today(self)
        bank = self._demo_bank_journal(env)
        Move = env['account.move']

        def invoice(key, partner, lines, days_ago):
            move = self._demo_record('al_l10n_pe_perception.demo_invoice_%s' % key, Move, {
                'move_type': 'out_invoice', 'partner_id': partner.id, 'journal_id': sale.id,
                'invoice_date': today - timedelta(days=days_ago),
                'invoice_line_ids': [Command.create({'product_id': p.id, 'quantity': q, 'price_unit': p.lst_price,
                                                     'tax_ids': [Command.set(igv.ids)]}) for p, q in lines]})
            if move.state == 'draft':
                move.action_post()
            return move

        def collect(key, move, days_ago):
            payment = env['account.payment.register'].with_context(
                active_model='account.move', active_ids=move.ids).create({
                    'payment_date': today - timedelta(days=days_ago), 'journal_id': bank.id,
                    'amount': round(move.amount_total + move.l10n_pe_perception_amount, 2),
                    'payment_difference_handling': 'open'})._create_payments()
            perception = env['l10n_pe.perception'].browse(payment.action_l10n_pe_create_perception()['res_id'])
            perception.action_post()
            self._demo_xmlid('al_l10n_pe_perception.demo_perception_%s' % key, perception)

        inv1 = invoice('1', customer, [(cement, 100), (rod, 20)], 30)
        inv2 = invoice('2', agent_customer, [(cement, 300)], 27)
        invoice('3', customer, [(rod, 40)], 22)
        if not self._demo_ref('al_l10n_pe_perception.demo_perception_1'):
            collect('1', inv1, 17)
        if not self._demo_ref('al_l10n_pe_perception.demo_perception_2'):
            collect('2', inv2, 12)
        bill = self._demo_record('al_l10n_pe_perception.demo_bill', Move, {
            'move_type': 'in_invoice', 'partner_id': supplier.id, 'journal_id': purchase.id,
            'invoice_date': today - timedelta(days=32), 'ref': 'DEMO PER C-1',
            'invoice_line_ids': [Command.create({'product_id': cement.id, 'quantity': 500, 'price_unit': 22.0,
                                                 'tax_ids': [Command.set(igv_p.ids)]})]})
        if bill.state == 'draft':
            bill.action_post()
        Received = env['l10n_pe.perception.received']
        self._demo_record('al_l10n_pe_perception.demo_received_supplier', Received, {
            'partner_id': supplier.id, 'kind': 'internal', 'document_kind': 'cpe', 'name': 'P001-00004521',
            'date': today - timedelta(days=25),
            'line_ids': [Command.create({'bill_id': bill.id, 'base_amount': bill.amount_total,
                                         'amount': round(bill.amount_total * 0.02, 2)})]}).action_post()
        self._demo_record('al_l10n_pe_perception.demo_received_import', Received, {
            'partner_id': customs.id, 'kind': 'import', 'document_kind': 'dua',
            'name': '118-%s-10-045678' % today.year, 'date': today - timedelta(days=19),
            'line_ids': [Command.create({'reference': 'DAM 118-%s-10-045678' % today.year,
                                         'base_amount': 42000.0, 'amount': 1470.0})]}).action_post()
