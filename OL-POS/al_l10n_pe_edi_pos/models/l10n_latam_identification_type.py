# -*- coding: utf-8 -*-
from odoo import api, models


class L10nLatamIdentificationType(models.Model):
    _inherit = 'l10n_latam.identification.type'

    @api.model
    def _load_pos_data_fields(self, config):
        # l10n_pe_pos solo carga el nombre; el TPV necesita el código SUNAT
        # para no emitir factura a un cliente cuyo documento no es RUC (6).
        fields = super()._load_pos_data_fields(config)
        if fields and self.env.company.country_id.code == 'PE' \
                and 'l10n_pe_vat_code' not in fields:
            fields.append('l10n_pe_vat_code')
        return fields
