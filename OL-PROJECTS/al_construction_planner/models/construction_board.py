# -*- coding: utf-8 -*-
"""Ejecución de la obra (requerimiento CREVAL v1.0, capítulo 4): el tablero de
obra y la tarea de obra en Planificación de obra, la sección Obra del tablero
del proyecto y el menú Ejecutar de la tarea en Proyectos. Las dos entradas
lanzan los mismos asistentes con la obra, el plan vigente y la tarea
precargados; cada puente agrega sus acciones."""
from odoo import api, fields, models
from odoo.exceptions import UserError

from .common import can_see_amounts

FEATURE_EXEC_PROJECT = 'al_construction_planner.group_planner_feature_exec_project'


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_board_plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan de la obra',
        compute='_compute_construction_board')
    construction_board_plan_version = fields.Integer(
        string='Versión del plan', compute='_compute_construction_board')
    construction_board_progress = fields.Float(
        string='Avance físico', compute='_compute_construction_board',
        help='Ejecutado validado entre lo planificado de contratas y personal propio.')
    construction_board_planned = fields.Monetary(
        string='Planificado', compute='_compute_construction_board', currency_field='currency_id')
    construction_board_committed = fields.Monetary(
        string='Comprometido', compute='_compute_construction_board',
        currency_field='currency_id')
    construction_board_actual = fields.Monetary(
        string='Real', compute='_compute_construction_board', currency_field='currency_id')
    construction_board_remaining = fields.Monetary(
        string='Saldo del plan', compute='_compute_construction_board',
        currency_field='currency_id')
    construction_progress_to_validate_count = fields.Integer(
        string='Avances por validar', compute='_compute_construction_board')
    construction_exceed_count = fields.Integer(
        string='Excesos autorizados', compute='_compute_construction_board')

    def _compute_construction_board(self):
        Progress = self.env['construction.task.progress']
        to_validate = dict(Progress._read_group(
            [('project_id', 'in', self.ids), ('state', '=', 'draft')], ['project_id'],
            ['__count']))
        exceeds = dict(self.env['construction.exceed.log']._read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['__count']))
        for project in self:
            plan = project._construction_current_plan() if project.id else \
                self.env['construction.resource.plan']
            project.construction_board_plan_id = plan
            project.construction_board_plan_version = plan.version
            executed, planned = plan._progress_amounts([('plan_id', '=', plan.id)]).get(
                False, (0.0, 0.0)) if plan else (0.0, 0.0)
            project.construction_board_progress = executed / planned if planned else 0.0
            project.construction_board_planned = plan.amount_total
            project.construction_board_committed = plan.amount_committed
            project.construction_board_actual = plan.amount_actual
            project.construction_board_remaining = plan.amount_remaining
            project.construction_progress_to_validate_count = to_validate.get(project, 0)
            project.construction_exceed_count = exceeds.get(project, 0)

    def _construction_board_context(self, task=None):
        """Contexto de los asistentes del plan con la obra, el plan vigente y
        la tarea (o toda la obra)."""
        self.ensure_one()
        plan = self._construction_current_plan()
        if not plan or plan.state not in ('approved', 'in_progress'):
            raise UserError(self.env._(
                'La obra %s no tiene un plan aprobado: la ejecución se lanza sobre el plan '
                'vigente.', self.display_name))
        context = {'default_plan_id': plan.id, 'construction_project_id': self.id}
        if task:
            context['construction_selection_task_ids'] = task.ids
        else:
            context['construction_selection_project'] = True
        return context

    def _construction_open(self, xmlid, task=None, domain=None, context=None, name=None):
        """Acción ``xmlid`` con la obra (y la tarea) cargadas."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(xmlid)
        values = dict(context or {})
        if domain is not None:
            action['domain'] = domain
        action['context'] = values
        if name:
            action['name'] = name
        return action

    def action_construction_open_in_projects(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'project.project',
                'res_id': self.id, 'view_mode': 'form',
                'views': [(self.env.ref('project.edit_project').id, 'form')]}

    def action_construction_view_progress_to_validate(self):
        self.ensure_one()
        return self._construction_open(
            'al_construction_planner.action_construction_progress_to_validate',
            domain=[('project_id', '=', self.id), ('state', '=', 'draft')])

    def action_construction_view_exceeds(self):
        self.ensure_one()
        return self._construction_open(
            'al_construction_planner.action_construction_exceed_log',
            domain=[('project_id', '=', self.id)])

    def action_construction_view_control(self):
        self.ensure_one()
        plan = self._construction_plan_or_raise()
        return self._construction_open(
            'al_construction_planner.action_construction_plan_control',
            domain=[('plan_id', '=', plan.id)])

    def action_construction_view_current_plan(self):
        self.ensure_one()
        plan = self._construction_plan_or_raise()
        return {'type': 'ir.actions.act_window', 'res_model': plan._name, 'res_id': plan.id,
                'view_mode': 'form'}

    # ------------------------------------------------------------------
    # Tablero del proyecto en Proyectos (4.6)
    # ------------------------------------------------------------------
    def _construction_stat_buttons(self):
        """Botones de la sección Obra: [(secuencia, grupo, botón)]. Cada
        puente suma los suyos."""
        self.ensure_one()
        plan = self.construction_board_plan_id
        buttons = [
            (1, 'al_construction_planner.group_planner_plan_viewer', {
                'icon': 'sitemap', 'text': self.env._('Plan de recursos'),
                'number': 'v%s' % plan.version if plan else '—',
                'action_type': 'object', 'action': 'action_construction_view_current_plan',
                'show': bool(plan)}),
            (2, 'al_construction_planner.group_planner_plan_viewer', {
                'icon': 'balance-scale', 'text': self.env._('Control de saldo'),
                'number': '%.0f %%' % (100 * (plan.amount_actual / plan.amount_total)
                                       if plan and plan.amount_total else 0.0),
                'action_type': 'object', 'action': 'action_construction_view_control',
                'show': bool(plan) and can_see_amounts(self.env)}),
            (6, 'al_construction_planner.group_planner_exec_validator', {
                'icon': 'check-square-o', 'text': self.env._('Avances por validar'),
                'number': self.construction_progress_to_validate_count,
                'action_type': 'object',
                'action': 'action_construction_view_progress_to_validate', 'show': True}),
        ]
        return buttons

    def _get_stat_buttons(self):
        buttons = super()._get_stat_buttons()
        if not self.is_construction_site or not self.env.user.has_group(FEATURE_EXEC_PROJECT):
            return buttons
        for sequence, group, button in self._construction_stat_buttons():
            if group and not self.env.user.has_groups(group):
                continue
            buttons.append(dict(button, sequence=200 + sequence, construction_section=True))
        return buttons


class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_show_execute = fields.Boolean(compute='_compute_construction_show_execute')

    def _compute_construction_show_execute(self):
        show = self.env.user.has_group(FEATURE_EXEC_PROJECT) or self.env.user.has_group(
            'al_construction_planner.group_planner_feature_exec_planner')
        for task in self:
            task.construction_show_execute = show and bool(task.construction_level) \
                and bool(task.project_id.is_construction_site)

    def action_construction_execute(self):
        """Menú Ejecutar de la tarea de obra (4.5 y 4.7)."""
        self.ensure_one()
        self.project_id._construction_board_context(self)
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Ejecutar · %s', self.display_name),
            'res_model': 'construction.task.execute.wizard', 'view_mode': 'form',
            'target': 'new', 'context': {'default_task_id': self.id},
        }


class ConstructionTaskExecuteWizard(models.TransientModel):
    _name = 'construction.task.execute.wizard'
    _description = 'Ejecutar desde la tarea de obra'

    task_id = fields.Many2one('project.task', string='Tarea', required=True, readonly=True)
    project_id = fields.Many2one(related='task_id.project_id', string='Obra')
    plan_id = fields.Many2one('construction.resource.plan', string='Plan vigente',
                              compute='_compute_plan_id')

    @api.depends('task_id')
    def _compute_plan_id(self):
        for wizard in self:
            wizard.plan_id = wizard.task_id.project_id._construction_current_plan()

    def _launch(self, xmlid, extra=None):
        """El asistente ``xmlid`` con la obra, el plan vigente y la tarea."""
        self.ensure_one()
        context = self.task_id.project_id._construction_board_context(self.task_id)
        context.update(extra or {})
        action = self.env['ir.actions.act_window']._for_xml_id(xmlid)
        action['context'] = context
        return action

    def action_register_progress(self):
        return self._launch('al_construction_planner.action_plan_progress_wizard')
