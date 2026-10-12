# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_income_coefficient = fields.Float(
        related='company_id.l10n_pe_income_coefficient', readonly=False)
    l10n_pe_income_coefficient_jan_feb = fields.Float(
        related='company_id.l10n_pe_income_coefficient_jan_feb', readonly=False)
    l10n_pe_income_suspended = fields.Boolean(
        related='company_id.l10n_pe_income_suspended', readonly=False)
    l10n_pe_tax_uit_amount = fields.Float(
        related='company_id.l10n_pe_tax_uit_amount', readonly=False)
    l10n_pe_monthly_tax_journal_id = fields.Many2one(
        related='company_id.l10n_pe_monthly_tax_journal_id', readonly=False)
    l10n_pe_income_advance_account_id = fields.Many2one(
        related='company_id.l10n_pe_income_advance_account_id', readonly=False)
    l10n_pe_income_payable_account_id = fields.Many2one(
        related='company_id.l10n_pe_income_payable_account_id', readonly=False)
