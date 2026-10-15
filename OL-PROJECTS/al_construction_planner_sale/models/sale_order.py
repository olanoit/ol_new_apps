# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    construction_site_name = fields.Char(
        string='Nombre de la obra',
        help='Con la referencia del cliente como código de obra, la obra que crea esta venta '
             'se llama «<código> <nombre de la obra>» (p. ej. «ROOFG-04-25 ROOF GARDEN»).')
