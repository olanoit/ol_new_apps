# -*- coding: utf-8 -*-
"""Asistente para actualizar el tipo de cambio SUNAT.

Autónomo: los campos de filtro de fechas están integrados aquí (antes venían
del ``filter.dates.mixin`` de ``al_base_mixin``, ya eliminado).
"""
import calendar
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Decolecta y apis.net.pe se consultan un día por llamada, dentro de la misma
# petición: un rango largo agotaría el tiempo del proceso. Para históricos
# largos está el BCRP, que trae el rango completo en una sola llamada.
MAX_DAILY_DAYS = 31

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
    source = fields.Selection(
        [('bcrp', 'BCRP — series históricas, sin token'),
         ('decolecta', 'Decolecta — requiere token'),
         ('apis_net', 'apis.net.pe — requiere token')],
        string='Fuente', default='bcrp', required=True,
        help='Fuente para las fechas pasadas. El BCRP publica la serie del '
             'sistema bancario SBS (la que SUNAT usa para efectos '
             'tributarios) de forma gratuita y trae el rango completo en una '
             'sola consulta. «Hoy» siempre se toma del TXT de SUNAT.')
    # Sin valor por defecto: el token guardado en la conexión es una
    # credencial de administrador y no se envía al navegador. Si se deja
    # vacío, el servidor usa el de la conexión de la compañía.
    apis_net_token = fields.Char(
        string='Token apis.net.pe',
        help='Opcional. Vacío: se usa el token de la conexión apis.net.pe '
             'configurada en el módulo de consulta RUC/DNI '
             '(l10n_pe_vat_sunat) de la compañía.')
    decolecta_token = fields.Char(
        string='Token Decolecta',
        help='Opcional. Vacío: se usa el token de la conexión Decolecta '
             'configurada para consultar RUC/DNI; el mismo token sirve para '
             'las dos cosas.')

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
        if self.range == 'month':
            start, end = self._month_bounds()
            if start:
                self.date_start = start
                self.date_end = min(end, fields.Date.context_today(self))

    def _month_bounds(self):
        try:
            y, m = int(self.year), int(self.month)
            return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])
        except (TypeError, ValueError):
            return None, None

    def _iter_dates(self):
        """Días a cargar, nunca posteriores a hoy (hora de Lima)."""
        if self.range == 'date':
            start = end = self.date
        elif self.range == 'month':
            # Del mes y el año, no del onchange: por RPC no corre.
            start, end = self._month_bounds()
        elif self.range == 'dates':
            start, end = self.date_start, self.date_end
        else:
            return []
        if not (start and end):
            return []
        end = min(end, fields.Date.context_today(self.with_context(tz='America/Lima')))
        return [start + timedelta(days=d) for d in range((end - start).days + 1)]

    def _notify(self, message, kind='warning'):
        params = {
            'title': _('Tipo de cambio'),
            'message': message,
            'type': kind,
            'sticky': False,
        }
        if kind == 'success':
            # Hecho el trabajo, el asistente se cierra solo.
            params['next'] = {'type': 'ir.actions.act_window_close'}
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': params,
        }

    def action_process(self):
        self.ensure_one()
        # La compañía del asistente decide de qué conexión sale el token.
        currency = self.currency_id.with_company(self.company_id)
        if self.range == 'now':
            data = currency.l10n_pe_update_today_sunat()
            if not data:
                return self._notify(_(
                    'SUNAT no devolvió el tipo de cambio de hoy. Inténtelo '
                    'más tarde o cargue la fecha desde el BCRP.'))
            return self._notify(
                _('Tipo de cambio del %(date)s cargado desde SUNAT.',
                  date=data['date']), kind='success')

        days = self._iter_dates()
        if not days:
            return self._notify(_('No hay fechas que procesar.'))

        if self.source == 'bcrp':
            # Una sola llamada para todo el rango.
            loaded = currency.l10n_pe_update_range_bcrp(days[0], days[-1])
            if not loaded:
                return self._notify(_(
                    'El BCRP no devolvió tipos de cambio para el rango '
                    'seleccionado. Revise las fechas o pruebe con otra fuente.'))
            return self._notify(
                _('%s fecha(s) cargadas desde el BCRP.', loaded), kind='success')

        # Decolecta y apis.net.pe se consultan día a día.
        if len(days) > MAX_DAILY_DAYS:
            return self._notify(_(
                '%(source)s se consulta día por día: elija como máximo '
                '%(max)s días, o use el BCRP para rangos largos.',
                source=dict(self._fields['source'].selection)[self.source],
                max=MAX_DAILY_DAYS))
        failed = 0
        for day in days:
            if self.source == 'decolecta':
                ok = currency.l10n_pe_update_date_decolecta(
                    day, token=self.decolecta_token or '')
            else:
                ok = currency.l10n_pe_update_date_apis(
                    day, token=self.apis_net_token or '')
            if not ok:
                failed += 1
        if failed:
            return self._notify(_(
                '%(failed)s de %(total)s fecha(s) no se pudieron obtener de '
                '%(source)s (límite, token o día sin publicación).',
                failed=failed, total=len(days),
                source=dict(self._fields['source'].selection)[self.source]))
        return self._notify(
            _('%s fecha(s) cargadas.', len(days)), kind='success')
