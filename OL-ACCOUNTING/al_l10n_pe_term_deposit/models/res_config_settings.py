# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_term_deposit_notice_days = fields.Integer(
        related='company_id.l10n_pe_term_deposit_notice_days', readonly=False)
