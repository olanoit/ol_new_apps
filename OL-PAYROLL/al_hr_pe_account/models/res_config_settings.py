# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_pe_payroll_move_journal_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.move_journal_id', readonly=False)
    l10n_pe_payroll_move_partner_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.move_partner_id', readonly=False)
    l10n_pe_payroll_detail_analytic = fields.Boolean(
        related='company_id.l10n_pe_main_parameter_id.detail_analytic', readonly=False)
    l10n_pe_payroll_detail_provision = fields.Boolean(
        related='company_id.l10n_pe_main_parameter_id.detallar_provision', readonly=False)
    # Cuentas de beneficios sociales (company_dependent en la configuración
    # principal; Ajustes siempre trabaja con la compañía activa, que es la suya).
    l10n_pe_payroll_cts_debe_account_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.cts_debe_account_id', readonly=False)
    l10n_pe_payroll_cts_haber_account_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.cts_haber_account_id', readonly=False)
    l10n_pe_payroll_grati_debe_account_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.grati_debe_account_id', readonly=False)
    l10n_pe_payroll_grati_haber_account_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.grati_haber_account_id', readonly=False)
    l10n_pe_payroll_boni_debe_account_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.boni_debe_account_id', readonly=False)
    l10n_pe_payroll_boni_haber_account_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.boni_haber_account_id', readonly=False)
    l10n_pe_payroll_vaca_debe_account_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.vaca_debe_account_id', readonly=False)
    l10n_pe_payroll_vaca_haber_account_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.vaca_haber_account_id', readonly=False)
    l10n_pe_payroll_cts_payable_account_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.cts_payable_account_id', readonly=False)
    l10n_pe_payroll_grati_payable_account_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.grati_payable_account_id', readonly=False)
    l10n_pe_payroll_liquidation_payable_account_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.liquidation_payable_account_id', readonly=False)
    l10n_pe_payroll_liq_concept_in_account_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.liq_concept_in_account_id', readonly=False)
    l10n_pe_payroll_liq_concept_out_account_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.liq_concept_out_account_id', readonly=False)
    l10n_pe_payroll_benefits_adjust_account_id = fields.Many2one(
        related='company_id.l10n_pe_main_parameter_id.benefits_adjust_account_id', readonly=False)
