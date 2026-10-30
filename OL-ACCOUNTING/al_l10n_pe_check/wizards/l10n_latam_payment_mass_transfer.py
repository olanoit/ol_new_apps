# -*- coding: utf-8 -*-
from odoo import api, fields, models


class L10nLatamPaymentMassTransfer(models.TransientModel):
    _inherit = 'l10n_latam.payment.mass.transfer'

    l10n_pe_warning = fields.Text(
        string='Avisos', compute='_compute_l10n_pe_warning',
        help='Cheques diferidos que aún no se pueden cobrar o con el plazo de presentación '
             'vencido, si se depositan en un banco.')

    @api.depends('check_ids', 'payment_date', 'to_journal_id')
    def _compute_l10n_pe_warning(self):
        for wizard in self:
            messages = []
            if wizard.to_journal_id.type == 'bank' and wizard.payment_date:
                messages = wizard.check_ids._origin._l10n_pe_presentation_warnings(wizard.payment_date)
            wizard.l10n_pe_warning = '\n'.join(messages) or False
