# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductCategory(models.Model):
    _inherit = 'product.category'

    construction_family_code = fields.Char(
        string='Código de familia', size=4, index=True,
        help='Cuatro dígitos con los que empieza el código de los productos de la familia '
             '(regla del maestro: familia más correlativo de 3 dígitos). Lo usa «Crear '
             'producto desde el plan».')

    @api.constrains('construction_family_code')
    def _check_construction_family_code(self):
        for category in self:
            code = category.construction_family_code
            if code and not re.fullmatch(r'\d{4}', code):
                raise ValidationError(self.env._(
                    'El código de familia de %s debe tener 4 dígitos.', category.display_name))


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    construction_created_from_plan_id = fields.Many2one(
        'construction.resource.plan', string='Creado desde el plan', readonly=True, copy=False,
        index='btree_not_null', ondelete='set null',
        help='Plan de recursos desde el que se creó el producto (P-17). Logística completa '
             'marca, proveedor y cuentas.')
