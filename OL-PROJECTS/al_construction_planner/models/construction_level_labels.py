# -*- coding: utf-8 -*-
"""Términos de la vertical en la interfaz (v1.8, M18-01).

Los campos que nombran un nivel del árbol (piso, departamento, ambiente,
mueble, módulo y niveles 1 a 6) toman en listas, formularios, filtros y
análisis el nombre que les da la plantilla de niveles: la de la obra que viene
en el contexto (CREVAL v1.0, 6.3) o, sin obra, la de la compañía. «Partida» y
«Actividad» en una constructora; «Mueble» y «Módulo» en mobiliario. Sin
plantilla quedan los nombres del planificador."""
import ast
import re

from odoo import api, models

# «Subpartida 1 (N4)» → «Subpartida 1».
LEVEL_NUMBER = re.compile(r'\s*\(N\d+\)\s*$')


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
            # Paquete 4 de CREVAL, CR-37: el mismo formato en todos los
            # niveles; la marca «(N4)» de los nombres numerados no se muestra.
            name = LEVEL_NUMBER.sub('', line.name or '')
            terms['level_%s' % depth] = name
            if line.level and line.level not in terms:
                terms[line.level] = name
        return terms

    @api.model
    def _construction_level_label_fields(self):
        return LEVEL_FIELDS

    @api.model
    def _construction_level_functions(self, template=None):
        """Funciones de nivel que tiene la plantilla, separadas por espacios
        (para ``column_invisible`` de las listas, paquete 1.20, M120-03)."""
        return ' '.join(key for key in self._construction_level_terms(template)
                        if not key.startswith('level_'))

    @api.model
    def _construction_space_stage_title(self):
        """«Etapa actual por partida» o «… por ambiente»: el nombre de la línea
        de la plantilla de la compañía con la función «nivel con etapas»
        (paquete 1.20, M120-03). Sin plantilla, el nombre de siempre."""
        name = self._construction_level_terms(
            self.env.company.construction_level_template_id).get('space')
        if not name:
            return self.env._('Etapa de los ambientes')
        return self.env._('Etapa actual por %s', name[:1].lower() + name[1:])

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
        if view_type in ('list', 'form'):
            self._construction_level_columns(arch, view_type)
            return arch, view
        if view_type != 'search':
            return arch, view
        terms = self._construction_level_terms()
        fields_map = self._construction_level_label_fields()
        if not terms:
            return arch, view
        level_names = {name for key, name in terms.items() if key.startswith('level_')}
        for node in arch.xpath('//filter[@context]'):
            try:
                context = ast.literal_eval(node.get('context'))
            except (ValueError, SyntaxError):
                continue
            group_by = context.get('group_by') if isinstance(context, dict) else None
            fname = (group_by or '').split(':')[0]
            key = fields_map.get(fname)
            if not key:
                continue
            if key in terms:
                node.set('string', terms[key])
            # CR-37: cada nivel una vez. Se ocultan el agrupador de una función
            # que la plantilla no tiene (Departamento en construcción), el de
            # un nivel que no existe y el de una función que repite un nivel.
            if key not in terms or (not key.startswith('level_')
                                    and terms[key] in level_names):
                node.set('invisible', '1')
        for node in arch.xpath('//field[@name]'):
            key = fields_map.get(node.get('name'))
            if key and key in terms and node.get('string'):
                node.set('string', terms[key])
        return arch, view


    @api.model
    def _construction_level_columns(self, arch, view_type):
        """Paquete 1.20, M120-03: una columna o un campo que nombra una función
        que la plantilla no tiene se oculta; si la tiene, lleva su nombre. Una
        lista incrustada en un registro (las líneas del plan) recibe en el
        contexto las funciones de la plantilla de su obra
        (``construction_level_functions``)."""
        terms = self._construction_level_terms()
        if not terms:
            return
        fields_map = self._construction_level_label_fields()
        hide = 'column_invisible' if view_type == 'list' else 'invisible'
        for node in arch.xpath('//field[@name]'):
            if node.xpath('ancestor::field'):
                continue
            key = fields_map.get(node.get('name'))
            if not key:
                continue
            if key not in terms:
                node.set(hide, '1')
                continue
            if node.get('string'):
                node.set('string', terms[key])
            if view_type == 'list' and not key.startswith('level_') \
                    and not node.get('column_invisible'):
                node.set('column_invisible',
                         "'%s' not in (context.get('construction_level_functions') or '%s')"
                         % (key, key))


class ProjectTask(models.Model):
    _name = 'project.task'
    _inherit = ['project.task', 'construction.level.labels.mixin']

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """M120-03: el informe de la etapa actual se titula con el nivel de la
        plantilla («Etapa actual por partida»)."""
        arch, view = super()._get_view(view_id, view_type, **options)
        report_views = {self.env.ref('al_construction_planner.%s' % xmlid,
                                     raise_if_not_found=False)
                        for xmlid in ('project_task_view_pivot_construction_space_stage',
                                      'project_task_view_graph_construction_space_stage',
                                      'project_task_view_list_construction_space_stage')}
        if view in report_views and arch.get('string'):
            arch.set('string', self._construction_space_stage_title())
        return arch, view

    @api.model
    def _construction_level_label_fields(self):
        return {
            'construction_floor_task_id': 'floor',
            'construction_apartment_task_id': 'apartment',
            'construction_space_task_id': 'space',
            'construction_furniture_task_id': 'furniture',
        }


class IrActionsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    def _get_action_dict(self):
        """M120-03: el título del informe de la etapa actual sale de la
        plantilla de la compañía."""
        result = super()._get_action_dict()
        report = self.env.ref('al_construction_planner.action_construction_space_stage_report',
                              raise_if_not_found=False)
        if report and self.id == report.id:
            result['name'] = self.env['construction.level.labels.mixin']\
                ._construction_space_stage_title()
        return result
