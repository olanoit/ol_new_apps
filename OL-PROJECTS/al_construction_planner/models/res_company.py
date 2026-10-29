# -*- coding: utf-8 -*-
from datetime import date, datetime, time, timedelta

import pytz

from odoo import fields, models

from .common import WEEKDAYS


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
    # Cancelar un plan aprobado o en ejecución sin consumos ni documentos
    # abiertos (pedido de Allcenter del 24-oct-2026, prueba ZZMONTEC).
    construction_plan_cancel_open = fields.Boolean(
        string='Cancelar planes en ejecución',
        help='Permite cancelar un plan aprobado o en ejecución que no tenga documentos '
             'abiertos (compras, requerimientos, OF, OC de servicio) ni consumos.')
    construction_plan_cancel_group_id = fields.Many2one(
        'res.groups', string='Quién cancela planes en ejecución',
        default=lambda self: self.env.ref('al_construction_planner.group_planner_manager',
                                          raise_if_not_found=False),
        help='Grupo que puede cancelarlos. Vacío: Planificación de obra / Administrador.')
    # Perfil de vertical (v1.7, M17-05): el que se aplicó y la plantilla de
    # niveles de las obras nuevas.
    construction_profile_id = fields.Many2one(
        'construction.vertical.profile', string='Perfil de vertical',
        help='El rubro de la compañía: deja configurado el planificador al aplicarlo.')
    construction_level_template_id = fields.Many2one(
        'construction.level.template', string='Plantilla de niveles de las obras nuevas')

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
        # Odoo 20: la zona horaria es de la compañía, ya no del calendario.
        tz = pytz.timezone(self.tz or self.partner_id.tz or 'UTC')
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

