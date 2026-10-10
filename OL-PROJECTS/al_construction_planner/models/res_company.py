# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

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

    def _construction_is_holiday(self, day):
        """Feriado de la compañía: un día cubierto por una ausencia global
        (sin recurso) de la compañía, en cualquiera de sus calendarios (la
        localización suele cargar los feriados en un calendario aparte). Los
        días sin horario (p. ej. el sábado en un calendario de lunes a
        viernes) no son feriados: el pago del sábado no se mueve por eso."""
        self.ensure_one()
        calendar = self.resource_calendar_id
        tz = pytz.timezone(calendar.tz or self.partner_id.tz or 'UTC')
        start = tz.localize(datetime.combine(day, time.min)).astimezone(pytz.utc)
        end = tz.localize(datetime.combine(day, time.max)).astimezone(pytz.utc)
        # sudo: el calendario de feriados lo lee cualquiera que liquide o
        # reporte, aunque no tenga acceso a las ausencias de RR. HH.
        leaves_sudo = self.env['resource.calendar.leaves'].sudo()
        return bool(leaves_sudo.search_count([
            ('resource_id', '=', False),
            ('company_id', 'in', [self.id, False]),
            ('date_from', '<=', end.replace(tzinfo=None)),
            ('date_to', '>=', start.replace(tzinfo=None)),
        ], limit=1))

    def _construction_previous_working_day(self, day):
        """``day`` o, si es feriado, el día anterior que no lo sea
        (especificación, «Feriados»: se corre al día hábil anterior)."""
        self.ensure_one()
        for _attempt in range(15):
            if not self._construction_is_holiday(day):
                return day
            day -= timedelta(days=1)
        return day
