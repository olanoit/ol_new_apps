# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_approval_engine = fields.Selection(
        related='company_id.construction_approval_engine', readonly=False)

    construction_internal_approval_category_id = fields.Many2one(
        related='company_id.construction_internal_approval_category_id', readonly=False)
