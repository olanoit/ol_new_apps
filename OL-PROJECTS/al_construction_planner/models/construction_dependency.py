# -*- coding: utf-8 -*-
"""Dependencias de terceros (v1.5, fase 19, P-32).

Una **dependencia** (``construction.dependency``) es lo que un tercero debe
entregar antes de empezar una etapa: encimera, electrodomésticos, frente
liberado, piloto aprobado o instalaciones. Mientras está abierta, la etapa de
las unidades que cubre no admite avances, el cronograma la marca y no se
puede programar antes de la fecha prevista.
"""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from .common import stage_selection

DEPENDENCY_KINDS = [
    ('countertop', 'Encimera'),
    ('appliances', 'Electrodomésticos'),
    ('front', 'Frente liberado'),
    ('pilot', 'Piloto aprobado'),
    ('mep', 'Instalaciones (eléctricas y sanitarias)'),
]
DEPENDENCY_STATES = [
    ('open', 'Abierta'),
    ('done', 'Cumplida'),
    ('cancel', 'Anulada'),
]


class ConstructionDependency(models.Model):
    _name = 'construction.dependency'
    _description = 'Dependencia de terceros en la obra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'state, date_expected, id'
    _check_company_auto = True

    name = fields.Char(string='Descripción', required=True)
    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, index=True, check_company=True,
        domain="[('is_construction_site', '=', True)]")
    company_id = fields.Many2one(
        'res.company', string='Compañía', compute='_compute_company_id', store=True, index=True,
        precompute=True)
    kind = fields.Selection(DEPENDENCY_KINDS, string='Tipo', required=True, default='countertop')
    partner_id = fields.Many2one(
        'res.partner', string='Responsable', check_company=True,
        help='El tercero que debe cumplirla: el cliente, su proveedor u otra contrata.')
    task_ids = fields.Many2many(
        'project.task', string='Niveles', check_company=True,
        domain="[('project_id', '=', project_id), "
               "('construction_level', 'in', ('group', 'floor', 'apartment', 'space'))]",
        help='Agrupadores, pisos, unidades o ambientes que espera. Vacío: toda la obra.')
    stage = fields.Selection(
        stage_selection, string='Etapa que bloquea', required=True, default='installation')
    date_expected = fields.Date(
        string='Fecha prevista', tracking=True,
        help='Desde cuándo se espera cumplida: la etapa no se programa antes.')
    date_done = fields.Date(string='Cumplida el', readonly=True, copy=False)
    state = fields.Selection(DEPENDENCY_STATES, string='Estado', required=True, default='open',
                             tracking=True, copy=False)
    note = fields.Text(string='Nota')
    stage_count = fields.Integer(string='Etapas bloqueadas', compute='_compute_stage_count')

    @api.depends('project_id.company_id')
    def _compute_company_id(self):
        for dependency in self:
            dependency.company_id = dependency.project_id.company_id or dependency.company_id \
                or self.env.company

    def _stages_domain(self):
        self.ensure_one()
        domain = [('project_id', '=', self.project_id.id), ('stage', '=', self.stage)]
        if self.task_ids:
            domain.append(('space_task_id', 'child_of', self.task_ids.ids))
        return domain

    def _blocked_stages(self):
        Stage = self.env['construction.space.stage']
        stages = Stage.browse()
        for dependency in self.filtered(lambda d: d.state == 'open'):
            stages |= Stage.search(dependency._stages_domain())
        return stages

    def _compute_stage_count(self):
        for dependency in self:
            dependency.stage_count = len(dependency._blocked_stages())

    def _covers(self, task):
        """La dependencia alcanza a ``task`` (sus niveles o uno de sus
        ancestros)."""
        self.ensure_one()
        if task.project_id != self.project_id:
            return False
        if not self.task_ids:
            return True
        node = task
        while node:
            if node in self.task_ids:
                return True
            node = node.parent_id
        return False

    @api.model
    def _open_for(self, task, stage):
        """Dependencias abiertas que bloquean la etapa ``stage`` de ``task``."""
        if not task or not stage:
            return self.browse()
        dependencies = self.search([('project_id', '=', task.project_id.id),
                                    ('stage', '=', stage), ('state', '=', 'open')])
        return dependencies.filtered(lambda d: d._covers(task))

    def action_done(self):
        self.write({'state': 'done', 'date_done': fields.Date.context_today(self)})

    def action_cancel(self):
        self.state = 'cancel'

    def action_reopen(self):
        self.write({'state': 'open', 'date_done': False})

    def action_view_stages(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Etapas bloqueadas · %s', self.name),
            'res_model': 'construction.space.stage',
            'view_mode': 'list',
            'domain': self._stages_domain(),
        }

    def action_shift_schedule(self):
        """Corre al día hábil siguiente a la fecha prevista las etapas que
        bloquea y que empiezan antes; cada una conserva sus días hábiles y
        empuja las siguientes de su ambiente."""
        moved = self.env['construction.space.stage']
        for dependency in self.filtered(lambda d: d.state == 'open'):
            if not dependency.date_expected:
                raise UserError(self.env._(
                    'Indique la fecha prevista de %s para mover el cronograma.', dependency.name))
            limit = dependency.date_expected
            for stage in dependency._blocked_stages().filtered(lambda s: s.date_start <= limit):
                company = stage._company_for_days()
                days = company._construction_count_site_days(stage.date_start, stage.date_end)
                start = company._construction_next_site_day(limit + timedelta(days=1))
                end = company._construction_add_site_days(start, days)
                stage.with_context(construction_dependency_shift=True).action_gantt_reschedule(
                    start, end, chain=True)
                moved |= stage
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'success' if moved else 'info', 'sticky': False,
                       'message': self.env._('%s etapas movidas.', len(moved))},
        }


class ConstructionSpaceStage(models.Model):
    _inherit = 'construction.space.stage'

    dependency_ids = fields.Many2many(
        'construction.dependency', string='Dependencias abiertas',
        compute='_compute_dependency_ids')
    blocked = fields.Boolean(string='Bloqueada', compute='_compute_dependency_ids')

    def _compute_dependency_ids(self):
        Dependency = self.env['construction.dependency']
        for record in self:
            record.dependency_ids = Dependency._open_for(record.space_task_id, record.stage)
            record.blocked = bool(record.dependency_ids)

    @api.model
    def action_gantt_reschedule(self, date_start, date_end, chain=False):
        start = fields.Date.to_date(date_start)
        if start and not self.env.context.get('construction_dependency_shift'):
            for dependency in self.env['construction.dependency']._open_for(
                    self.space_task_id, self.stage):
                if dependency.date_expected and start <= dependency.date_expected:
                    raise UserError(self.env._(
                        '%(stage)s espera «%(dependency)s» hasta el %(date)s: programe la '
                        'etapa después.', stage=self.display_name, dependency=dependency.name,
                        date=fields.Date.to_string(dependency.date_expected)))
        return super().action_gantt_reschedule(date_start, date_end, chain=chain)


class ConstructionTaskProgress(models.Model):
    _inherit = 'construction.task.progress'

    @api.model_create_multi
    def create(self, vals_list):
        progresses = super().create(vals_list)
        Dependency = self.env['construction.dependency']
        for progress in progresses:
            dependencies = Dependency._open_for(progress.task_id,
                                                progress.plan_line_id.stage)
            if dependencies:
                raise UserError(self.env._(
                    'La etapa de %(task)s está bloqueada por %(dependencies)s: no admite '
                    'avances hasta que se cumpla.', task=progress.task_id.display_name,
                    dependencies=', '.join(dependencies.mapped('name'))))
        return progresses
