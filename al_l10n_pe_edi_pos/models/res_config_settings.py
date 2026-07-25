# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_l10n_pe_boleta_journal_id = fields.Many2one(
        related='pos_config_id.l10n_pe_boleta_journal_id', readonly=False)
    pos_l10n_pe_factura_journal_id = fields.Many2one(
        related='pos_config_id.l10n_pe_factura_journal_id', readonly=False)
