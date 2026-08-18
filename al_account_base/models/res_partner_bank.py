# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    # Sin ``size``: truncar convertiría un código erróneo en uno válido —
    # «123» pasaría a «12», que es otro banco— y el libro saldría mal sin que
    # nadie lo advierta. Mejor rechazarlo.
    l10n_pe_bank_code = fields.Char(
        string='Código SUNAT del banco',
        help='Código de la entidad financiera donde está la cuenta, según la '
             'tabla 3 del Anexo 2 del PLE. Es obligatorio en el Libro Caja y '
             'Bancos, formato 1.2.')

    @api.constrains('l10n_pe_bank_code')
    def _check_l10n_pe_bank_code(self):
        for account in self:
            code = (account.l10n_pe_bank_code or '').strip()
            if code and not (code.isdigit() and len(code) == 2):
                raise ValidationError(_(
                    'El código SUNAT del banco debe tener dos dígitos '
                    '(tabla 3 del PLE); se recibió «%s».', code))
