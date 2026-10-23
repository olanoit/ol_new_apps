# -*- coding: utf-8 -*-
"""Producto indivisible (paquete 1.11, M111-12): un tablero que el almacén
solo entrega por plancha entera. Lo decide su unidad «Plancha entera» y el
producto puede forzarlo hacia un lado u otro."""
import math

from odoo import api, fields, models

INDIVISIBLE_MODES = [
    ('uom', 'Según la unidad'),
    ('yes', 'Sí'),
    ('no', 'No'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    construction_indivisible_mode = fields.Selection(
        INDIVISIBLE_MODES, string='Plancha indivisible', default='uom', required=True,
        help='Según la unidad: es indivisible si su unidad está marcada «Plancha entera». '
             'Sí o No fuerzan la regla para este producto.')
    construction_is_indivisible = fields.Boolean(
        string='Es indivisible', compute='_compute_construction_is_indivisible', store=True,
        help='Se entrega, compra y despacha en planchas enteras.')
    construction_sheet_area_m2 = fields.Float(
        related='uom_id.construction_sheet_area_m2', string='Área de la plancha (m²)')

    @api.depends('construction_indivisible_mode', 'uom_id.construction_whole_sheet')
    def _compute_construction_is_indivisible(self):
        for template in self:
            mode = template.construction_indivisible_mode
            template.construction_is_indivisible = mode == 'yes' or (
                mode == 'uom' and template.uom_id.construction_whole_sheet)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _construction_is_whole(self, company=None):
        """El producto se entrega en planchas enteras en ``company`` (la
        casilla de la compañía activa y el producto indivisible). Única regla
        para la orden, la reserva, el requerimiento y las compras."""
        self.ensure_one()
        company = company or self.env.company
        return bool(company.construction_whole_sheet and self.construction_is_indivisible)

    def _construction_whole_qty(self, need, company=None):
        """Planchas enteras a entregar para una necesidad (UdM del producto):
        toda fracción mayor que la tolerancia de la compañía sube."""
        self.ensure_one()
        company = company or self.env.company
        uom = self.uom_id
        need = uom.round(max(need, 0.0))            # 7.000001 → 7.00, no 8
        whole = math.floor(need)
        fraction = uom.round(need - whole)
        if uom.compare(fraction, 0.0) > 0 \
                and uom.compare(fraction, company.construction_whole_sheet_tolerance) > 0:
            whole += 1
        return float(whole)
