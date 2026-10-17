# -*- coding: utf-8 -*-
from odoo import fields, models

SALE_CONDITIONS = [
    ('otc', 'Venta libre'),
    ('prescription', 'Con receta médica'),
    ('controlled', 'Receta especial (controlado)'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Datos del registro sanitario que DIGEMID exige en el rotulado y en la
    # venta de productos farmacéuticos (Ley 29459).
    pharmacy_sanitary_registry = fields.Char(
        string='Registro sanitario', help='Número del registro sanitario DIGEMID (p. ej. EN-01234).')
    pharmacy_active_ingredient = fields.Char(
        string='Principio activo', help='Denominación común internacional (DCI).')
    pharmacy_concentration = fields.Char(string='Concentración', help='Por ejemplo 500 mg.')
    pharmacy_dosage_form = fields.Char(
        string='Forma farmacéutica', help='Tableta, cápsula, jarabe, crema…')
    pharmacy_sale_condition = fields.Selection(
        SALE_CONDITIONS, string='Condición de venta',
        help='La que figura en el registro sanitario.')
