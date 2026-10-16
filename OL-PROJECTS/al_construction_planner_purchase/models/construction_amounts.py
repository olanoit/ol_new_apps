# -*- coding: utf-8 -*-
"""Visibilidad de montos (v1.8, M18-10): los campos en soles de este puente solo
llegan al navegador de quien tiene el grupo «Planificación de obra: ve
montos» (ver al_construction_planner/models/construction_amounts.py)."""
from odoo import api, models


class ConstructionPurchasePriceReport(models.Model):
    _name = 'construction.purchase.price.report'
    _inherit = ['construction.purchase.price.report', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'price_unit_currency', 'price_unit', 'amount'}
