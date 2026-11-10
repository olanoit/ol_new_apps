# -*- coding: utf-8 -*-
"""Conversión de las piezas al tablero (paquete 1.18, M118-11, decisión D3):
Oficina Técnica dice cuántos m² útiles da una unidad del producto (una
plancha); con ese dato la BOM del módulo toma el tablero de sus piezas."""
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    construction_board_m2 = fields.Float(
        string='m² útiles por unidad', digits=(16, 4),
        help='Para tableros: m² de piezas que salen de una unidad del producto (p. ej. 4.00 por '
             'plancha). Con él, la BOM de cada módulo toma el tablero de sus piezas; sin él, la '
             'pieza no da tablero y la importación avisa.')
