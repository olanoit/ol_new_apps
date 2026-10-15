# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.al_construction_planner.models.common import TYPOLOGY_FAMILIES


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Partida del contrato (D23: una línea de la OV por partida, cantidad 1).
    construction_family = fields.Selection(
        TYPOLOGY_FAMILIES, string='Familia de la partida',
        help='En la orden de venta del contrato de una obra: la partida reúne las líneas del '
             'plan de los ambientes cuya tipología es de esta familia. Sin familia, la partida '
             'toma el resto de la obra (como MOMEN, una sola partida «Cocinas»).')
