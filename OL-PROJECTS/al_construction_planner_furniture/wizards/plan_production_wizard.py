# -*- coding: utf-8 -*-
from odoo import models


class ConstructionPlanProductionWizard(models.TransientModel):
    _inherit = 'construction.plan.production.wizard'

    def _production_source(self, space):
        """En mobiliario, un mueble terminado por ambiente: el producto y la BOM
        de su tipología."""
        typology = space.construction_typology_id
        product = typology.product_tmpl_id.product_variant_id
        if typology.bom_id and product:
            return product, typology.bom_id, 1.0, typology
        return super()._production_source(space)
