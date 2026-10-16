# -*- coding: utf-8 -*-
"""Visibilidad de montos (v1.8, M18-10): los campos en soles de el reparto del costo de personal solo
llegan al navegador de quien tiene el grupo «Planificación de obra: ve
montos» (ver al_construction_planner/models/construction_amounts.py)."""
from odoo import api, models


class ConstructionLaborCostAllocation(models.Model):
    _name = 'construction.labor.cost.allocation'
    _inherit = ['construction.labor.cost.allocation', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'amount_total'}


class ConstructionLaborCostAllocationLine(models.Model):
    _name = 'construction.labor.cost.allocation.line'
    _inherit = ['construction.labor.cost.allocation.line', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'hourly_cost', 'amount'}
