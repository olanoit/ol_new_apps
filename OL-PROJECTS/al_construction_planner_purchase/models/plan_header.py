# -*- coding: utf-8 -*-
from odoo import models

P = 'al_construction_planner.'
M = 'al_construction_planner_purchase.'


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def _construction_header_actions(self):
        """Paquete 1.20, M120-08: las opciones de este puente en la cabecera del
        plan (antes, botones sueltos)."""
        return super()._construction_header_actions() + [
            {'menu': 'program', 'sequence': 10, 'label': self.env._('Programar compra masiva'),
             'kind': 'action', 'target': M + 'action_plan_purchase_wizard', 'groups': [P + 'group_planner_user'],
             'states': ('approved', 'in_progress')},
            {'menu': 'program', 'sequence': 20, 'label': self.env._('Requerimiento de materiales para obra'),
             'kind': 'action', 'target': M + 'action_plan_request_wizard', 'groups': [P + 'group_planner_user'],
             'states': ('approved', 'in_progress')},
        ]
