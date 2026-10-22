from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_round, format_date

#: Circular 0008-2021-BCRP: la tasa máxima de interés convencional moratorio es el 15 % de la
#: tasa máxima de interés convencional compensatorio.
MORATORY_SHARE = 0.15


class L10nPeCollectionRateCap(models.Model):
    """Tasas máximas de interés convencional que fija el BCRP cada semestre (1 de mayo y
    1 de noviembre) para las operaciones fuera del sistema financiero (Código Civil art.
    1243, Circular 0008-2021-BCRP). El interés moratorio que liquida Cobranza no puede
    superar la tasa moratoria del periodo: el exceso no es exigible."""
    _name = 'l10n_pe.collection.rate.cap'
    _description = 'Tasa máxima de interés del BCRP'
    _order = 'date_from desc, currency_type'

    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    currency_type = fields.Selection(
        [('pen', 'Moneda nacional'), ('foreign', 'Moneda extranjera')], string='Moneda', required=True,
        help='Moneda extranjera se aplica a los documentos en dólares y en cualquier otra moneda.')
    compensatory_rate = fields.Float(
        string='Compensatorio máximo (TEA %)', digits=(7, 2), required=True,
        help='Tasa máxima de interés convencional compensatorio publicada por el BCRP.')
    moratory_rate = fields.Float(
        string='Moratorio máximo (TEA %)', digits=(7, 2), compute='_compute_moratory_rate', store=True,
        readonly=False, help='El 15 % de la tasa compensatoria máxima (Circular 0008-2021-BCRP).')
    source = fields.Char(string='Fuente', help='Nota informativa o circular del BCRP.')

    _date_range = models.Constraint('CHECK (date_from <= date_to)', 'La fecha final debe ser posterior a la inicial.')

    @api.depends('compensatory_rate')
    def _compute_moratory_rate(self):
        for cap in self:
            cap.moratory_rate = float_round(cap.compensatory_rate * MORATORY_SHARE, precision_digits=2)

    @api.depends('date_from', 'date_to', 'currency_type')
    def _compute_display_name(self):
        currencies = dict(self._fields['currency_type']._description_selection(self.env))
        for cap in self:
            cap.display_name = '%s %s – %s' % (
                currencies.get(cap.currency_type, ''), format_date(self.env, cap.date_from),
                format_date(self.env, cap.date_to))

    @api.constrains('date_from', 'date_to', 'currency_type')
    def _check_overlap(self):
        for cap in self:
            if self.search_count([
                ('id', '!=', cap.id), ('currency_type', '=', cap.currency_type),
                ('date_from', '<=', cap.date_to), ('date_to', '>=', cap.date_from),
            ]):
                raise ValidationError(_('Ya hay una tasa máxima del BCRP para esa moneda en esas fechas.'))

    @api.model
    def _l10n_pe_currency_type(self, currency):
        return 'pen' if currency.name == 'PEN' else 'foreign'

    @api.model
    def _l10n_pe_for_date(self, date, currency_type):
        return self.search([('currency_type', '=', currency_type), ('date_from', '<=', date),
                            ('date_to', '>=', date)], limit=1)

    @api.model
    def _l10n_pe_interest_factor(self, rate, date_from, date_to, currency_type):
        """Factor de interés entre dos fechas con la TEA pactada, recortada en cada tramo al
        moratorio máximo del BCRP vigente. Año de 360 días.

        :return: (factor, recortado, días sin tope registrado)
        """
        caps = self.search([('currency_type', '=', currency_type), ('date_to', '>=', date_from),
                            ('date_from', '<', date_to)], order='date_from')
        factor, capped, uncovered = 1.0, False, 0
        day = date_from
        while day < date_to:
            cap = caps.filtered(lambda c: c.date_from <= day <= c.date_to)[:1]
            if cap:
                end = min(cap.date_to + timedelta(days=1), date_to)
                applied = min(rate, cap.moratory_rate)
                capped = capped or applied < rate
            else:
                following = caps.filtered(lambda c: c.date_from > day)[:1]
                end = min(following.date_from, date_to) if following else date_to
                applied = rate
                uncovered += (end - day).days
            factor *= (1 + applied / 100.0) ** ((end - day).days / 360.0)
            day = end
        return factor - 1, capped, uncovered

    @api.model
    def _l10n_pe_rate_warning(self, rate, date=None):
        """Aviso cuando la tasa pactada supera el moratorio máximo vigente, o cuando no hay
        tope registrado para hoy."""
        if not rate or rate <= 0:
            return False
        date = date or fields.Date.context_today(self)
        caps = self.search([('date_from', '<=', date), ('date_to', '>=', date)])
        if not caps:
            return _('No hay tasas máximas del BCRP registradas para hoy: regístrelas en Cobranza ‣ '
                     'Configuración ‣ Tasas máximas del BCRP (se publican cada 1 de mayo y 1 de noviembre).')
        over = caps.filtered(lambda c: rate > c.moratory_rate)
        if not over:
            return False
        limits = ', '.join('%s %% en %s' % (
            ('%.2f' % c.moratory_rate).replace('.', ','),
            'soles' if c.currency_type == 'pen' else 'moneda extranjera') for c in over)
        return _('La tasa de %(rate)s %% supera el interés moratorio máximo del BCRP vigente hasta el '
                 '%(date)s (%(limits)s). Los intereses se liquidan con el tope; el exceso no es exigible.',
                 rate=('%.2f' % rate).replace('.', ','), date=format_date(self.env, over[0].date_to),
                 limits=limits)
