# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_price_alert_pct = fields.Float(
        related='company_id.construction_price_alert_pct', readonly=False)
