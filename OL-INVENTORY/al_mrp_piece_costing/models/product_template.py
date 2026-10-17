# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    piece_is_cut = fields.Boolean(
        string='Pieza de corte',
        help='Producto-pieza creado desde el despiece (sistema matriz o corte manual).')
    piece_area_m2 = fields.Float(
        string='Área (m²)', digits=(16, 6),
        help='Área de una pieza: reparte la bolsa general y la de su tablero.')
    piece_edge_ml = fields.Float(
        string='Tapacanto (m)', digits=(16, 6),
        help='Metros de tapacanto de una pieza: reparte la bolsa de tapacanto.')
    piece_is_edge_banding = fields.Boolean(
        string='Es tapacanto',
        help='Su consumo forma la bolsa de tapacanto del costeo por medida. Se marca aquí, no '
             'por nombre ni por categoría.')
    piece_project_ref = fields.Char(
        string='Obra de origen', index='btree_not_null',
        help='Código de la obra de la pieza, para su trazabilidad.')
    piece_material_id = fields.Many2one(
        'product.product', string='Tablero de origen', index='btree_not_null',
        help='Tablero del que se corta la pieza: el valor consumido de ese tablero se reparte '
             'por área solo entre sus piezas. Sin él, la pieza solo recibe la bolsa general.')
