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
    # Paquete 1.17, punto 15 de «Configuración y datos».
    construction_sale_partida_product_id = fields.Many2one(
        'product.product', string='Producto de venta por partida',
        domain="[('type', '=', 'service')]",
        help='El de las líneas que escribe «Pasar el resumen a la cotización».')
    construction_planning_user_id = fields.Many2one(
        'res.users', string='Responsable de planificación',
        help='Recibe las actividades de obra adjudicada y de altas al tarifario.')
    construction_sale_milestone_template = fields.Char(
        string='Plantilla de hitos por defecto',
        help='La que «Traer la venta» escribe en CONTRATOS.')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    construction_sheet_material_categ_id = fields.Many2one(
        related='company_id.construction_sheet_material_categ_id', readonly=False)
    construction_sale_partida_product_id = fields.Many2one(
        related='company_id.construction_sale_partida_product_id', readonly=False)
    construction_planning_user_id = fields.Many2one(
        related='company_id.construction_planning_user_id', readonly=False)
    construction_sale_milestone_template = fields.Char(
        related='company_id.construction_sale_milestone_template', readonly=False)
