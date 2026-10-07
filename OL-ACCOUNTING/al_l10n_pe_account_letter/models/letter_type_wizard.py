# -*- coding: utf-8 -*-

from odoo import models, fields


class L10nPeLetterTypeWizard(models.TransientModel):
    _name = 'l10n_pe.letter.type.wizard'
    _description = 'Tipo de letra'

    # Solo los envíos al banco: el protesto tiene su propio asistente (con
    # asiento) y volver a cartera no es una operación del canje masivo.
    letter_type = fields.Selection(
        selection=[
            ('billing', 'Cobranza libre'),
            ('discount', 'Descuento'),
        ],
        string='Tipo de letra',
        default='billing',
        required=True,
    )
    date_canje = fields.Date(
        string='Fecha de canje', required=True, default=fields.Date.context_today)
    bank_id = fields.Many2one('res.bank', string='Banco', required=True)
    code = fields.Char(string='Código', required=True)
    letter_id = fields.Many2one(
        'l10n_pe.letter',
        string='Letra',
    )

    def action_multi_redeemed(self):
        massive_letter = self.env['l10n_pe.letter'].action_multi_redeemed(
            self.letter_type, self.date_canje, self.bank_id.id, self.code)

        return {
            'name': 'Canje masivo de letras',
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_pe.letter.massive',
            'res_id': massive_letter.id,
            'view_mode': 'form',
        }
