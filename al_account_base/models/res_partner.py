# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Sin ``size``, por el mismo motivo que el código de banco: «00123»
    # truncado a «0012» sería otro establecimiento.
    l10n_pe_annex_code = fields.Char(
        string='Establecimiento anexo',
        help='Código de cuatro dígitos del establecimiento anexo declarado en '
             'el RUC. Se informa en los libros de inventario y en las guías '
             'de remisión. El establecimiento principal es «0000».')

    @api.constrains('l10n_pe_annex_code')
    def _check_l10n_pe_annex_code(self):
        for partner in self:
            code = (partner.l10n_pe_annex_code or '').strip()
            if code and not (code.isdigit() and len(code) == 4):
                raise ValidationError(_(
                    'El código de establecimiento anexo de %(partner)s debe '
                    'tener cuatro dígitos (por ejemplo «0000»); se recibió '
                    '«%(code)s».',
                    partner=partner.display_name, code=code))
