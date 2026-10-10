# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .common import LEVELS, ML_GROUPS, MODULE_TYPES, UNIT_STATES

# Nivel inmediatamente superior de cada nivel (la obra es el proyecto).
PARENT_LEVEL = {'apartment': 'floor', 'space': 'apartment', 'module': 'space'}


class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_level = fields.Selection(
        LEVELS, string='Nivel de obra', index=True,
        help='Define la jerarquía del árbol del plan: piso › departamento › ambiente › módulo.')
    construction_floor_task_id = fields.Many2one(
        'project.task', string='Piso', compute='_compute_construction_ancestors', store=True,
        index=True, recursive=True)
    construction_apartment_task_id = fields.Many2one(
        'project.task', string='Departamento', compute='_compute_construction_ancestors',
        store=True, index=True, recursive=True)
    construction_space_task_id = fields.Many2one(
        'project.task', string='Ambiente', compute='_compute_construction_ancestors',
        store=True, index=True, recursive=True)
    construction_typology_id = fields.Many2one(
        'construction.typology', string='Tipología', index=True, check_company=True,
        domain="[('project_id', '=', project_id)]", help='Tipología del ambiente.')
    construction_module_code = fields.Char(string='Código del módulo')
    construction_module_type = fields.Selection(MODULE_TYPES, string='Tipo de módulo')
    construction_width_mm = fields.Integer(string='Ancho (mm)')
    construction_ml_group = fields.Selection(ML_GROUPS, string='Grupo ML')
    construction_unit_state = fields.Selection(
        UNIT_STATES, string='Estado del módulo', tracking=True,
        help='Avance físico del módulo: planificado, en producción, producido, en obra, '
             'instalado y entregado.')
    construction_plan_line_ids = fields.One2many(
        'construction.resource.plan.line', 'task_id', string='Recursos del nivel')
    construction_plan_amount = fields.Monetary(
        string='Monto planificado', compute='_compute_construction_plan_amount',
        currency_field='construction_currency_id',
        help='Suma de las líneas del plan vigente de este nivel y de todo lo que tiene debajo.')
    construction_currency_id = fields.Many2one(
        related='company_id.currency_id', string='Moneda de la obra')

    @api.depends('parent_id', 'construction_level',
                 'parent_id.construction_floor_task_id',
                 'parent_id.construction_apartment_task_id',
                 'parent_id.construction_space_task_id')
    def _compute_construction_ancestors(self):
        for task in self:
            ancestors = {'floor': False, 'apartment': False, 'space': False}
            node = task
            # La obra tiene cinco niveles: como mucho cuatro saltos hacia arriba.
            for _depth in range(6):
                if not node:
                    break
                level = node.construction_level
                if level in ancestors and not ancestors[level]:
                    ancestors[level] = node
                node = node.parent_id
            task.construction_floor_task_id = ancestors['floor']
            task.construction_apartment_task_id = ancestors['apartment']
            task.construction_space_task_id = ancestors['space']

    @api.constrains('construction_level', 'parent_id')
    def _check_construction_level(self):
        """Un nivel cuelga del nivel inmediatamente superior (o de la obra si
        es piso). Las subtareas sin nivel no se validan."""
        for task in self:
            expected = PARENT_LEVEL.get(task.construction_level)
            if not expected:
                continue
            if task.parent_id.construction_level != expected:
                raise ValidationError(self.env._(
                    'La tarea %(task)s es de nivel %(level)s: debe colgar de un %(parent)s.',
                    task=task.display_name,
                    level=dict(LEVELS)[task.construction_level],
                    parent=dict(LEVELS)[expected].lower()))

    def _construction_plan_domain(self):
        """Líneas del plan vigente (o del borrador si no hay vigente) del nodo
        y de sus descendientes, por el ancestro almacenado de su nivel."""
        self.ensure_one()
        field = {
            'floor': 'floor_task_id', 'apartment': 'apartment_task_id',
            'space': 'space_task_id', 'module': 'module_task_id',
        }.get(self.construction_level)
        if not field:
            return [('task_id', '=', self.id)]
        plan = self.project_id._construction_current_plan()
        return [(field, '=', self.id), ('plan_id', '=', plan.id)]

    def _compute_construction_plan_amount(self):
        Line = self.env['construction.resource.plan.line']
        for task in self:
            if not task.id or not task.construction_level:
                task.construction_plan_amount = 0.0
                continue
            result = Line._read_group(task._construction_plan_domain(), [], ['amount_planned:sum'])
            task.construction_plan_amount = result[0][0] if result else 0.0
