# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_payroll_fortnightly_type = fields.Selection(
        related='company_id.l10n_pe_main_parameter_id.fortnightly_type', readonly=False)
    l10n_pe_payroll_fortnightly_rate = fields.Float(
        related='company_id.l10n_pe_main_parameter_id.tasa', readonly=False)
    l10n_pe_payroll_fortnightly_family_allowance = fields.Boolean(
        related='company_id.l10n_pe_main_parameter_id.compute_af', readonly=False)
    l10n_pe_payroll_fortnightly_pension = fields.Boolean(
        related='company_id.l10n_pe_main_parameter_id.compute_afiliacion', readonly=False)
    l10n_pe_payroll_vacation_family_allowance = fields.Boolean(
        related='company_id.l10n_pe_main_parameter_id.compute_af_vac', readonly=False)
    l10n_pe_payroll_settlement_employee_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.employee_in_charge_id', readonly=False)
