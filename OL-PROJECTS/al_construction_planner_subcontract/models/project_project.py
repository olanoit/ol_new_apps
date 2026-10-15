# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_settlement_count = fields.Integer(
        string='Nº de liquidaciones', compute='_compute_construction_settlement_count')

    def _compute_construction_settlement_count(self):
        counts = dict(self.env['construction.contract.settlement']._read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['__count']))
        for project in self:
            project.construction_settlement_count = counts.get(project, 0)

    def action_view_construction_settlements(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Liquidaciones de %s', self.display_name),
            'res_model': 'construction.contract.settlement',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
