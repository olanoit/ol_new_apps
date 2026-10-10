# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_week_start_day = fields.Selection(
        related='company_id.construction_week_start_day', readonly=False)
    construction_settlement_day = fields.Selection(
        related='company_id.construction_settlement_day', readonly=False)
    construction_payment_day = fields.Selection(
        related='company_id.construction_payment_day', readonly=False)
    construction_retention_account_id = fields.Many2one(
        related='company_id.construction_retention_account_id', readonly=False)
    construction_price_alert_pct = fields.Float(
        related='company_id.construction_price_alert_pct', readonly=False)
    # Ruta del ingreso (P-21): valores por defecto de las obras nuevas.
    construction_valuation_every = fields.Integer(
        related='company_id.construction_valuation_every', readonly=False)
    construction_valuation_unit = fields.Selection(
        related='company_id.construction_valuation_unit', readonly=False)
    construction_valuation_submit_days = fields.Integer(
        related='company_id.construction_valuation_submit_days', readonly=False)
    construction_client_confirm_days = fields.Integer(
        related='company_id.construction_client_confirm_days', readonly=False)
    construction_invoice_days = fields.Integer(
        related='company_id.construction_invoice_days', readonly=False)
    construction_collection_days = fields.Integer(
        related='company_id.construction_collection_days', readonly=False)
    construction_advance_pct = fields.Float(
        related='company_id.construction_advance_pct', readonly=False)
    construction_advance_amortization_pct = fields.Float(
        related='company_id.construction_advance_amortization_pct', readonly=False)
    construction_guarantee_pct = fields.Float(
        related='company_id.construction_guarantee_pct', readonly=False)
    construction_guarantee_release = fields.Selection(
        related='company_id.construction_guarantee_release', readonly=False)
    construction_income_calendar_id = fields.Many2one(
        related='company_id.construction_income_calendar_id', readonly=False)
    construction_guarantee_account_id = fields.Many2one(
        related='company_id.construction_guarantee_account_id', readonly=False)
    construction_advance_account_id = fields.Many2one(
        related='company_id.construction_advance_account_id', readonly=False)
