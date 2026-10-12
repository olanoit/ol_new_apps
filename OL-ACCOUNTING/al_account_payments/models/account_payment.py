# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    pe_payment_method_id = fields.Many2one(
        comodel_name='pe.catalog.payment', string='Medio pago')
    bank_operation_number = fields.Char(string='Número de operación banco')

    def action_post(self):
        missing = self.filtered(
            lambda p: p.journal_id.l10n_pe_require_operation_number and not p.bank_operation_number)
        if missing:
            raise UserError(self.env._(
                'Indique el número de operación del banco en: %s.',
                ', '.join(missing.mapped(lambda p: p.display_name or p.journal_id.name))))
        return super().action_post()
