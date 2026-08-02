# -*- coding: utf-8 -*-

from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_pe_letter_redeemed_state = fields.Selection(
        string='Estado de canje',
        selection=[
            ('not_redeemed', 'No canjeado'),
            ('redeemed', 'Canjeado'),
        ],
        default='not_redeemed',
    )
    l10n_pe_letter_id = fields.Many2one(
        'l10n_pe.letter',
        string='Letra', ondelete='set null'
    )
    l10n_pe_letter_ids = fields.Many2many('l10n_pe.letter', 'account_move_letter_rel',
                                          'move_id', 'letter_id', string='Letras')

    l10n_pe_letter_name = fields.Char(
        string='Nombre de la letra',
        related='l10n_pe_letter_id.name',
    )

    # Método para el botón de abrir el canje relacionado
    def action_open_letter(self):
        return {
            'name': 'Canje',
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_pe.letter',
            'view_mode': 'form',
            'res_id': self.l10n_pe_letter_id.id,
            'target': 'new',
        }

    def action_open_letters(self):
        return {
            'name': 'Canjes',
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_pe.letter',
            'view_mode': 'list',
            'domain': [('id', 'in', self.l10n_pe_letter_ids.ids)],
            'target': 'new',
        }
