# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_exchange_rate_type_out = fields.Selection(
        related='company_id.l10n_pe_exchange_rate_type_out', readonly=False)
    l10n_pe_exchange_rate_type_in = fields.Selection(
        related='company_id.l10n_pe_exchange_rate_type_in', readonly=False)
