# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_retention_account_id = fields.Many2one(
        related='company_id.construction_retention_account_id', readonly=False)
    construction_discount_account_id = fields.Many2one(
        related='company_id.construction_discount_account_id', readonly=False)
