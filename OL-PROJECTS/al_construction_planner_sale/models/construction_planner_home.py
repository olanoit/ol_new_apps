# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.exceptions import UserError


class ConstructionPlannerHome(models.AbstractModel):
    _inherit = 'construction.planner.home'

    @api.model
    def _next_milestone_candidates(self, project, today):
        """Corte, presentación, confirmación, factura y cobro de las
        valorizaciones previstas (P-21)."""
        candidates = super()._next_milestone_candidates(project, today)
        labels = {
            'cutoff': self.env._('Valorización %s · corte'),
            'submit': self.env._('Valorización %s · presentación'),
            'confirm': self.env._('Valorización %s · confirmación'),
            'invoice': self.env._('Valorización %s · factura'),
            'collection': self.env._('Valorización %s · cobro'),
        }
        try:
            forecast = project._construction_get_valuation_forecast() \
                if project.construction_sale_order_id else {'rows': []}
        except UserError:
            forecast = {'rows': []}
        for row in forecast['rows']:
            for key, label in labels.items():
                if row.get(key) and row[key] >= today:
                    candidates.append((row[key], label % row['number']))
        return candidates

    @api.model
    def _pending_definitions(self, today):
        return super()._pending_definitions(today) + [
            ('deliveries_to_confirm', 'manager', self.env._('Entregas semanales por confirmar'),
             self.env._('Ingresos'), 'construction.weekly.delivery',
             [('state', '=', 'draft')],
             'al_construction_planner_sale.action_construction_weekly_delivery'),
            ('valuations_to_invoice', 'revenue',
             self.env._('Valorizaciones confirmadas por facturar'), self.env._('Ingresos'),
             'construction.valuation', [('state', '=', 'confirmed')],
             'al_construction_planner_sale.action_construction_valuation'),
        ]
