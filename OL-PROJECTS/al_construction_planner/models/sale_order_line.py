# -*- coding: utf-8 -*-
from odoo import fields, models

from .common import TYPOLOGY_FAMILIES


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Partida del contrato (D23: una línea de la OV por partida, cantidad 1).
    construction_family = fields.Selection(
        TYPOLOGY_FAMILIES, string='Familia de la partida',
        help='En la orden de venta del contrato de una obra: la partida reúne las líneas del '
             'plan de los ambientes cuya tipología es de esta familia. Sin familia, la partida '
             'toma el resto de la obra (como MOMEN, una sola partida «Cocinas»).')
    construction_valuation_line_ids = fields.One2many(
        'construction.valuation.line', 'sale_line_id', string='Valorizaciones',
        readonly=True)

    def _construction_price(self, day=None):
        """Precio de la partida (subtotal sin impuestos de la línea) en la
        moneda de la compañía de la obra."""
        self.ensure_one()
        order = self.order_id
        company = order.company_id
        return order.currency_id._convert(
            self.price_subtotal, company.currency_id, company,
            day or fields.Date.context_today(self))
