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
