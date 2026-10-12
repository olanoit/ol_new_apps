# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError

from .perception import INVOICE_TO_CPE


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    l10n_pe_perception_ids = fields.One2many(
        'l10n_pe.perception', 'payment_id', string='Comprobantes de percepción', readonly=True)
    l10n_pe_perception_count = fields.Integer(
        string='Nº de comprobantes de percepción', compute='_compute_l10n_pe_perception_count')

    def _compute_l10n_pe_perception_count(self):
        for payment in self:
            payment.l10n_pe_perception_count = len(payment.l10n_pe_perception_ids)

    def _l10n_pe_perception_paid_by_invoice(self):
        """Lo que este cobro pagó de cada factura sujeta, en la moneda de la
        factura (conciliaciones parciales del cobro)."""
        self.ensure_one()
        paid = {}
        lines = self.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable')
        for partial in lines.matched_debit_ids:
            invoice = partial.debit_move_id.move_id
            if invoice.move_type == 'out_invoice' and invoice.l10n_pe_perception_code:
                paid[invoice] = paid.get(invoice, 0.0) + partial.debit_amount_currency
        if not paid:
            # cobro sin asiento propio (v19, hasta conciliar el extracto)
            for invoice in self.reconciled_invoice_ids.filtered('l10n_pe_perception_code'):
                paid[invoice] = invoice.amount_total
        return paid

    def action_l10n_pe_create_perception(self):
        """«Comprobante de percepción»: borrador con lo que este cobro pagó de
        cada factura sujeta, uno por tasa (art. 10.4)."""
        self.ensure_one()
        if self.payment_type != 'inbound' or self.partner_type != 'customer':
            raise UserError(self.env._('El comprobante de percepción sale de un cobro a cliente.'))
        paid = self._l10n_pe_perception_paid_by_invoice()
        if not paid:
            raise UserError(self.env._(
                'El cobro no está conciliado con facturas sujetas a percepción. Concílielo o '
                'emita el comprobante desde las facturas de venta.'))
        by_code = {}
        for invoice, amount in paid.items():
            by_code.setdefault(INVOICE_TO_CPE[invoice.l10n_pe_perception_code], []).append(
                (invoice, amount))
        perceptions = self.env['l10n_pe.perception']
        for code, entries in by_code.items():
            perceptions |= perceptions.create({
                'company_id': self.company_id.id,
                'partner_id': self.partner_id.commercial_partner_id.id,
                'payment_id': self.id,
                'date': self.date,
                'perception_code': code,
                'line_ids': [(0, 0, {'invoice_id': invoice.id, 'paid_amount': amount})
                             for invoice, amount in entries],
            })
        if len(perceptions) == 1:
            return perceptions._l10n_pe_perception_open(perceptions)
        return self.action_l10n_pe_view_perceptions()

    def action_l10n_pe_view_perceptions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Comprobantes de percepción'),
            'res_model': 'l10n_pe.perception',
            'view_mode': 'list,form',
            'domain': [('payment_id', '=', self.id)],
        }
