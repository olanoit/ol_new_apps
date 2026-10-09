# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_payroll_tareaje_night_from = fields.Float(
        related='company_id.l10n_pe_main_parameter_id.tareaje_night_from', readonly=False)
    l10n_pe_payroll_tareaje_night_to = fields.Float(
        related='company_id.l10n_pe_main_parameter_id.tareaje_night_to', readonly=False)
    l10n_pe_payroll_tareaje_he25_hours = fields.Float(
        related='company_id.l10n_pe_main_parameter_id.tareaje_he25_hours', readonly=False)
    l10n_pe_payroll_tareaje_late_tolerance = fields.Float(
        related='company_id.l10n_pe_main_parameter_id.tareaje_late_tolerance', readonly=False)
    l10n_pe_payroll_tareaje_round_minutes = fields.Integer(
        related='company_id.l10n_pe_main_parameter_id.tareaje_round_minutes', readonly=False)
    l10n_pe_payroll_tareaje_cost_basis = fields.Selection(
        related='company_id.l10n_pe_main_parameter_id.tareaje_cost_basis', readonly=False)
