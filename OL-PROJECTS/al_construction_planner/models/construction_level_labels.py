# -*- coding: utf-8 -*-
"""Términos de la vertical en la interfaz (v1.8, M18-01).

Los campos que nombran un nivel del árbol (piso, departamento, ambiente,
mueble, módulo y niveles 1 a 6) toman en listas, formularios, filtros y
análisis el nombre que les da la plantilla de niveles de la compañía:
«Partida» y «Actividad» en una constructora; «Mueble» y «Módulo» en
mobiliario. Sin plantilla quedan los nombres del planificador."""
from odoo import api, models

#: Campo → función del nivel en la plantilla (``level`` de la línea de la
#: plantilla) o ``level_<n>`` (n-ésimo nivel de la plantilla).
LEVEL_FIELDS = {
    'floor_task_id': 'floor', 'apartment_task_id': 'apartment', 'space_task_id': 'space',
    'furniture_task_id': 'furniture', 'module_task_id': 'module',
    **{'level_%s_id' % depth: 'level_%s' % depth for depth in range(1, 7)},
}


class ConstructionLevelLabelsMixin(models.AbstractModel):
    _name = 'construction.level.labels.mixin'
    _description = 'Nombres de los niveles según la plantilla de la compañía'

    @api.model
    def _construction_level_terms(self, template=None):
        """{función o level_<n>: nombre} de la plantilla (la de la compañía si
        no se pasa)."""
        template = template if template is not None else \
            self.env.company.construction_level_template_id
        terms = {}
        if not template:
            return terms
        for depth, line in enumerate(template.line_ids.sorted(lambda l: (l.sequence, l.id)),
                                     start=1):
            terms['level_%s' % depth] = line.name
            if line.level and line.level not in terms:
                terms[line.level] = line.name
        return terms

    @api.model
    def _construction_level_label_fields(self):
        return LEVEL_FIELDS

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        res = super().fields_get(allfields, attributes)
        terms = self._construction_level_terms()
        if not terms:
            return res
        for fname, key in self._construction_level_label_fields().items():
            if fname in res and key in terms and 'string' in res[fname]:
                res[fname]['string'] = terms[key]
        return res


class ProjectTask(models.Model):
    _name = 'project.task'
    _inherit = ['project.task', 'construction.level.labels.mixin']

    @api.model
    def _construction_level_label_fields(self):
        return {
            'construction_floor_task_id': 'floor',
            'construction_apartment_task_id': 'apartment',
            'construction_space_task_id': 'space',
            'construction_furniture_task_id': 'furniture',
        }
