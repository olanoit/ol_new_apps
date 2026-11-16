# -*- coding: utf-8 -*-
"""Sede de obra con ubicación y horario (v1.5, fase 17)."""
import math
import secrets
from datetime import datetime, timedelta

import pytz

from odoo import api, fields, models

EARTH_RADIUS_M = 6371000.0
#: Quiosco: documentos o PIN errados seguidos que lo pausan, en qué ventana y
#: por cuánto. El enlace de la tablet es su única protección: sin este tope,
#: quien lo tenga prueba documentos o PIN hasta dar con el de cada persona.
KIOSK_MAX_FAILURES = 5
KIOSK_FAILURE_WINDOW = timedelta(minutes=10)
KIOSK_PAUSE = timedelta(minutes=10)


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
        # Paquete 1.20, M120-06: sin el ejemplo de mobiliario.
        help='Cuenta del plan Etapa que recibe el costo del personal de esta sede. Vacía: la '
             'del perfil.')
    kiosk_token = fields.Char(
        string='Clave del quiosco', copy=False, groups='hr.group_hr_user',
        default=lambda self: secrets.token_urlsafe(16),
        help='Parte del enlace de la tablet de la sede: cámbiela si el enlace se filtra.')
    kiosk_url = fields.Char(string='Enlace del quiosco', compute='_compute_kiosk_url',
                            groups='hr.group_hr_user')

    kiosk_failed_count = fields.Integer(
        string='Intentos errados del quiosco', copy=False, readonly=True,
        groups='hr.group_hr_user')
    kiosk_failed_since = fields.Datetime(
        string='Primer intento errado', copy=False, readonly=True, groups='hr.group_hr_user')
    kiosk_paused_until = fields.Datetime(
        string='Quiosco en pausa hasta', copy=False, readonly=True, groups='hr.group_hr_user',
        help='Tras varios documentos o PIN errados seguidos, el quiosco deja de marcar unos '
             'minutos. Si el enlace se filtró, cambie la clave del quiosco.')

    def _kiosk_paused_minutes(self):
        """Minutos que le quedan a la pausa del quiosco (0 si marca)."""
        self.ensure_one()
        now = fields.Datetime.now()
        if not self.kiosk_paused_until or self.kiosk_paused_until <= now:
            return 0
        return max(1, int((self.kiosk_paused_until - now).total_seconds() // 60) + 1)

    def _kiosk_register_attempt(self, found):
        """Cuenta los intentos errados seguidos: un acierto pone el contador
        en cero; al llegar al tope en la ventana, el quiosco entra en pausa."""
        self.ensure_one()
        now = fields.Datetime.now()
        if found:
            if self.kiosk_failed_count:
                self.write({'kiosk_failed_count': 0, 'kiosk_failed_since': False})
            return
        fresh = not self.kiosk_failed_since or now - self.kiosk_failed_since > KIOSK_FAILURE_WINDOW
        count = 1 if fresh else self.kiosk_failed_count + 1
        vals = {'kiosk_failed_count': count,
                'kiosk_failed_since': now if fresh else self.kiosk_failed_since}
        if count >= KIOSK_MAX_FAILURES:
            vals.update({'kiosk_failed_count': 0, 'kiosk_failed_since': False,
                         'kiosk_paused_until': now + KIOSK_PAUSE})
        self.write(vals)

    def _compute_kiosk_url(self):
        base = self.get_base_url()
        for site in self:
            site.kiosk_url = '%s/obra/quiosco/%s/%s' % (base, site.id, site.kiosk_token or '') \
                if site.id else False

    def action_new_kiosk_token(self):
        for site in self:
            site.write({'kiosk_token': secrets.token_urlsafe(16), 'kiosk_failed_count': 0,
                        'kiosk_failed_since': False, 'kiosk_paused_until': False})

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
        'l10n_pe.hr.construction.site', 'project_id', string='Sedes de la obra',
        # M111-01: sin Nómina el campo se omite (exportar, duplicar) en vez de
        # dar error de acceso; los cálculos del planificador lo leen con sudo.
        groups='hr_payroll.group_hr_payroll_user')

    def _construction_site(self):
        self.ensure_one()
        return self.construction_hr_site_ids[:1]

    @api.model
    def _construction_site_for(self, project):
        return project._construction_site() if project else self.env['l10n_pe.hr.construction.site']
