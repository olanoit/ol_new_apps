# -*- coding: utf-8 -*-
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .term_deposit_account_config import DEPOSIT_TYPES

STATES = [
    ('draft', 'Borrador'),
    ('open', 'Vigente'),
    ('expired', 'Vencido'),
    ('closed', 'Cancelado'),
    ('renewed', 'Renovado'),
]
DAY_BASES = [('360', '360 días'), ('365', '365 días')]
GUARANTEES = ('guarantee_fund', 'guarantee_given')


class L10nPeTermDeposit(models.Model):
    _name = 'l10n_pe.term.deposit'
    _description = 'Depósito a plazo o garantía'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'date_start desc, id desc'

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    state = fields.Selection(STATES, string='Estado', default='draft', required=True,
                             readonly=True, copy=False, tracking=True)
    deposit_type = fields.Selection(DEPOSIT_TYPES, string='Tipo', required=True, default='term',
                                    tracking=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    partner_id = fields.Many2one(
        'res.partner', string='Entidad', required=True, check_company=True, tracking=True,
        help='Banco del depósito o del fondo, o quien recibe la garantía (p. ej. el arrendador).')
    reference = fields.Char(string='N.º de operación', tracking=True,
                            help='Número del certificado, de la cuenta o del contrato.')
    user_id = fields.Many2one('res.users', string='Responsable', default=lambda self: self.env.user,
                              help='Recibe el aviso de vencimiento.')
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                  default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary(string='Capital', required=True, tracking=True)
    rate = fields.Float(string='TEA (%)', digits=(6, 4), tracking=True,
                        help='Tasa efectiva anual. Vacía (0): no genera intereses.')
    day_basis = fields.Selection(DAY_BASES, string='Base de días', required=True, default='360',
                                 help='Año comercial (360) o calendario (365) para el interés de los días.')
    date_start = fields.Date(string='Fecha de apertura', required=True, default=fields.Date.context_today,
                             tracking=True)
    term_days = fields.Integer(string='Plazo (días)', tracking=True,
                               help='Vacío en las garantías sin plazo.')
    date_end = fields.Date(string='Vencimiento', compute='_compute_date_end', store=True, readonly=False,
                           tracking=True)
    auto_renew = fields.Boolean(string='Renovación automática',
                                help='Al vencer se renueva solo por el mismo plazo y la misma tasa.')
    capitalize_interest = fields.Boolean(string='Capitalizar intereses',
                                         help='Al renovar, los intereses se suman al capital del nuevo depósito.')
    journal_id = fields.Many2one(
        'account.journal', string='Banco', required=True, check_company=True,
        domain="[('type', 'in', ('bank', 'cash'))]",
        help='Cuenta bancaria de la que sale el dinero y a la que vuelve.')
    misc_journal_id = fields.Many2one(
        'account.journal', string='Diario de intereses', required=True, check_company=True,
        domain="[('type', '=', 'general')]",
        default=lambda self: self.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', self.env.company.id)], limit=1),
        help='Diario del devengo mensual de intereses.')
    deposit_account_id = fields.Many2one(
        'account.account', string='Cuenta del depósito', check_company=True,
        compute='_compute_accounts', store=True, readonly=False)
    interest_account_id = fields.Many2one(
        'account.account', string='Intereses por cobrar', check_company=True,
        compute='_compute_accounts', store=True, readonly=False)
    income_account_id = fields.Many2one(
        'account.account', string='Ingreso por intereses', check_company=True,
        compute='_compute_accounts', store=True, readonly=False)
    expected_interest = fields.Monetary(string='Interés al vencimiento', compute='_compute_expected_interest',
                                        help='Interés de todo el plazo con la TEA y la base de días.')
    interest_accrued = fields.Monetary(string='Intereses devengados', readonly=True, copy=False)
    interest_collected = fields.Monetary(string='Intereses cobrados', readonly=True, copy=False)
    released_amount = fields.Monetary(string='Capital liberado', readonly=True, copy=False)
    remaining_amount = fields.Monetary(string='Saldo', compute='_compute_remaining', store=True)
    move_ids = fields.Many2many('account.move', string='Asientos', readonly=True, copy=False)
    move_count = fields.Integer(compute='_compute_move_count')
    renewed_from_id = fields.Many2one('l10n_pe.term.deposit', string='Renueva a', readonly=True, copy=False,
                                      check_company=True)
    renewal_id = fields.Many2one('l10n_pe.term.deposit', string='Renovado en', readonly=True, copy=False,
                                 check_company=True)
    notice_sent = fields.Boolean(string='Aviso enviado', readonly=True, copy=False)
    due_soon = fields.Boolean(string='Por vencer', compute='_compute_due_soon')
    notes = fields.Html(string='Notas')

    _positive_amount = models.Constraint('CHECK(amount >= 0)', 'El capital no puede ser negativo.')

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------
    @api.depends('date_start', 'term_days')
    def _compute_date_end(self):
        for deposit in self:
            if deposit.date_start and deposit.term_days:
                deposit.date_end = deposit.date_start + timedelta(days=deposit.term_days)
            else:
                deposit.date_end = deposit.date_end

    @api.onchange('date_end')
    def _onchange_date_end(self):
        if self.date_end and self.date_start:
            self.term_days = (self.date_end - self.date_start).days

    @api.depends('deposit_type', 'currency_id', 'company_id')
    def _compute_accounts(self):
        Config = self.env['l10n_pe.term.deposit.account.config']
        for deposit in self:
            if deposit.state not in ('draft', False) and deposit.deposit_account_id:
                continue
            config = Config._l10n_pe_get(deposit.company_id, deposit.deposit_type, deposit.currency_id)
            deposit.deposit_account_id = config.deposit_account_id
            deposit.interest_account_id = config.interest_account_id
            deposit.income_account_id = config.income_account_id

    @api.depends('amount', 'rate', 'day_basis', 'date_start', 'date_end')
    def _compute_expected_interest(self):
        for deposit in self:
            deposit.expected_interest = deposit._l10n_pe_interest_until(deposit.date_end) \
                if deposit.date_end else 0.0

    @api.depends('amount', 'released_amount')
    def _compute_remaining(self):
        for deposit in self:
            deposit.remaining_amount = deposit.amount - deposit.released_amount

    def _compute_move_count(self):
        for deposit in self:
            deposit.move_count = len(deposit.move_ids)

    @api.depends('date_end', 'state', 'company_id.l10n_pe_term_deposit_notice_days')
    def _compute_due_soon(self):
        today = fields.Date.context_today(self)
        for deposit in self:
            notice = deposit.company_id.l10n_pe_term_deposit_notice_days
            deposit.due_soon = bool(deposit.state == 'open' and deposit.date_end
                                    and deposit.date_end - timedelta(days=notice) <= today)

    def _l10n_pe_interest_until(self, date):
        """Interés devengado desde la apertura hasta ``date`` (sin pasar del
        vencimiento): capital × ((1 + TEA)^(días / base) − 1)."""
        self.ensure_one()
        if not self.rate or not date or not self.date_start:
            return 0.0
        end = min(date, self.date_end) if self.date_end else date
        days = max((end - self.date_start).days, 0)
        # El depósito a plazo no se libera en parte: su base es el capital (así
        # el interés del plazo sigue visible después de cancelarlo). En las
        # garantías, el saldo vigente.
        base = self.amount if self.deposit_type == 'term' else self.remaining_amount
        interest = base * ((1 + self.rate / 100.0) ** (days / int(self.day_basis)) - 1)
        return self.currency_id.round(interest)

    @api.constrains('date_start', 'date_end', 'deposit_type')
    def _check_dates(self):
        for deposit in self:
            if deposit.date_end and deposit.date_end <= deposit.date_start:
                raise ValidationError(self.env._('El vencimiento debe ser posterior a la apertura.'))
            if deposit.deposit_type == 'term' and not deposit.date_end:
                raise ValidationError(self.env._('Un depósito a plazo necesita plazo o vencimiento.'))

    # ------------------------------------------------------------------
    # Asientos
    # ------------------------------------------------------------------
    def _line_vals(self, date, account, amount_currency, name, partner=False):
        """Apunte en la moneda del depósito con su contravalor a la fecha."""
        company = self.company_id
        return {
            'name': name,
            'account_id': account.id,
            'partner_id': partner.id if partner else False,
            'currency_id': self.currency_id.id,
            'amount_currency': amount_currency,
            'balance': self.currency_id._convert(amount_currency, company.currency_id, company, date),
        }

    def _post_move(self, journal, date, ref, lines):
        """Crea y publica el asiento; el céntimo de conversión va al primer apunte."""
        lines = [vals for vals in lines if not self.currency_id.is_zero(vals['amount_currency'])]
        if not lines:
            return self.env['account.move']
        difference = self.company_id.currency_id.round(sum(vals['balance'] for vals in lines))
        if difference:
            lines[0]['balance'] -= difference
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': journal.id, 'date': date, 'ref': ref,
            'line_ids': [(0, 0, vals) for vals in lines],
        })
        move.action_post()
        self.move_ids = [(4, move.id)]
        return move

    def _bank_account(self):
        account = self.journal_id.default_account_id
        if not account:
            raise UserError(self.env._('El diario %s no tiene cuenta.', self.journal_id.display_name))
        return account

    def _check_accounts(self):
        self.ensure_one()
        if not (self.deposit_account_id and self.interest_account_id and self.income_account_id):
            raise UserError(self.env._(
                'Configure las cuentas de «%s» en Perú ▸ Configuración ▸ Cuentas de la '
                'localización ▸ Depósitos y garantías.', dict(DEPOSIT_TYPES)[self.deposit_type]))

    # ------------------------------------------------------------------
    # Apertura
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('l10n_pe.term.deposit') or '/'
        return super().create(vals_list)

    def action_open(self):
        """Saca el dinero del banco a la cuenta del depósito."""
        for deposit in self:
            if deposit.state != 'draft':
                raise UserError(self.env._('Solo se abre un depósito en borrador.'))
            if deposit.currency_id.compare_amounts(deposit.amount, 0.0) <= 0:
                raise UserError(self.env._('Indique el capital.'))
            deposit._check_accounts()
            label = self.env._('Apertura %(name)s %(type)s', name=deposit.name,
                               type=dict(DEPOSIT_TYPES)[deposit.deposit_type])
            deposit._post_move(deposit.journal_id, deposit.date_start, label, [
                deposit._line_vals(deposit.date_start, deposit.deposit_account_id, deposit.amount, label,
                                   partner=deposit.partner_id),
                deposit._line_vals(deposit.date_start, deposit._bank_account(), -deposit.amount, label),
            ])
            deposit.state = 'open'
        return True

    def unlink(self):
        if self.filtered(lambda d: d.state != 'draft'):
            raise UserError(self.env._('Solo se eliminan depósitos en borrador.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Intereses
    # ------------------------------------------------------------------
    def _l10n_pe_accrue(self, date):
        """Devenga los intereses hasta ``date``: lo que falta entre lo ya
        devengado y el interés acumulado a esa fecha. Idempotente."""
        moves = self.env['account.move']
        for deposit in self.filtered(lambda d: d.state in ('open', 'expired') and d.rate):
            date_move = min(date, deposit.date_end) if deposit.date_end else date
            if date_move <= deposit.date_start:
                continue
            pending = deposit.currency_id.round(
                deposit._l10n_pe_interest_until(date_move) - deposit.interest_accrued)
            if deposit.currency_id.compare_amounts(pending, 0.0) <= 0:
                continue
            label = self.env._('Intereses %(name)s al %(date)s', name=deposit.name, date=date_move)
            moves |= deposit._post_move(deposit.misc_journal_id, date_move, label, [
                deposit._line_vals(date_move, deposit.interest_account_id, pending, label,
                                   partner=deposit.partner_id),
                deposit._line_vals(date_move, deposit.income_account_id, -pending, label),
            ])
            deposit.interest_accrued += pending
        return moves

    def action_accrue(self):
        self._l10n_pe_accrue(fields.Date.context_today(self))
        return True

    def _l10n_pe_interest_pending(self):
        """Intereses devengados que aún no se cobran (saldo de la 1631)."""
        self.ensure_one()
        return self.currency_id.round(self.interest_accrued - self.interest_collected)

    # ------------------------------------------------------------------
    # Asistente
    # ------------------------------------------------------------------
    def _open_wizard(self, operation):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': dict(self.env['l10n_pe.term.deposit.wizard']._fields['operation'].selection)[operation],
            'res_model': 'l10n_pe.term.deposit.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_deposit_id': self.id, 'default_operation': operation},
        }

    def action_close(self):
        return self._open_wizard('close')

    def action_renew(self):
        return self._open_wizard('renew')

    def action_release(self):
        return self._open_wizard('release')

    def action_open_moves(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Asientos'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.move_ids.ids)],
            'context': {'create': False},
        }

    # ------------------------------------------------------------------
    # Operaciones (las usan el asistente y el cron)
    # ------------------------------------------------------------------
    def _l10n_pe_close(self, date, interest_received=None):
        """Cancela el depósito: vuelve al banco el saldo de capital y los
        intereses. La diferencia con lo devengado ajusta el ingreso."""
        self.ensure_one()
        self._l10n_pe_accrue(date)
        pending = self._l10n_pe_interest_pending()
        received = pending if interest_received is None else interest_received
        capital = self.remaining_amount
        label = self.env._('Cancelación %s', self.name)
        lines = [
            self._line_vals(date, self._bank_account(), self.remaining_amount + received, label),
            self._line_vals(date, self.deposit_account_id, -self.remaining_amount, label, partner=self.partner_id),
            self._line_vals(date, self.interest_account_id, -pending, label, partner=self.partner_id),
            self._line_vals(date, self.income_account_id, pending - received,
                            self.env._('Ajuste de intereses %s', self.name)),
        ]
        self._post_move(self.journal_id, date, label, lines)
        self.write({'interest_collected': self.interest_collected + pending,
                    'released_amount': self.amount, 'state': 'closed'})
        self.activity_ids.action_done()
        self.message_post(body=self.env._('Depósito cancelado: capital %(capital)s e intereses %(interest)s.',
                                          capital=capital, interest=received))
        return True

    def _l10n_pe_renew(self, date, term_days=None, rate=None, capitalize=None):
        """Renueva el depósito: uno nuevo desde ``date`` con el capital (más
        los intereses si se capitalizan); si no se capitalizan, los intereses
        van al banco."""
        self.ensure_one()
        if self.deposit_type != 'term':
            raise UserError(self.env._('Solo se renuevan los depósitos a plazo.'))
        self._l10n_pe_accrue(date)
        capitalize = self.capitalize_interest if capitalize is None else capitalize
        pending = self._l10n_pe_interest_pending()
        new_capital = self.remaining_amount + (pending if capitalize else 0.0)
        term_days = term_days or self.term_days
        new = self.copy({
            'date_start': date, 'amount': new_capital, 'term_days': term_days,
            'date_end': date + timedelta(days=term_days), 'rate': self.rate if rate is None else rate,
            'renewed_from_id': self.id, 'reference': self.reference,
        })
        label = self.env._('Renovación %(old)s en %(new)s', old=self.name, new=new.name)
        lines = [
            self._line_vals(date, new.deposit_account_id, new_capital, label, partner=new.partner_id),
            self._line_vals(date, self.deposit_account_id, -self.remaining_amount, label, partner=self.partner_id),
            self._line_vals(date, self.interest_account_id, -pending, label, partner=self.partner_id),
        ]
        if not capitalize:
            lines.insert(0, self._line_vals(date, self._bank_account(), pending, label))
        move = self._post_move(self.journal_id, date, label, lines)
        new.write({'state': 'open', 'move_ids': [(4, move.id)]})
        self.write({'interest_collected': self.interest_collected + pending, 'released_amount': self.amount,
                    'state': 'renewed', 'renewal_id': new.id})
        self.activity_ids.action_done()
        self.message_post(body=self.env._('Renovado en %s.', new._get_html_link()))
        return new

    def _l10n_pe_release(self, date, amount):
        """Libera capital de una garantía (total o parcial); al liberar todo
        se cobran también los intereses devengados y se cierra."""
        self.ensure_one()
        if self.deposit_type not in GUARANTEES:
            raise UserError(self.env._('Solo se liberan las garantías: un depósito a plazo se cancela o se renueva.'))
        if self.currency_id.compare_amounts(amount, 0.0) <= 0 or \
                self.currency_id.compare_amounts(amount, self.remaining_amount) > 0:
            raise UserError(self.env._('El importe a liberar debe ser mayor que cero y no superar el saldo (%s).',
                                       self.remaining_amount))
        if self.currency_id.compare_amounts(amount, self.remaining_amount) == 0:
            return self._l10n_pe_close(date)
        label = self.env._('Liberación parcial %s', self.name)
        self._l10n_pe_accrue(date)
        self._post_move(self.journal_id, date, label, [
            self._line_vals(date, self._bank_account(), amount, label),
            self._line_vals(date, self.deposit_account_id, -amount, label, partner=self.partner_id),
        ])
        self.released_amount += amount
        return True

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_l10n_pe_term_deposits(self):
        """Diario e idempotente: devenga los intereses al cierre del mes
        anterior, vence (o renueva) los depósitos y avisa antes del vencimiento."""
        today = fields.Date.context_today(self)
        month_end = today.replace(day=1) - relativedelta(days=1)
        for company in self.env['res.company'].search([]):
            deposits = self.with_company(company).search([
                ('company_id', '=', company.id), ('state', 'in', ('open', 'expired'))])
            deposits._l10n_pe_accrue(month_end)
            for deposit in deposits.filtered(lambda d: d.state == 'open' and d.date_end and d.date_end <= today):
                if deposit.auto_renew and deposit.deposit_type == 'term':
                    deposit._l10n_pe_renew(deposit.date_end)
                else:
                    deposit._l10n_pe_accrue(deposit.date_end)
                    deposit.state = 'expired'
            notice = company.l10n_pe_term_deposit_notice_days
            for deposit in deposits.filtered(lambda d: d.state == 'open' and not d.notice_sent and d.date_end
                                             and d.date_end - timedelta(days=notice) <= today):
                deposit.activity_schedule(
                    'mail.mail_activity_data_todo', date_deadline=deposit.date_end,
                    summary=self.env._('Vence %s', deposit.name),
                    note=self.env._('Vence el %(date)s: cancele, renueve o libere.', date=deposit.date_end),
                    user_id=(deposit.user_id or self.env.user).id)
                deposit.notice_sent = True
        return True
