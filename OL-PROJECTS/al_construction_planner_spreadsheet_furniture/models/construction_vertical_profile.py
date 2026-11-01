# -*- coding: utf-8 -*-
from odoo import api, models


class ConstructionVerticalProfile(models.Model):
    _inherit = 'construction.vertical.profile'

    @api.model
    def _construction_set_furniture_sheet(self):
        """El perfil Mobiliario del planificador abre el maestro de
        mobiliario, salvo que la base ya le haya puesto otro tipo de hoja."""
        profile = self.env.ref('al_construction_planner.profile_furniture',
                               raise_if_not_found=False)
        if profile and not profile.construction_spreadsheet_kind:
            profile.construction_spreadsheet_kind = 'furniture'
