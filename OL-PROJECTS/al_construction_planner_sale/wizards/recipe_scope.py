# -*- coding: utf-8 -*-
from odoo import models


class ConstructionRecipeImportWizard(models.TransientModel):
    _inherit = 'construction.recipe.import.wizard'

    def _recipe_scope_values(self):
        """Sin obra, el envío de la hoja guarda las recetas en la cotización
        (CR-18, D4), no en la biblioteca."""
        scope = super()._recipe_scope_values()
        order_id = self.env.context.get('construction_recipe_sale_order_id')
        scope['construction_sale_order_id'] = order_id if order_id and not self.project_id \
            else False
        return scope
