# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    l10n_pe_cci = fields.Char(
        string='CCI',
        help='Código de Cuenta Interbancario de 20 dígitos: lo usa el pago masivo cuando la '
             'cuenta del proveedor es de otro banco que el de la empresa.')
    l10n_pe_account_kind = fields.Selection(
        [('checking', 'Corriente'), ('savings', 'Ahorros')], string='Tipo de cuenta',
        default='checking',
        help='Tipo de la cuenta en su banco; algunos formatos de pago masivo lo informan.')

    @api.constrains('l10n_pe_cci')
    def _check_l10n_pe_cci(self):
        for account in self.filtered('l10n_pe_cci'):
            cci = account.l10n_pe_cci.replace('-', '').replace(' ', '')
            if not (cci.isdigit() and len(cci) == 20):
                raise ValidationError(self.env._(
                    'El CCI de la cuenta %(account)s debe tener 20 dígitos.',
                    account=account.display_name))
