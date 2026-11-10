# -*- coding: utf-8 -*-
from odoo import api, models


class ConstructionPlannerHome(models.AbstractModel):
    _inherit = 'construction.planner.home'

    @api.model
    def _pending_areas(self):
        """Paquete 7 de CREVAL, CR-65: área de los pendientes del puente."""
        return dict(super()._pending_areas(), settlements_to_validate='contracts')

    @api.model
    def _pending_definitions(self, today):
        return super()._pending_definitions(today) + [
            ('settlements_to_validate', 'planner', self.env._('Liquidaciones por validar'),
             self.env._('Contratas'), 'construction.contract.settlement',
             [('state', '=', 'submitted')] + self._pending_mine(),
             'al_construction_planner_subcontract.action_construction_contract_settlement'),
        ]
