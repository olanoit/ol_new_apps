# -*- coding: utf-8 -*-
from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def load_product_from_pos(self, config_id, domain, offset=0, limit=0):
        """Los productos que el TPV carga después (búsqueda, código de barras)
        llegan también con sus presentaciones."""
        result = super().load_product_from_pos(config_id, domain, offset=offset, limit=limit)
        template_ids = [template['id'] for template in result.get('product.template', [])]
        if template_ids:
            config = self.env['pos.config'].browse(config_id)
            Presentation = self.env['pharmacy.presentation']
            presentations = Presentation.search([('product_tmpl_id', 'in', template_ids)])
            result['pharmacy.presentation'] = Presentation._load_pos_data_read(presentations, config)
        return result
