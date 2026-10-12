# -*- coding: utf-8 -*-
"""Custom display name para ciudades (incluye estado/departamento).

En Odoo 17+ ``name_get()`` fue reemplazado por
``_compute_display_name`` con dependencias declaradas. Esto permite
cachear el cómputo y respetar invalidación automática del ORM.
"""
from odoo import api, models
from odoo.exceptions import ValidationError


class ResCity(models.Model):
    _inherit = 'res.city'

    @api.constrains('name', 'country_id', 'state_id')
    def _check_unique_pe_city(self):
        """Una ciudad peruana por nombre y departamento. Solo en Perú: una
        restricción SQL sobre todas las ciudades impedía instalar módulos
        oficiales con ciudades homónimas de otros países (l10n_us_hr_payroll
        trae varias con el mismo nombre en un mismo estado)."""
        for city in self.filtered(lambda c: c.country_id.code == 'PE' and c.name):
            if self.search_count([
                ('id', '!=', city.id), ('name', '=', city.name),
                ('country_id', '=', city.country_id.id),
                ('state_id', '=', city.state_id.id)], limit=1):
                raise ValidationError(self.env._(
                    'Ya existe una ciudad con ese nombre en ese departamento.'))

    @api.depends('name', 'state_id.name')
    def _compute_display_name(self):
        for city in self:
            if city.state_id:
                city.display_name = '%s (%s)' % (city.name, city.state_id.name)
            else:
                city.display_name = city.name or ''
