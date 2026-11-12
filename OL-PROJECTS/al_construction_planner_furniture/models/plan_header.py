# -*- coding: utf-8 -*-
from odoo import models

P = 'al_construction_planner.'
M = 'al_construction_planner_furniture.'


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def _construction_header_actions(self):
        """Paquete 1.20, M120-08: las opciones de este puente en la cabecera del
        plan (antes, botones sueltos)."""
        return super()._construction_header_actions() + [
            {'menu': 'execute', 'sequence': 40, 'label': self.env._('Fabricar o enviar módulos'),
             'kind': 'action', 'target': M + 'action_construction_module_dispatch_wizard', 'groups': [],
             'states': ('approved', 'in_progress')},
        ]
