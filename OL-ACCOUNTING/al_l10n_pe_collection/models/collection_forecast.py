import io
from collections import defaultdict
from datetime import timedelta

import xlsxwriter
from dateutil.relativedelta import relativedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

SOURCES = [
    ('promise', 'Compromiso'),
    ('prediction', 'Predicción de pago'),
    ('behavior', 'Historial de pago'),
    ('due', 'Vencimiento'),
    ('manual', 'Ajustada'),
]
MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
          'octubre', 'noviembre', 'diciembre']


class L10nPeCollectionTools(models.AbstractModel):
    """Cálculos compartidos: alcance por gestor o zona y lo cobrado en un periodo."""
    _name = 'l10n_pe.collection.tools'
    _description = 'Cálculos de cobranza'

    @api.model
    def _scope_partners(self, company, users=None, zones=None):
        """Clientes de esos gestores o zonas (``None``: sin filtro)."""
        if not users and not zones:
            return None
        Partner = self.env['res.partner'].with_company(company)
        domain = []
        if users:
            domain.append(('followup_responsible_id', 'in', users.ids))
        if zones:
            domain.append(('l10n_pe_collection_zone_id', 'in', zones.ids))
        return Partner.search(domain)

    @api.model
    def _collected_lines_domain(self, company, date_from, date_to, partners=None):
        domain = [
            ('company_id', 'child_of', company.root_id.id),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('account_id', 'not in', company._l10n_pe_collection_excluded_accounts().ids),
            ('journal_id.type', 'in', ('bank', 'cash')),
            ('balance', '<', 0),
            ('date', '>=', date_from), ('date', '<=', date_to),
        ]
        if partners is not None:
            domain.append(('partner_id', 'child_of', partners.ids))
        return domain

    @api.model
    def _collected(self, company, date_from, date_to, partners=None):
        """Lo cobrado (abonos de bancos y cajas en cuentas por cobrar) en el periodo."""
        if partners is not None and not partners:
            return 0.0
        groups = self.env['account.move.line']._read_group(
            self._collected_lines_domain(company, date_from, date_to, partners), aggregates=['balance:sum'])
        return -(groups[0][0] or 0.0) if groups else 0.0


class L10nPeCollectionForecast(models.Model):
    """Proyección de cobranza: cuándo y cuánto se espera cobrar de la cartera.

    Fecha esperada de cada cuota: la del compromiso de pago vigente; si no hay,
    el vencimiento más el atraso promedio del cliente (historial de pagos); si
    no hay historial, el vencimiento. Lo vencido sin compromiso entra en el
    primer periodo. Importe esperado: saldo × probabilidad del tramo de
    antigüedad. Fecha e importe se pueden ajustar y se conservan al actualizar.
    """
    _name = 'l10n_pe.collection.forecast'
    _description = 'Proyección de cobranza'
    _inherit = ['mail.thread']
    _order = 'date_from desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Nombre', required=True, default=lambda self: _('Proyección de cobranza'))
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    date_from = fields.Date(string='Desde', required=True, default=fields.Date.context_today, tracking=True)
    period_type = fields.Selection([('week', 'Semanas'), ('month', 'Meses')], string='Periodos',
                                   required=True, default='week')
    period_count = fields.Integer(string='Cantidad de periodos', required=True, default=8)
    user_ids = fields.Many2many('res.users', string='Gestores', help='Vacío: todos.')
    zone_ids = fields.Many2many('l10n_pe.collection.zone', string='Zonas', help='Vacío: todas.')
    use_behavior = fields.Boolean(string='Usar la predicción de pago', default=True,
                                  help='Corre la fecha esperada según la predicción de pago de cada cuota: historial '
                                       'del cliente (o de la cartera), atraso que ya lleva y estacionalidad.')
    use_probability = fields.Boolean(string='Aplicar probabilidad por antigüedad', default=True)
    line_ids = fields.One2many('l10n_pe.collection.forecast.line', 'forecast_id', string='Partidas', copy=False)
    period_ids = fields.One2many('l10n_pe.collection.forecast.period', 'forecast_id', string='Resumen', copy=False)
    portfolio_amount = fields.Monetary(string='Cartera', compute='_compute_totals')
    expected_amount = fields.Monetary(string='Cobranza esperada', compute='_compute_totals')
    overdue_amount = fields.Monetary(string='Vencido', compute='_compute_totals')
    refreshed_on = fields.Datetime(string='Actualizado el', readonly=True, copy=False)

    @api.depends('line_ids.residual', 'line_ids.expected_amount', 'line_ids.days_overdue')
    def _compute_totals(self):
        for forecast in self:
            forecast.portfolio_amount = sum(forecast.line_ids.mapped('residual'))
            forecast.expected_amount = sum(forecast.line_ids.mapped('expected_amount'))
            forecast.overdue_amount = sum(forecast.line_ids.filtered(lambda l: l.days_overdue > 0).mapped('residual'))

    @api.constrains('period_count')
    def _check_period_count(self):
        for forecast in self:
            if not 1 <= forecast.period_count <= 52:
                raise ValidationError(_('Indique entre 1 y 52 periodos.'))

    # ------------------------------------------------------------------
    # Periodos
    # ------------------------------------------------------------------

    def _period_bounds(self):
        self.ensure_one()
        if self.period_type == 'week':
            start = self.date_from - timedelta(days=self.date_from.weekday())
            step = relativedelta(weeks=1)
        else:
            start = self.date_from.replace(day=1)
            step = relativedelta(months=1)
        bounds = []
        for _index in range(self.period_count):
            end = start + step - timedelta(days=1)
            label = '%s – %s' % (start.strftime('%d/%m'), end.strftime('%d/%m')) if self.period_type == 'week' \
                else '%s %s' % (MONTHS[start.month - 1].capitalize(), start.year)
            bounds.append((start, end, label))
            start = end + timedelta(days=1)
        bounds.append((start, False, _('Desde el %s', start.strftime('%d/%m/%Y'))))
        return bounds

    def _period_for(self, day):
        self.ensure_one()
        for period in self.period_ids.sorted('sequence'):
            if not period.date_end or day <= period.date_end:
                return period
        return self.period_ids[-1:]

    # ------------------------------------------------------------------
    # Partidas
    # ------------------------------------------------------------------

    def _open_lines(self):
        self.ensure_one()
        company = self.company_id
        domain = [
            ('company_id', 'child_of', company.root_id.id),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('account_id', 'not in', company._l10n_pe_collection_excluded_accounts().ids),
            ('reconciled', '=', False),
            ('amount_residual', '>', 0),
            ('partner_id', '!=', False),  # sin cliente no hay a quién cobrar (como la cartera)
        ]
        partners = self.env['l10n_pe.collection.tools']._scope_partners(company, self.user_ids, self.zone_ids)
        if partners is not None:
            domain.append(('partner_id', 'child_of', partners.ids))
        return self.env['account.move.line'].search(domain, order='partner_id, date_maturity, id')

    def _promise_dates(self, lines):
        """{apunte: fecha comprometida}. Un compromiso con documentos fecha esos
        documentos; uno sin documentos, las cuotas vencidas del cliente de la más
        antigua a la más reciente hasta cubrir el importe."""
        dates = {}
        promises = self.env['l10n_pe.collection.promise'].search([
            ('state', '=', 'pending'), ('company_id', 'child_of', self.company_id.root_id.id),
            ('partner_id', 'in', lines.partner_id.commercial_partner_id.ids)], order='date')
        for promise in promises.filtered('line_ids'):
            for line in promise.line_ids & lines:
                dates.setdefault(line, promise.date)
        by_partner = defaultdict(lambda: self.env['account.move.line'])
        for line in lines:
            by_partner[line.partner_id.commercial_partner_id] |= line
        for promise in promises.filtered(lambda p: not p.line_ids):
            remaining = promise.amount
            for line in by_partner[promise.partner_id.commercial_partner_id].sorted(
                    lambda l: l.date_maturity or l.date):
                if remaining <= 0:
                    break
                if line in dates or (line.date_maturity or line.date) >= self.date_from:
                    continue
                dates[line] = promise.date
                remaining -= line.amount_residual
        return dates

    def _line_values(self, lines):
        self.ensure_one()
        company = self.company_id
        Bucket = self.env['l10n_pe.collection.bucket']
        promise_dates = self._promise_dates(lines)
        predictions = {}
        if self.use_behavior:
            predictions = self.env['l10n_pe.collection.predictor']._predict_lines(
                lines.filtered(lambda l: l not in promise_dates), company, self.date_from)
        values = []
        for line in lines:
            partner = line.partner_id.commercial_partner_id
            due = line.date_maturity or line.date
            days = (self.date_from - due).days
            bucket = Bucket._l10n_pe_for_days(days, company)
            if line in promise_dates:
                expected, source = promise_dates[line], 'promise'
            elif line in predictions and predictions[line]['delay'] > 0:
                expected, source = predictions[line]['date'], 'prediction'
            else:
                expected, source = due, 'due'
            probability = bucket.probability if self.use_probability and bucket else 100.0
            values.append({
                'move_line_id': line.id,
                'partner_id': partner.id,
                'user_id': partner.with_company(company).followup_responsible_id.id,
                'zone_id': partner.with_company(company).l10n_pe_collection_zone_id.id,
                'date_due': due,
                'days_overdue': max(days, 0),
                'bucket_id': bucket.id,
                'residual': line.amount_residual,
                'probability': probability,
                'expected_amount': company.currency_id.round(line.amount_residual * probability / 100.0),
                'expected_date': max(expected, self.date_from),
                'source': source,
            })
        return values

    def action_refresh(self):
        """Recalcula la proyección desde la cartera; conserva los ajustes a mano."""
        for forecast in self:
            edited = {line.move_line_id.id: (line.expected_date, line.expected_amount)
                      for line in forecast.line_ids if line.is_edited}
            forecast.line_ids.unlink()
            forecast.period_ids.unlink()
            forecast.period_ids = [Command.create({'sequence': i, 'date_start': start, 'date_end': end, 'name': label})
                                   for i, (start, end, label) in enumerate(forecast._period_bounds())]
            commands = []
            for vals in forecast._line_values(forecast._open_lines()):
                previous = edited.get(vals['move_line_id'])
                if previous:
                    vals.update(expected_date=previous[0], expected_amount=previous[1], is_edited=True,
                                source='manual')
                vals['period_id'] = forecast._period_for(vals['expected_date']).id
                commands.append(Command.create(vals))
            forecast.line_ids = commands
            forecast.refreshed_on = fields.Datetime.now()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        forecasts = super().create(vals_list)
        forecasts.action_refresh()
        return forecasts

    def write(self, vals):
        res = super().write(vals)
        if {'date_from', 'period_type', 'period_count', 'user_ids', 'zone_ids', 'use_behavior',
                'use_probability'} & set(vals):
            self.action_refresh()
        return res

    # ------------------------------------------------------------------
    # Vistas y Excel
    # ------------------------------------------------------------------

    def action_open_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Análisis de %s', self.name),
            'res_model': 'l10n_pe.collection.forecast.line',
            'view_mode': 'pivot,graph,list',
            'domain': [('forecast_id', '=', self.id)],
            'context': {'search_default_group_user': 1},
        }

    def action_prediction_backtest(self):
        self.ensure_one()
        return self.env['l10n_pe.collection.predictor']._backtest_notification(self.company_id)

    def action_export_xlsx(self):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        bold = workbook.add_format({'bold': True})
        money = workbook.add_format({'num_format': '#,##0.00'})
        pct = workbook.add_format({'num_format': '0.0'})
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy'})

        sheet = workbook.add_worksheet(_('Resumen'))
        sheet.write(0, 0, '%s · %s' % (self.company_id.name, self.name), bold)
        sheet.write(1, 0, _('Desde el %(date)s, en %(currency)s', date=self.date_from.strftime('%d/%m/%Y'),
                            currency=self.currency_id.name))
        headers = [_('Periodo'), _('Cartera'), _('Esperado'), _('Acumulado'), _('Cobrado'), _('Diferencia')]
        for col, header in enumerate(headers):
            sheet.write(3, col, header, bold)
        for row, period in enumerate(self.period_ids.sorted('sequence'), start=4):
            sheet.write(row, 0, period.name)
            sheet.write_number(row, 1, period.residual, money)
            sheet.write_number(row, 2, period.expected_amount, money)
            sheet.write_number(row, 3, period.cumulative_amount, money)
            if period.is_past:
                sheet.write_number(row, 4, period.collected_amount, money)
                sheet.write_number(row, 5, period.variance, money)
        sheet.set_column(0, 0, 26)
        sheet.set_column(1, 5, 15)

        detail = workbook.add_worksheet(_('Partidas'))
        headers = [_('Gestor'), _('Zona'), _('Cliente'), _('Documento'), _('Vencimiento'), _('Días de atraso'),
                   _('Tramo'), _('Saldo'), _('Probabilidad %'), _('Esperado'), _('Fecha esperada'), _('Origen'),
                   _('Periodo')]
        for col, header in enumerate(headers):
            detail.write(0, col, header, bold)
        sources = dict(SOURCES)
        for row, line in enumerate(self.line_ids.sorted(lambda l: (l.expected_date, l.id)), start=1):
            detail.write(row, 0, line.user_id.name or '')
            detail.write(row, 1, line.zone_id.name or '')
            detail.write(row, 2, line.partner_id.name or '')
            detail.write(row, 3, line.move_id.name or '')
            detail.write_datetime(row, 4, fields.Datetime.to_datetime(line.date_due), date_fmt)
            detail.write_number(row, 5, line.days_overdue)
            detail.write(row, 6, line.bucket_id.name or '')
            detail.write_number(row, 7, line.residual, money)
            detail.write_number(row, 8, line.probability, pct)
            detail.write_number(row, 9, line.expected_amount, money)
            detail.write_datetime(row, 10, fields.Datetime.to_datetime(line.expected_date), date_fmt)
            detail.write(row, 11, sources.get(line.source, ''))
            detail.write(row, 12, line.period_id.name or '')
        detail.set_column(0, 3, 24)
        detail.set_column(4, 12, 14)
        workbook.close()
        attachment = self.env['ir.attachment'].create({
            'name': '%s %s.xlsx' % (self.name, self.date_from.strftime('%Y-%m-%d')),
            'raw': output.getvalue(),
            'res_model': self._name, 'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % attachment.id,
                'target': 'download'}


class L10nPeCollectionForecastPeriod(models.Model):
    _name = 'l10n_pe.collection.forecast.period'
    _description = 'Periodo de la proyección de cobranza'
    _order = 'sequence'

    forecast_id = fields.Many2one('l10n_pe.collection.forecast', string='Proyección', required=True,
                                  ondelete='cascade', index=True)
    company_id = fields.Many2one(related='forecast_id.company_id', store=True)
    currency_id = fields.Many2one(related='forecast_id.currency_id')
    sequence = fields.Integer()
    name = fields.Char(string='Periodo')
    date_start = fields.Date(string='Inicio')
    date_end = fields.Date(string='Fin')
    line_ids = fields.One2many('l10n_pe.collection.forecast.line', 'period_id', string='Partidas')
    residual = fields.Monetary(string='Cartera', compute='_compute_amounts')
    expected_amount = fields.Monetary(string='Esperado', compute='_compute_amounts')
    cumulative_amount = fields.Monetary(string='Acumulado', compute='_compute_amounts')
    is_past = fields.Boolean(string='Terminado', compute='_compute_collected')
    collected_amount = fields.Monetary(string='Cobrado', compute='_compute_collected',
                                       help='Lo cobrado en el periodo terminado (abonos de bancos y cajas).')
    variance = fields.Monetary(string='Diferencia', compute='_compute_collected',
                               help='Cobrado menos esperado.')

    @api.depends('line_ids.expected_amount', 'line_ids.residual', 'forecast_id.period_ids')
    def _compute_amounts(self):
        for forecast in self.forecast_id:
            total = 0.0
            for period in forecast.period_ids.sorted('sequence'):
                period.residual = sum(period.line_ids.mapped('residual'))
                period.expected_amount = sum(period.line_ids.mapped('expected_amount'))
                total += period.expected_amount
                period.cumulative_amount = total
        for period in self.filtered(lambda p: not p.forecast_id):
            period.residual = period.expected_amount = period.cumulative_amount = 0.0

    @api.depends('date_start', 'date_end', 'expected_amount')
    def _compute_collected(self):
        today = fields.Date.context_today(self)
        tools = self.env['l10n_pe.collection.tools']
        for period in self:
            forecast = period.forecast_id
            period.is_past = bool(period.date_end and period.date_end < today and forecast)
            if not period.is_past:
                period.collected_amount = period.variance = 0.0
                continue
            partners = tools._scope_partners(forecast.company_id, forecast.user_ids, forecast.zone_ids)
            start = max(period.date_start, forecast.date_from)
            period.collected_amount = tools._collected(forecast.company_id, start, period.date_end, partners)
            period.variance = period.collected_amount - period.expected_amount


class L10nPeCollectionForecastLine(models.Model):
    _name = 'l10n_pe.collection.forecast.line'
    _description = 'Partida de la proyección de cobranza'
    _order = 'expected_date, id'

    forecast_id = fields.Many2one('l10n_pe.collection.forecast', string='Proyección', required=True,
                                  ondelete='cascade', index=True)
    company_id = fields.Many2one(related='forecast_id.company_id', store=True)
    currency_id = fields.Many2one(related='forecast_id.currency_id')
    period_id = fields.Many2one('l10n_pe.collection.forecast.period', string='Periodo', index=True)
    move_line_id = fields.Many2one('account.move.line', string='Apunte', readonly=True, index=True)
    move_id = fields.Many2one(related='move_line_id.move_id', string='Documento')
    partner_id = fields.Many2one('res.partner', string='Cliente', readonly=True)
    user_id = fields.Many2one('res.users', string='Gestor', readonly=True)
    zone_id = fields.Many2one('l10n_pe.collection.zone', string='Zona', readonly=True)
    date_due = fields.Date(string='Vencimiento', readonly=True)
    days_overdue = fields.Integer(string='Días de atraso', readonly=True, aggregator='max')
    bucket_id = fields.Many2one('l10n_pe.collection.bucket', string='Tramo', readonly=True)
    residual = fields.Monetary(string='Saldo', readonly=True)
    probability = fields.Float(string='Probabilidad (%)', readonly=True, digits=(5, 1), aggregator='avg')
    expected_amount = fields.Monetary(string='Esperado')
    expected_date = fields.Date(string='Fecha esperada', required=True)
    source = fields.Selection(SOURCES, string='Origen de la fecha', readonly=True)
    is_edited = fields.Boolean(string='Ajustada', readonly=True)

    def write(self, vals):
        if {'expected_date', 'expected_amount'} & set(vals):
            vals = dict(vals, is_edited=True, source='manual')
        res = super().write(vals)
        if 'expected_date' in vals:
            for line in self:
                line.period_id = line.forecast_id._period_for(line.expected_date)
        return res

    def action_reset(self):
        """Quita el ajuste: al actualizar vuelve a la fecha y el importe calculados."""
        self.write({'is_edited': False})
        self.forecast_id.action_refresh()
        return True
