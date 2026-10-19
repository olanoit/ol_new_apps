# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_pos_voucher_account_id = fields.Many2one(
        related='company_id.l10n_pe_pos_voucher_account_id', readonly=False)
