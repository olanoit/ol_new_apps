# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_term_deposit_notice_days = fields.Integer(
        related='company_id.l10n_pe_term_deposit_notice_days', readonly=False)
    l10n_pe_term_deposit_itf = fields.Boolean(
        related='company_id.l10n_pe_term_deposit_itf', readonly=False)
    l10n_pe_term_deposit_itf_rate = fields.Float(
        related='company_id.l10n_pe_term_deposit_itf_rate', readonly=False)
    l10n_pe_term_deposit_itf_account_id = fields.Many2one(
        related='company_id.l10n_pe_term_deposit_itf_account_id', readonly=False)
