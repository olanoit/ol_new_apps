# -*- coding: utf-8 -*-
from odoo import api, models

P = 'al_construction_planner.'

G = 'al_construction_planner.group_planner_feature_'


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _construction_feature_menus(self):
        """Paquete 1.20, M120-07: la valorización por entregas e hitos (mobiliario) y la
        valorización por avance (construcción), cada una con su función del perfil."""
        p = 'al_construction_planner_sale.'
        return super()._construction_feature_menus() + [
            (p + 'menu_planner_unit_milestones', G + 'milestones'),
            (p + 'menu_planner_deliveries', G + 'milestones'),
            (p + 'menu_planner_milestone_templates', G + 'milestones'),
            (p + 'menu_planner_valuation_prepare', G + 'valuation'),
            (p + 'menu_planner_valuations', G + 'valuation'),
            (p + 'menu_planner_valuation_targets', G + 'valuation'),
        ]

    @api.model
    def _construction_moment_moves(self):
        """Paquete 1.20, M120-02: las plantillas de hitos en «Hojas de trabajo y cobro»."""
        p = 'al_construction_planner_sale.'
        return super()._construction_moment_moves() + [
            (p + 'menu_planner_milestone_templates', P + 'menu_planner_config_sheets', 30),
        ]
