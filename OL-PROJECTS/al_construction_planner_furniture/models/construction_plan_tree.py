# -*- coding: utf-8 -*-
"""Metros lineales y módulos en el árbol de recursos (rubro mobiliario)."""
from odoo import api, models


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def _tree_show_ml(self):
        """Metros lineales en las obras de mueble: las que tienen tipologías
        con ML o una plantilla con nivel de mueble o de módulo con ancho."""
        self.ensure_one()
        return bool(self.env['construction.typology'].search_count([
            ('project_id', '=', self.project_id.id),
            '|', ('ml_low', '>', 0), ('ml_high', '>', 0)], limit=1)) or super()._tree_show_ml()

    @api.model
    def _tree_space_ml(self, spaces):
        """ML de cada ambiente: bajo + alto de su tipología."""
        return {space.id: (space.construction_typology_id.ml_low or 0.0)
                + (space.construction_typology_id.ml_high or 0.0) for space in spaces}

    @api.model
    def _tree_module_info(self, task):
        ml = (task.construction_width_mm or 0) / 1000.0 \
            if task.construction_ml_group in ('low', 'high') else 0.0
        return ml, task.construction_module_code or ''

    @api.model
    def _tree_furniture_ml(self, children, task_field):
        """ML del mueble: la suma de los anchos de sus módulos o, sin anchos,
        los del mueble de la tipología."""
        ml = {}
        for module in self.env['project.task'].search([('construction_level', '=', 'module'),
                                                       (task_field, 'in', children.ids)]):
            if module.construction_ml_group in ('low', 'high'):
                key = module[task_field].id
                ml[key] = ml.get(key, 0.0) + (module.construction_width_mm or 0) / 1000.0
        for task in children:
            if not ml.get(task.id):
                ml[task.id] = task.construction_furniture_ml or 0.0
        return ml

    @api.model
    def _tree_loose_ml(self, module_domain, spaces):
        """Módulos sueltos (su ambiente no está entero en la selección): su
        ancho si es de un grupo ML."""
        loose = self.env['project.task'].search(module_domain + [
            ('construction_space_task_id', 'not in', spaces.ids),
            ('construction_ml_group', 'in', ('low', 'high'))])
        return sum(loose.mapped('construction_width_mm')) / 1000.0
