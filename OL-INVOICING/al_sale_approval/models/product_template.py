# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    sale_approval_required = fields.Boolean(
        string='Requiere aprobación de venta',
        help='Una orden de venta con este producto solo se confirma con una solicitud '
             'aprobada en Aprobaciones.')
