# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    construction_creates_site = fields.Boolean(
        string='Crea una obra',
        help='Al confirmar la venta de este servicio, el proyecto que se crea queda marcado '
             'como obra y con la venta como orden de venta del contrato (calendario e '
             'ingresos de la obra).')
