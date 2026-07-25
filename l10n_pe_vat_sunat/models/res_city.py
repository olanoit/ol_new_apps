# -*- coding: utf-8 -*-
"""Custom display name para ciudades (incluye estado/departamento).

En Odoo 17+ ``name_get()`` fue reemplazado por
``_compute_display_name`` con dependencias declaradas. Esto permite
cachear el cómputo y respetar invalidación automática del ORM.
"""
from odoo import api, models


class ResCity(models.Model):
    _inherit = 'res.city'

    # v19: _sql_constraints ya no se soporta (no-op silencioso).
    _unique_city_id = models.Constraint(
        'UNIQUE(name, country_id, state_id)',
        'Ya existe una ciudad con ese nombre en ese departamento.')

    @api.depends('name', 'state_id.name')
    def _compute_display_name(self):
        for city in self:
            if city.state_id:
                city.display_name = '%s (%s)' % (city.name, city.state_id.name)
            else:
                city.display_name = city.name or ''
