# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_cash_advance_account_id = fields.Many2one(
        related='company_id.l10n_pe_cash_advance_account_id', readonly=False)
    l10n_pe_petty_cash_account_id = fields.Many2one(
        related='company_id.l10n_pe_petty_cash_account_id', readonly=False)
    l10n_pe_cash_settlement_journal_id = fields.Many2one(
        related='company_id.l10n_pe_cash_settlement_journal_id', readonly=False)
    l10n_pe_mobility_account_id = fields.Many2one(
        related='company_id.l10n_pe_mobility_account_id', readonly=False)
    l10n_pe_rmv_amount = fields.Monetary(
        related='company_id.l10n_pe_rmv_amount', readonly=False)
    l10n_pe_mobility_limit_pct = fields.Float(
        related='company_id.l10n_pe_mobility_limit_pct', readonly=False)
