# -*- coding: utf-8 -*-
from odoo import fields, models

# Tabla 23 del Anexo 1 de la RS 040-2022/SUNAT: clasificación de los bienes y
# servicios adquiridos. Alimenta el campo 33 del formato RCE 8.4.
RCE_CLASSIFICATION = [
    ('1', '1 - Mercadería, materia prima, suministro, envases y embalajes'),
    ('2', '2 - Adquisiciones de activo fijo'),
    ('3', '3 - Otros activos no considerados en el numeral 2'),
    ('4', '4 - Gastos de educación, recreación, salud, culturales, '
          'representación, capacitación, de viaje, mantenimiento de vehículo '
          'y premios'),
    ('5', '5 - Otros gastos no incluidos en el numeral 4'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_pe_rce_classification = fields.Selection(
        RCE_CLASSIFICATION,
        string='Clasificación RCE',
        help='Clasificación de los bienes y servicios adquiridos (tabla 23 de '
             'SUNAT). Se informa en el campo 33 del Registro de Compras '
             'Electrónico 8.4. Solo es obligatoria para los contribuyentes '
             'con ingresos superiores a 1500 UIT.')
