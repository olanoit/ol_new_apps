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

    @api.model_create_multi
    def create(self, vals_list):
        attendances = super().create(vals_list)
        attendances._construction_assign_nearest_site()
        return attendances

    def write(self, vals):
        res = super().write(vals)
        if {'in_latitude', 'in_longitude'} & set(vals):
            self._construction_assign_nearest_site()
        return res

    def _construction_assign_nearest_site(self):
        """Marcación con ubicación (app o modo quiosco de Odoo) y sin sede: toma
        la sede más cercana de la compañía del empleado."""
        Site = self.env['l10n_pe.hr.construction.site']
        for attendance in self.filtered(lambda a: not a.l10n_pe_construction_site_id
                                        and (a.in_latitude or a.in_longitude)):
            site = Site._construction_nearest_site(
                attendance.in_latitude, attendance.in_longitude, attendance.employee_id.company_id)
            if site:
                attendance.l10n_pe_construction_site_id = site

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
