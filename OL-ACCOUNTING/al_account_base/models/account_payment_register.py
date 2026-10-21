# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    @api.depends('line_ids')
    def _compute_actionable_errors(self):
        super()._compute_actionable_errors()
        for wizard in self:
            reasons = wizard.line_ids._l10n_pe_payment_block_reasons()
            if reasons:
                wizard.actionable_errors = {
                    **(wizard.actionable_errors or {}),
                    'l10n_pe_payment_block': {'message': '\n'.join(reasons), 'level': 'danger'},
                }

    def _create_payments(self):
        reasons = self.line_ids._l10n_pe_payment_block_reasons()
        if reasons:
            raise UserError('\n'.join(reasons))
        return super()._create_payments()
