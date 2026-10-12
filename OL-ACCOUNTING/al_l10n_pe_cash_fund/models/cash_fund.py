# -*- coding: utf-8 -*-
"""Fondos a cargo de un responsable: entregas a rendir y caja chica.

El dinero entregado se carga a una cuenta por cobrar al responsable (PCGE
1413 «Personal - Entregas a rendir cuenta»); las rendiciones la abonan con
los comprobantes que se pagaron con él y las planillas de movilidad; el
saldo se devuelve, se reembolsa o, en la caja chica, se repone.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

FUND_TYPES = [
    ('advance', 'Entrega a rendir'),
    ('petty_cash', 'Caja chica'),
]

FUND_STATES = [
    ('draft', 'Borrador'),
    ('approved', 'Aprobado'),
    ('open', 'Entregado'),
    ('closed', 'Cerrado'),
    ('cancel', 'Cancelado'),
]

# Movimientos de dinero del fondo (pagos de Odoo enlazados).
PAYMENT_KINDS = [
    ('delivery', 'Entrega'),
    ('replenishment', 'Reposición'),
    ('reimbursement', 'Reembolso'),
    ('return', 'Devolución'),
]
OUTBOUND_KINDS = ('delivery', 'replenishment', 'reimbursement')


class L10nPeCashFund(models.Model):
    _name = 'l10n_pe.cash.fund'
    _description = 'Entrega a rendir o caja chica'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', default='/', readonly=True, copy=False, tracking=True)
    fund_type = fields.Selection(
        FUND_TYPES, string='Tipo', required=True, default='advance', tracking=True,
        help='Entrega a rendir: dinero para un encargo, que se rinde y se cierra. Caja chica: '
             'fondo fijo que se rinde y se repone por lo gastado.')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True, tracking=True,
        default=lambda self: self.env.company.currency_id)
    partner_id = fields.Many2one(
        'res.partner', string='Responsable', required=True, tracking=True, check_company=True,
        help='Trabajador (su contacto) o tercero que recibe el dinero y lo rinde.')
    user_id = fields.Many2one(
        'res.users', string='Solicitado por', default=lambda self: self.env.user, tracking=True)
    purpose = fields.Char(string='Motivo', required=True, tracking=True)
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today,
                       tracking=True)
    date_due = fields.Date(
        string='Rendir hasta', tracking=True,
        help='Fecha límite para rendir; vencida, el fondo aparece en «Por rendir vencidas».')
    amount = fields.Monetary(
        string='Monto', required=True, tracking=True,
        help='Monto solicitado (entrega a rendir) o monto fijo del fondo (caja chica).')
    journal_id = fields.Many2one(
        'account.journal', string='Diario de pago', check_company=True, tracking=True,
        domain="[('type', 'in', ('bank', 'cash'))]",
        help='Banco o caja desde el que se entrega, repone o reembolsa el dinero.')
    account_id = fields.Many2one(
        'account.account', string='Cuenta del fondo', required=True, check_company=True,
        compute='_compute_account_id', store=True, readonly=False, precompute=True,
        domain="[('reconcile', '=', True)]", tracking=True,
        help='Cuenta por cobrar al responsable (conciliable); por defecto la de Ajustes.')
    state = fields.Selection(FUND_STATES, string='Estado', default='draft', required=True,
                             tracking=True, copy=False)
    note = fields.Html(string='Notas')

    payment_ids = fields.One2many('account.payment', 'l10n_pe_cash_fund_id', string='Pagos',
                                  readonly=True)
    settlement_ids = fields.One2many('l10n_pe.cash.settlement', 'fund_id', string='Rendiciones')
    payment_count = fields.Integer(compute='_compute_counts')
    settlement_count = fields.Integer(compute='_compute_counts')

    amount_delivered = fields.Monetary(
        string='Entregado', compute='_compute_amounts',
        help='Entregas, reposiciones y reembolsos confirmados.')
    amount_settled = fields.Monetary(string='Rendido', compute='_compute_amounts')
    amount_returned = fields.Monetary(string='Devuelto', compute='_compute_amounts')
    amount_balance = fields.Monetary(
        string='Saldo por rendir', compute='_compute_amounts',
        help='Positivo: dinero en poder del responsable. Negativo: gasto mayor que lo '
             'entregado, que la empresa le debe reembolsar.')
    is_overdue = fields.Boolean(string='Rendición vencida', compute='_compute_is_overdue',
                                search='_search_is_overdue')

    _amount_positive = models.Constraint('CHECK(amount > 0)', 'El monto debe ser mayor que cero.')

    @api.depends('fund_type', 'company_id')
    def _compute_account_id(self):
        for fund in self:
            fund.account_id = fund.company_id._l10n_pe_cash_fund_account(fund.fund_type)

    @api.depends('payment_ids', 'settlement_ids')
    def _compute_counts(self):
        for fund in self:
            fund.payment_count = len(fund.payment_ids)
            fund.settlement_count = len(fund.settlement_ids)

    @api.depends('payment_ids.state', 'payment_ids.amount', 'payment_ids.l10n_pe_cash_fund_kind',
                 'settlement_ids.state', 'settlement_ids.amount_total')
    def _compute_amounts(self):
        for fund in self:
            payments = fund.payment_ids.filtered(
                lambda p: p.state not in ('draft', 'canceled', 'rejected'))
            delivered = sum(payments.filtered(
                lambda p: p.l10n_pe_cash_fund_kind in OUTBOUND_KINDS).mapped('amount'))
            returned = sum(payments.filtered(
                lambda p: p.l10n_pe_cash_fund_kind == 'return').mapped('amount'))
            settled = sum(fund.settlement_ids.filtered(
                lambda s: s.state == 'posted').mapped('amount_total'))
            fund.amount_delivered = delivered
            fund.amount_returned = returned
            fund.amount_settled = settled
            fund.amount_balance = fund.currency_id.round(delivered - returned - settled)

    @api.depends('date_due', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for fund in self:
            fund.is_overdue = bool(fund.state == 'open' and fund.date_due and fund.date_due < today)

    def _search_is_overdue(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            return NotImplemented
        positive = (operator == '=') == value
        domain = [('state', '=', 'open'), ('date_due', '<', fields.Date.context_today(self))]
        return domain if positive else ['!', '&', *domain]

    @api.depends('name', 'partner_id', 'purpose')
    def _compute_display_name(self):
        for fund in self:
            fund.display_name = '%s · %s' % (fund.name, fund.partner_id.name or '') \
                if fund.name and fund.name != '/' else (fund.purpose or self.env._('Nuevo fondo'))

    # ------------------------------------------------------------------
    # Flujo
    # ------------------------------------------------------------------
    def _check_state(self, allowed):
        if any(fund.state not in allowed for fund in self):
            raise UserError(self.env._('La acción no está permitida en el estado actual del fondo.'))

    def action_approve(self):
        self._check_state(('draft',))
        for fund in self:
            if not fund.account_id.reconcile:
                raise UserError(self.env._(
                    'La cuenta %s del fondo debe ser conciliable.', fund.account_id.display_name))
            code = 'l10n_pe.cash.fund.%s' % fund.fund_type
            if fund.name in (False, '/'):
                fund.name = self.env['ir.sequence'].with_company(fund.company_id).next_by_code(
                    code, sequence_date=fund.date) or '/'
            fund.state = 'approved'

    def action_cancel(self):
        for fund in self:
            if fund.payment_ids.filtered(lambda p: p.state not in ('draft', 'canceled', 'rejected')) \
                    or fund.settlement_ids.filtered(lambda s: s.state == 'posted'):
                raise UserError(self.env._(
                    'El fondo %s ya tiene pagos o rendiciones confirmados: anúlelos antes.',
                    fund.display_name))
        self.payment_ids.filtered(lambda p: p.state == 'draft').action_cancel()
        self.state = 'cancel'

    def action_draft(self):
        self._check_state(('cancel', 'approved'))
        self.state = 'draft'

    def _prepare_payment_vals(self, kind, amount):
        self.ensure_one()
        if not self.journal_id:
            raise UserError(self.env._('Indique el diario de pago del fondo %s.', self.display_name))
        outbound = kind in OUTBOUND_KINDS
        labels = dict(PAYMENT_KINDS)
        return {
            'payment_type': 'outbound' if outbound else 'inbound',
            'partner_type': 'supplier' if outbound else 'customer',
            'partner_id': self.partner_id.id,
            'amount': amount,
            'currency_id': self.currency_id.id,
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
            'date': fields.Date.context_today(self),
            'memo': '%s %s · %s' % (labels[kind], self.name, self.purpose),
            'destination_account_id': self.account_id.id,
            'l10n_pe_cash_fund_id': self.id,
            'l10n_pe_cash_fund_kind': kind,
        }

    def _create_payment(self, kind, amount):
        """Pago en borrador enlazado al fondo, abierto para confirmarlo. Se crea
        con asiento (``force_payment_move``): la rendición concilia contra él
        aunque el diario no tenga cuentas de pagos pendientes."""
        self.ensure_one()
        if self.currency_id.compare_amounts(amount, 0.0) <= 0:
            raise UserError(self.env._('No hay importe que registrar.'))
        payment = self.env['account.payment'].with_context(force_payment_move=True).create(
            self._prepare_payment_vals(kind, amount))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'res_id': payment.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_deliver(self):
        """Entrega el monto aprobado (o abre la caja chica con su monto fijo)."""
        self._check_state(('approved',))
        self.ensure_one()
        self.state = 'open'
        return self._create_payment('delivery', self.amount)

    def action_replenish(self):
        """Caja chica: repone lo rendido para volver al monto fijo."""
        self._check_state(('open',))
        self.ensure_one()
        if self.fund_type != 'petty_cash':
            raise UserError(self.env._('Solo la caja chica se repone.'))
        return self._create_payment('replenishment', self.amount - self.amount_balance)

    def action_register_return(self):
        """El responsable devuelve el dinero no gastado."""
        self._check_state(('open',))
        self.ensure_one()
        return self._create_payment('return', self.amount_balance)

    def action_register_reimbursement(self):
        """La empresa reembolsa lo gastado de más."""
        self._check_state(('open',))
        self.ensure_one()
        return self._create_payment('reimbursement', -self.amount_balance)

    def action_close(self):
        self._check_state(('open',))
        for fund in self:
            if fund.settlement_ids.filtered(lambda s: s.state == 'draft'):
                raise UserError(self.env._(
                    'El fondo %s tiene rendiciones en borrador.', fund.display_name))
            if not fund.currency_id.is_zero(fund.amount_balance):
                raise UserError(self.env._(
                    'El fondo %(fund)s tiene un saldo de %(amount)s: registre la devolución o el '
                    'reembolso antes de cerrarlo.', fund=fund.display_name,
                    amount=fund.currency_id.format(fund.amount_balance)))
            if fund.payment_ids.filtered(lambda p: p.state == 'draft'):
                raise UserError(self.env._(
                    'El fondo %s tiene pagos en borrador: confírmelos o cancélelos.',
                    fund.display_name))
            fund._reconcile_fund_lines()
            fund.state = 'closed'

    def action_reopen(self):
        self._check_state(('closed',))
        self.state = 'open'

    # ------------------------------------------------------------------
    # Contabilidad
    # ------------------------------------------------------------------
    def _fund_move_lines(self):
        """Apuntes del fondo en su cuenta: los de sus pagos y rendiciones."""
        self.ensure_one()
        moves = self.payment_ids.filtered(
            lambda p: p.state not in ('draft', 'canceled', 'rejected')).move_id
        moves |= self.settlement_ids.filtered(lambda s: s.state == 'posted').move_id
        return moves.line_ids.filtered(
            lambda line: line.account_id == self.account_id and line.parent_state == 'posted')

    def _reconcile_fund_lines(self):
        """Concilia lo pendiente del fondo (entregas contra rendiciones y
        devoluciones); si no cuadra, la conciliación queda parcial."""
        for fund in self:
            lines = fund._fund_move_lines().filtered(lambda line: not line.reconciled)
            if lines.filtered(lambda l: l.balance > 0) and lines.filtered(lambda l: l.balance < 0):
                lines.reconcile()

    # ------------------------------------------------------------------
    # Botones inteligentes
    # ------------------------------------------------------------------
    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Pagos de %s', self.display_name),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('l10n_pe_cash_fund_id', '=', self.id)],
            'context': {'create': False},
        }

    def action_view_settlements(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Rendiciones de %s', self.display_name),
            'res_model': 'l10n_pe.cash.settlement',
            'view_mode': 'list,form',
            'domain': [('fund_id', '=', self.id)],
            'context': {'default_fund_id': self.id},
        }

    def action_new_settlement(self):
        self._check_state(('open',))
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_pe.cash.settlement',
            'view_mode': 'form',
            'context': {'default_fund_id': self.id},
        }
