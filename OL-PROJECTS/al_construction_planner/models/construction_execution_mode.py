# -*- coding: utf-8 -*-
"""Modalidad de ejecución por partida (requerimiento CREVAL v1.0, 6.4).

Cada partida de la obra lleva su modalidad: personal propio, contrata solo de
mano de obra o contrata a todo costo. La receta trae la de por defecto y el
planificador la cambia por partida antes de aprobar el plan; después, con una
nueva versión del plan. La modalidad decide qué líneas genera el plan."""
from odoo import api, fields, models
from odoo.exceptions import UserError

EXECUTION_MODES = [
    ('own', 'Personal propio'),
    ('labor_contract', 'Contrata solo de mano de obra'),
    ('full_contract', 'Contrata a todo costo'),
]


class ConstructionExecutionTemplate(models.Model):
    _inherit = 'construction.execution.template'

    execution_mode = fields.Selection(
        EXECUTION_MODES, string='Modalidad por defecto', default='own', required=True,
        tracking=True,
        help='Personal propio: cada recurso genera su línea. Contrata solo de mano de obra: la '
             'mano de obra y las herramientas van en una línea de contrata; los materiales y '
             'equipos, aparte. Contrata a todo costo: una sola línea de contrata por el costo '
             'total de la receta, sin pedir materiales.')
    contract_activity_id = fields.Many2one(
        'construction.labor.activity', string='Actividad de la contrata', check_company=True,
        help='La que paga a la contrata en las modalidades de contrata. Vacía: la de la línea de '
             'contrata de la receta.')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_execution_mode = fields.Selection(
        EXECUTION_MODES, string='Modalidad de ejecución',
        compute='_compute_construction_execution_mode', store=True, readonly=False,
        help='La de la receta, cambiable por partida antes de aprobar el plan; después, con una '
             'nueva versión del plan.')

    @api.depends('construction_execution_template_id.execution_mode')
    def _compute_construction_execution_mode(self):
        for task in self:
            task.construction_execution_mode = \
                task.construction_execution_template_id.execution_mode or False

    def write(self, vals):
        if 'construction_execution_mode' in vals \
                and not self.env.context.get('construction_plan_force'):
            self._construction_check_mode_change(vals['construction_execution_mode'])
        return super().write(vals)

    def _construction_check_mode_change(self, mode):
        """Con el plan vigente aprobado, la modalidad de una partida con
        líneas se cambia en una nueva versión del plan."""
        Line = self.env['construction.resource.plan.line'].sudo()
        Plan = self.env['construction.resource.plan'].sudo()
        for task in self.filtered(lambda t: t.construction_execution_mode != mode):
            plan = task.project_id._construction_current_plan()
            # Con una versión en preparación (borrador), el cambio va en ella.
            in_preparation = Plan.search_count(
                [('project_id', '=', task.project_id.id), ('state', '=', 'draft')], limit=1)
            if plan and plan.state != 'draft' and not in_preparation and Line.search_count(
                    [('plan_id', '=', plan.id), ('task_id', '=', task.id)], limit=1):
                raise UserError(self.env._(
                    'La partida %s ya está en el plan aprobado: cambie su modalidad en una nueva '
                    'versión del plan.', task.display_name))


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    construction_apu_detail = fields.Text(
        string='Detalle del análisis de precio unitario', copy=True,
        help='En «Contrata a todo costo»: los recursos de la receta, como referencia de análisis. '
             'No se piden ni se compran.')
