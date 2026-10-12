# -*- coding: utf-8 -*-
from odoo import fields, models

from .res_company import POST_MODES


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Del RUC: se guardan en la compañía raíz.
    l10n_pe_cpe_client_id = fields.Char(
        related='company_id.root_id.l10n_pe_cpe_client_id', readonly=False,
        groups='base.group_system')
    l10n_pe_cpe_client_secret = fields.Char(
        related='company_id.root_id.l10n_pe_cpe_client_secret', readonly=False,
        groups='base.group_system')
    l10n_pe_cpe_post_mode = fields.Selection(
        POST_MODES, related='company_id.l10n_pe_cpe_post_mode', readonly=False, required=True)
