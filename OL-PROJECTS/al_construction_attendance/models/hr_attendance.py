# -*- coding: utf-8 -*-
"""Marcación del personal propio en la sede (v1.5, fase 17): distancia,
fuera de rango y fuera de hora calculados desde la sede de la marcación
(reemplazan los campos manuales de distancia y rango)."""
from odoo import api, fields, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    l10n_pe_site_distance_m = fields.Float(
        string='Distancia a la sede (m)', compute='_compute_l10n_pe_site_checks', store=True,
        digits=(12, 1))
    l10n_pe_site_out_of_range = fields.Boolean(
        string='Fuera de rango', compute='_compute_l10n_pe_site_checks', store=True)
    l10n_pe_site_late = fields.Boolean(
        string='Fuera de hora', compute='_compute_l10n_pe_site_checks', store=True)

    @api.depends('check_in', 'in_latitude', 'in_longitude', 'l10n_pe_construction_site_id',
                 'l10n_pe_construction_site_id.latitude', 'l10n_pe_construction_site_id.longitude',
                 'l10n_pe_construction_site_id.radius_m',
                 'l10n_pe_construction_site_id.entry_deadline')
    def _compute_l10n_pe_site_checks(self):
        for attendance in self:
            site = attendance.l10n_pe_construction_site_id
            lat, lon = attendance.in_latitude, attendance.in_longitude
            attendance.l10n_pe_site_distance_m = site._distance_to(lat, lon) if site else 0.0
            attendance.l10n_pe_site_out_of_range = bool(site) and site._out_of_range(lat, lon)
            attendance.l10n_pe_site_late = bool(site) and site._is_late(attendance.check_in)
