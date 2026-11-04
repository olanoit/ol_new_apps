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
PE_CUI_KEY = 'PE_CUI'
# Código del catálogo 06 → clave del identificador en Odoo. El RUC (6) no
# está: va en el campo ``vat``.
# Nombre corto del documento por código del catálogo 06.
PE_DOCUMENT_LABELS = {
    '0': _lt('Doc. trib. no domiciliado'),
    '1': _lt('DNI'),
    '4': _lt('Carné de extranjería'),
    '6': _lt('RUC'),
    '7': _lt('Pasaporte'),
    'A': _lt('Cédula diplomática'),
    'F': _lt('PTP'),
}
PE_IDENTIFIER_KEYS = {
    **{code: key for key, code in PE_SUNAT_CODES.items()},
    '4': PE_CE_KEY,
}
# Nombres en español peruano (catálogo 06 de SUNAT) de los identificadores
# de l10n_pe. Odoo 20 los trae en inglés y sin traducción, y son los que
# muestran el «+» junto al RUC y la lista de identificadores del contacto.
PE_IDENTIFIER_LABELS = {
    'PE_DNI': (_lt('DNI'), _lt('Documento Nacional de Identidad emitido por RENIEC.')),
    'PE_CPP': (_lt('Carné de Permiso Temporal de Permanencia'),
               _lt('CPP emitido por Migraciones.')),
    'PE_DIC': (_lt('Cédula diplomática de identidad'),
               _lt('Emitida por el Ministerio de Relaciones Exteriores.')),
    'PE_IDCR': (_lt('Documento de identidad del país de residencia'),
                _lt('Documento de identidad de un no domiciliado, emitido en su país de residencia.')),
    'PE_IN': (_lt('Doc. tributario de persona jurídica no domiciliada'),
              _lt('Identification Number (IN) de una empresa del extranjero.')),
    'PE_NDTD': (_lt('Doc. tributario no domiciliado sin RUC'),
                _lt('Documento tributario de otro país, para quien no tiene RUC.')),
    'PE_PTP': (_lt('Permiso Temporal de Permanencia (PTP)'),
               _lt('Permiso Temporal de Permanencia emitido por Migraciones.')),
    'PE_SP': (_lt('Salvoconducto'), _lt('Salvoconducto emitido por Migraciones.')),
    'PE_TAM': (_lt('Tarjeta Andina de Migración (TAM)'),
               _lt('Tarjeta Andina de Migración, para turistas de la Comunidad Andina.')),
    'PE_TIN': (_lt('Doc. tributario de persona natural no domiciliada'),
               _lt('Tax Identification Number (TIN) de una persona del extranjero.')),
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

    # Nombre del documento con que se identifica el contacto en los
    # comprobantes y reportes (antes l10n_latam_identification_type_id.name).
    l10n_pe_document_label = fields.Char(
        string='Tipo de documento', compute='_compute_l10n_pe_document_label')

    @api.depends('l10n_pe_sunat_id_code', 'vat', 'additional_identifiers')
    def _compute_l10n_pe_document_label(self):
        labels = dict(PE_DOCUMENT_LABELS)
        for partner in self:
            code = partner.l10n_pe_sunat_id_code
            partner.l10n_pe_document_label = labels.get(code) or (
                partner._get_preferred_legal_entity_identifier_vals().get('label') or '')

    @api.model
    def _get_all_additional_identifiers_metadata(self):
        metadata = super()._get_all_additional_identifiers_metadata()
        for key, (label, help_text) in PE_IDENTIFIER_LABELS.items():
            if key in metadata:
                metadata[key] = {**metadata[key], 'label': label, 'help': help_text}
        # El RUC va en ``vat``: «Company ID» lo duplicaría. ``hide`` es la forma
        # nativa de no ofrecerlo en el «+»; si un contacto ya lo tiene, se sigue
        # viendo en su lista.
        if PE_CUI_KEY in metadata:
            metadata[PE_CUI_KEY] = {
                **metadata[PE_CUI_KEY],
                'label': _lt('RUC (duplicado)'),
                'help': _lt('El RUC se registra en el campo RUC del contacto.'),
                'display_optional': 'hide',
            }
        return {
            **metadata,
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
