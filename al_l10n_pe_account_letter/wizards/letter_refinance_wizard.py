# -*- coding: utf-8 -*-

from odoo import models, fields, api


class L10nPeLetterRefinanceWizard(models.TransientModel):
    _name = 'l10n_pe.letter.refinance.wizard'
    _description = 'Factura refinanciada'

    letter_id = fields.Many2one(
        'l10n_pe.letter',
        string='Letra',
    )
    refinance_date = fields.Date(
        string='Fecha de refinanciación',
        required=True,
    )

    def create_refinance(self):
        letter_id = self.letter_id
        refinance_date = self.refinance_date
        created_refinance_letter = self.env['l10n_pe.letter'].create_refinance(letter_id, refinance_date)

        return {
            'name': 'Canje de letra refinanaciada',
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_pe.letter',
            'res_id': created_refinance_letter.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # Restriccion de la fecha de refinanciación
    @api.onchange('refinance_date')
    def _onchange_refinance_date(self):
        if self.refinance_date:
            min_date = min(self.letter_id.invoice_line_ids.move_line_id.mapped('date'), default=False)
            if min_date and self.refinance_date < min_date:
                return {
                    'warning': {
                        'title': 'Advertencia',
                        'message': f'La fecha de refinanciamiento no puede ser menor que la mínima fecha de pago en las líneas de factura ({min_date}).',
                    },
                    'value': {
                        'refinance_date': min_date,
                    }
                }
