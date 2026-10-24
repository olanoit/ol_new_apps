# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    al_stock_overview_style = fields.Selection(
        related='company_id.al_stock_overview_style', readonly=False)
    al_stock_overview_graph = fields.Boolean(
        related='company_id.al_stock_overview_graph', readonly=False)
    al_stock_overview_width = fields.Selection(
        related='company_id.al_stock_overview_width', readonly=False)
