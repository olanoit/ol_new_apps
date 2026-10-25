# -*- coding: utf-8 -*-
from odoo import Command, models


class ConstructionPlanProductionWizard(models.TransientModel):
    _inherit = 'construction.plan.production.wizard'

    def _production_source(self, space):
        """En mobiliario, un mueble terminado por ambiente: el producto de su
        tipología con su lista de fabricación (la última etapa de la cadena,
        paquete 1.10 M110-02) o, si no tiene, su lista de materiales."""
        typology = space.construction_typology_id
        product = typology.product_tmpl_id.product_variant_id
        bom = typology.production_bom_id or typology.bom_id
        if bom and product:
            return product, bom, 1.0, typology
        return super()._production_source(space)

    def _production_extra_values(self, line):
        """Los módulos de los ambientes de la orden (paquete 1.10, M110-03):
        al cerrarla pasan a «Producido»."""
        values = super()._production_extra_values(line)
        modules = self.env['project.task'].search([
            ('construction_space_task_id', 'in', line.space_task_ids.ids),
            ('construction_level', '=', 'module')])
        if modules:
            values['construction_module_task_ids'] = [Command.set(modules.ids)]
        return values

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
                self._space_label(task) for task in unmeasured)))
        return values, notes
