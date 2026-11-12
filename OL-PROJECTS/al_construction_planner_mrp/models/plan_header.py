# -*- coding: utf-8 -*-
from odoo import models

P = 'al_construction_planner.'
M = 'al_construction_planner_mrp.'


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def _construction_header_actions(self):
        """Paquete 1.20, M120-08: las opciones de este puente en la cabecera del
        plan (antes, botones sueltos)."""
        return super()._construction_header_actions() + [
            {'menu': 'program', 'sequence': 30, 'label': self.env._('Requerimiento de fabricación'),
             'kind': 'action', 'target': M + 'action_plan_production_wizard', 'groups': [P + 'group_planner_user'],
             'states': ('approved', 'in_progress')},
        ]
