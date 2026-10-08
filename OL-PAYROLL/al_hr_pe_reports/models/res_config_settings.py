# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_payroll_voucher_encrypt = fields.Boolean(
        related='company_id.l10n_pe_main_parameter_id.l10n_pe_voucher_encrypt', readonly=False)
    l10n_pe_payroll_payment_journal_ids = fields.Many2many(
        related='company_id.l10n_pe_main_parameter_id.journals_banks', readonly=False)
