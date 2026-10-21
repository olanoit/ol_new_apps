# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    pharmacy_ingredient_filter = fields.Boolean(
        string='Filtrar por principio activo', default=True,
        help='Sobre el catálogo de la caja se filtra por principio activo en lugar de por etiquetas.')

    @api.model
    def _load_pos_data_read(self, records, config):
        # El filtro por principio activo reemplaza al de etiquetas
        # (al_pos_product_view), si está instalado.
        read_records = super()._load_pos_data_read(records, config)
        for record in read_records:
            if record.get('pharmacy_ingredient_filter') and 'iface_filter_products_by_tag' in record:
                record['iface_filter_products_by_tag'] = False
        return read_records


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_pharmacy_ingredient_filter = fields.Boolean(
        related='pos_config_id.pharmacy_ingredient_filter', readonly=False)
