# -*- coding: utf-8 -*-
"""Sede de obra con ubicación y horario (v1.5, fase 17)."""
import math
import secrets
from datetime import datetime

import pytz

from odoo import api, fields, models

EARTH_RADIUS_M = 6371000.0


def haversine_m(lat1, lon1, lat2, lon2):
    """Distancia en metros entre dos puntos (fórmula del semiverseno)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlam = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


class L10nPeHrConstructionSite(models.Model):
    _inherit = 'l10n_pe.hr.construction.site'

    project_id = fields.Many2one(
        'project.project', string='Obra del planificador', index=True,
        domain=[('is_construction_site', '=', True)],
        help='Proyecto de la obra. Las sedes de área (planta, oficina) van sin obra.')
    latitude = fields.Float(string='Latitud', digits=(10, 7))
    longitude = fields.Float(string='Longitud', digits=(10, 7))
    radius_m = fields.Integer(
        string='Radio (m)', default=200,
        help='Una marcación o un avance más lejos que esto de la sede queda «Fuera de rango».')
    entry_deadline = fields.Float(
        string='Hora límite de ingreso', default=7.0 + 50 / 60.0,
        help='Ingresos después de esta hora quedan «Fuera de hora» (7:50 por defecto).')
    default_stage_account_id = fields.Many2one(
        'account.analytic.account', string='Etapa por defecto', check_company=True,
        help='Etapa del costo del personal de la sede: obra → instalación (INS), planta → '
             'producción (PRD).')
    kiosk_token = fields.Char(
        string='Clave del quiosco', copy=False, groups='hr.group_hr_user',
        default=lambda self: secrets.token_urlsafe(16),
        help='Parte del enlace de la tablet de la sede: cámbiela si el enlace se filtra.')
    kiosk_url = fields.Char(string='Enlace del quiosco', compute='_compute_kiosk_url',
                            groups='hr.group_hr_user')

    def _compute_kiosk_url(self):
        base = self.get_base_url()
        for site in self:
            site.kiosk_url = '%s/obra/quiosco/%s/%s' % (base, site.id, site.kiosk_token or '') \
                if site.id else False

    def action_new_kiosk_token(self):
        for site in self:
            site.kiosk_token = secrets.token_urlsafe(16)

    def _distance_to(self, latitude, longitude):
        self.ensure_one()
        if not (self.latitude or self.longitude) or not (latitude or longitude):
            return 0.0
        return round(haversine_m(self.latitude, self.longitude, latitude, longitude), 1)

    @api.model
    def _construction_nearest_site(self, latitude, longitude, company):
        """Sede con ubicación más cercana a una marcación de la compañía."""
        if not (latitude or longitude):
            return self.browse()
        sites = self.search([
            ('company_id', 'in', [company.id, False]),
            '|', ('latitude', '!=', 0), ('longitude', '!=', 0)])
        return min(sites, key=lambda s: s._distance_to(latitude, longitude), default=self.browse())

    def _out_of_range(self, latitude, longitude):
        self.ensure_one()
        if not (self.latitude or self.longitude) or not (latitude or longitude):
            return False
        return self._distance_to(latitude, longitude) > (self.radius_m or 0)

    def _tz(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        return pytz.timezone(company.resource_calendar_id.tz or company.partner_id.tz
                             or 'America/Lima')

    def _is_late(self, check_in):
        """Ingreso después de la hora límite, en la hora local de la sede."""
        self.ensure_one()
        if not check_in or not self.entry_deadline:
            return False
        local = pytz.utc.localize(fields.Datetime.to_datetime(check_in)).astimezone(self._tz())
        return local.hour + local.minute / 60.0 > self.entry_deadline + 1e-9

    def _local_day_bounds(self, day):
        """Inicio y fin del día ``day`` (hora local de la sede) en UTC."""
        self.ensure_one()
        tz = self._tz()
        start = tz.localize(datetime.combine(day, datetime.min.time())).astimezone(pytz.utc)
        end = tz.localize(datetime.combine(day, datetime.max.time())).astimezone(pytz.utc)
        return start.replace(tzinfo=None), end.replace(tzinfo=None)


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_hr_site_ids = fields.One2many(
        'l10n_pe.hr.construction.site', 'project_id', string='Sedes de la obra')

    def _construction_site(self):
        self.ensure_one()
        return self.construction_hr_site_ids[:1]

    @api.model
    def _construction_site_for(self, project):
        return project._construction_site() if project else self.env['l10n_pe.hr.construction.site']
