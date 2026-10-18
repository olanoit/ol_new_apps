# -*- coding: utf-8 -*-
"""Catálogos farmacéuticos: principio activo (DCI), forma farmacéutica y vía
de administración. Son globales (sin compañía), como los catálogos de
SUNAT: la denominación común internacional no cambia entre compañías."""
from odoo import api, fields, models

STRENGTH_UNITS = [
    ('mg', 'mg'),
    ('g', 'g'),
    ('mcg', 'mcg'),
    ('ui', 'UI'),
    ('ml', 'mL'),
    ('percent', '%'),
    ('mg_ml', 'mg/mL'),
    ('mg_5ml', 'mg/5 mL'),
    ('mcg_dose', 'mcg/dosis'),
]


class PharmacyIngredient(models.Model):
    _name = 'pharmacy.ingredient'
    _description = 'Principio activo (DCI)'
    _order = 'name'
    _rec_names_search = ['name', 'synonyms', 'atc_code']

    name = fields.Char(string='Denominación común (DCI)', required=True, index='trigram')
    atc_code = fields.Char(string='Código ATC', help='Clasificación anatómica, terapéutica y química de la OMS.')
    synonyms = fields.Char(string='Sinónimos', help='Otros nombres con los que se busca (separados por comas).')
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint('UNIQUE(name)', 'Ya existe ese principio activo.')

    @api.model
    def _get_or_create(self, name):
        name = ' '.join((name or '').split())
        if not name:
            return self.browse()
        ingredient = self.with_context(active_test=False).search([('name', '=ilike', name)], limit=1)
        return ingredient or self.create({'name': name.capitalize()})


class PharmacyDosageForm(models.Model):
    _name = 'pharmacy.dosage.form'
    _description = 'Forma farmacéutica'
    _order = 'sequence, name'

    name = fields.Char(string='Forma farmacéutica', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint('UNIQUE(name)', 'Ya existe esa forma farmacéutica.')


class PharmacyRoute(models.Model):
    _name = 'pharmacy.route'
    _description = 'Vía de administración'
    _order = 'sequence, name'

    name = fields.Char(string='Vía', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint('UNIQUE(name)', 'Ya existe esa vía de administración.')


class PharmacyProductIngredient(models.Model):
    _name = 'pharmacy.product.ingredient'
    _description = 'Composición del producto'
    _order = 'product_tmpl_id, sequence, id'

    product_tmpl_id = fields.Many2one('product.template', string='Producto', required=True,
                                      index=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    ingredient_id = fields.Many2one('pharmacy.ingredient', string='Principio activo', required=True,
                                    ondelete='restrict', index=True)
    strength = fields.Float(string='Concentración', digits=(16, 4))
    strength_unit = fields.Selection(STRENGTH_UNITS, string='Unidad', default='mg')

    @api.depends('ingredient_id', 'strength', 'strength_unit')
    def _compute_display_name(self):
        for line in self:
            line.display_name = line._label()

    def _label(self):
        self.ensure_one()
        if not self.strength:
            return self.ingredient_id.name or ''
        unit = dict(STRENGTH_UNITS).get(self.strength_unit, '')
        strength = ('%f' % self.strength).rstrip('0').rstrip('.')
        return '%s %s %s' % (self.ingredient_id.name, strength, unit)

    def _key(self):
        """Parte de la clave de equivalencia: DCI, concentración y unidad."""
        self.ensure_one()
        return '%s:%s:%s' % (self.ingredient_id.id, round(self.strength or 0.0, 4),
                             self.strength_unit or '')
