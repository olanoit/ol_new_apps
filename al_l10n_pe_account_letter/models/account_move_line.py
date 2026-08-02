# -*- coding: utf-8 -*-

from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_pe_letter_line_id = fields.Many2one('l10n_pe.letter.line')

    l10n_pe_letter_invoice_line_id = fields.Many2one(
        'l10n_pe.letter.invoice.line',
        string='Pago',
        ondelete='set null',
    )
    l10n_pe_letter_id = fields.Many2one(
        'l10n_pe.letter',
        string='Letra',
    )
    l10n_pe_partner_vat = fields.Char(
        string='Vat',
        related='partner_id.vat',
    )
