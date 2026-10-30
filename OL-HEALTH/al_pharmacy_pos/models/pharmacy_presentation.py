# -*- coding: utf-8 -*-
from odoo import api, models


class PharmacyPresentation(models.Model):
    _name = 'pharmacy.presentation'
    _inherit = ['pharmacy.presentation', 'pos.load.mixin']

    @api.model
    def _load_pos_data_domain(self, data):
        # Odoo 20: data trae recordsets (antes, listas de diccionarios).
        template_ids = data['product.template'].ids
        return [('product_tmpl_id', 'in', template_ids)]

    @api.model
    def _load_pos_data_fields(self, config):
        return ['id', 'product_tmpl_id', 'name', 'factor', 'price', 'display_name', 'uom_id',
                'sequence']
