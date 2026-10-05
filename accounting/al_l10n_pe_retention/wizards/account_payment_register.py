# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    # Etiquetas en español del marco nativo de retenciones
    withholding_line_ids = fields.One2many(string='Retenciones')
    withholding_net_amount = fields.Monetary(string='Neto a pagar')
    withholding_outstanding_account_id = fields.Many2one(
        string='Cuenta transitoria de pagos',
        help='Cuenta puente del pago cuando el método no tiene cuenta '
             'propia. Se propone desde Ajustes ▸ Perú ▸ «Cuenta '
             'transitoria (retenciones)».')

    @api.depends('withholding_payment_account_id', 'should_withhold_tax')
    def _compute_withholding_outstanding_account_id(self):
        """El nativo solo propone la cuenta copiándola del último pago
        similar: en una base nueva queda vacía y el campo es obligatorio.
        Fallback: la cuenta configurada en la compañía."""
        super()._compute_withholding_outstanding_account_id()
        for wizard in self:
            if (wizard.should_withhold_tax
                    and not wizard.withholding_payment_account_id
                    and not wizard.withholding_outstanding_account_id):
                wizard.withholding_outstanding_account_id = (
                    wizard.company_id
                    .l10n_pe_retention_outstanding_account_id)
