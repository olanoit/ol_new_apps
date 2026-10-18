# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    pharmacy_presentation_ids = fields.One2many(
        'pharmacy.presentation', 'product_tmpl_id', string='Presentaciones',
        help='Cajas, blísteres u otras presentaciones con precio propio. La unidad suelta se '
             'vende al precio del producto.')
    pharmacy_presentation_count = fields.Integer(compute='_compute_pharmacy_presentation_count')

    @api.depends('pharmacy_presentation_ids')
    def _compute_pharmacy_presentation_count(self):
        for template in self:
            template.pharmacy_presentation_count = len(template.pharmacy_presentation_ids)
