# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    l10n_pe_batch_format = fields.Selection(
        related='bank_id.l10n_pe_batch_format', string='Formato de pago masivo')
    l10n_pe_batch_service_code = fields.Char(
        string='Código del servicio',
        help='Lo asigna el banco al afiliar el pago a proveedores. BCP: subtipo de la '
             'planilla (P por defecto); Interbank: código del servicio (04); Scotiabank: '
             'forma de pago (1, cargo en cuenta).')
    l10n_pe_batch_company_code = fields.Char(
        string='Código de la empresa',
        help='Interbank: código de la empresa en el banco (MC001 si se deja vacío).')
    l10n_pe_batch_process_type = fields.Selection(
        [('A', 'Inmediato'), ('F', 'En la fecha del lote')], string='Proceso (BBVA)',
        default='A')

    def _default_outbound_payment_methods(self):
        res = super()._default_outbound_payment_methods()
        if self._is_payment_method_available('pe_bank_txt'):
            res |= self.env.ref('al_l10n_pe_batch_payment.account_payment_method_pe_bank_txt')
        return res
