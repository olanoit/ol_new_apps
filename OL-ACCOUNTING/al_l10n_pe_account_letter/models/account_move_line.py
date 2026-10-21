# -*- coding: utf-8 -*-

from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_pe_letter_line_id = fields.Many2one('l10n_pe.letter.line', string='Letra canjeada')

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
        string='N.º de documento',
        related='partner_id.vat',
    )

    def _l10n_pe_payment_block_reason(self):
        """Una letra en el banco (cobranza libre o descuento) la cobra el banco:
        se cancela con «Cobro del banco» (o la liquidación del descuento), no
        con un pago directo. Protestada, vuelve a la empresa y se puede cobrar."""
        letter_line = self.l10n_pe_letter_line_id
        if (letter_line and letter_line.move_invoice_type == 'out_invoice'
                and letter_line.letter_type in ('billing', 'discount') and not self.reconciled):
            kind = dict(letter_line._fields['letter_type']._description_selection(self.env))[letter_line.letter_type]
            return self.env._(
                'La letra %(letter)s está en %(bank)s (%(kind)s): la cobra el banco. Regístrela con '
                '«Cobro del banco» en el canje de letras cuando el banco abone, o con «Protesto» si '
                'no se pagó.',
                letter=letter_line.nro_letter or letter_line.display_name,
                bank=letter_line.bank_id.name or self.env._('el banco'), kind=kind.lower())
        return super()._l10n_pe_payment_block_reason()
