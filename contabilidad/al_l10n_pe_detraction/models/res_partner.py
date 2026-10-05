# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_pe_detraction_account = fields.Char(
        string='Cuenta de detracciones',
        size=11,
        help='Número de la cuenta corriente de detracciones abierta en el '
             'Banco de la Nación. Es obligatorio para incluir al contacto en '
             'un depósito masivo.')

    @api.constrains('l10n_pe_detraction_account')
    def _check_l10n_pe_detraction_account(self):
        for partner in self:
            account = (partner.l10n_pe_detraction_account or '').strip()
            if account and not account.isdigit():
                raise ValidationError(_(
                    'La cuenta de detracciones de %s debe contener solo '
                    'dígitos.', partner.display_name))
