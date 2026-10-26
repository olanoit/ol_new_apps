# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_treasury_plan_approval_amount = fields.Monetary(
        related='company_id.l10n_pe_treasury_plan_approval_amount', readonly=False)
    l10n_pe_treasury_plan_double_amount = fields.Monetary(
        related='company_id.l10n_pe_treasury_plan_double_amount', readonly=False)
    l10n_pe_treasury_transfer_approval_amount = fields.Monetary(
        related='company_id.l10n_pe_treasury_transfer_approval_amount', readonly=False)
    l10n_pe_treasury_notice_days = fields.Integer(
        related='company_id.l10n_pe_treasury_notice_days', readonly=False)
    l10n_pe_bancarization_mode = fields.Selection(
        related='company_id.l10n_pe_bancarization_mode', readonly=False)
    l10n_pe_bancarization_amount_pen = fields.Float(
        related='company_id.l10n_pe_bancarization_amount_pen', readonly=False)
    l10n_pe_bancarization_amount_usd = fields.Float(
        related='company_id.l10n_pe_bancarization_amount_usd', readonly=False)
