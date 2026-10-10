# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError


def _months_between(start, end):
    """Meses enteros de ``start`` a ``end`` (primer día de un mes)."""
    return (end.year - start.year) * 12 + end.month - start.month


class L10nPeLeaseOperationMixin(models.AbstractModel):
    """Comprobaciones comunes de la remedición y la terminación: rigen desde el
    primer día de un mes y no deben quedar asientos del pasivo ni del activo
    contabilizados desde esa fecha (se rehacen)."""
    _name = 'l10n_pe.lease.operation.mixin'
    _description = 'Operación sobre un arrendamiento'

    def _check_operation_date(self, lease, date):
        if lease.state != 'running':
            raise UserError(self.env._('El contrato %s no está en curso.', lease.name))
        if date.day != 1:
            raise UserError(self.env._('La fecha debe ser el primer día de un mes.'))
        if not lease.date_start < date <= lease.date_end:
            raise UserError(self.env._('La fecha debe estar dentro del plazo del contrato (%(start)s – %(end)s).',
                                       start=lease.date_start, end=lease.date_end))
        # Los asientos del préstamo se juzgan por la fecha de su cuota: la
        # reversión de una reclasificación anterior lleva fecha del mes siguiente.
        posted = lease.loan_id.line_ids.generated_move_ids.filtered(
            lambda m: m.state == 'posted' and m.generating_loan_line_id.date >= date)
        posted |= lease.asset_id.depreciation_move_ids.filtered(lambda m: m.state == 'posted' and m.date >= date)
        if posted:
            raise UserError(self.env._(
                'Ya hay asientos contabilizados desde %(date)s (%(moves)s): elija el primer día del mes siguiente '
                'al último asiento contabilizado.', date=date, moves=', '.join(posted[:3].mapped('display_name'))))

    @staticmethod
    def _close_loan(loan, date):
        """Cierra el préstamo al ``date``: borra sus asientos en borrador posteriores."""
        if loan and loan.state == 'running':
            loan.env['account.loan.close.wizard'].create({'loan_id': loan.id, 'date': date}).action_save()


class L10nPeLeaseRemeasure(models.TransientModel):
    """Remedición (NIIF 16 párr. 39–46): cambio de cuota, de plazo o de tasa.
    El pasivo se recalcula con las cuotas que faltan y la diferencia ajusta el
    derecho de uso."""
    _name = 'l10n_pe.lease.remeasure'
    _description = 'Remedición del arrendamiento'
    _inherit = ['l10n_pe.lease.operation.mixin']
    _check_company_auto = True

    lease_id = fields.Many2one('l10n_pe.lease', string='Contrato', required=True, check_company=True)
    company_id = fields.Many2one(related='lease_id.company_id')
    currency_id = fields.Many2one(related='lease_id.currency_id')
    date = fields.Date(string='Rige desde', required=True,
                       default=lambda self: fields.Date.context_today(self) + relativedelta(day=1, months=1),
                       help='Primer día del mes desde el que cambian las cuotas.')
    payment_amount = fields.Monetary(string='Cuota mensual nueva', required=True)
    remaining_months = fields.Integer(string='Cuotas que faltan', required=True,
                                      help='Meses de contrato desde la fecha, incluido ese mes.')
    annual_rate = fields.Float(string='Tasa anual (%)', digits=(6, 4), required=True,
                               help='NIIF 16: con cambio de plazo u opción se usa una tasa revisada a la fecha; '
                                    'con un cambio de cuota por índice se mantiene la tasa.')
    reason = fields.Char(string='Motivo', required=True)
    carrying_amount = fields.Monetary(string='Pasivo actual', compute='_compute_preview')
    new_liability = fields.Monetary(string='Pasivo remedido', compute='_compute_preview')
    difference = fields.Monetary(string='Ajuste del pasivo y del derecho de uso', compute='_compute_preview')

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        lease = self.env['l10n_pe.lease'].browse(vals.get('lease_id') or self.env.context.get('default_lease_id'))
        if lease:
            date = vals.get('date') or fields.Date.context_today(self) + relativedelta(day=1, months=1)
            vals.setdefault('payment_amount', lease.line_ids[-1:].payment or lease.payment_amount)
            vals.setdefault('annual_rate', lease.annual_rate)
            vals.setdefault('remaining_months', max(_months_between(date, lease.date_end + relativedelta(days=1)), 0))
        return vals

    @api.depends('lease_id', 'date', 'payment_amount', 'remaining_months', 'annual_rate')
    def _compute_preview(self):
        for wizard in self:
            lease = wizard.lease_id
            if not (lease and wizard.date and wizard.remaining_months > 0 and wizard.payment_amount):
                wizard.update({'carrying_amount': 0.0, 'new_liability': 0.0, 'difference': 0.0})
                continue
            carrying = lease._principal_before(wizard.date)
            new, _rows = wizard._new_schedule()
            wizard.carrying_amount = carrying
            wizard.new_liability = new
            wizard.difference = lease.currency_id.round(new - carrying)

    def _new_schedule(self):
        lease = self.lease_id
        previous = lease.line_ids.filtered(lambda l: l.date < self.date)
        advance = lease.payment_timing == 'advance'
        first = (max(previous.mapped('number')) + 1) if previous else (2 if advance else 1)
        if advance and not previous:
            # Antes de la primera cuota de la tabla: la del mes de la fecha es la n.º 2.
            first = _months_between(lease.date_start, self.date) + 1
        return lease._build_rows(self.date, self.remaining_months, self.payment_amount,
                                 lease._rate(self.annual_rate), advance, first, payment_at_start=True)

    def action_apply(self):
        self.ensure_one()
        lease, date = self.lease_id, self.date
        self._check_operation_date(lease, date)
        if self.remaining_months <= 0:
            raise UserError(self.env._('Indique las cuotas que faltan.'))
        day_before = date - relativedelta(days=1)
        lease._exchange_difference(day_before)
        carrying = lease._principal_before(date)
        new_liability, rows = self._new_schedule()
        difference = lease.currency_id.round(new_liability - carrying)
        rate = lease._company_rate(date)
        difference_company = lease._to_company(difference, rate=rate)
        old_loan = lease.loan_id
        old = {'old_payment': lease.line_ids[-1:].payment or lease.payment_amount,
               'old_term': lease.term_months, 'old_rate': lease.annual_rate}

        # Pasivo: se cierra el préstamo y la tabla sigue con las cuotas nuevas.
        self._close_loan(old_loan, day_before)
        lease.line_ids.filtered(lambda l: l.date >= date).unlink()
        lease.line_ids = [Command.create(lease._line_vals(row)) for row in rows]
        new_lines = lease.line_ids.filtered(lambda l: l.date >= date)
        new_term = _months_between(lease.date_start, date) + self.remaining_months
        lease.write({'payment_amount': self.payment_amount, 'term_months': new_term,
                     'annual_rate': self.annual_rate})
        lease.loan_id = lease._create_loan(new_lines, date, rate, suffix=self.env._(' (remedición %s)', date))

        # Derecho de uso: aumenta o disminuye por el mismo importe, con el plazo nuevo.
        moves = self._adjust_right_of_use(lease, day_before, difference_company, new_term)
        lease.event_ids = [Command.create(dict(old, **{
            'kind': 'remeasurement', 'date': date, 'old_liability': carrying, 'new_liability': new_liability,
            'difference': difference, 'amount_company': difference_company, 'new_payment': self.payment_amount,
            'new_term': new_term, 'new_rate': self.annual_rate, 'move_ids': [Command.set(moves.ids)],
            'old_loan_id': old_loan.id,
            'note': self.reason}))]
        lease.message_post(body=self.env._(
            'Remedición desde %(date)s (%(reason)s): pasivo %(old)s → %(new)s; ajuste %(diff)s.',
            date=date, reason=self.reason, old=lease.currency_id.format(carrying),
            new=lease.currency_id.format(new_liability), diff=lease.currency_id.format(difference)))
        return {'type': 'ir.actions.act_window_close'}

    def _adjust_right_of_use(self, lease, date, amount, new_term):
        """Aumento: «Reevaluar» del activo crea el aumento bruto contra el
        pasivo. Disminución: se rebaja el valor del activo contra el pasivo
        (no contra gasto) y lo que exceda su valor en libros va a resultados."""
        asset = lease.asset_id
        move = self.env['account.move']
        currency = lease.company_currency_id
        if currency.compare_amounts(amount, 0) < 0:
            residual = asset._get_residual_value_at_date(date)
            decrease = min(-amount, residual)
            if not currency.is_zero(decrease):
                vals = self.env['account.move']._prepare_move_for_asset_depreciation({
                    'amount': decrease, 'asset_id': asset, 'date': date,
                    'depreciation_beginning_date': date, 'depreciation_end_date': date,
                    'asset_number_days': 0, 'asset_value_change': True,
                    'asset_move_type': 'negative_revaluation',
                    'move_ref': self.env._('Remedición %s: disminución del derecho de uso', lease.name),
                })
                label = self.env._('Remedición %s: disminución del derecho de uso', lease.name)
                vals.update(ref=label, l10n_pe_lease_id=lease.id)
                # El activo mide la disminución por su línea de gasto: se registra
                # nativa y luego se reclasifica ese gasto contra el pasivo.
                move = self.env['account.move'].create(vals)
                move._post()
                move |= lease._post_move(date, label, [
                    lease._move_line(lease.liability_long_account_id, decrease, label, 0.0),
                    lease._move_line(asset.account_depreciation_expense_id, -decrease, label)])
            excess = currency.round(-amount - decrease)
            if not currency.is_zero(excess):
                gain = lease.company_id.gain_account_id
                if not gain:
                    raise UserError(self.env._('Configure la cuenta de ganancia de activos de la compañía.'))
                label = self.env._('Remedición %s: exceso sobre el derecho de uso', lease.name)
                move |= lease._post_move(date, label, [lease._move_line(lease.liability_long_account_id, excess, label, 0.0),
                                                       lease._move_line(gain, -excess, label)])
            amount = 0.0
        wizard = self.env['asset.modify'].create({
            'asset_id': asset.id,
            'name': self.reason,
            'modify_action': 'modify',
            'date': date,
            'method_number': new_term,
            'method_period': asset.method_period,
            'value_residual': currency.round(asset._get_residual_value_at_date(date) + max(amount, 0.0)),
            'salvage_value': asset.salvage_value,
            'account_asset_id': lease.rou_account_id.id,
            'account_asset_counterpart_id': lease.liability_long_account_id.id,
            'account_depreciation_id': asset.account_depreciation_id.id,
            'account_depreciation_expense_id': asset.account_depreciation_expense_id.id,
        })
        children_before = asset.children_ids
        wizard.modify()
        increase = (asset.children_ids - children_before).original_move_line_ids.move_id
        increase.write({'l10n_pe_lease_id': lease.id,
                        'ref': self.env._('Remedición %s: aumento del derecho de uso', lease.name)})
        return move | increase


class L10nPeLeaseTerminate(models.TransientModel):
    """Terminación anticipada (NIIF 16 párr. 46): se dan de baja el derecho de
    uso y el pasivo pendiente; la diferencia va a resultados."""
    _name = 'l10n_pe.lease.terminate'
    _description = 'Terminación anticipada del arrendamiento'
    _inherit = ['l10n_pe.lease.operation.mixin']
    _check_company_auto = True

    lease_id = fields.Many2one('l10n_pe.lease', string='Contrato', required=True, check_company=True)
    company_id = fields.Many2one(related='lease_id.company_id')
    currency_id = fields.Many2one(related='lease_id.currency_id')
    date = fields.Date(string='Termina desde', required=True,
                       default=lambda self: fields.Date.context_today(self) + relativedelta(day=1, months=1),
                       help='Primer día del mes sin contrato: el último mes con alquiler es el anterior.')
    reason = fields.Char(string='Motivo', required=True)
    gain_account_id = fields.Many2one(related='company_id.gain_account_id', readonly=False,
                                      string='Cuenta de ganancia')
    loss_account_id = fields.Many2one(related='company_id.loss_account_id', readonly=False,
                                      string='Cuenta de pérdida')
    carrying_amount = fields.Monetary(string='Pasivo que se da de baja', compute='_compute_preview')

    @api.depends('lease_id', 'date')
    def _compute_preview(self):
        for wizard in self:
            wizard.carrying_amount = wizard.lease_id._principal_before(wizard.date) \
                if wizard.lease_id and wizard.date else 0.0

    def action_apply(self):
        self.ensure_one()
        lease, date = self.lease_id, self.date
        self._check_operation_date(lease, date)
        if not (lease.company_id.gain_account_id and lease.company_id.loss_account_id):
            raise UserError(self.env._('Indique las cuentas de ganancia y de pérdida.'))
        day_before = date - relativedelta(days=1)
        lease._exchange_difference(day_before)
        carrying = lease._principal_before(date)
        carrying_company = lease._to_company(carrying, day_before)
        self._close_loan(lease.loan_id, day_before)
        lease.line_ids.filtered(lambda l: l.date >= date).unlink()

        # Derecho de uso: baja al valor en libros (pérdida) ...
        action = lease.asset_id.set_to_close(self.env['account.move.line'], date=day_before, message=self.reason)
        disposal = self.env['account.move'].browse(action.get('res_id') if isinstance(action, dict) else [])
        disposal |= lease.asset_id.depreciation_move_ids.filtered(
            lambda m: m.state == 'draft' and m.asset_move_type == 'disposal')
        disposal._post()
        # ... y el pasivo pendiente a resultados (ganancia).
        label = self.env._('Terminación %s: baja del pasivo', lease.name)
        move = lease._post_move(day_before, label, [
            lease._move_line(lease.liability_long_account_id, carrying_company, label, carrying),
            lease._move_line(lease.company_id.gain_account_id, -carrying_company, label)])
        lease.event_ids = [Command.create({
            'kind': 'termination', 'date': date, 'old_liability': carrying, 'new_liability': 0.0,
            'difference': -carrying, 'amount_company': -carrying_company,
            'move_ids': [Command.set((move | disposal).ids)],
            'old_loan_id': lease.loan_id.id, 'note': self.reason})]
        lease.write({'state': 'closed', 'termination_date': date})
        lease.message_post(body=self.env._(
            'Terminación anticipada desde %(date)s (%(reason)s): pasivo dado de baja %(liability)s.',
            date=date, reason=self.reason, liability=lease.currency_id.format(carrying)))
        return {'type': 'ir.actions.act_window_close'}


class L10nPeLeaseExchange(models.TransientModel):
    _name = 'l10n_pe.lease.exchange'
    _description = 'Diferencia de cambio del arrendamiento'
    _check_company_auto = True

    lease_id = fields.Many2one('l10n_pe.lease', string='Contrato', required=True, check_company=True)
    company_id = fields.Many2one(related='lease_id.company_id')
    date = fields.Date(string='Al', required=True,
                       default=lambda self: fields.Date.context_today(self) + relativedelta(day=1, days=-1),
                       help='Normalmente el último día del mes: el pasivo se expresa al tipo de cambio de esa fecha.')

    def action_apply(self):
        self.ensure_one()
        if not self.lease_id.is_foreign_currency:
            raise UserError(self.env._('El contrato está en la moneda de la compañía: no hay diferencia de cambio.'))
        moves = self.lease_id._exchange_difference(self.date)
        if not moves:
            self.lease_id.message_post(body=self.env._('Diferencia de cambio al %s: sin ajuste.', self.date))
        return {'type': 'ir.actions.act_window_close'}


class L10nPeLeaseTaxReport(models.TransientModel):
    """Diferencias temporales del impuesto a la renta. Contablemente el gasto
    es depreciación del derecho de uso + interés; tributariamente se deduce la
    cuota de alquiler devengada (el derecho de uso no es activo fijo ni
    intangible: no se deprecia para el impuesto, Informe 054-2021-SUNAT/7T0000).
    La diferencia origina impuesto diferido (NIC 12)."""
    _name = 'l10n_pe.lease.tax.report'
    _description = 'Diferencias temporales de arrendamientos'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    year = fields.Integer(string='Ejercicio', required=True,
                          default=lambda self: fields.Date.context_today(self).year)
    tax_rate = fields.Float(string='Tasa del impuesto a la renta (%)', default=29.5, digits=(5, 2))
    line_ids = fields.One2many('l10n_pe.lease.tax.report.line', 'report_id', string='Contratos', readonly=True)
    total_book = fields.Monetary(string='Gasto contable', compute='_compute_totals')
    total_tax = fields.Monetary(string='Gasto tributario', compute='_compute_totals')
    total_difference = fields.Monetary(string='Diferencia temporal', compute='_compute_totals')
    total_deferred = fields.Monetary(string='Impuesto diferido', compute='_compute_totals')

    @api.depends('line_ids')
    def _compute_totals(self):
        for report in self:
            lines = report.line_ids
            report.total_book = sum(lines.mapped('book_expense'))
            report.total_tax = sum(lines.mapped('tax_expense'))
            report.total_difference = sum(lines.mapped('difference'))
            report.total_deferred = sum(lines.mapped('deferred_tax'))

    def action_compute(self):
        self.ensure_one()
        start, end = fields.Date.from_string('%s-01-01' % self.year), fields.Date.from_string('%s-12-31' % self.year)
        in_year = lambda m: m.state == 'posted' and start <= m.date <= end
        leases = self.env['l10n_pe.lease'].search([
            ('company_id', '=', self.company_id.id), ('state', 'in', ('running', 'closed')),
            ('initial_move_id', '!=', False)])
        lines = []
        for lease in leases:
            assets = lease.asset_id | lease.asset_id.children_ids
            depreciation = sum(assets.depreciation_move_ids.filtered(
                lambda m: in_year(m) and m.asset_move_type == 'depreciation').mapped('depreciation_value'))
            interest = sum(line.interest for line in lease._loans().line_ids
                           if line.generated_move_ids.filtered(lambda m: m.is_loan_payment_move and in_year(m)))
            rent = sum(abs(bill.amount_untaxed_signed) * (1 if bill.move_type == 'in_invoice' else -1)
                       for bill in lease._vendor_bills().filtered(in_year))
            if not (depreciation or interest or rent):
                continue
            book = self.currency_id.round(depreciation + interest)
            difference = self.currency_id.round(book - rent)
            lines.append(Command.create({
                'lease_id': lease.id, 'depreciation': depreciation, 'interest': interest,
                'book_expense': book, 'tax_expense': rent, 'difference': difference,
                'deferred_tax': self.currency_id.round(difference * self.tax_rate / 100.0),
            }))
        self.line_ids = [Command.clear()] + lines
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'current'}


class L10nPeLeaseTaxReportLine(models.TransientModel):
    _name = 'l10n_pe.lease.tax.report.line'
    _description = 'Diferencia temporal por contrato'

    report_id = fields.Many2one('l10n_pe.lease.tax.report', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='report_id.currency_id')
    lease_id = fields.Many2one('l10n_pe.lease', string='Contrato', readonly=True)
    depreciation = fields.Monetary(string='Depreciación del derecho de uso')
    interest = fields.Monetary(string='Interés del pasivo')
    book_expense = fields.Monetary(string='Gasto contable')
    tax_expense = fields.Monetary(string='Alquiler deducible',
                                  help='Cuotas de las facturas del arrendador del ejercicio (base imponible).')
    difference = fields.Monetary(string='Diferencia temporal',
                                 help='Gasto contable − alquiler deducible. Positiva: se adiciona en la '
                                      'declaración y genera un activo por impuesto diferido; negativa: se deduce '
                                      'y lo revierte.')
    deferred_tax = fields.Monetary(string='Impuesto diferido')
