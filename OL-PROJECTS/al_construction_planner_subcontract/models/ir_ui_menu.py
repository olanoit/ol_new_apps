# -*- coding: utf-8 -*-
from odoo import api, models

P = 'al_construction_planner.'

G = 'al_construction_planner.group_planner_feature_'


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _construction_feature_menus(self):
        """Paquete 1.20, M120-07: deductivos, intervenciones y fondo de garantía."""
        p = 'al_construction_planner_subcontract.'
        return super()._construction_feature_menus() + [
            (p + 'menu_planner_deductions', G + 'deductions'),
            (p + 'menu_planner_interventions', G + 'deductions'),
            (p + 'menu_planner_guarantee_funds', G + 'deductions'),
            (p + 'menu_planner_deduction_types', G + 'deductions'),
            (p + 'menu_planner_contract_requirements', G + 'deductions'),
        ]

    @api.model
    def _construction_moment_moves(self):
        """Paquete 1.20, M120-02: la configuración de contratas en su sección."""
        p = 'al_construction_planner_subcontract.'
        return super()._construction_moment_moves() + [
            (p + 'menu_planner_contract_conditions', P + 'menu_planner_config_contracts', 30),
            (p + 'menu_planner_deduction_types', P + 'menu_planner_config_contracts', 40),
            (p + 'menu_planner_contract_requirements', P + 'menu_planner_config_contracts', 50),
            (p + 'menu_planner_contract_documents', P + 'menu_planner_config_contracts', 60),
            (p + 'menu_planner_contract_opening', P + 'menu_planner_config_contracts', 70),
        ]

    @api.model
    def _construction_moment_names(self):
        p = 'al_construction_planner_subcontract.'
        return dict(super()._construction_moment_names(), **{
            p + 'menu_planner_deductions': self.env._('Deductivos de contrata'),
        })
