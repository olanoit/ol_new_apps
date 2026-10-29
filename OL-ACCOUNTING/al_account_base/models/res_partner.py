# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import LazyTranslate

from odoo.addons.l10n_pe.tools.partner_identifiers import PE_RUC_SUNAT_CODE, PE_SUNAT_CODES

_lt = LazyTranslate(__name__)

# Clave de ``additional_identifiers`` del Carnet de Extranjería. Odoo no la
# define; al ser de categoría «CN» sin código propio, l10n_pe la informa a
# SUNAT con el código 4 del catálogo 06.
PE_CE_KEY = 'PE_CE'
# Código del catálogo 06 → clave del identificador en Odoo. El RUC (6) no
# está: va en el campo ``vat``.
PE_IDENTIFIER_KEYS = {
    **{code: key for key, code in PE_SUNAT_CODES.items()},
    '4': PE_CE_KEY,
}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Sin ``size``, por el mismo motivo que el código de banco: «00123»
    # truncado a «0012» sería otro establecimiento.
    l10n_pe_annex_code = fields.Char(
        string='Establecimiento anexo',
        help='Código de cuatro dígitos del establecimiento anexo declarado en '
             'el RUC. Se informa en los libros de inventario y en las guías '
             'de remisión. El establecimiento principal es «0000».')

    @api.model
    def _get_all_additional_identifiers_metadata(self):
        return {
            **super()._get_all_additional_identifiers_metadata(),
            PE_CE_KEY: {
                'label': _lt('Carnet de Extranjería'),
                'help': _lt('Carnet de Extranjería emitido por Migraciones.'),
                'category': 'CN',
                'countries': ['PE'],
            },
        }

    @api.model
    def _l10n_pe_identification_vals(self, sunat_code, number):
        """Valores de ``create``/``write`` para identificar al contacto con
        el documento ``number`` del tipo ``sunat_code`` (catálogo 06)."""
        if not number:
            return {}
        if sunat_code == PE_RUC_SUNAT_CODE:
            return {'vat': number}
        key = PE_IDENTIFIER_KEYS.get(sunat_code)
        if not key:
            raise ValidationError(_(
                'Tipo de documento de identidad «%s» desconocido.', sunat_code))
        return {'additional_identifiers': {key: number}}

    def _l10n_pe_set_identification(self, sunat_code, number):
        """Registra el documento en el contacto, validándolo y conservando
        los demás identificadores."""
        self.ensure_one()
        if sunat_code == PE_RUC_SUNAT_CODE:
            self.vat = number
        elif key := PE_IDENTIFIER_KEYS.get(sunat_code):
            self._set_additional_identifier(key, number)
        else:
            raise ValidationError(_(
                'Tipo de documento de identidad «%s» desconocido.', sunat_code))

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
