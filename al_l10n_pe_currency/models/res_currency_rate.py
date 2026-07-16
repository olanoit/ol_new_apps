# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCurrencyRate(models.Model):
    _inherit = 'res.currency.rate'

    # Tipo de cambio peruano (SUNAT publica compra y venta). Odoo nativo solo
    # maneja una tasa única (`rate`); estos campos son el valor agregado local.
    rate_purchase = fields.Float(
        string='Compra', digits='Dual_Currency_TRM',
        help='Tipo de cambio compra publicado por SUNAT.')
    rate_sale = fields.Float(
        string='Venta', digits='Dual_Currency_TRM',
        help='Tipo de cambio venta publicado por SUNAT. Es el usado por defecto '
             'para la conversión contable (rate = 1 / venta).')
    ref_origin = fields.Selection(
        [('sunat', 'SUNAT'), ('apis_net', 'apis.net.pe'), ('manual', 'Manual')],
        string='Origen', default='manual', required=True,
        help='Fuente que generó este tipo de cambio.')

    # Nota: se usa la constraint nativa de v19 unique(name, currency_id,
    # company_id) — un tipo de cambio por día/moneda/compañía. `ref_origin` es
    # solo informativo (no forma parte de la unicidad).
