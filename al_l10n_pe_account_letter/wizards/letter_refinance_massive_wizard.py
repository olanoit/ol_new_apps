# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class L10nPeLetterRefinanceMassiveWizard(models.TransientModel):
    _name = 'l10n_pe.letter.refinance.massive.wizard'
    _description = 'Refinanciación masiva de canjes de letras'

    partner_id = fields.Many2one('res.partner', string='Cliente', readonly=True)
    journal_id = fields.Many2one('account.journal', string='Diario', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    refinance_date = fields.Date(string='Fecha de refinanciación', required=True)
    total_amount = fields.Monetary(
        string='Importe total',
        currency_field='currency_id',
        compute='_compute_total_amount',
    )
    letter_ids = fields.Many2many(
        'l10n_pe.letter',
        'account_massive_refinance_rel',
        'wizard_id',
        'letter_id',
        string='Canjes seleccionados',
        readonly=True,
    )

    @api.depends('letter_ids', 'letter_ids.rest_amount_currency')
    def _compute_total_amount(self):
        for wizard in self:
            wizard.total_amount = sum(wizard.letter_ids.mapped('rest_amount_currency'))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids') or []
        letters = self.env['l10n_pe.letter'].browse(active_ids)
        if not letters:
            raise UserError('Seleccione al menos un canje de letra para refinanciar.')

        letters._validate_massive_refinance_selection()

        first_letter = letters[0]
        res.setdefault('letter_ids', [(6, 0, letters.ids)])
        res.setdefault('partner_id', first_letter.partner_id.id)
        res.setdefault('journal_id', first_letter.journal_id.id)
        res.setdefault('company_id', first_letter.company_id.id)
        currency = first_letter.currency_id or first_letter.company_currency_id
        res.setdefault('currency_id', currency.id)
        if 'refinance_date' not in res:
            res['refinance_date'] = self.env.context.get('default_refinance_date') or fields.Date.context_today(self)
        return res

    def action_confirm(self):
        self.ensure_one()
        letters = self.letter_ids
        if not letters:
            raise UserError('Debe seleccionar al menos un canje para refinanciar.')

        new_letter = self.env['l10n_pe.letter'].create_massive_refinance(letters, self.refinance_date)

        return {
            'name': 'Canje de letra refinanciado',
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_pe.letter',
            'res_id': new_letter.id,
            'view_mode': 'form',
            'target': 'current',
        }
