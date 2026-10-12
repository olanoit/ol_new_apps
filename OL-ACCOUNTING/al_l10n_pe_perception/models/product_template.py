# -*- coding: utf-8 -*-
from odoo import fields, models

# Bienes sujetos a percepción (Apéndice 1 de la Ley 29173; desde el 1/1/2015
# solo rigen los numerales 1 a 12, Ley 30230 y D.S. 317-2014-EF) y
# combustibles (R.S. 128-2002/SUNAT).
PERCEPTION_TYPES = [
    ('internal', 'Apéndice 1 de la Ley 29173'),
    ('internal_low', 'Apéndice 1 – numerales 1, 2 y 3 (consumidor final hasta S/ 100)'),
    ('glp', 'Gas licuado de petróleo (Apéndice 1, numeral 4)'),
    ('fuel', 'Combustible líquido derivado del petróleo'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_pe_perception_type = fields.Selection(
        PERCEPTION_TYPES, string='Percepción del IGV',
        help='Bien sujeto al régimen de percepciones del IGV en la venta interna. Vacío: no '
             'sujeto. La factura calcula la percepción solo si la compañía es agente de '
             'percepción de ese régimen.')
