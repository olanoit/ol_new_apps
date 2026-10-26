import base64
import io
from datetime import timedelta

import xlsxwriter
from dateutil.relativedelta import relativedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

CATEGORIES = [
    ('transit', 'En tránsito'),
    ('receivable', 'Por cobrar'),
    ('payable', 'Por pagar'),
    ('check_own', 'Cheque propio'),
    ('check_third', 'Cheque de terceros'),
    ('deposit', 'Depósito a plazo'),
    ('detraction', 'Detracción por pagar'),
    ('manual', 'Manual'),
]
THIRD_PARTY_CHECK_CODES = ('new_third_party_checks', 'in_third_party_checks')
MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
          'octubre', 'noviembre', 'diciembre']


class L10nPeCashForecast(models.Model):
    """Flujo de caja proyectado de la compañía.

    Parte del saldo disponible de bancos y caja a la fecha y suma, por periodo,
    lo que se espera cobrar y pagar según los libros: apuntes abiertos por
    cobrar y por pagar (por vencimiento; lo vencido en el primer periodo),
    cobros y pagos en tránsito en las cuentas de pendientes, cheques, depósitos
    a plazo y partidas manuales. Cada partida tiene una fecha esperada e
    importe editables (el escenario), que se conservan al actualizar.
    """
    _name = 'l10n_pe.cash.forecast'
    _description = 'Flujo de caja proyectado'
    _inherit = ['mail.thread']
    _order = 'date_from desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Nombre', required=True, default=lambda self: _('Flujo de caja'))
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    date_from = fields.Date(string='Desde', required=True, default=fields.Date.context_today, tracking=True)
    period_type = fields.Selection(
        [('week', 'Semanas'), ('month', 'Meses')], string='Periodos', required=True, default='week',
        tracking=True)
    period_count = fields.Integer(string='Cantidad de periodos', required=True, default=12)
    opening_balance = fields.Monetary(
        string='Saldo inicial', readonly=True, copy=False,
        help='Bancos y caja disponibles al cierre de la fecha «Desde».')
    restricted_balance = fields.Monetary(
        string='Fondos no disponibles', readonly=True, copy=False,
        help='Saldo de los diarios marcados como no disponibles (p. ej. detracciones del Banco de '
             'la Nación). No se suma al saldo inicial.')
    line_ids = fields.One2many('l10n_pe.cash.forecast.line', 'forecast_id', string='Partidas', copy=False)
    period_ids = fields.One2many('l10n_pe.cash.forecast.period', 'forecast_id', string='Resumen', copy=False)
    total_in = fields.Monetary(string='Ingresos', compute='_compute_totals')
    total_out = fields.Monetary(string='Egresos', compute='_compute_totals')
    closing_balance = fields.Monetary(string='Saldo final', compute='_compute_totals')
    min_balance = fields.Monetary(
        string='Saldo mínimo', compute='_compute_totals',
        help='El menor saldo de cierre de los periodos: si es negativo, hace falta financiamiento.')
    refreshed_on = fields.Datetime(string='Actualizado el', readonly=True, copy=False)

    @api.depends('opening_balance', 'line_ids.amount', 'period_ids')
    def _compute_totals(self):
        for forecast in self:
            amounts = forecast.line_ids.mapped('amount')
            forecast.total_in = sum(a for a in amounts if a > 0)
            forecast.total_out = -sum(a for a in amounts if a < 0)
            forecast.closing_balance = forecast.opening_balance + forecast.total_in - forecast.total_out
            closings = forecast.period_ids.mapped('closing')
            forecast.min_balance = min(closings) if closings else forecast.opening_balance

    @api.constrains('period_count')
    def _check_period_count(self):
        for forecast in self:
            if not 1 <= forecast.period_count <= 60:
                raise ValidationError(_('Indique entre 1 y 60 periodos.'))

    # ------------------------------------------------------------------
    # Periodos
    # ------------------------------------------------------------------

    def _l10n_pe_period_bounds(self):
        """[(inicio, fin, nombre)] de los periodos; el último, abierto, recoge lo posterior."""
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
            if self.period_type == 'week':
                label = '%s – %s' % (start.strftime('%d/%m'), end.strftime('%d/%m'))
            else:
                label = '%s %s' % (MONTHS[start.month - 1].capitalize(), start.year)
            bounds.append((start, end, label))
            start = end + timedelta(days=1)
        bounds.append((start, False, _('Desde el %s', start.strftime('%d/%m/%Y'))))
        return bounds

    def _l10n_pe_period_for(self, day):
        self.ensure_one()
        for period in self.period_ids.sorted('sequence'):
            if not period.date_end or day <= period.date_end:
                return period
        return self.period_ids[-1:]

    # ------------------------------------------------------------------
    # Fuentes
    # ------------------------------------------------------------------

    def _l10n_pe_journals(self):
        self.ensure_one()
        return self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self.company_id),
            ('type', 'in', ('bank', 'cash'))])

    def _l10n_pe_check_portfolio_journals(self, journals):
        """Diarios de la cartera de cheques de terceros: su saldo son cheques que
        recién estarán disponibles en su fecha de pago."""
        return journals.filtered(lambda j: set(j.inbound_payment_method_line_ids.mapped('code'))
                                 & set(THIRD_PARTY_CHECK_CODES))

    def _l10n_pe_balance(self, accounts):
        if not accounts:
            return 0.0
        groups = self.env['account.move.line']._read_group(
            [('account_id', 'in', accounts.ids), ('parent_state', '=', 'posted'),
             ('date', '<=', self.date_from), ('company_id', 'child_of', self.company_id.root_id.id)],
            aggregates=['balance:sum'])
        return self.currency_id.round(groups[0][0] or 0.0) if groups else 0.0

    def _l10n_pe_excluded_accounts(self):
        """Cuentas por cobrar o por pagar que no se cobran ni se pagan en efectivo:
        anticipos (se aplican a la factura) y detracciones por cobrar (van a la
        cuenta del Banco de la Nación)."""
        company = self.company_id.root_id
        accounts = self.env['account.account']
        if hasattr(company, '_l10n_pe_advance_accounts'):
            accounts |= company._l10n_pe_advance_accounts()
        if 'l10n_pe_detraction_receivable_account_id' in company._fields:
            accounts |= company.l10n_pe_detraction_receivable_account_id
        return accounts

    def _l10n_pe_line_from_aml(self, aml, category):
        due = aml.date_maturity or aml.date
        return {
            'category': category,
            'move_line_id': aml.id,
            'partner_id': aml.partner_id.commercial_partner_id.id,
            'name': aml.move_id.name if not aml.name or aml.name == aml.move_id.name
            else '%s · %s' % (aml.move_id.name, aml.name),
            'date_due': due,
            'amount': aml.amount_residual,
        }

    def _l10n_pe_source_values(self, journals):
        """Partidas automáticas (sin fecha esperada ni periodo)."""
        self.ensure_one()
        AML = self.env['account.move.line']
        company = self.company_id
        common = [('parent_state', '=', 'posted'), ('reconciled', '=', False),
                  ('company_id', 'child_of', company.root_id.id)]
        values = []
        # Cheques propios entregados: se debitan en su fecha de pago.
        own_checks = []
        if 'l10n_latam.check' in self.env:
            own_checks = self.env['l10n_latam.check'].search([
                ('company_id', 'child_of', company.root_id.id), ('issue_state', '=', 'handed'),
                ('outstanding_line_id', '!=', False)])
        own_check_lines = own_checks.outstanding_line_id if own_checks else AML
        # Cobros y pagos en tránsito en las cuentas de pendientes de los métodos.
        outstanding = (journals.inbound_payment_method_line_ids.payment_account_id
                       | journals.outbound_payment_method_line_ids.payment_account_id
                       ).filtered(lambda a: a.account_type != 'asset_cash' and a.reconcile)
        if outstanding:
            for aml in AML.search(common + [('account_id', 'in', outstanding.ids),
                                            ('id', 'not in', own_check_lines.ids)]):
                values.append(self._l10n_pe_line_from_aml(aml, 'transit'))
        for check in own_checks:
            aml = check.outstanding_line_id
            if aml.reconciled:
                continue
            vals = self._l10n_pe_line_from_aml(aml, 'check_own')
            vals.update({'date_due': check.payment_date, 'name': _('Cheque %s', check.name)})
            values.append(vals)
        # Cuentas por cobrar y por pagar.
        detraction_payable = company.root_id.l10n_pe_detraction_payable_account_id \
            if 'l10n_pe_detraction_payable_account_id' in company._fields else self.env['account.account']
        for aml in AML.search(common + [
                ('account_id.account_type', 'in', ('asset_receivable', 'liability_payable')),
                ('account_id', 'not in', self._l10n_pe_excluded_accounts().ids),
                ('amount_residual', '!=', 0.0)]):
            if aml.account_id in detraction_payable:
                category = 'detraction'
            else:
                category = 'receivable' if aml.account_id.account_type == 'asset_receivable' else 'payable'
            values.append(self._l10n_pe_line_from_aml(aml, category))
        # Cheques de terceros en cartera: disponibles en su fecha de pago.
        portfolio = self._l10n_pe_check_portfolio_journals(journals)
        if portfolio and 'l10n_latam.check' in self.env:
            for check in self.env['l10n_latam.check'].search([('current_journal_id', 'in', portfolio.ids)]):
                values.append({
                    'category': 'check_third',
                    'partner_id': check.partner_id.commercial_partner_id.id,
                    'name': _('Cheque %s', check.name),
                    'date_due': check.payment_date,
                    'amount': check.currency_id._convert(check.amount, self.currency_id, company, self.date_from),
                    'source_ref': 'l10n_latam.check,%s' % check.id,
                })
        # Depósitos a plazo vigentes: capital e intereses al vencimiento.
        if 'l10n_pe.term.deposit' in self.env:
            for deposit in self.env['l10n_pe.term.deposit'].search([
                    ('company_id', 'child_of', company.root_id.id), ('state', '=', 'open'),
                    ('deposit_type', '=', 'term'), ('date_end', '!=', False)]):
                amount = deposit.remaining_amount + deposit._l10n_pe_interest_until(deposit.date_end)
                values.append({
                    'category': 'deposit',
                    'name': deposit.display_name,
                    'date_due': deposit.date_end,
                    'amount': deposit.currency_id._convert(amount, self.currency_id, company, self.date_from),
                    'source_ref': 'l10n_pe.term.deposit,%s' % deposit.id,
                })
        return values

    # ------------------------------------------------------------------
    # Actualizar
    # ------------------------------------------------------------------

    def action_refresh(self):
        """Recalcula saldos y partidas desde los libros. Conserva las partidas
        manuales y la fecha esperada o el importe que el usuario cambió."""
        for forecast in self:
            journals = forecast._l10n_pe_journals()
            restricted = journals.filtered('l10n_pe_forecast_exclude')
            portfolio = forecast._l10n_pe_check_portfolio_journals(journals)
            available = journals - restricted - portfolio
            forecast.opening_balance = forecast._l10n_pe_balance(
                available.default_account_id.filtered(lambda a: a.account_type == 'asset_cash'))
            forecast.restricted_balance = forecast._l10n_pe_balance(restricted.default_account_id)

            # Fecha e importe ajustados a mano, leídos antes de borrar las partidas.
            edited = {forecast._l10n_pe_line_key(line): (line.date_expected, line.amount)
                      for line in forecast.line_ids if line.is_edited and line.category != 'manual'}
            manual = forecast.line_ids.filtered(lambda l: l.category == 'manual')
            (forecast.line_ids - manual).unlink()
            forecast.period_ids.unlink()
            forecast.period_ids = [Command.create({'sequence': index, 'date_start': start, 'date_end': end,
                                                   'name': label})
                                   for index, (start, end, label) in enumerate(forecast._l10n_pe_period_bounds())]
            new_lines = []
            for vals in forecast._l10n_pe_source_values(journals):
                key = vals.get('move_line_id') or vals.get('source_ref')
                previous = edited.get(key)
                if previous:
                    vals.update({'date_expected': previous[0], 'amount': previous[1], 'is_edited': True})
                else:
                    vals['date_expected'] = max(vals['date_due'], forecast.date_from)
                vals['period_id'] = forecast._l10n_pe_period_for(vals['date_expected']).id
                new_lines.append(Command.create(vals))
            for line in manual:
                line.period_id = forecast._l10n_pe_period_for(line.date_expected)
            forecast.line_ids = new_lines
            forecast.refreshed_on = fields.Datetime.now()
        return True

    @staticmethod
    def _l10n_pe_line_key(line):
        return line.move_line_id.id or line.source_ref

    @api.model_create_multi
    def create(self, vals_list):
        forecasts = super().create(vals_list)
        forecasts.action_refresh()
        return forecasts

    def write(self, vals):
        res = super().write(vals)
        if {'date_from', 'period_type', 'period_count'} & set(vals):
            self.action_refresh()
        return res

    # ------------------------------------------------------------------
    # Vistas y exportación
    # ------------------------------------------------------------------

    def action_open_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Partidas de %s', self.name),
            'res_model': 'l10n_pe.cash.forecast.line',
            'view_mode': 'pivot,graph,list',
            'domain': [('forecast_id', '=', self.id)],
            'context': {'default_forecast_id': self.id, 'default_category': 'manual'},
        }

    def action_export_xlsx(self):
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        bold = workbook.add_format({'bold': True})
        money = workbook.add_format({'num_format': '#,##0.00'})
        money_bold = workbook.add_format({'num_format': '#,##0.00', 'bold': True})
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy'})

        sheet = workbook.add_worksheet(_('Resumen'))
        sheet.write(0, 0, '%s · %s' % (self.company_id.name, self.name), bold)
        sheet.write(1, 0, _('Desde el %(date)s, en %(currency)s', date=self.date_from.strftime('%d/%m/%Y'),
                            currency=self.currency_id.name))
        headers = [_('Periodo'), _('Saldo inicial'), _('Ingresos'), _('Egresos'), _('Neto'), _('Saldo final'),
                   _('Real'), _('Diferencia')]
        for col, header in enumerate(headers):
            sheet.write(3, col, header, bold)
        for row, period in enumerate(self.period_ids.sorted('sequence'), start=4):
            sheet.write(row, 0, period.name)
            for col, value in enumerate((period.opening, period.inflows, period.outflows, period.net,
                                         period.closing), start=1):
                sheet.write_number(row, col, value, money_bold if col == 5 else money)
            if period.is_past:
                sheet.write_number(row, 6, period.actual_net, money)
                sheet.write_number(row, 7, period.variance, money)
        sheet.set_column(0, 0, 34)
        sheet.set_column(1, 7, 15)

        detail = workbook.add_worksheet(_('Partidas'))
        headers = [_('Periodo'), _('Tipo'), _('Socio'), _('Documento'), _('Vencimiento'), _('Fecha esperada'),
                   _('Importe')]
        for col, header in enumerate(headers):
            detail.write(0, col, header, bold)
        labels = dict(CATEGORIES)
        for row, line in enumerate(self.line_ids.sorted(lambda l: (l.date_expected, l.id)), start=1):
            detail.write(row, 0, line.period_id.name or '')
            detail.write(row, 1, labels.get(line.category, ''))
            detail.write(row, 2, line.partner_id.name or '')
            detail.write(row, 3, line.name or '')
            if line.date_due:
                detail.write_datetime(row, 4, fields.Datetime.to_datetime(line.date_due), date_fmt)
            detail.write_datetime(row, 5, fields.Datetime.to_datetime(line.date_expected), date_fmt)
            detail.write_number(row, 6, line.amount, money)
        detail.set_column(0, 0, 30)
        detail.set_column(1, 3, 28)
        detail.set_column(4, 6, 15)
        workbook.close()

        attachment = self.env['ir.attachment'].create({
            'name': '%s %s.xlsx' % (self.name, self.date_from.strftime('%Y-%m-%d')),
            'datas': base64.b64encode(output.getvalue()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % attachment.id,
                'target': 'download'}


class L10nPeCashForecastPeriod(models.Model):
    _name = 'l10n_pe.cash.forecast.period'
    _description = 'Periodo del flujo de caja'
    _check_company_auto = True
    _order = 'sequence'

    forecast_id = fields.Many2one('l10n_pe.cash.forecast', string='Flujo de caja', required=True,
                                  ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(related='forecast_id.company_id', store=True)
    currency_id = fields.Many2one(related='forecast_id.currency_id')
    sequence = fields.Integer()
    name = fields.Char(string='Periodo')
    date_start = fields.Date(string='Inicio')
    date_end = fields.Date(string='Fin')
    line_ids = fields.One2many('l10n_pe.cash.forecast.line', 'period_id', string='Partidas')
    opening = fields.Monetary(string='Saldo inicial', compute='_compute_amounts')
    inflows = fields.Monetary(string='Ingresos', compute='_compute_amounts')
    outflows = fields.Monetary(string='Egresos', compute='_compute_amounts')
    net = fields.Monetary(string='Neto', compute='_compute_amounts')
    closing = fields.Monetary(string='Saldo final', compute='_compute_amounts')
    is_past = fields.Boolean(string='Terminado', compute='_compute_actual')
    actual_net = fields.Monetary(
        string='Real', compute='_compute_actual',
        help='Movimiento neto de bancos y caja disponibles en el periodo ya terminado, según libros.')
    variance = fields.Monetary(string='Diferencia', compute='_compute_actual', help='Real menos proyectado.')

    @api.depends('line_ids.amount', 'forecast_id.opening_balance', 'forecast_id.period_ids')
    def _compute_amounts(self):
        for forecast in self.forecast_id:
            balance = forecast.opening_balance
            for period in forecast.period_ids.sorted('sequence'):
                amounts = period.line_ids.mapped('amount')
                period.opening = balance
                period.inflows = sum(a for a in amounts if a > 0)
                period.outflows = -sum(a for a in amounts if a < 0)
                period.net = period.inflows - period.outflows
                balance += period.net
                period.closing = balance
        for period in self.filtered(lambda p: not p.forecast_id):
            period.opening = period.inflows = period.outflows = period.net = period.closing = 0.0

    @api.depends('date_start', 'date_end', 'net')
    def _compute_actual(self):
        today = fields.Date.context_today(self)
        for period in self:
            forecast = period.forecast_id
            # Solo periodos terminados: en el que está en curso la comparación engaña.
            period.is_past = bool(period.date_end and period.date_end < today and forecast)
            if not period.is_past:
                period.actual_net = period.variance = 0.0
                continue
            journals = forecast._l10n_pe_journals()
            available = journals - journals.filtered('l10n_pe_forecast_exclude') \
                - forecast._l10n_pe_check_portfolio_journals(journals)
            accounts = available.default_account_id.filtered(lambda a: a.account_type == 'asset_cash')
            # El primer periodo empieza en «Desde»: lo anterior ya está en el saldo inicial.
            start = max(period.date_start, forecast.date_from + timedelta(days=1))
            domain = [('account_id', 'in', accounts.ids), ('parent_state', '=', 'posted'),
                      ('date', '>=', start), ('date', '<=', period.date_end)]
            groups = self.env['account.move.line']._read_group(domain, aggregates=['balance:sum'])
            period.actual_net = (groups[0][0] or 0.0) if groups and accounts else 0.0
            period.variance = period.actual_net - period.net


class L10nPeCashForecastLine(models.Model):
    _name = 'l10n_pe.cash.forecast.line'
    _description = 'Partida del flujo de caja'
    _check_company_auto = True
    _order = 'date_expected, id'

    forecast_id = fields.Many2one('l10n_pe.cash.forecast', string='Flujo de caja', required=True,
                                  ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(related='forecast_id.company_id', store=True)
    currency_id = fields.Many2one(related='forecast_id.currency_id')
    period_id = fields.Many2one('l10n_pe.cash.forecast.period', string='Periodo', index=True, check_company=True)
    category = fields.Selection(CATEGORIES, string='Tipo', required=True, default='manual')
    direction = fields.Selection([('in', 'Ingreso'), ('out', 'Egreso')], string='Sentido',
                                 compute='_compute_direction', store=True)
    move_line_id = fields.Many2one('account.move.line', string='Apunte', readonly=True, index='btree_not_null')
    move_id = fields.Many2one(related='move_line_id.move_id', string='Documento')
    account_id = fields.Many2one(related='move_line_id.account_id', string='Cuenta', store=True)
    source_ref = fields.Char(string='Origen', readonly=True, help='Cheque o depósito a plazo de la partida.')
    partner_id = fields.Many2one('res.partner', string='Socio')
    name = fields.Char(string='Concepto')
    date_due = fields.Date(string='Vencimiento', readonly=True)
    date_expected = fields.Date(string='Fecha esperada', required=True)
    is_overdue = fields.Boolean(string='Vencido', compute='_compute_is_overdue', store=True)
    amount = fields.Monetary(string='Importe', help='Positivo: ingreso. Negativo: egreso.')
    is_edited = fields.Boolean(
        string='Ajustado', readonly=True,
        help='Fecha o importe cambiados a mano: se conservan al actualizar el flujo.')

    @api.depends('amount')
    def _compute_direction(self):
        for line in self:
            line.direction = 'in' if line.amount >= 0 else 'out'

    @api.depends('date_due', 'forecast_id.date_from')
    def _compute_is_overdue(self):
        for line in self:
            line.is_overdue = bool(line.date_due and line.forecast_id.date_from
                                   and line.date_due < line.forecast_id.date_from)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines.filtered(lambda l: not l.period_id):
            line.period_id = line.forecast_id._l10n_pe_period_for(line.date_expected)
        return lines

    def write(self, vals):
        if {'date_expected', 'amount'} & set(vals):
            vals = dict(vals, is_edited=True)
        res = super().write(vals)
        if 'date_expected' in vals:
            for line in self:
                line.period_id = line.forecast_id._l10n_pe_period_for(line.date_expected)
        return res

    def action_reset(self):
        """Quita el ajuste: al actualizar vuelve a la fecha y al importe de los libros."""
        self.write({'is_edited': False})
        self.forecast_id.action_refresh()
        return True

    @api.constrains('category', 'move_line_id', 'source_ref')
    def _check_manual(self):
        for line in self:
            if line.category != 'manual' and not (line.move_line_id or line.source_ref):
                raise ValidationError(_('Las partidas que agrega a mano son de tipo «Manual».'))
