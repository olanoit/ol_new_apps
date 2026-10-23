# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Planchas enteras (paquete 1.11, M111-12): la casilla vive en la
    # compañía (al_stock_base) porque el requerimiento de obra también la lee.
    construction_whole_sheet = fields.Boolean(
        related='company_id.construction_whole_sheet', readonly=False)
    construction_whole_sheet_tolerance = fields.Float(
        related='company_id.construction_whole_sheet_tolerance', readonly=False)
