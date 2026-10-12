# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, api, fields, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_detraction(self):
        """Un servicio sujeto al SPOT (código 037, 12 %), una venta de
        S/ 5 900 con su detracción de S/ 708 y una compra de S/ 2 360 con el
        depósito de la detracción (S/ 283) y su constancia."""
        company = self._demo_company()
        if not company or self._demo_ref('al_l10n_pe_detraction.demo_bill'):
            return
        env = self._demo_env(company)
        Journal = env['account.journal']
        bank = self._demo_bank_journal(env)
        tax_s, tax_p = self._demo_tax(env, 'sale'), self._demo_tax(env, 'purchase')
        if not bank or not tax_s or not tax_p:
            return
        # Cuenta de detracciones en el Banco de la Nación (la pide el XML de la venta).
        self._demo_record('al_l10n_pe_detraction.demo_national_bank_account', env['res.partner.bank'], {
            'partner_id': company.partner_id.id, 'bank_id': env.ref('l10n_pe.peruvian_national_bank').id,
            'acc_number': '00-045-123456'})
        service = self._demo_record('al_l10n_pe_detraction.demo_product_service', env['product.product'], {
            'name': 'DEMO SPOT Servicio empresarial', 'type': 'service', 'default_code': 'DEMO-SPOT-01',
            'l10n_pe_detraction_type_id': env.ref('al_l10n_pe_detraction.detraction_037').id})
        partner = self._demo_partner(env, 'al_l10n_pe_detraction.demo_partner', 'DEMO SPOT Contraparte S.A.C.',
                                     self._demo_ruc('2060555333'))
        sale = self._demo_journal(env, 'al_l10n_pe_detraction.demo_journal_sale', 'DEMO SPOT Ventas', 'DSPV', 'sale')
        purchase = self._demo_journal(env, 'al_l10n_pe_detraction.demo_journal_purchase', 'DEMO SPOT Compras',
                                      'DSPC', 'purchase')
        today = fields.Date.context_today(self)

        def invoice(key, move_type, journal, tax, price, days_ago, ref=False):
            move = self._demo_record('al_l10n_pe_detraction.demo_%s' % key, env['account.move'], {
                'move_type': move_type, 'partner_id': partner.id, 'journal_id': journal.id,
                'invoice_date': today - timedelta(days=days_ago), 'ref': ref,
                'invoice_line_ids': [Command.create({'product_id': service.id, 'quantity': 1.0, 'price_unit': price,
                                                     'tax_ids': [Command.set(tax.ids)]})]})
            if move.state == 'draft':
                move.action_post()
            return move

        invoice('invoice', 'out_invoice', sale, tax_s, 5000.0, 12)
        bill = invoice('bill', 'in_invoice', purchase, tax_p, 2000.0, 11, ref='F001-00000888')
        if not bill.l10n_pe_detraction_number:
            env['l10n_pe.detraction.deposit.wizard'].create({
                'move_id': bill.id, 'journal_id': bank.id, 'payment_date': today - timedelta(days=10),
                'constancy_number': 'DEMO-%s-0001' % today.year}).action_confirm()
