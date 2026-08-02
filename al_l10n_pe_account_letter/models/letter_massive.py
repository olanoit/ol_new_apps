# -*- coding: utf-8 -*-

from odoo import models, fields, api


class L10nPeLetterMassive(models.Model):
    _name = 'l10n_pe.letter.massive'
    _inherit = 'l10n_pe.letter'
    _description = 'Gestión de letras masivas'

    canje_move_ids = fields.Many2many('account.move', 'account_letter_move_massive_canje_rel', 'letter_id', 'move_id',
                                      string='Asientos de canje', readonly=True)

    letter_invoices_ids = fields.Many2many(
        'l10n_pe.letter.invoice.line',
        string='Facturas',
    )
    letter_move_ids = fields.Many2many(
        'l10n_pe.letter.line',
        string='Letras',
    )

    refinance_origin_ids = fields.Many2many(
        'l10n_pe.letter',
        string='Canjes de origen',
        compute='_compute_massive_refinance_origin_ids',
        readonly=True,
    )

    @api.depends('inverse_id', 'is_refinance_children')
    def _compute_massive_refinance_origin_ids(self):
        for record in self:
            if not record.id:
                record.refinance_origin_ids = False
                continue
            parent_record = self.env['l10n_pe.letter'].browse(record.id)
            record.refinance_origin_ids = parent_record.refinance_origin_ids

    @api.depends('letter_line_ids', 'letter_move_ids')
    def _compute_is_banked(self):
        for record in self:
            if record.is_massive_letter:
                letter_line = record.letter_move_ids
            else:
                letter_line = record.letter_line_ids
            if record.state == 'redeemed' and letter_line:
                all_banked = all(letter.bank_id for letter in letter_line)
                all_code = all(letter.code for letter in letter_line)
                all_letter_type = all(letter.letter_type for letter in letter_line)
                if all_banked and all_code and all_letter_type:
                    record.state = 'banked'
                else:
                    record.state = 'redeemed'

    @api.depends('invoice_line_ids.invoice_name', 'letter_invoices_ids.invoice_name')
    def _compute_related_invoice_names(self):
        for record in self:
            if record.invoice_line_ids:
                invoice_names = record.invoice_line_ids.mapped('invoice_name')
                record.related_invoice_names = '-'.join(invoice_names)
            elif record.letter_invoices_ids:
                invoice_names = record.letter_invoices_ids.mapped('invoice_name')
                record.related_invoice_names = '-'.join(invoice_names)
            else:
                record.related_invoice_names = False

    def action_open_related_massive_invoices(self):
        self.ensure_one()
        invoices = self.mapped('letter_invoices_ids.move_line_id.move_id')
        if self.type == 'out_invoice':
            action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        else:
            action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_in_invoice_type")
        if len(invoices) > 0:
            action['domain'] = [('id', 'in', invoices.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    related_massive_invoice_count = fields.Integer(
        string='Facturas relacionadas',
        compute='_compute_related_massive_invoice_count',
        store=True
    )

    @api.depends('letter_invoices_ids')
    def _compute_related_massive_invoice_count(self):
        for record in self:
            record.related_massive_invoice_count = len(record.letter_invoices_ids)
