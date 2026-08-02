# -*- coding: utf-8 -*-

from odoo import models, fields


class L10nPeLetterTypeWizard(models.TransientModel):
    _name = 'l10n_pe.letter.type.wizard'
    _description = 'Tipo de letra'

    letter_type = fields.Selection(
        selection=[
            ('portfolio', 'En cartera'),
            ('billing', 'Cobranza libre'),
            ('discount', 'Descuento'),
            ('protested', 'Protestada'),
        ],
        string='Tipo de letra',
    )
    letter_id = fields.Many2one(
        'l10n_pe.letter',
        string='Letra',
    )

    def action_multi_redeemed(self):
        massive_letter = self.letter_id.action_multi_redeemed(self.letter_type)

        return {
            'name': 'Canje masivo de letras',
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_pe.letter.massive',
            'res_id': massive_letter.id,
            'view_mode': 'form',
        }
