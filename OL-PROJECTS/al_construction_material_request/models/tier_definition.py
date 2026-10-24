# -*- coding: utf-8 -*-
from odoo import api, fields, models


class TierDefinition(models.Model):
    _inherit = 'tier.definition'

    # Regla del interno sin jefe (M111-19 C): la crea y actualiza la compañía.
    construction_internal_fallback = fields.Boolean(
        string='Interno sin jefe', readonly=True, copy=False)

    @api.model
    def _get_tier_validation_model_names(self):
        res = super()._get_tier_validation_model_names()
        res.append('construction.material.request')
        return res
