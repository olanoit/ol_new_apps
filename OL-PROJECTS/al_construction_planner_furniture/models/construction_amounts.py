# -*- coding: utf-8 -*-
"""Visibilidad de montos (v1.8, M18-10): los campos en soles de la vertical Mobiliario solo
llegan al navegador de quien tiene el grupo «Planificación de obra: ve
montos» (ver al_construction_planner/models/construction_amounts.py)."""
from odoo import api, models


class ConstructionTypology(models.Model):
    _inherit = 'construction.typology'

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'module_assembly_amount'}


class ConstructionRateListLine(models.Model):
    _name = 'construction.rate.list.line'
    _inherit = ['construction.rate.list.line', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'price'}


class ConstructionRealRecipe(models.Model):
    _name = 'construction.real.recipe'
    _inherit = ['construction.real.recipe', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'amount_planned', 'amount_real'}


class ConstructionRecipeVersus(models.Model):
    _name = 'construction.recipe.versus'
    _inherit = ['construction.recipe.versus', 'construction.amounts.mixin']

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'cost_unit', 'amount_planned', 'amount_real', 'amount_difference'}
