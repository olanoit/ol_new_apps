# -*- coding: utf-8 -*-
from odoo import api, models

P = 'al_construction_planner.'


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _construction_moment_moves(self):
        """Paquete 1.20, M120-01 y M120-02: los metrados en Avance y lo de mobiliario en
        las secciones de Configuración."""
        p = 'al_construction_planner_furniture.'
        return super()._construction_moment_moves() + [
            (p + 'menu_planner_measured_spaces', P + 'menu_planner_progress', 50),
            (p + 'menu_planner_real_recipes', P + 'menu_planner_progress', 60),
            (p + 'menu_planner_typologies', P + 'menu_planner_config_recipes', 40),
            (p + 'menu_construction_furniture_type', P + 'menu_planner_config_recipes', 50),
            (p + 'menu_planner_join_rules', P + 'menu_planner_config_recipes', 60),
            (p + 'menu_planner_master_import', P + 'menu_planner_config_recipes', 70),
            (p + 'menu_planner_projection_import', P + 'menu_planner_config_recipes', 80),
            (p + 'menu_planner_rate_lists', P + 'menu_planner_config_contracts', 20),
            (p + 'menu_planner_rubro_accounts', P + 'menu_planner_config_analytic', 20),
        ]
