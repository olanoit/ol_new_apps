# -*- coding: utf-8 -*-
from odoo import api, models

P = 'al_construction_planner.'

G = 'al_construction_planner.group_planner_feature_'


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _construction_feature_menus(self):
        """Paquete 1.20, M120-07: el parte diario y el tareo del residente."""
        p = 'al_construction_portal.'
        return super()._construction_feature_menus() + [
            (p + 'menu_construction_daily_reports', G + 'daily_report'),
            (p + 'menu_construction_portal_tareo', G + 'daily_report'),
        ]

    @api.model
    def _construction_moment_moves(self):
        """Paquete 1.20, M120-01 y M120-02: el parte diario va a Avance, el tareo a
        Personal propio y la configuración del portal a «Portal y asistencia»."""
        p = 'al_construction_portal.'
        return super()._construction_moment_moves() + [
            (p + 'menu_construction_daily_reports', P + 'menu_planner_progress', 40),
            (p + 'menu_construction_portal_tareo', P + 'menu_planner_exec_staff', 30),
            (p + 'menu_construction_portal_kits', P + 'menu_planner_config_portal', 20),
            (p + 'menu_construction_portal_reasons', P + 'menu_planner_config_portal', 30),
            (p + 'menu_construction_portal_notice_rules', P + 'menu_planner_config_portal', 40),
        ]
