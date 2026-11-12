# -*- coding: utf-8 -*-
from odoo import api, models

P = 'al_construction_planner.'


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _construction_moment_moves(self):
        """Paquete 1.20, M120-02: las hojas de mobiliario en «Hojas de trabajo y cobro»."""
        p = 'al_construction_planner_spreadsheet_furniture.'
        return super()._construction_moment_moves() + [
            (p + 'menu_construction_sheet_parameter', P + 'menu_planner_config_sheets', 10),
            (p + 'menu_construction_sale_rate', P + 'menu_planner_config_sheets', 20),
        ]
