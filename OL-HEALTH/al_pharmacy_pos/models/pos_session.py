# -*- coding: utf-8 -*-
from odoo import api, models


class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def _load_pos_data_models(self, config):
        # Después de product.template: el dominio usa los productos cargados.
        return super()._load_pos_data_models(config) + ['pharmacy.presentation', 'pharmacy.ingredient']
