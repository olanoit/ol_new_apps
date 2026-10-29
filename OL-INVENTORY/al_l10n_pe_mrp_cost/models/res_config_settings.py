# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_mrp_labor_account_id = fields.Many2one(
        related='company_id.l10n_pe_mrp_labor_account_id', readonly=False)
