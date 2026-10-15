# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.al_construction_planner.models.common import ML_GROUPS, MODULE_TYPES


class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_furniture_ml = fields.Float(
        string='Metros lineales del mueble', digits=(16, 2),
        help='Los del mueble de la tipología; con módulos con ancho, el árbol suma sus anchos.')
    construction_module_code = fields.Char(string='Código del módulo')
    construction_module_type = fields.Selection(MODULE_TYPES, string='Tipo de módulo')
    construction_width_mm = fields.Integer(string='Ancho (mm)')
    construction_ml_group = fields.Selection(ML_GROUPS, string='Grupo ML')

    def _construction_furniture_for(self, ml_group, module_type=False):
        """Mueble del ambiente donde va un módulo sin mueble en su plantilla:
        el de su grupo ML o, sin grupo, el de su tipo (mueble bajo o alto; los
        demás en «Otros muebles»)."""
        self.ensure_one()
        names = {'low': self.env._('Mueble bajo'), 'high': self.env._('Mueble alto')}
        key = ml_group if ml_group in names else module_type
        return self._construction_furniture_named(names.get(key, self.env._('Otros muebles')))

    def _construction_furniture_named(self, name, ml=0.0):
        """Mueble ``name`` del ambiente; se crea con el nivel Mueble de la
        plantilla de la obra si aún no existe."""
        self.ensure_one()
        furniture = self.search([('parent_id', '=', self.id),
                                 ('construction_level', '=', 'furniture'), ('name', '=', name)],
                                limit=1)
        if not furniture:
            furniture = self.with_context(mail_create_nolog=True, tracking_disable=True).create(dict(
                self.project_id._construction_level_vals('furniture'), name=name,
                project_id=self.project_id.id, parent_id=self.id, user_ids=False,
                construction_furniture_ml=ml))
        elif ml and not furniture.construction_furniture_ml:
            furniture.construction_furniture_ml = ml
        return furniture
