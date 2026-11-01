# -*- coding: utf-8 -*-
"""Categoría raíz de materiales de la hoja de trabajo (paquete 1.13, M113-06):
las listas de grupo, categoría y producto del maestro solo muestran lo que
cuelga de ella. Sin configurar, todas las categorías, como antes."""
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    construction_sheet_material_categ_id = fields.Many2one(
        'product.category', string='Categoría raíz de materiales de la hoja',
        help='Las listas de materiales de la hoja de trabajo (grupo, categoría y producto) '
             'muestran solo las categorías que cuelgan de esta. Vacía: todas.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_sheet_material_categ_id = fields.Many2one(
        related='company_id.construction_sheet_material_categ_id', readonly=False)
