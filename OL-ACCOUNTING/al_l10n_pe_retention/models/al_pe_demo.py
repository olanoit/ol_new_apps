# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import Command, api, fields, models


class AlPeDemo(models.AbstractModel):
    _inherit = 'al.pe.demo'

    @api.model
    def _load_demo_retention(self):
        """La compañía demo como agente de retención: una compra de
        S/ 2 360 pagada con su comprobante de retención (S/ 70,80) y una venta
        de S/ 3 540 a un cliente agente con la retención que nos hizo
        (S/ 106,20). No se envía nada a SUNAT."""
        company = self._demo_company()
        if not company or self._demo_ref('al_l10n_pe_retention.demo_received'):
            return
        env = self._demo_env(company)
        tax_p, tax_s = self._demo_tax(env, 'purchase'), self._demo_tax(env, 'sale')
        if not company.l10n_pe_retention_tax_id or not tax_p or not tax_s:
            return
        Account = env['account.account']
        received = Account.search([*Account._check_company_domain(company), ('code', '=like', '40114%')], limit=1)
        outstanding = self._demo_account(env, 'al_l10n_pe_retention.demo_account_outstanding', '104901',
                                          'Pagos con retención pendientes', 'asset_current', reconcile=True)
        company.write({
            'l10n_pe_retention_agent': True,
            'l10n_pe_retention_received_account_id': company.l10n_pe_retention_received_account_id.id
            or received.id,
            'l10n_pe_retention_outstanding_account_id': company.l10n_pe_retention_outstanding_account_id.id
            or outstanding.id,
        })
        supplier = self._demo_partner(env, 'al_l10n_pe_retention.demo_supplier', 'Proveedor S.A.C.',
                                      self._demo_ruc('2060555111'))
        customer = self._demo_partner(env, 'al_l10n_pe_retention.demo_customer', 'Cliente Agente S.A.C.',
                                      self._demo_ruc('2060555222'), is_retention_agent=True,
                                      l10n_pe_padron_manual=True)
        purchase = self._demo_journal(env, 'al_l10n_pe_retention.demo_journal_purchase', 'Compras con retención', 'DRTC',
                                      'purchase')
        sale = self._demo_journal(env, 'al_l10n_pe_retention.demo_journal_sale', 'Ventas con retención', 'DRTV', 'sale')
        today = fields.Date.context_today(self)
        bill = self._demo_record('al_l10n_pe_retention.demo_bill', env['account.move'], {
            'move_type': 'in_invoice', 'partner_id': supplier.id, 'journal_id': purchase.id,
            'invoice_date': today - timedelta(days=10), 'ref': 'F001-00000901',
            'invoice_line_ids': [Command.create({'name': 'Servicio de mantenimiento', 'quantity': 1,
                                                 'price_unit': 2000.0, 'tax_ids': [Command.set(tax_p.ids)]})]})
        if bill.state == 'draft':
            bill.action_post()
        if bill.payment_state == 'not_paid':
            payment = env['account.payment.register'].with_context(
                active_model='account.move', active_ids=bill.ids).create({
                    'payment_date': today - timedelta(days=9),
                    'journal_id': self._demo_bank_journal(env).id})._create_payments()
            self._demo_xmlid('al_l10n_pe_retention.demo_payment', payment)
        invoice = self._demo_record('al_l10n_pe_retention.demo_invoice', env['account.move'], {
            'move_type': 'out_invoice', 'partner_id': customer.id, 'journal_id': sale.id,
            'invoice_date': today - timedelta(days=10),
            'invoice_line_ids': [Command.create({'name': 'Venta a cliente agente', 'quantity': 1,
                                                 'price_unit': 3000.0, 'tax_ids': [Command.set(tax_s.ids)]})]})
        if invoice.state == 'draft':
            invoice.action_post()
        self._demo_record('al_l10n_pe_retention.demo_received', env['l10n_pe.retention.received'], {
            'name': 'R777-00000055', 'date': today - timedelta(days=8), 'partner_id': customer.id,
            'line_ids': [Command.create({'move_id': invoice.id, 'amount': 106.20})]}).action_post()
