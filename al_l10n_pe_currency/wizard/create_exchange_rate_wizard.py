# -*- coding: utf-8 -*-
"""Asistente para actualizar el tipo de cambio SUNAT.

Autónomo: los campos de filtro de fechas están integrados aquí (antes venían
del ``filter.dates.mixin`` de ``al_base_mixin``, ya eliminado).
"""
import calendar
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

MONTH_SELECTION = [
    ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
    ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
    ('9', 'Setiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
]


class L10nPeExchangeRateWizard(models.TransientModel):
    _name = 'l10n_pe.exchange.rate.wizard'
    _description = 'Actualizar tipo de cambio SUNAT'

    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True,
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False))
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    apis_net_token = fields.Char(
        string='Token apis.net.pe',
        default=lambda self: self.env['res.currency']._l10n_pe_apis_net_token(),
        help='Opcional. Necesario para consultar fechas históricas sin límite. '
             'Se prellena con el token configurado en la conexión apis.net.pe '
             'del módulo de consulta RUC/DNI (l10n_pe_vat_sunat) si existe.')

    range = fields.Selection(
        [('now', 'Hoy'), ('date', 'Por día'), ('dates', 'Rango de fechas'),
         ('month', 'Por mes')],
        string='Período', default='now', required=True)
    date = fields.Date('Día', default=fields.Date.context_today)
    date_start = fields.Date('Desde')
    date_end = fields.Date('Hasta')
    month = fields.Selection(
        MONTH_SELECTION, string='Mes',
        default=lambda self: str(fields.Date.context_today(self).month))
    year = fields.Char(
        'Año', default=lambda self: str(fields.Date.context_today(self).year))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_(
                    'La fecha "Hasta" debe ser mayor o igual que "Desde".'))

    @api.onchange('range', 'month', 'year')
    def _onchange_month_range(self):
        if self.range == 'month' and self.year and self.month:
            try:
                y, m = int(self.year), int(self.month)
            except ValueError:
                return
            last_day = calendar.monthrange(y, m)[1]
            self.date_start = date(y, m, 1)
            self.date_end = min(date(y, m, last_day), fields.Date.context_today(self))

    def _iter_dates(self):
        if self.range == 'date':
            return [self.date]
        if self.range in ('dates', 'month'):
            if not (self.date_start and self.date_end):
                return []
            days = (self.date_end - self.date_start).days
            return [self.date_start + timedelta(days=d) for d in range(days + 1)]
        return []

    def action_process(self):
        self.ensure_one()
        currency = self.currency_id
        if self.range == 'now':
            currency.l10n_pe_update_today_sunat()
            return {'type': 'ir.actions.act_window_close'}
        failed = 0
        for day in self._iter_dates():
            if not currency.l10n_pe_update_date_apis(day, token=self.apis_net_token or ''):
                failed += 1
        if failed:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'title': _('Tipo de cambio'),
                    'message': _('%s fecha(s) no se pudieron obtener de '
                                 'apis.net.pe (límite/token).', failed),
                    'type': 'warning', 'sticky': False,
                },
            }
        return {'type': 'ir.actions.act_window_close'}
