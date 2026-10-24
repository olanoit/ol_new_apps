# -*- coding: utf-8 -*-
"""Catálogo de requerimientos del portal (requerimiento CREVAL v1.0, 4.11,
pantalla 8): los productos aparecen según una marca en su categoría
(materiales de partida, EPP, útiles y aseo) y los kits son listas de
productos con sus cantidades."""
from odoo import fields, models

CATALOGS = [
    ('partida', 'Materiales de partida'),
    ('epp', 'EPP'),
    ('office', 'Útiles y aseo'),
]


class ProductCategory(models.Model):
    _inherit = 'product.category'

    construction_portal_catalog = fields.Selection(
        CATALOGS, string='Catálogo del portal de obra',
        help='Materiales de partida: se piden para una partida con el saldo del plan. EPP y '
             'útiles y aseo: van en un requerimiento interno con la analítica de gastos '
             'generales de la obra.')


class ConstructionPortalKit(models.Model):
    _name = 'construction.portal.kit'
    _description = 'Kit del portal de obra'
    _order = 'sequence, name'
    _check_company_auto = True

    name = fields.Char(string='Kit', required=True, translate=True)
    sequence = fields.Integer(default=10)
    catalog = fields.Selection([item for item in CATALOGS if item[0] != 'partida'],
                               string='Catálogo', required=True, default='epp')
    company_id = fields.Many2one('res.company', string='Compañía',
                                 default=lambda self: self.env.company)
    line_ids = fields.One2many('construction.portal.kit.line', 'kit_id', string='Productos',
                               copy=True)
    active = fields.Boolean(default=True)


class ConstructionPortalKitLine(models.Model):
    _name = 'construction.portal.kit.line'
    _description = 'Producto del kit del portal'

    kit_id = fields.Many2one('construction.portal.kit', string='Kit', required=True,
                             ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    qty = fields.Float(string='Cantidad', digits='Product Unit', default=1.0, required=True)
