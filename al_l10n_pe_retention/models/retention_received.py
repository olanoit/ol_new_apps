# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nPeRetentionReceived(models.Model):
    """Retenciones SUFRIDAS: un cliente agente de retención nos retuvo el
    3% y entregó su comprobante de retención. El registro genera el
    asiento (IGV retenido 40114 contra el cliente) y lo concilia con la
    factura, dejando el crédito listo para aplicar contra el IGV."""
    _name = 'l10n_pe.retention.received'
    _description = 'PE - Retención de IGV sufrida (cliente agente)'
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Nº comprobante de retención', required=True, size=24,
        help='Número del comprobante emitido por el cliente (R###-…).')
    date = fields.Date(
        string='Fecha del comprobante', required=True,
        default=fields.Date.context_today)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    partner_id = fields.Many2one(
        'res.partner', string='Cliente (agente de retención)', required=True)
    move_id = fields.Many2one(
        'account.move', string='Factura de venta', required=True,
        domain="[('move_type', '=', 'out_invoice'),"
               " ('state', '=', 'posted'),"
               " ('commercial_partner_id', '=', partner_id)]")
    amount = fields.Monetary(
        string='Monto retenido', required=True,
        help='3% del pago según el comprobante del cliente.')
    entry_id = fields.Many2one(
        'account.move', string='Asiento', readonly=True, copy=False)
    state = fields.Selection(
        [('draft', 'Borrador'), ('posted', 'Registrado')],
        default='draft', string='Estado', copy=False)

    @api.onchange('move_id')
    def _onchange_move_id(self):
        for record in self:
            if record.move_id and not record.amount:
                record.amount = record.company_id.currency_id.round(
                    abs(record.move_id.amount_total_signed)
                    * record.company_id.l10n_pe_retention_rate / 100.0)

    def action_post(self):
        for record in self:
            if record.state != 'draft':
                continue
            company = record.company_id
            account = company.l10n_pe_retention_received_account_id
            if not account:
                raise UserError(self.env._(
                    'Configure la «Cuenta de retenciones sufridas» '
                    '(40114) en Ajustes ▸ Perú.'))
            journal = (company.l10n_pe_retention_received_journal_id
                       or self.env['account.journal'].search(
                           [('company_id', '=', company.id),
                            ('type', '=', 'general')], limit=1))
            receivable = record.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type == 'asset_receivable'
                and not l.reconciled)
            entry = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': journal.id,
                'date': record.date,
                'ref': self.env._('Retención sufrida %(number)s',
                                  number=record.name),
                'line_ids': [
                    (0, 0, {'account_id': account.id,
                            'partner_id': record.partner_id.id,
                            'name': record.name,
                            'debit': record.amount, 'credit': 0.0}),
                    (0, 0, {'account_id':
                            receivable[:1].account_id.id
                            or record.partner_id.with_company(company)
                            .property_account_receivable_id.id,
                            'partner_id': record.partner_id.id,
                            'name': record.name,
                            'debit': 0.0, 'credit': record.amount}),
                ]})
            entry.action_post()
            entry_receivable = entry.line_ids.filtered(
                lambda l: l.credit > 0)
            if receivable:
                (receivable + entry_receivable).reconcile()
            record.write({'entry_id': entry.id, 'state': 'posted'})
        return True

    def action_draft(self):
        for record in self.filtered(lambda r: r.state == 'posted'):
            if record.entry_id:
                record.entry_id.button_draft()
                record.entry_id.button_cancel()
            record.write({'state': 'draft', 'entry_id': False})
        return True
