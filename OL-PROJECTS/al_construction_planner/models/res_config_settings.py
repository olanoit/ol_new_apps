# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_week_start_day = fields.Selection(
        related='company_id.construction_week_start_day', readonly=False)
    construction_settlement_day = fields.Selection(
        related='company_id.construction_settlement_day', readonly=False)
    construction_payment_day = fields.Selection(
        related='company_id.construction_payment_day', readonly=False)
    construction_categ_assembly_id = fields.Many2one(
        related='company_id.construction_categ_assembly_id', readonly=False)
    construction_categ_installation_id = fields.Many2one(
        related='company_id.construction_categ_installation_id', readonly=False)
