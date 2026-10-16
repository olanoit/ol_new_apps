# -*- coding: utf-8 -*-
"""Visibilidad de montos (v1.8, M18-10): los campos en soles de los días de cuadrilla solo
llegan al navegador de quien tiene el grupo «Planificación de obra: ve
montos» (ver al_construction_planner/models/construction_amounts.py)."""
from odoo import api, models


class ConstructionCrewDay(models.Model):
    _name = 'construction.crew.day'
    _inherit = ['construction.crew.day', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'amount'}
