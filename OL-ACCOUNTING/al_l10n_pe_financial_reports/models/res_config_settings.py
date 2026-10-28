# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_ws_function_prefixes = fields.Char(
        related='company_id.l10n_pe_ws_function_prefixes', readonly=False)
