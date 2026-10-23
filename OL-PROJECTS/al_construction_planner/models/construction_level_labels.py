# -*- coding: utf-8 -*-
"""Términos de la vertical en la interfaz (v1.8, M18-01).

Los campos que nombran un nivel del árbol (piso, departamento, ambiente,
mueble, módulo y niveles 1 a 6) toman en listas, formularios, filtros y
análisis el nombre que les da la plantilla de niveles: la de la obra que viene
en el contexto (CREVAL v1.0, 6.3) o, sin obra, la de la compañía. «Partida» y
«Actividad» en una constructora; «Mueble» y «Módulo» en mobiliario. Sin
plantilla quedan los nombres del planificador."""
import ast

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
    def _construction_context_template(self):
        """Plantilla de la obra del contexto: la obra, el plan o el registro
        activo; si no, la de la compañía."""
        ctx = self.env.context
        project = self.env['project.project']
        project_id = ctx.get('construction_project_id') or ctx.get('default_project_id')
        if project_id and isinstance(project_id, int):
            project = project.browse(project_id).exists()
        plan_id = ctx.get('default_plan_id') or (
            ctx.get('active_id') if ctx.get('active_model') == 'construction.resource.plan'
            else False)
        if not project and plan_id and isinstance(plan_id, int):
            project = self.env['construction.resource.plan'].browse(plan_id).exists().project_id
        if not project and ctx.get('active_model') == 'project.project' \
                and isinstance(ctx.get('active_id'), int):
            project = project.browse(ctx['active_id']).exists()
        return project.construction_level_template_id \
            or self.env.company.construction_level_template_id

    @api.model
    def _construction_level_terms(self, template=None):
        """{función o level_<n>: nombre} de la plantilla (la de la obra del
        contexto o de la compañía si no se pasa)."""
        template = template if template is not None else self._construction_context_template()
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

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type='form', **options):
        """La vista cambia con la plantilla de la obra del contexto."""
        key = super()._get_view_cache_key(view_id, view_type, **options)
        return key + (self._construction_context_template().id,)

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """Filtros y agrupaciones por nivel con el nombre de la plantilla."""
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type != 'search':
            return arch, view
        terms = self._construction_level_terms()
        fields_map = self._construction_level_label_fields()
        if not terms:
            return arch, view
        for node in arch.xpath('//filter[@context]'):
            try:
                context = ast.literal_eval(node.get('context'))
            except (ValueError, SyntaxError):
                continue
            group_by = context.get('group_by') if isinstance(context, dict) else None
            fname = (group_by or '').split(':')[0]
            key = fields_map.get(fname)
            if key and key in terms:
                node.set('string', terms[key])
        for node in arch.xpath('//field[@name]'):
            key = fields_map.get(node.get('name'))
            if key and key in terms and node.get('string'):
                node.set('string', terms[key])
        return arch, view


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
