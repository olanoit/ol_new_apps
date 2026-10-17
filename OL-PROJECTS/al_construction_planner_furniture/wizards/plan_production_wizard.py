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

    def _prepare_lines(self):
        """Ambiente medido (M19-06): la orden se puede preparar igual, con el
        aviso de los ambientes que el supervisor aún no marcó como medidos."""
        values, notes = super()._prepare_lines()
        space_ids = {space_id for vals in values
                     for space_id in vals['space_task_ids'][0][2]}
        unmeasured = self.env['project.task'].browse(sorted(space_ids)).filtered(
            lambda t: t.construction_typology_id and not t.construction_measured)
        if unmeasured:
            notes.append(self.env._('Sin marcar como medidos: %s.', ', '.join(
                unmeasured.mapped('display_name'))))
        return values, notes
