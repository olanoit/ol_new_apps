# -*- coding: utf-8 -*-
from odoo import api, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _load_pos_data_fields(self, config):
        # Odoo 20: el tipo y número de documento SUNAT del cliente (catálogo
        # 06) deciden si se le puede emitir factura (RUC, código 6).
        fields = super()._load_pos_data_fields(config)
        if fields and self.env.company.country_id.code == 'PE':
            fields += [name for name in ('l10n_pe_sunat_id_code', 'l10n_pe_sunat_id_value')
                       if name not in fields]
        return fields
