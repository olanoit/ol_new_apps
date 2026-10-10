# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .construction_resource_plan import DRAFT_STATES, OPEN_STATES


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_plan_ids = fields.One2many(
        'construction.resource.plan', 'project_id', string='Planes de recursos')
    construction_plan_count = fields.Integer(
        string='Nº de planes de recursos', compute='_compute_construction_plan_count')
    construction_typology_ids = fields.One2many(
        'construction.typology', 'project_id', string='Tipologías')
    construction_typology_count = fields.Integer(
        string='Nº de tipologías', compute='_compute_construction_plan_count')

    def _compute_construction_plan_count(self):
        plans = dict(self.env['construction.resource.plan']._read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['__count']))
        typologies = dict(self.env['construction.typology']._read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['__count']))
        for project in self:
            project.construction_plan_count = plans.get(project, 0)
            project.construction_typology_count = typologies.get(project, 0)

    def _construction_current_plan(self):
        """Plan vigente de la obra o, si aún no se aprobó ninguno, el que está
        en preparación."""
        self.ensure_one()
        Plan = self.env['construction.resource.plan']
        return (Plan.search([('project_id', '=', self.id), ('state', 'in', OPEN_STATES)], limit=1)
                or Plan.search([('project_id', '=', self.id), ('state', 'in', DRAFT_STATES)],
                               limit=1))

    def action_view_construction_plans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Planes de recursos'),
            'res_model': 'construction.resource.plan',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_construction_typologies(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Tipologías'),
            'res_model': 'construction.typology',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
