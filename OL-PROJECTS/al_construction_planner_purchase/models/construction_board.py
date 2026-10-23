# -*- coding: utf-8 -*-
"""Pedir material desde el tablero de obra, el menú Ejecutar y el tablero del
proyecto (requerimiento CREVAL v1.0, capítulo 4)."""
from odoo import models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def action_construction_request_material(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner_purchase.action_plan_request_wizard')
        action['context'] = self._construction_board_context()
        return action

    def _construction_stat_buttons(self):
        return super()._construction_stat_buttons() + [
            (5, 'al_construction_planner.group_planner_user', {
                'icon': 'cubes', 'text': self.env._('Pedir material'), 'number': '',
                'action_type': 'object', 'action': 'action_construction_request_material',
                'show': bool(self.construction_board_plan_id)}),
            (11, 'al_construction_material_request.group_construction_requester', {
                'icon': 'truck', 'text': self.env._('Requerimientos de obra'),
                # sudo: solo el número de requerimientos de la obra; el botón lo ve
                # quien es solicitante.
                'number': self.sudo().construction_request_count, 'action_type': 'object',
                'action': 'action_view_construction_requests', 'show': True}),
        ]


class ConstructionTaskExecuteWizard(models.TransientModel):
    _inherit = 'construction.task.execute.wizard'

    def action_request_material(self):
        return self._launch('al_construction_planner_purchase.action_plan_request_wizard')
