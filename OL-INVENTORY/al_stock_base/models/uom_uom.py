# -*- coding: utf-8 -*-
"""Planchas enteras (paquete 1.11, M111-12): la unidad «Plancha L×A m» marca
los tableros que el almacén solo entrega por plancha entera; su área sale del
factor de la unidad (referencia m²)."""
from odoo import api, fields, models


class UomUom(models.Model):
    _inherit = 'uom.uom'

    construction_whole_sheet = fields.Boolean(
        string='Plancha entera',
        help='Los productos con esta unidad se entregan, compran y despachan en planchas '
             'enteras; la fracción que se pide queda como necesidad.')
    construction_sheet_area_m2 = fields.Float(
        string='Área de la plancha (m²)', digits=(16, 4),
        compute='_compute_construction_sheet_area_m2',
        help='El factor de la unidad convertido a m², si su referencia es el m².')

    @api.depends('relative_factor', 'relative_uom_id', 'factor')
    def _compute_construction_sheet_area_m2(self):
        square_meter = self.env.ref('uom.product_uom_square_meter', raise_if_not_found=False)
        for uom in self:
            if square_meter and uom.id and uom._has_common_reference(square_meter):
                uom.construction_sheet_area_m2 = uom._compute_quantity(
                    1.0, square_meter, round=False)
            else:
                uom.construction_sheet_area_m2 = 0.0
