# -*- coding: utf-8 -*-
"""Cuadrillas propias en el tablero de obra, el menú Ejecutar y el menú por
momento (requerimiento CREVAL v1.0, capítulo 4)."""
from odoo import api, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def action_construction_assign_crew(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'al_construction_planner_crew.action_plan_crew_wizard')
        action['context'] = self._construction_board_context()
        return action

    def _construction_stat_buttons(self):
        return super()._construction_stat_buttons() + [
            (4, 'al_construction_planner.group_planner_user', {
                'icon': 'users', 'text': self.env._('Asignar cuadrilla'), 'number': '',
                'action_type': 'object', 'action': 'action_construction_assign_crew',
                'show': bool(self.construction_board_plan_id)}),
        ]


class ConstructionTaskExecuteWizard(models.TransientModel):
    _inherit = 'construction.task.execute.wizard'

    def action_assign_crew(self):
        return self._launch('al_construction_planner_crew.action_plan_crew_wizard')


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _construction_moment_moves(self):
        return super()._construction_moment_moves() + [
            ('al_construction_planner_crew.menu_planner_crew_assign',
             'al_construction_planner.menu_planner_exec_staff', 5),
        ]
