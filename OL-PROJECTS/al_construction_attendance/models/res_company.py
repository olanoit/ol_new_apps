# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_labor_cost_account_id = fields.Many2one(
        'account.analytic.account', string='Partida de mano de obra fija (MODF)',
        help='Partida de costo del personal propio: la planilla repartida por obra la lleva '
             'junto a la cuenta de la obra y la etapa de la sede.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_labor_cost_account_id = fields.Many2one(
        related='company_id.construction_labor_cost_account_id', readonly=False)
