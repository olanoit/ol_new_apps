# -*- coding: utf-8 -*-
"""Visibilidad de montos (v1.8, M18-10): los campos en soles de las liquidaciones de contratas solo
llegan al navegador de quien tiene el grupo «Planificación de obra: ve
montos» (ver al_construction_planner/models/construction_amounts.py)."""
from odoo import api, models


class ConstructionContractSettlement(models.Model):
    _name = 'construction.contract.settlement'
    _inherit = ['construction.contract.settlement', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'amount_gross', 'retention_amount', 'amount_discount', 'amount_net', 'amount_planned'}


class ConstructionContractSettlementLine(models.Model):
    _name = 'construction.contract.settlement.line'
    _inherit = ['construction.contract.settlement.line', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'price_unit', 'amount'}
