# -*- coding: utf-8 -*-
"""Domicilio estructurado del trabajador (T-Registro, estructura 04).

SUNAT no acepta la dirección como texto libre: la pide descompuesta en
vía, número, interior, manzana, lote, zona y ubigeo. Se guardan **dos**
direcciones porque el T-Registro permite declarar un domicilio distinto
como referencia del centro asistencial de EsSalud.

El ubigeo reutiliza ``l10n_pe.res.city.district`` de la localización
nativa (1 874 distritos con su código de 6 dígitos): es exactamente la
tabla 28 del Anexo 2, así que no se duplica.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # --- Dirección 1: domicilio ---
    l10n_pe_road_type_id = fields.Many2one(
        'l10n_pe.hr.road.type', string='Tipo de vía (T05)')
    l10n_pe_road_name = fields.Char(string='Nombre de la vía')
    l10n_pe_road_number = fields.Char(string='N° de la vía', size=6)
    l10n_pe_department = fields.Char(string='Departamento (dpto.)', size=5)
    l10n_pe_interior = fields.Char(string='Interior', size=5)
    l10n_pe_block = fields.Char(string='Manzana', size=6)
    l10n_pe_lot = fields.Char(string='Lote', size=5)
    l10n_pe_km = fields.Char(string='Kilómetro', size=5)
    l10n_pe_block_name = fields.Char(string='Block', size=5)
    l10n_pe_stage = fields.Char(string='Etapa', size=5)
    l10n_pe_zone_type_id = fields.Many2one(
        'l10n_pe.hr.zone.type', string='Tipo de zona (T06)')
    l10n_pe_zone_name = fields.Char(string='Nombre de la zona')
    l10n_pe_address_reference = fields.Char(string='Referencia')
    l10n_pe_district_id = fields.Many2one(
        'l10n_pe.res.city.district', string='Distrito (ubigeo)',
        help='Su código de 6 dígitos es el ubigeo que pide SUNAT.')

    # --- Dirección 2: referencia del centro asistencial ---
    l10n_pe_health_center_indicator = fields.Selection(
        selection=[('1', '1 — Dirección 1'), ('2', '2 — Dirección 2')],
        string='Domicilio del centro asistencial', default='1',
        help='Cuál de las dos direcciones usa EsSalud para asignar el '
             'centro asistencial del trabajador.')
    l10n_pe_road_type2_id = fields.Many2one(
        'l10n_pe.hr.road.type', string='Tipo de vía (2)')
    l10n_pe_road_name2 = fields.Char(string='Nombre de la vía (2)')
    l10n_pe_road_number2 = fields.Char(string='N° de la vía (2)', size=6)
    l10n_pe_department2 = fields.Char(string='Departamento (2)', size=5)
    l10n_pe_interior2 = fields.Char(string='Interior (2)', size=5)
    l10n_pe_block2 = fields.Char(string='Manzana (2)', size=6)
    l10n_pe_lot2 = fields.Char(string='Lote (2)', size=5)
    l10n_pe_km2 = fields.Char(string='Kilómetro (2)', size=5)
    l10n_pe_block_name2 = fields.Char(string='Block (2)', size=5)
    l10n_pe_stage2 = fields.Char(string='Etapa (2)', size=5)
    l10n_pe_zone_type2_id = fields.Many2one(
        'l10n_pe.hr.zone.type', string='Tipo de zona (2)')
    l10n_pe_zone_name2 = fields.Char(string='Nombre de la zona (2)')
    l10n_pe_address_reference2 = fields.Char(string='Referencia (2)')
    l10n_pe_district2_id = fields.Many2one(
        'l10n_pe.res.city.district', string='Distrito (2)')

    l10n_pe_address_display = fields.Char(
        string='Domicilio (T-Registro)',
        compute='_compute_l10n_pe_address_display',
        help='La dirección 1 tal como queda armada para SUNAT.')

    @api.depends('l10n_pe_road_type_id', 'l10n_pe_road_name',
                 'l10n_pe_road_number', 'l10n_pe_zone_name',
                 'l10n_pe_district_id')
    def _compute_l10n_pe_address_display(self):
        for employee in self:
            parts = [
                employee.l10n_pe_road_type_id.name,
                employee.l10n_pe_road_name,
                employee.l10n_pe_road_number,
                employee.l10n_pe_zone_name,
                employee.l10n_pe_district_id.name,
            ]
            employee.l10n_pe_address_display = ' '.join(
                part for part in parts if part) or False

    @api.constrains('l10n_pe_health_center_indicator', 'l10n_pe_district2_id')
    def _check_l10n_pe_health_center(self):
        for employee in self:
            if (employee.l10n_pe_health_center_indicator == '2'
                    and not employee.l10n_pe_district2_id):
                raise ValidationError(_(
                    '%(name)s: si el centro asistencial se asigna por la '
                    'dirección 2, hay que informarla.',
                    name=employee.display_name))

    def _l10n_pe_address_values(self, second=False):
        """Los 14 campos del bloque de dirección, en el orden de la E04."""
        self.ensure_one()
        suffix = '2' if second else ''
        road_type = self['l10n_pe_road_type%s_id' % suffix]
        zone_type = self['l10n_pe_zone_type%s_id' % suffix]
        district = self['l10n_pe_district%s_id' % suffix]
        return [
            road_type.code or '',
            self['l10n_pe_road_name%s' % suffix] or '',
            self['l10n_pe_road_number%s' % suffix] or '',
            self['l10n_pe_department%s' % suffix] or '',
            self['l10n_pe_interior%s' % suffix] or '',
            self['l10n_pe_block%s' % suffix] or '',
            self['l10n_pe_lot%s' % suffix] or '',
            self['l10n_pe_km%s' % suffix] or '',
            self['l10n_pe_block_name%s' % suffix] or '',
            self['l10n_pe_stage%s' % suffix] or '',
            zone_type.code or '',
            self['l10n_pe_zone_name%s' % suffix] or '',
            self['l10n_pe_address_reference%s' % suffix] or '',
            district.code or '',
        ]
