# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields, models

from odoo.addons.al_construction_planner.models.common import GUARANTEE_RELEASES, VALUATION_UNITS


class ResCompany(models.Model):
    _inherit = 'res.company'

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
