# -*- coding: utf-8 -*-
"""Cambios de obra y cobro al cliente en el tablero de obra, el menú Ejecutar y
el tablero del proyecto (requerimiento CREVAL v1.0, capítulo 4)."""
from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_change_draft_count = fields.Integer(
        string='Cambios en borrador', compute='_compute_construction_change_draft_count')

    def _compute_construction_change_draft_count(self):
        counts = dict(self.env['construction.change.order']._read_group(
            [('project_id', 'in', self.ids), ('state', '=', 'draft')], ['project_id'],
            ['__count']))
        for project in self:
            project.construction_change_draft_count = counts.get(project, 0)

    def action_construction_view_changes(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner_sale.action_construction_change_order')
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {'default_project_id': self.id}
        return action

    def action_construction_view_contracts(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner_sale.action_construction_contract')
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {'default_project_id': self.id}
        return action

    def _construction_stat_buttons(self):
        user = 'al_construction_planner.group_planner_user'
        return super()._construction_stat_buttons() + [
            (10, user, {'icon': 'exchange', 'text': self.env._('Cambios de obra'),
                        'number': self.construction_change_draft_count, 'action_type': 'object',
                        'action': 'action_construction_view_changes', 'show': True}),
            (12, 'al_construction_planner.group_planner_revenue', {
                'icon': 'handshake-o', 'text': self.env._('Valorizaciones al cliente'),
                'number': self.construction_valuation_count, 'action_type': 'object',
                'action': 'action_view_construction_valuations', 'show': True}),
        ]


class ConstructionTaskExecuteWizard(models.TransientModel):
    _inherit = 'construction.task.execute.wizard'

    def action_register_change(self):
        """Cambio de obra en borrador con la obra, el plan vigente y la tarea."""
        self.ensure_one()
        task = self.task_id
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Registrar cambio'),
            'res_model': 'construction.change.order', 'view_mode': 'form', 'target': 'current',
            'context': {
                'default_project_id': task.project_id.id,
                'default_line_ids': [(0, 0, {'task_id': task.id})],
            },
        }
