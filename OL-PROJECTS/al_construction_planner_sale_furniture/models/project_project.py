# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def _construction_partida_resolver(self, partidas):
        """Con familias en las partidas (mobiliario): la partida con familia
        toma las líneas cuyo ambiente (o la propia línea) tiene una tipología de
        esa familia; la única partida sin familia, el resto."""
        self.ensure_one()
        if not any(partidas.mapped('construction_family')) and not self.construction_typology_ids:
            return super()._construction_partida_resolver(partidas)
        catch_all = partidas.filtered(lambda l: not l.construction_family)
        if len(catch_all) > 1:
            raise UserError(self.env._(
                'La orden de venta %(order)s tiene %(count)s partidas sin familia: solo una '
                'puede tomar el resto de la obra. Indique la familia de cada partida.',
                order=self.construction_sale_order_id.name, count=len(catch_all)))
        by_family = {line.construction_family: line for line in partidas
                     if line.construction_family}

        def resolve(plan_line):
            family = (plan_line.space_task_id.construction_typology_id.family
                      or plan_line.typology_id.family)
            return by_family.get(family) or catch_all
        return resolve
