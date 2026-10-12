# -*- coding: utf-8 -*-
from datetime import date, datetime, time, timedelta

import pytz

from odoo import fields, models

from .common import GUARANTEE_RELEASES, VALUATION_UNITS, WEEKDAYS


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Valores por defecto de las obras nuevas (especificación: «res.company
    # (valores por defecto) y project.project (configuración de cada obra)»).
    construction_week_start_day = fields.Selection(
        WEEKDAYS, string='Inicio de semana de obra', default='3',
        help='Primer día de las semanas de liquidación, entregas y cronograma. El cierre es '
             'el día anterior.')
    construction_settlement_day = fields.Selection(
        WEEKDAYS, string='Día de liquidación de contratas', default='3')
    construction_payment_day = fields.Selection(
        WEEKDAYS, string='Día de pago de contratas', default='5')
    construction_retention_account_id = fields.Many2one(
        'account.account', string='Cuenta de retención de contratas', check_company=True,
        domain="[('account_type', 'in', ('liability_current', 'liability_payable'))]",
        help='Si se indica, la factura de cada liquidación lleva una línea negativa con la '
             'retención a esta cuenta y su total es el neto a pagar. Sin cuenta, la factura '
             'va por el bruto y la retención queda solo en la liquidación.')
    construction_price_alert_pct = fields.Float(
        string='Alerta de precio sobre el plan (%)', default=5.0,
        help='El abastecimiento de la obra marca el producto cuyo último precio de compra '
             'supera el costo del plan en este porcentaje o más.')

    # Ruta del ingreso (P-21): valores por defecto del calendario de
    # valorización, facturación y cobranza de las obras nuevas.
    construction_valuation_every = fields.Integer(
        string='Valorizar cada (semanas)', default=2,
        help='Cada cuántas semanas de la obra se corta una valorización.')
    construction_valuation_unit = fields.Selection(
        VALUATION_UNITS, string='Frecuencia de valorización', default='week')
    construction_valuation_submit_days = fields.Integer(
        string='Días para presentar', default=2, help='Desde el corte de la valorización.')
    construction_client_confirm_days = fields.Integer(
        string='Días para la confirmación del cliente', default=5,
        help='Desde la presentación de la valorización.')
    construction_invoice_days = fields.Integer(
        string='Días para facturar', default=2, help='Desde la confirmación del cliente.')
    construction_collection_days = fields.Integer(
        string='Plazo de cobro (días)', default=30,
        help='Desde la factura. La obra toma el plazo de pago del cliente del contrato si lo '
             'tiene; si no, este.')
    construction_advance_pct = fields.Float(string='Adelanto (%)', default=0.0)
    construction_advance_amortization_pct = fields.Float(
        string='Amortización del adelanto por valorización (%)', default=0.0,
        help='Previsión: en la práctica la amortización la decide el cliente en cada '
             'valorización.')
    construction_guarantee_pct = fields.Float(string='Fondo de garantía (%)', default=5.0)
    construction_guarantee_release = fields.Selection(
        GUARANTEE_RELEASES, string='Cobro del fondo de garantía', default='close')
    construction_income_calendar_id = fields.Many2one(
        'resource.calendar', string='Días hábiles del ingreso', check_company=True,
        help='Horario que define los días hábiles de las fechas de presentación, '
             'confirmación, factura y cobro de las valorizaciones (p. ej. lunes a viernes, '
             'aunque la obra trabaje los sábados). Sin horario, el de la compañía. Los '
             'feriados son los de la compañía.')
    construction_guarantee_account_id = fields.Many2one(
        'account.account', string='Cuenta del fondo de garantía', check_company=True,
        domain="[('account_type', 'in', ('asset_receivable', 'asset_current'))]",
        help='Si se indica, la factura de cada valorización lleva el fondo de garantía como '
             'línea negativa a esta cuenta (por cobrar al cierre) y su total es el neto. Sin '
             'cuenta, la factura va por lo confirmado y el fondo queda en la valorización.')
    construction_advance_account_id = fields.Many2one(
        'account.account', string='Cuenta del adelanto de clientes', check_company=True,
        domain="[('account_type', 'in', ('liability_current', 'liability_payable', "
               "'asset_receivable'))]",
        help='Si se indica, la factura de cada valorización lleva la amortización del adelanto '
             'como línea negativa a esta cuenta. Sin cuenta, la amortización queda solo en la '
             'valorización.')

    construction_categ_assembly_id = fields.Many2one(
        'product.category', string='Categoría de los servicios de armado',
        help='Categoría (p. ej. 601) de los productos de servicio de las actividades de '
             'producción y armado: su modelo de distribución analítica pone la etapa.')
    construction_categ_installation_id = fields.Many2one(
        'product.category', string='Categoría de los servicios de instalación',
        help='Categoría (p. ej. 602) de las actividades de instalación y entregas.')

    def _construction_is_holiday(self, day):
        """Feriado de la compañía: un día cubierto por una ausencia global
        (sin recurso) de la compañía, en cualquiera de sus calendarios (la
        localización suele cargar los feriados en un calendario aparte), o un
        feriado nacional de Perú (``pe.public.holiday``). Los días sin horario
        (p. ej. el sábado en un calendario de lunes a viernes) no son
        feriados: el pago del sábado no se mueve por eso."""
        self.ensure_one()
        return day in self._construction_holidays(day.year)

    def _construction_holidays(self, year):
        """Fechas feriadas del año, leídas una sola vez por transacción (el
        calendario de ingresos y el cronograma preguntan día por día)."""
        self.ensure_one()
        cache = self.env.cr.cache.setdefault('al_construction_holidays', {})
        key = (self.id, year)
        if key in cache:
            return cache[key]
        calendar = self.resource_calendar_id
        tz = pytz.timezone(calendar.tz or self.partner_id.tz or 'UTC')
        first, last = date(year, 1, 1), date(year, 12, 31)
        start = tz.localize(datetime.combine(first, time.min)).astimezone(pytz.utc)
        end = tz.localize(datetime.combine(last, time.max)).astimezone(pytz.utc)
        days = set()
        # sudo: el calendario de feriados lo lee cualquiera que liquide o
        # reporte, aunque no tenga acceso a las ausencias de RR. HH.
        leaves_sudo = self.env['resource.calendar.leaves'].sudo().search([
            ('resource_id', '=', False),
            ('company_id', 'in', [self.id, False]),
            ('date_from', '<=', end.replace(tzinfo=None)),
            ('date_to', '>=', start.replace(tzinfo=None)),
        ])
        for leave in leaves_sudo:
            day = pytz.utc.localize(leave.date_from).astimezone(tz).date()
            stop = pytz.utc.localize(leave.date_to).astimezone(tz).date()
            while day <= stop:
                if first <= day <= last:
                    days.add(day)
                day += timedelta(days=1)
        # Feriados de Perú (al_hr_pe_public_holidays, si está instalado): los
        # nacionales de día completo para todos, aunque aún no se hayan
        # sincronizado con los calendarios. Los de un solo régimen laboral
        # (25 de octubre, construcción civil) no mueven fechas de la obra.
        if 'pe.public.holiday' in self.env:
            # sudo: catálogo de feriados de RR. HH., de solo lectura aquí.
            days.update(self.env['pe.public.holiday'].sudo().search([
                ('date', '>=', first), ('date', '<=', last), ('is_full_day', '=', True),
                ('labor_regime', '=', False)]).mapped('date'))
        cache[key] = days
        return days

    def _construction_previous_working_day(self, day):
        """``day`` o, si es feriado, el día anterior que no lo sea
        (especificación, «Feriados»: se corre al día hábil anterior)."""
        self.ensure_one()
        for _attempt in range(15):
            if not self._construction_is_holiday(day):
                return day
            day -= timedelta(days=1)
        return day

    def _construction_is_working_day(self, day, cache=None):
        """Día hábil del ingreso: con horario en el calendario de días hábiles
        del ingreso o, sin él, en el de la compañía (sin horario, todos los
        días de la semana) y sin feriado."""
        self.ensure_one()
        if cache is not None and day in cache:
            return cache[day]
        calendar = self.construction_income_calendar_id or self.resource_calendar_id
        weekdays = {int(a.dayofweek) for a in calendar.attendance_ids if not a.display_type}
        working = (not weekdays or day.weekday() in weekdays) and \
            not self._construction_is_holiday(day)
        if cache is not None:
            cache[day] = working
        return working

    def _construction_next_working_day(self, day, cache=None):
        """``day`` o el siguiente día hábil (especificación, P-21: una fecha
        del ingreso que cae en día no hábil pasa al siguiente día hábil)."""
        self.ensure_one()
        for _attempt in range(31):
            if self._construction_is_working_day(day, cache):
                return day
            day += timedelta(days=1)
        return day

    # ------------------------------------------------------------------
    # Días hábiles de la obra (cronograma, v1.5 M15-17 y M15-18)
    # ------------------------------------------------------------------
    def _construction_site_weekdays(self):
        """Días de la semana con horario en el calendario de la compañía
        (sin calendario: lunes a viernes)."""
        self.ensure_one()
        weekdays = {int(a.dayofweek) for a in self.resource_calendar_id.attendance_ids
                    if not a.display_type}
        return weekdays or {0, 1, 2, 3, 4}

    def _construction_is_site_day(self, day):
        """Día hábil de la obra: con horario en el calendario de la compañía y
        sin feriado (calendarios y feriados nacionales de Perú)."""
        self.ensure_one()
        return day.weekday() in self._construction_site_weekdays() \
            and not self._construction_is_holiday(day)

    def _construction_next_site_day(self, day):
        """``day`` o el siguiente día hábil de la obra."""
        self.ensure_one()
        for _attempt in range(60):
            if self._construction_is_site_day(day):
                return day
            day += timedelta(days=1)
        return day

    def _construction_add_site_days(self, start, days):
        """Último día de un tramo de ``days`` días hábiles que empieza en
        ``start`` (que se corre al siguiente día hábil si no lo es)."""
        self.ensure_one()
        day = self._construction_next_site_day(start)
        for _done in range(1, max(int(days or 1), 1)):
            day = self._construction_next_site_day(day + timedelta(days=1))
        return day

    def _construction_count_site_days(self, start, end):
        """Días hábiles de la obra entre ``start`` y ``end`` (ambos incluidos;
        al menos 1)."""
        self.ensure_one()
        count, day = 0, start
        while day <= end:
            if self._construction_is_site_day(day):
                count += 1
            day += timedelta(days=1)
        return max(count, 1)

