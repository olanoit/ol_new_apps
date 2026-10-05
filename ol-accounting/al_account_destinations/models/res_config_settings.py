# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_dest_type = fields.Selection(
        related='company_id.l10n_pe_dest_type', readonly=False,
        string='Tipo de destino')
