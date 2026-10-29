# -*- coding: utf-8 -*-
"""Posición de tesorería: cuánto dinero hay y cuánto se puede usar.

Los saldos salen de la contabilidad, no de un registro paralelo:

* el **saldo en bancos** es el de la cuenta del diario (1041…), que en Odoo 19
  mueven los extractos conciliados y los asientos directos;
* lo **en tránsito** son los pagos y cobros confirmados que aún no se concilian
  con el extracto (su asiento está en la cuenta de pendientes del diario);
* lo **programado** son los pagos aprobados de las programaciones que aún no
  se pagan.
"""
from odoo import api, fields, models
from odoo.fields import Domain

from .account_journal import ACCOUNT_KINDS


class L10nPeTreasuryPosition(models.Model):
    _name = 'l10n_pe.treasury.position'
    _description = 'Posición de tesorería'
    _inherit = ['mail.thread']
    _check_company_auto = True
    _order = 'date desc, id desc'

    name = fields.Char(string='Posición', compute='_compute_name', store=True)
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today, tracking=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda de la compañía')
    journal_ids = fields.Many2many(
        'account.journal', string='Bancos y cajas', check_company=True,
        domain="[('type', 'in', ('bank', 'cash'))]",
        help='Vacío: todos los bancos y cajas de la compañía.')
    line_ids = fields.One2many('l10n_pe.treasury.position.line', 'position_id', string='Cuentas',
                               copy=False)
    total_balance = fields.Monetary(string='Saldo en bancos y cajas (S/)', compute='_compute_totals',
                                    store=True)
    total_available = fields.Monetary(string='Disponible (S/)', compute='_compute_totals', store=True)
    total_restricted = fields.Monetary(string='Restringido (S/)', compute='_compute_totals', store=True)
    total_scheduled = fields.Monetary(string='Pagos programados (S/)', compute='_compute_totals', store=True)
    computed_at = fields.Datetime(string='Calculada el', readonly=True, copy=False)
    note = fields.Html(string='Notas')

    @api.depends('date')
    def _compute_name(self):
        for position in self:
            position.name = self.env._('Posición al %s', position.date.strftime('%d/%m/%Y')) \
                if position.date else self.env._('Posición')

    @api.depends('line_ids.balance_company', 'line_ids.available_company',
                 'line_ids.scheduled_company', 'line_ids.restricted')
    def _compute_totals(self):
        for position in self:
            lines = position.line_ids
            position.total_balance = sum(lines.mapped('balance_company'))
            position.total_available = sum(lines.mapped('available_company'))
            position.total_restricted = sum(lines.filtered('restricted').mapped('balance_company'))
            position.total_scheduled = sum(lines.mapped('scheduled_company'))

    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    def _l10n_pe_journals(self):
        self.ensure_one()
        return self.journal_ids or self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self.company_id),
            ('type', 'in', ('bank', 'cash'))], order='type, sequence, id')

    def _l10n_pe_scheduled_amounts(self, journals):
        """Pagos aprobados y aún no pagados por diario, en su moneda."""
        lines = self.env['l10n_pe.treasury.payment.plan.line'].search([
            ('plan_id.state', '=', 'approved'), ('plan_id.journal_id', 'in', journals.ids),
            ('plan_id.date', '<=', self.date), ('payment_id', '=', False)])
        amounts = {}
        for line in lines:
            amounts[line.plan_id.journal_id.id] = amounts.get(line.plan_id.journal_id.id, 0.0) + line.amount
        return amounts

    def _l10n_pe_transit_amounts(self, journal):
        """Cobros (positivo) y pagos (negativo) confirmados sin conciliar con el
        extracto, en la moneda del diario."""
        self.ensure_one()
        currency = journal._l10n_pe_treasury_currency()
        company = journal.company_id
        payments = self.env['account.payment'].search([
            ('journal_id', '=', journal.id), ('state', 'in', ('in_process', 'paid')),
            ('is_matched', '=', False), ('move_id', '!=', False), ('date', '<=', self.date),
            ('outstanding_account_id', '!=', journal.default_account_id.id)])
        receipts = payments_out = 0.0
        for payment in payments:
            amount = payment.currency_id._convert(payment.amount, currency, company, payment.date) \
                if payment.currency_id != currency else payment.amount
            if payment.payment_type == 'inbound':
                receipts += amount
            else:
                payments_out -= amount
        return currency.round(receipts), currency.round(payments_out)

    def _l10n_pe_book_balance(self, journal):
        """Saldo de la cuenta del diario a la fecha, en la moneda del diario."""
        self.ensure_one()
        account = journal.default_account_id
        if not account:
            return 0.0
        foreign = journal.currency_id and journal.currency_id != journal.company_id.currency_id
        aggregate = 'amount_currency:sum' if foreign else 'balance:sum'
        domain = Domain([('account_id', '=', account.id), ('parent_state', '=', 'posted'),
                         ('date', '<=', self.date), ('company_id', 'child_of', journal.company_id.root_id.id)])
        if foreign:
            domain &= Domain('currency_id', '=', journal.currency_id.id)
        [(total,)] = self.env['account.move.line']._read_group(domain, aggregates=[aggregate])
        return total or 0.0

    def _l10n_pe_statement_balance(self, journal):
        """Último saldo final de extracto hasta la fecha (o ``False`` si no hay)."""
        statement = self.env['account.bank.statement'].search([
            ('journal_id', '=', journal.id), ('date', '<=', self.date)], order='date desc, id desc', limit=1)
        return statement.balance_end_real if statement else False

    def _l10n_pe_line_values(self, journal, scheduled):
        currency = journal._l10n_pe_treasury_currency()
        receipts, payments = self._l10n_pe_transit_amounts(journal)
        statement = self._l10n_pe_statement_balance(journal)
        return {
            'position_id': self.id,
            'journal_id': journal.id,
            'kind': journal.l10n_pe_treasury_kind or ('cash' if journal.type == 'cash' else 'checking'),
            'bank_id': journal.bank_account_id.l10n_pe_bank_id.id,
            'currency_id': currency.id,
            'restricted': journal.l10n_pe_forecast_exclude,
            'balance': currency.round(self._l10n_pe_book_balance(journal)),
            'statement_balance': statement or 0.0,
            'has_statement': statement is not False,
            'receipts_transit': receipts,
            'payments_transit': payments,
            'scheduled': currency.round(scheduled.get(journal.id, 0.0)),
            'min_balance': journal.l10n_pe_treasury_min_balance,
            'overdraft': journal.l10n_pe_treasury_overdraft,
        }

    def action_compute(self):
        for position in self:
            journals = position._l10n_pe_journals()
            scheduled = position._l10n_pe_scheduled_amounts(journals)
            position.line_ids.unlink()
            self.env['l10n_pe.treasury.position.line'].create([
                position._l10n_pe_line_values(journal, scheduled) for journal in journals])
            position.computed_at = fields.Datetime.now()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        positions = super().create(vals_list)
        positions.action_compute()
        return positions

    def action_open_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.display_name,
            'res_model': 'l10n_pe.treasury.position.line',
            'view_mode': 'list,pivot,graph',
            'domain': [('position_id', '=', self.id)],
            'context': {'create': False},
        }

    @api.model
    def _cron_l10n_pe_daily_position(self):
        """Guarda la posición del día de cada compañía con bancos (una por día)."""
        today = fields.Date.context_today(self)
        for company in self.env['res.company'].search([]):
            journals = self.env['account.journal'].search([
                *self.env['account.journal']._check_company_domain(company), ('type', 'in', ('bank', 'cash'))],
                limit=1)
            if not journals:
                continue
            position = self.with_company(company).search(
                [('company_id', '=', company.id), ('date', '=', today), ('journal_ids', '=', False)], limit=1)
            if position:
                position.action_compute()
            else:
                self.with_company(company).create({'date': today, 'company_id': company.id})
        return True


class L10nPeTreasuryPositionLine(models.Model):
    _name = 'l10n_pe.treasury.position.line'
    _description = 'Cuenta en la posición de tesorería'
    _check_company_auto = True
    _order = 'position_id, restricted, kind, journal_id'

    position_id = fields.Many2one('l10n_pe.treasury.position', string='Posición', required=True,
                                  ondelete='cascade', index=True, check_company=True)
    date = fields.Date(related='position_id.date', store=True)
    company_id = fields.Many2one(related='position_id.company_id', store=True, index=True)
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda de la compañía')
    journal_id = fields.Many2one('account.journal', string='Banco o caja', required=True, check_company=True)
    kind = fields.Selection(ACCOUNT_KINDS, string='Tipo de cuenta')
    bank_id = fields.Many2one('l10n_pe.bank', string='Banco')
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True)
    restricted = fields.Boolean(string='Restringida')
    has_statement = fields.Boolean(string='Con extracto')
    balance = fields.Monetary(string='Saldo contable', help='Saldo de la cuenta del diario a la fecha.')
    statement_balance = fields.Monetary(string='Saldo del extracto',
                                        help='Saldo final del último extracto hasta la fecha.')
    receipts_transit = fields.Monetary(string='Cobros en tránsito',
                                       help='Cobros confirmados aún no conciliados con el extracto.')
    payments_transit = fields.Monetary(string='Pagos en tránsito',
                                       help='Pagos confirmados aún no conciliados con el extracto (negativo).')
    scheduled = fields.Monetary(string='Pagos programados',
                                help='Pagos aprobados en las programaciones que aún no se pagan.')
    min_balance = fields.Monetary(string='Saldo mínimo')
    overdraft = fields.Monetary(string='Sobregiro autorizado')
    projected = fields.Monetary(string='Saldo proyectado', compute='_compute_amounts', store=True,
                                help='Saldo contable + cobros y pagos en tránsito − pagos programados.')
    available = fields.Monetary(string='Disponible', compute='_compute_amounts', store=True,
                                help='Saldo proyectado − saldo mínimo + sobregiro. Cero en las cuentas '
                                     'restringidas.')
    rate = fields.Float(string='T.C.', digits=(12, 4), compute='_compute_amounts', store=True,
                        help='Soles por unidad de la moneda de la cuenta a la fecha de la posición.')
    balance_company = fields.Monetary(string='Saldo (S/)', currency_field='company_currency_id',
                                      compute='_compute_amounts', store=True)
    available_company = fields.Monetary(string='Disponible (S/)', currency_field='company_currency_id',
                                        compute='_compute_amounts', store=True)
    scheduled_company = fields.Monetary(string='Programado (S/)', currency_field='company_currency_id',
                                        compute='_compute_amounts', store=True)

    @api.depends('balance', 'receipts_transit', 'payments_transit', 'scheduled', 'min_balance',
                 'overdraft', 'restricted', 'currency_id', 'date')
    def _compute_amounts(self):
        for line in self:
            company = line.company_id
            line.projected = line.balance + line.receipts_transit + line.payments_transit - line.scheduled
            line.available = 0.0 if line.restricted else \
                line.projected - line.min_balance + line.overdraft
            if line.currency_id == company.currency_id or not line.currency_id:
                rate = 1.0
            else:
                rate = line.currency_id._convert(1.0, company.currency_id, company, line.date, round=False)
            line.rate = rate
            line.balance_company = company.currency_id.round(line.balance * rate)
            line.available_company = company.currency_id.round(line.available * rate)
            line.scheduled_company = company.currency_id.round(line.scheduled * rate)

    def action_open_journal_items(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.journal_id.display_name,
            'res_model': 'account.move.line',
            'view_mode': 'list,form',
            'domain': [('account_id', '=', self.journal_id.default_account_id.id), ('parent_state', '=', 'posted'),
                       ('date', '<=', self.date)],
            'context': {'create': False},
        }
