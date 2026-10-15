# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_price_alert_pct = fields.Float(
        string='Alerta de precio sobre el plan (%)', default=5.0,
        help='El abastecimiento de la obra marca el producto cuyo último precio de compra '
             'supera el costo del plan en este porcentaje o más.')
