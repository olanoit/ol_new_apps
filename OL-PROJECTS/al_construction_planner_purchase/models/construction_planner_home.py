# -*- coding: utf-8 -*-
from odoo import api, models

from .construction_supply_board import SOON_DAYS


class ConstructionPlannerHome(models.AbstractModel):
    _inherit = 'construction.planner.home'

    @api.model
    def _pending_definitions(self, today):
        return super()._pending_definitions(today) + [
            ('supply_no_po', 'planner',
             self.env._('Necesidades sin OC en menos de %s días', SOON_DAYS),
             self.env._('Abastecimiento'), 'supply', 'no_po',
             'al_construction_planner_purchase.action_construction_supply_board'),
            ('supply_price', 'planner', self.env._('Último precio sobre el costo del plan'),
             self.env._('Abastecimiento'), 'supply', 'price',
             'al_construction_planner_purchase.action_construction_supply_board'),
        ]

    @api.model
    def _supply_alerts(self, today):
        plans = self.env['construction.resource.plan'].search(
            [('state', 'in', ('approved', 'in_progress'))])
        return self.env['construction.supply.board']._get_supply_alerts(
            plans.project_id, date_ref=today)

    @api.model
    def _pending_entry(self, model, domain, label, action_ref, today, cache):
        """Alertas de abastecimiento: se calculan una vez para los dos pendientes."""
        if model != 'supply':
            return super()._pending_entry(model, domain, label, action_ref, today, cache)
        if 'supply' not in cache:
            cache['supply'] = self._supply_alerts(today)
        matching = [a for a in cache['supply'] if a['type'] == domain]
        action = self.env['ir.actions.actions']._for_xml_id(action_ref)
        if matching:
            action['context'] = {'construction_project_id': matching[0]['project_id']}
        return len(matching), action
