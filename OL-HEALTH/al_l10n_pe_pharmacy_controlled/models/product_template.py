# -*- coding: utf-8 -*-
"""Listas de fiscalización de estupefacientes, psicotrópicos y precursores
(DS 023-2001-SA y modificatorias, actualizado por el DS 020-2024-SA)."""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

CONTROL_LISTS = [
    ('IIA', 'IIA - Estupefacientes (receta especial)'),
    ('IIB', 'IIB - Estupefacientes (receta retenida)'),
    ('IIIA', 'IIIA - Psicotrópicos (receta especial)'),
    ('IIIB', 'IIIB - Psicotrópicos (receta especial)'),
    ('IIIC', 'IIIC - Psicotrópicos (receta especial)'),
    ('IVA', 'IVA - Psicotrópicos (receta retenida)'),
    ('IVB', 'IVB - Psicotrópicos (receta retenida)'),
    ('VI', 'VI - Receta retenida'),
    ('cannabis', 'Cannabis y derivados de uso medicinal'),
]
# Receta especial (original y dos copias, vigencia de 3 días).
SPECIAL_LISTS = {'IIA', 'IIIA', 'IIIB', 'IIIC', 'cannabis'}
# Receta común que queda retenida en el establecimiento (art. 36).
RETAINED_LISTS = {'IIB', 'IVA', 'IVB', 'VI'}
NARCOTIC_LISTS = {'IIA', 'IIB'}
PSYCHOTROPIC_LISTS = {'IIIA', 'IIIB', 'IIIC', 'IVA', 'IVB', 'VI'}


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    pharmacy_control_list = fields.Selection(
        CONTROL_LISTS, string='Lista de fiscalización',
        help='Producto controlado: fija la receta que exige, el libro donde se registra y el '
             'balance trimestral.')
    pharmacy_control_book = fields.Selection([
        ('narcotic', 'Libro de estupefacientes'),
        ('psychotropic', 'Libro de psicotrópicos'),
        ('cannabis', 'Registro de cannabis'),
    ], string='Libro', compute='_compute_pharmacy_control_book', store=True)

    @api.depends('pharmacy_control_list')
    def _compute_pharmacy_control_book(self):
        for template in self:
            control = template.pharmacy_control_list
            template.pharmacy_control_book = (
                'narcotic' if control in NARCOTIC_LISTS
                else 'psychotropic' if control in PSYCHOTROPIC_LISTS
                else 'cannabis' if control == 'cannabis' else False)

    @api.onchange('pharmacy_control_list')
    def _onchange_pharmacy_control_list(self):
        if self.pharmacy_control_list:
            self.pharmacy_ok = True
            self.pharmacy_sale_condition = ('controlled' if self.pharmacy_control_list in SPECIAL_LISTS
                                            else 'prescription')

    @api.constrains('pharmacy_control_list', 'pharmacy_sale_condition')
    def _check_pharmacy_control_condition(self):
        for template in self.filtered('pharmacy_control_list'):
            if template.pharmacy_control_list in SPECIAL_LISTS \
                    and template.pharmacy_sale_condition != 'controlled':
                raise ValidationError(self.env._(
                    '%s está en la lista %s: su condición de venta es receta especial.',
                    template.display_name, template.pharmacy_control_list))
            if template.pharmacy_control_list in RETAINED_LISTS \
                    and template.pharmacy_sale_condition not in ('prescription', 'controlled'):
                raise ValidationError(self.env._(
                    '%s está en la lista %s: se vende con receta.',
                    template.display_name, template.pharmacy_control_list))

    def _pharmacy_needs_special_prescription(self):
        self.ensure_one()
        return self.pharmacy_control_list in SPECIAL_LISTS

    def _pharmacy_retains_prescription(self):
        self.ensure_one()
        return self.pharmacy_control_list in SPECIAL_LISTS | RETAINED_LISTS
