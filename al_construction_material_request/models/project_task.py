# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    construction_request_count = fields.Integer(
        string='Nº de requerimientos de obra', compute='_compute_construction_request_count')

    def _compute_construction_request_count(self):
        groups = self.env['construction.material.request']._read_group(
            [('task_id', 'in', self.ids)], ['task_id'], ['__count'])
        counts = {task.id: count for task, count in groups}
        for task in self:
            task.construction_request_count = counts.get(task.id, 0)

    def action_view_construction_requests(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_material_request.action_construction_material_request')
        action['domain'] = [('task_id', '=', self.id)]
        action['context'] = {
            'default_project_id': self.project_id.id,
            'default_task_id': self.id,
        }
        return action
