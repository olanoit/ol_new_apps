# -*- coding: utf-8 -*-
"""Listado de medicamentos genéricos esenciales del MINSA (Ley 32033; DS
014-2011-SA, art. 32-A): por cada ítem que se ofrece en versión de marca hay
que tener disponible el genérico en DCI, en al menos el 30 % de los ítems.
El listado vigente se importa (RM 220-2024/MINSA mientras no se actualice)."""
from odoo import fields, models


class PharmacyEssentialMedicine(models.Model):
    _name = 'pharmacy.essential.medicine'
    _description = 'Medicamento esencial genérico (listado MINSA)'
    _order = 'ingredient_id, strength'

    ingredient_id = fields.Many2one('pharmacy.ingredient', string='Principio activo (DCI)',
                                    required=True, ondelete='restrict')
    strength = fields.Char(string='Concentración')
    dosage_form_id = fields.Many2one('pharmacy.dosage.form', string='Forma farmacéutica')
    list_reference = fields.Char(string='Norma', default='RM 220-2024/MINSA')
    active = fields.Boolean(default=True)

    def _matching_products(self, company):
        """Productos de la compañía con el principio activo y, si el ítem la
        indica, la forma farmacéutica."""
        self.ensure_one()
        domain = [('pharmacy_ok', '=', True),
                  ('pharmacy_ingredient_line_ids.ingredient_id', '=', self.ingredient_id.id),
                  '|', ('company_id', '=', False), ('company_id', '=', company.id)]
        if self.dosage_form_id:
            domain.append(('pharmacy_dosage_form_id', '=', self.dosage_form_id.id))
        return self.env['product.template'].search(domain)
