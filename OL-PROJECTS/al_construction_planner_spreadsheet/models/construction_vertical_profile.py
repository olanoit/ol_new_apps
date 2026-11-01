# -*- coding: utf-8 -*-
"""Tipo de hoja de trabajo del perfil (paquete 1.16, etapa 4).

El tipo de hoja de una obra sale de su perfil, no del código del perfil: los
perfiles «Construcción PROF 4» a «PROF 6» de la etapa 1 tienen otro código y
abrían el maestro de mobiliario en una base con los dos puentes."""
from odoo import api, fields, models

from .documents_document import SHEET_KINDS


class ConstructionVerticalProfile(models.Model):
    _inherit = 'construction.vertical.profile'

    construction_spreadsheet_kind = fields.Selection(
        SHEET_KINDS, string='Hoja de trabajo',
        help='Qué hoja abre «Hoja de trabajo» en las obras del perfil. Vacío: presupuesto y '
             'plan.')

    def _export_data(self):
        data = super()._export_data()
        data['spreadsheet_kind'] = self.construction_spreadsheet_kind or False
        return data

    @api.model
    def _import_data(self, data):
        profile = super()._import_data(data)
        if 'spreadsheet_kind' in data:
            profile.construction_spreadsheet_kind = data['spreadsheet_kind'] or False
        return profile
