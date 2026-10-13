# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    sale_approval_category_id = fields.Many2one(
        'approval.category', string='Categoría de aprobación de ventas',
        help='Categoría de Aprobaciones con la que se piden las aprobaciones de las '
             'órdenes de venta.')
