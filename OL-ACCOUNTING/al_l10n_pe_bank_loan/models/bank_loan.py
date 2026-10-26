# -*- coding: utf-8 -*-
"""Préstamos y pagarés bancarios.

Ciclo y asientos (cuentas por tipo y moneda, PCGE por defecto):

=====================  ==========================================  ============================
Paso                   Debe                                        Haber
=====================  ==========================================  ============================
Desembolso             Banco (cobros pendientes), 6391 gastos      4511 capital
Devengo mensual        67311 intereses                             45511 intereses por pagar
Pago de la cuota       4511 capital, 45511 devengado, 67311 resto, Banco (pagos pendientes)
                       651 seguro, 6391 comisión
Gracia total           45511 devengado, 67311 resto                4511 (intereses capitalizados)
Prepago                4511 capital, 45511 / 67311 intereses       Banco (pagos pendientes)
=====================  ==========================================  ============================

Los movimientos de banco van a la cuenta de pendientes del diario para
conciliarlos con el extracto, como un pago de Odoo.
"""
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools.schedule import build_schedule, due_dates, irr_annual
from .bank_loan_account_config import LOAN_TYPES

STATES = [
    ('draft', 'Borrador'),
    ('running', 'Vigente'),
    ('paid', 'Cancelado'),
    ('cancel', 'Anulado'),
]
METHODS = [
    ('french', 'Francés (cuota fija)'),
    ('german', 'Alemán (amortización constante)'),
    ('bullet', 'Al vencimiento (solo intereses)'),
]
FREQUENCIES = [('1', 'Mensual'), ('2', 'Bimestral'), ('3', 'Trimestral'), ('6', 'Semestral'), ('12', 'Anual')]
GRACE_TYPES = [('none', 'Sin gracia'), ('partial', 'Parcial (solo intereses)'),
               ('total', 'Total (intereses capitalizados)')]
DAY_BASES = [('360', '360 días'), ('365', '365 días')]


class L10nPeBankLoan(models.Model):
    _name = 'l10n_pe.bank.loan'
    _description = 'Préstamo bancario'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'date_disbursement desc, id desc'

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    state = fields.Selection(STATES, string='Estado', default='draft', required=True, readonly=True,
                             copy=False, tracking=True)
    loan_type = fields.Selection(LOAN_TYPES, string='Tipo', required=True, default='loan', tracking=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda de la compañía')
    partner_id = fields.Many2one('res.partner', string='Banco', required=True, check_company=True, tracking=True)
    reference = fields.Char(string='N.º de operación', tracking=True,
                            help='Número del préstamo o del pagaré en el banco.')
    purpose = fields.Char(string='Destino', help='Para qué se usa el dinero (capital de trabajo, activo fijo…).')
    credit_line_id = fields.Many2one(
        'l10n_pe.treasury.credit.line', string='Línea de crédito', check_company=True,
        domain="[('partner_id', '=', partner_id), ('line_type', 'in', ('global', 'loan'))]")
    user_id = fields.Many2one('res.users', string='Responsable', default=lambda self: self.env.user,
                              help='Recibe el aviso antes de cada vencimiento.')
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                  default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary(string='Capital', required=True, tracking=True)
    rate = fields.Float(string='TEA (%)', digits=(6, 4), required=True, tracking=True,
                        help='Tasa efectiva anual del préstamo.')
    day_basis = fields.Selection(DAY_BASES, string='Base de días', required=True, default='360')
    method = fields.Selection(METHODS, string='Amortización', required=True, default='french')
    frequency = fields.Selection(FREQUENCIES, string='Frecuencia', required=True, default='1')
    installment_count = fields.Integer(string='N.º de cuotas', required=True, default=12)
    grace_type = fields.Selection(GRACE_TYPES, string='Periodo de gracia', required=True, default='none')
    grace_count = fields.Integer(string='Cuotas de gracia')
    date_disbursement = fields.Date(string='Desembolso', required=True, default=fields.Date.context_today,
                                    tracking=True)
    date_first_due = fields.Date(string='Primer vencimiento', compute='_compute_date_first_due', store=True,
                                 readonly=False)
    insurance_rate = fields.Float(string='Desgravamen (% mensual)', digits=(6, 4),
                                  help='Tasa mensual del seguro de desgravamen sobre el saldo de capital.')
    fee_amount = fields.Monetary(string='Comisión por cuota', help='Portes, envío de estado de cuenta, etc.')
    disbursement_fee = fields.Monetary(string='Gastos de desembolso',
                                       help='Comisión de estructuración, tasación, notaría… que el banco descuenta.')
    journal_id = fields.Many2one('account.journal', string='Banco de la empresa', required=True, check_company=True,
                                 domain="[('type', '=', 'bank')]",
                                 help='Cuenta en la que entra el desembolso y de la que salen las cuotas.')
    misc_journal_id = fields.Many2one(
        'account.journal', string='Diario de intereses', required=True, check_company=True,
        domain="[('type', '=', 'general')]",
        default=lambda self: self.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', self.env.company.id)], limit=1),
        help='Diario del devengo mensual de intereses y de la capitalización.')
    principal_account_id = fields.Many2one('account.account', string='Capital adeudado', check_company=True,
                                           compute='_compute_accounts', store=True, readonly=False)
    interest_payable_account_id = fields.Many2one('account.account', string='Intereses por pagar',
                                                  check_company=True, compute='_compute_accounts', store=True,
                                                  readonly=False)
    interest_expense_account_id = fields.Many2one('account.account', string='Gasto por intereses',
                                                  check_company=True, compute='_compute_accounts', store=True,
                                                  readonly=False)
    insurance_account_id = fields.Many2one('account.account', string='Seguro', check_company=True,
                                           compute='_compute_accounts', store=True, readonly=False)
    fee_account_id = fields.Many2one('account.account', string='Comisiones', check_company=True,
                                     compute='_compute_accounts', store=True, readonly=False)
    itf_applies = fields.Boolean(string='Afecto al ITF',
                                 help='Registra el ITF del desembolso y de cada pago (Ley 28194).')
    line_ids = fields.One2many('l10n_pe.bank.loan.line', 'loan_id', string='Cronograma', copy=False)
    move_ids = fields.Many2many('account.move', string='Asientos', readonly=True, copy=False)
    move_count = fields.Integer(string='N.º de asientos', compute='_compute_move_count')
    prepaid_amount = fields.Monetary(string='Capital prepagado', readonly=True, copy=False)
    principal_balance = fields.Monetary(string='Saldo de capital', compute='_compute_balances', store=True)
    current_portion = fields.Monetary(string='Porción corriente', compute='_compute_portions',
                                      help='Capital que vence en los próximos 12 meses.')
    non_current_portion = fields.Monetary(string='Porción no corriente', compute='_compute_portions')
    interest_total = fields.Monetary(string='Intereses del cronograma', compute='_compute_totals')
    installment_amount = fields.Monetary(string='Cuota', compute='_compute_totals',
                                         help='Primera cuota después del periodo de gracia.')
    tcea = fields.Float(string='TCEA (%)', digits=(6, 2), compute='_compute_totals',
                        help='Tasa de costo efectivo anual: intereses, seguro, comisiones y gastos de desembolso.')
    next_due_date = fields.Date(string='Próximo vencimiento', compute='_compute_next', store=True)
    next_amount = fields.Monetary(string='Próxima cuota', compute='_compute_next', store=True)
    paid_count = fields.Integer(string='Cuotas pagadas', compute='_compute_next', store=True)
    fx_warning = fields.Char(string='Aviso de diferencia de cambio', compute='_compute_fx_warning')
    notes = fields.Html(string='Notas')

    _positive_amount = models.Constraint('CHECK(amount > 0)', 'El capital debe ser mayor que cero.')
    _positive_count = models.Constraint('CHECK(installment_count > 0)', 'Indique el número de cuotas.')

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------
    @api.depends('date_disbursement', 'frequency')
    def _compute_date_first_due(self):
        for loan in self:
            if loan.date_disbursement and not (loan.state != 'draft' and loan.date_first_due):
                loan.date_first_due = loan.date_disbursement + relativedelta(months=int(loan.frequency or 1))

    @api.depends('loan_type', 'currency_id', 'company_id')
    def _compute_accounts(self):
        Config = self.env['l10n_pe.bank.loan.account.config']
        for loan in self:
            if loan.state not in ('draft', False) and loan.principal_account_id:
                continue
            config = Config._l10n_pe_get(loan.company_id, loan.loan_type, loan.currency_id)
            loan.principal_account_id = config.principal_account_id
            loan.interest_payable_account_id = config.interest_payable_account_id
            loan.interest_expense_account_id = config.interest_expense_account_id
            loan.insurance_account_id = config.insurance_account_id
            loan.fee_account_id = config.fee_account_id

    def _compute_move_count(self):
        for loan in self:
            loan.move_count = len(loan.move_ids)

    @api.depends('state', 'amount', 'line_ids.state', 'line_ids.balance_start', 'line_ids.principal',
                 'line_ids.date_due')
    def _compute_balances(self):
        for loan in self:
            pending = loan.line_ids.filtered(lambda l: l.state == 'pending').sorted('date_due')
            if loan.state == 'draft':
                balance = loan.amount
            elif loan.state == 'running':
                balance = pending[:1].balance_start if pending else 0.0
            else:
                balance = 0.0
            loan.principal_balance = balance

    def _compute_portions(self):
        limit = fields.Date.context_today(self) + relativedelta(months=12)
        for loan in self:
            pending = loan.line_ids.filtered(lambda l: l.state == 'pending')
            current = sum(pending.filtered(lambda l: l.date_due <= limit).mapped('principal')) \
                if loan.state == 'running' else 0.0
            loan.current_portion = min(current, loan.principal_balance)
            loan.non_current_portion = loan.principal_balance - loan.current_portion

    @api.depends('line_ids.interest', 'line_ids.amount_total', 'line_ids.grace', 'disbursement_fee',
                 'date_disbursement', 'amount', 'day_basis')
    def _compute_totals(self):
        for loan in self:
            lines = loan.line_ids.sorted('date_due')
            loan.interest_total = sum(lines.mapped('interest')) + sum(lines.mapped('capitalized'))
            regular = lines.filtered(lambda l: not l.grace)
            loan.installment_amount = regular[:1].amount_total
            tcea = None
            if lines and loan.date_disbursement:
                flows = [(0, loan.amount - loan.disbursement_fee)] + [
                    ((line.date_due - loan.date_disbursement).days, -line.amount_total) for line in lines]
                tcea = irr_annual(flows, basis=int(loan.day_basis))
            loan.tcea = tcea * 100.0 if tcea is not None else 0.0

    @api.depends('line_ids.state', 'line_ids.date_due', 'line_ids.amount_total')
    def _compute_next(self):
        for loan in self:
            pending = loan.line_ids.filtered(lambda l: l.state == 'pending').sorted('date_due')
            loan.next_due_date = pending[:1].date_due
            loan.next_amount = pending[:1].amount_total
            loan.paid_count = len(loan.line_ids.filtered(lambda l: l.state == 'paid'))

    @api.depends('currency_id', 'company_id', 'principal_account_id', 'interest_payable_account_id')
    def _compute_fx_warning(self):
        # Como en los depósitos: la diferencia de cambio la ajusta el cierre de
        # T.C. de la suite sobre las cuentas marcadas; aquí solo se avisa.
        Account = self.env['account.account']
        for loan in self:
            message = False
            if loan.currency_id and loan.currency_id != loan.company_id.currency_id \
                    and 'l10n_pe_exchange_closing' in Account._fields:
                unmarked = (loan.principal_account_id | loan.interest_payable_account_id).filtered(
                    lambda a: not a.l10n_pe_exchange_closing)
                if unmarked:
                    message = self.env._(
                        'Préstamo en %(currency)s: marque %(accounts)s para el cierre de tipo de cambio '
                        '(Contabilidad ▸ Plan contable) para ajustar su saldo al cierre de mes.',
                        currency=loan.currency_id.name, accounts=', '.join(unmarked.mapped('code')))
            loan.fx_warning = message

    @api.constrains('grace_count', 'installment_count', 'grace_type')
    def _check_grace(self):
        for loan in self:
            if loan.grace_type != 'none' and not (0 < loan.grace_count < loan.installment_count):
                raise ValidationError(self.env._('Las cuotas de gracia deben ser menos que el total de cuotas.'))

    @api.constrains('date_first_due', 'date_disbursement')
    def _check_dates(self):
        for loan in self:
            if loan.date_first_due and loan.date_first_due <= loan.date_disbursement:
                raise ValidationError(self.env._('El primer vencimiento debe ser posterior al desembolso.'))

    # ------------------------------------------------------------------
    # Cronograma
    # ------------------------------------------------------------------
    def _l10n_pe_schedule_values(self, principal, start, dates, fixed_installment=None, grace=True):
        self.ensure_one()
        return build_schedule(
            principal, self.rate, int(self.day_basis), start, dates, method=self.method,
            grace_count=self.grace_count if grace else 0, grace_type=self.grace_type if grace else 'none',
            insurance_rate=self.insurance_rate, fee=self.fee_amount, months=int(self.frequency),
            rounding=self.currency_id.decimal_places, fixed_installment=fixed_installment)

    def _l10n_pe_line_vals(self, values, sequence_start=1):
        return [{
            'loan_id': self.id, 'sequence': sequence_start + index, 'date_start': vals['date_start'],
            'date_due': vals['date_due'],
            'balance_start': vals['balance_start'], 'principal': vals['principal'], 'interest': vals['interest'],
            'capitalized': vals.get('capitalized', 0.0), 'insurance': vals['insurance'], 'fee': vals['fee'],
            'balance_end': vals['balance_end'], 'grace': vals['grace'],
        } for index, vals in enumerate(values)]

    def action_compute_schedule(self):
        for loan in self:
            if loan.state != 'draft':
                raise UserError(self.env._('El cronograma solo se calcula en borrador; use el prepago para cambiarlo.'))
            dates = due_dates(loan.date_first_due, loan.installment_count, int(loan.frequency))
            values = loan._l10n_pe_schedule_values(loan.amount, loan.date_disbursement, dates)
            loan.line_ids.unlink()
            self.env['l10n_pe.bank.loan.line'].create(loan._l10n_pe_line_vals(values))
        return True

    # ------------------------------------------------------------------
    # Asientos
    # ------------------------------------------------------------------
    def _line(self, date, account, amount_currency, name, partner=True):
        """Apunte en la moneda del préstamo con su contravalor a la fecha."""
        company = self.company_id
        return {
            'name': name,
            'account_id': account.id,
            'partner_id': self.partner_id.id if partner else False,
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
            'l10n_pe_bank_loan_id': self.id,
            'line_ids': [fields.Command.create(vals) for vals in lines],
        })
        move.action_post()
        self.move_ids = [fields.Command.link(move.id)]
        return move

    def _l10n_pe_itf_lines(self, date, amount, label, direction):
        """ITF del movimiento de banco: gasto contra la cuenta de pendientes."""
        self.ensure_one()
        if not self.itf_applies:
            return []
        from odoo.addons.al_l10n_pe_itf.models.res_company import itf_amount
        itf = itf_amount(amount, self.company_id.root_id.l10n_pe_itf_rate)
        if not itf:
            return []
        account = self.company_id._l10n_pe_itf_account()
        if not account:
            raise UserError(self.env._('Indique la cuenta del ITF en Ajustes ▸ Perú ▸ ITF.'))
        bank = self.journal_id._l10n_pe_treasury_outstanding_account(direction)
        name = self.env._('ITF %s', label)
        return [self._line(date, account, itf, name, partner=False), self._line(date, bank, -itf, name, partner=False)]

    def _check_accounts(self):
        self.ensure_one()
        if not (self.principal_account_id and self.interest_payable_account_id and self.interest_expense_account_id):
            raise UserError(self.env._(
                'Configure las cuentas de «%s» en Perú ▸ Configuración ▸ Cuentas de la localización ▸ '
                'Préstamos bancarios.', dict(LOAN_TYPES)[self.loan_type]))

    # ------------------------------------------------------------------
    # Desembolso
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('l10n_pe.bank.loan') or '/'
        return super().create(vals_list)

    def unlink(self):
        if self.filtered(lambda l: l.state not in ('draft', 'cancel')):
            raise UserError(self.env._('Solo se eliminan préstamos en borrador o anulados.'))
        return super().unlink()

    def action_confirm(self):
        """Registra el desembolso: entra el dinero al banco y nace la deuda."""
        for loan in self:
            if loan.state != 'draft':
                raise UserError(self.env._('Solo se desembolsa un préstamo en borrador.'))
            loan._check_accounts()
            if not loan.line_ids:
                loan.action_compute_schedule()
            schedule_principal = loan.currency_id.round(
                sum(loan.line_ids.mapped('principal')) - sum(loan.line_ids.mapped('capitalized')))
            if loan.currency_id.compare_amounts(schedule_principal, loan.amount) != 0:
                raise UserError(self.env._(
                    'El capital del cronograma (%(schedule)s) no coincide con el del préstamo (%(amount)s).',
                    schedule=schedule_principal, amount=loan.amount))
            if loan.credit_line_id:
                line = loan.credit_line_id
                if line.currency_id.compare_amounts(
                        line.amount_available, line._l10n_pe_convert(loan.amount, loan.currency_id)) < 0:
                    raise UserError(self.env._('El préstamo supera el disponible de la línea %(line)s (%(available)s).',
                                               line=line.name, available=line.amount_available))
            date = loan.date_disbursement
            label = self.env._('Desembolso %(name)s %(bank)s', name=loan.name, bank=loan.partner_id.name)
            bank = loan.journal_id._l10n_pe_treasury_outstanding_account('inbound')
            lines = [
                loan._line(date, bank, loan.amount - loan.disbursement_fee, label, partner=False),
                loan._line(date, loan.principal_account_id, -loan.amount, label),
            ]
            if loan.disbursement_fee:
                if not loan.fee_account_id:
                    raise UserError(self.env._('Indique la cuenta de comisiones del préstamo.'))
                lines.append(loan._line(date, loan.fee_account_id, loan.disbursement_fee,
                                        self.env._('Gastos de desembolso %s', loan.name)))
            lines += loan._l10n_pe_itf_lines(date, loan.amount - loan.disbursement_fee, label, 'inbound')
            loan._post_move(loan.journal_id, date, label, lines)
            loan.state = 'running'
            loan.message_post(body=self.env._('Desembolsado: %(amount)s %(currency)s.', amount=loan.amount,
                                              currency=loan.currency_id.name))
        return True

    def action_cancel(self):
        for loan in self:
            if loan.state == 'running' and loan.line_ids.filtered(lambda l: l.state == 'paid'):
                raise UserError(self.env._('No se anula un préstamo con cuotas pagadas.'))
            posted = loan.move_ids.filtered(lambda m: m.state == 'posted')
            if posted:
                reversals = posted._reverse_moves(cancel=True)
                loan.move_ids = [fields.Command.link(move.id) for move in reversals]
            loan.line_ids.write({'interest_accrued': 0.0})
            loan.state = 'cancel'
            loan.activity_ids.unlink()
        return True

    def action_draft(self):
        for loan in self.filtered(lambda l: l.state == 'cancel'):
            loan.write({'state': 'draft', 'move_ids': [fields.Command.clear()]})
        return True

    # ------------------------------------------------------------------
    # Intereses
    # ------------------------------------------------------------------
    def _l10n_pe_accrue(self, date):
        """Devenga hasta ``date`` el interés de las cuotas pendientes (lineal por
        días dentro de cada periodo); idempotente."""
        moves = self.env['account.move']
        for loan in self.filtered(lambda l: l.state == 'running'):
            label = self.env._('Intereses %(name)s al %(date)s', name=loan.name, date=date)
            amounts = {}
            for line in loan.line_ids.filtered(lambda l: l.state == 'pending'):
                pending = line.currency_id.round(line._l10n_pe_interest_until(date) - line.interest_accrued)
                if line.currency_id.compare_amounts(pending, 0.0) > 0:
                    amounts[line] = pending
            total = sum(amounts.values())
            if not total:
                continue
            moves |= loan._post_move(loan.misc_journal_id, date, label, [
                loan._line(date, loan.interest_expense_account_id, total, label),
                loan._line(date, loan.interest_payable_account_id, -total, label),
            ])
            for line, pending in amounts.items():
                line.interest_accrued += pending
        return moves

    def action_accrue(self):
        self._l10n_pe_accrue(fields.Date.context_today(self))
        return True

    # ------------------------------------------------------------------
    # Pago de cuota y prepago
    # ------------------------------------------------------------------
    def _l10n_pe_first_pending(self):
        self.ensure_one()
        return self.line_ids.filtered(lambda l: l.state == 'pending').sorted('date_due')[:1]

    def _l10n_pe_interest_lines(self, date, line, interest, label):
        """Interés pagado: primero cancela lo devengado (45511) y la diferencia va
        al gasto (67311), en el sentido que corresponda."""
        accrued = line.interest_accrued
        result = []
        if accrued:
            result.append(self._line(date, self.interest_payable_account_id, accrued, label))
        if not self.currency_id.is_zero(interest - accrued):
            result.append(self._line(date, self.interest_expense_account_id, interest - accrued, label))
        return result

    def write(self, vals):
        res = super().write(vals)
        if {'state', 'credit_line_id', 'line_ids'} & set(vals):
            self.credit_line_id._l10n_pe_invalidate_usage()
        return res

    def _l10n_pe_pay_line(self, line, date, interest=None, insurance=None, fee=None):
        """Paga la cuota ``line`` (la más antigua pendiente)."""
        self.ensure_one()
        if self.state != 'running' or line.state != 'pending' or line != self._l10n_pe_first_pending():
            raise UserError(self.env._('Pague las cuotas en orden: la siguiente es la %s.',
                                       self._l10n_pe_first_pending().sequence))
        self._l10n_pe_accrue(min(date, line.date_due))
        interest = line.interest if interest is None else interest
        insurance = line.insurance if insurance is None else insurance
        fee = line.fee if fee is None else fee
        label = self.env._('Cuota %(seq)s %(name)s', seq=line.sequence, name=self.name)
        if line.grace and line.capitalized:
            # Gracia total: no sale dinero, el interés se suma al capital.
            lines = self._l10n_pe_interest_lines(date, line, line.capitalized, label) + [
                self._line(date, self.principal_account_id, -line.capitalized, label)]
            move = self._post_move(self.misc_journal_id, date, label, lines)
            total = 0.0
        else:
            total = line.principal + interest + insurance + fee
            bank = self.journal_id._l10n_pe_treasury_outstanding_account('outbound')
            lines = [self._line(date, self.principal_account_id, line.principal, label)]
            lines += self._l10n_pe_interest_lines(date, line, interest, label)
            if insurance:
                lines.append(self._line(date, self.insurance_account_id or self.interest_expense_account_id,
                                        insurance, self.env._('Desgravamen %s', label)))
            if fee:
                lines.append(self._line(date, self.fee_account_id or self.interest_expense_account_id, fee,
                                        self.env._('Comisión %s', label)))
            lines.append(self._line(date, bank, -total, label, partner=False))
            lines += self._l10n_pe_itf_lines(date, total, label, 'outbound')
            move = self._post_move(self.journal_id, date, label, lines)
        line.write({'state': 'paid', 'move_id': move.id, 'paid_date': date, 'paid_amount': total,
                    'interest_paid': interest if not line.capitalized else 0.0, 'interest_accrued': 0.0})
        if not self._l10n_pe_first_pending():
            self.state = 'paid'
            self.activity_ids.action_done()
            self.message_post(body=self.env._('Préstamo cancelado.'))
        return move

    def _l10n_pe_prepay(self, date, amount, mode='installment'):
        """Prepago de capital en ``date``: paga ``amount`` de capital más los
        intereses corridos de la cuota en curso y rehace las cuotas pendientes
        (``installment``: misma cantidad de cuotas, cuota menor; ``term``: misma
        cuota, menos cuotas)."""
        self.ensure_one()
        current = self._l10n_pe_first_pending()
        if self.state != 'running' or not current:
            raise UserError(self.env._('Solo se prepaga un préstamo vigente con cuotas pendientes.'))
        if date < current.date_start or date > current.date_due:
            raise UserError(self.env._('La fecha del prepago debe estar dentro del periodo de la cuota %s.',
                                       current.sequence))
        balance = current.balance_start
        if self.currency_id.compare_amounts(amount, 0.0) <= 0 or self.currency_id.compare_amounts(amount, balance) > 0:
            raise UserError(self.env._('El prepago debe ser mayor que cero y no superar el saldo (%s).', balance))
        self._l10n_pe_accrue(date)
        interest = current._l10n_pe_interest_until(date)
        label = self.env._('Prepago %s', self.name)
        bank = self.journal_id._l10n_pe_treasury_outstanding_account('outbound')
        total = amount + interest
        lines = [self._line(date, self.principal_account_id, amount, label)]
        lines += self._l10n_pe_interest_lines(date, current, interest, label)
        lines.append(self._line(date, bank, -total, label, partner=False))
        lines += self._l10n_pe_itf_lines(date, total, label, 'outbound')
        move = self._post_move(self.journal_id, date, label, lines)
        pending = self.line_ids.filtered(lambda l: l.state == 'pending').sorted('date_due')
        old_installment = current.principal + current.interest
        dates = pending.mapped('date_due')
        sequence = current.sequence
        pending.unlink()
        new_balance = self.currency_id.round(balance - amount)
        if not self.currency_id.is_zero(new_balance):
            fixed = old_installment if mode == 'term' and self.method == 'french' else None
            values = self._l10n_pe_schedule_values(new_balance, date, dates, fixed_installment=fixed, grace=False)
            if mode == 'term' and self.method == 'german':
                step = current.principal
                values = []
                remaining = new_balance
                previous = date
                for due in dates:
                    if remaining <= 0:
                        break
                    part = min(step, remaining)
                    chunk = build_schedule(remaining, self.rate, int(self.day_basis), previous, [due],
                                           method='bullet', insurance_rate=self.insurance_rate,
                                           fee=self.fee_amount, months=int(self.frequency),
                                           rounding=self.currency_id.decimal_places)[0]
                    chunk.update({'principal': part, 'balance_end': self.currency_id.round(remaining - part)})
                    values.append(chunk)
                    remaining = self.currency_id.round(remaining - part)
                    previous = due
            self.env['l10n_pe.bank.loan.line'].create(self._l10n_pe_line_vals(values, sequence_start=sequence))
        self.write({'prepaid_amount': self.prepaid_amount + amount})
        self.message_post(body=self.env._('Prepago de %(amount)s %(currency)s el %(date)s.', amount=amount,
                                          currency=self.currency_id.name, date=date))
        if not self._l10n_pe_first_pending():
            self.state = 'paid'
            self.activity_ids.action_done()
        return move

    def _open_wizard(self, operation):
        self.ensure_one()
        line = self._l10n_pe_first_pending()
        return {
            'type': 'ir.actions.act_window',
            'name': dict(self.env['l10n_pe.bank.loan.payment']._fields['operation'].selection)[operation],
            'res_model': 'l10n_pe.bank.loan.payment',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_loan_id': self.id, 'default_operation': operation, 'default_line_id': line.id},
        }

    def action_pay_installment(self):
        return self._open_wizard('installment')

    def action_prepay(self):
        return self._open_wizard('prepay')

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
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_l10n_pe_bank_loans(self):
        """Diario: devenga al cierre del mes anterior, capitaliza las cuotas de
        gracia total vencidas y avisa antes de cada vencimiento."""
        today = fields.Date.context_today(self)
        month_end = today.replace(day=1) - relativedelta(days=1)
        for company in self.env['res.company'].search([]):
            loans = self.with_company(company).search([('company_id', '=', company.id), ('state', '=', 'running')])
            loans._l10n_pe_accrue(month_end)
            notice = company.l10n_pe_treasury_notice_days
            for loan in loans:
                while True:
                    line = loan._l10n_pe_first_pending()
                    if not (line and line.grace and line.capitalized and line.date_due <= today):
                        break
                    loan._l10n_pe_pay_line(line, line.date_due)
                line = loan._l10n_pe_first_pending()
                if line and not line.notice_sent and line.date_due - timedelta(days=notice) <= today:
                    loan.activity_schedule(
                        'mail.mail_activity_data_todo', date_deadline=line.date_due,
                        summary=self.env._('Cuota %(seq)s de %(name)s', seq=line.sequence, name=loan.name),
                        note=self.env._('Vence el %(date)s: %(amount)s %(currency)s.', date=line.date_due,
                                        amount=line.amount_total, currency=loan.currency_id.name),
                        user_id=(loan.user_id or self.env.user).id)
                    line.notice_sent = True
        return True


class L10nPeBankLoanLine(models.Model):
    _name = 'l10n_pe.bank.loan.line'
    _description = 'Cuota de préstamo bancario'
    _check_company_auto = True
    _order = 'loan_id, date_due, id'

    loan_id = fields.Many2one('l10n_pe.bank.loan', string='Préstamo', required=True, ondelete='cascade', index=True,
                              check_company=True)
    company_id = fields.Many2one(related='loan_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='loan_id.currency_id', store=True)
    partner_id = fields.Many2one(related='loan_id.partner_id', store=True, string='Banco')
    loan_state = fields.Selection(related='loan_id.state', store=True, string='Estado del préstamo')
    sequence = fields.Integer(string='N.º')
    date_start = fields.Date(string='Inicio del periodo', required=True,
                             help='Vencimiento anterior, el desembolso o la fecha del último prepago.')
    date_due = fields.Date(string='Vencimiento', required=True)
    days = fields.Integer(string='Días', compute='_compute_days', store=True)
    balance_start = fields.Monetary(string='Saldo inicial')
    principal = fields.Monetary(string='Amortización')
    interest = fields.Monetary(string='Interés')
    capitalized = fields.Monetary(string='Interés capitalizado', help='Gracia total: interés que se suma al capital.')
    insurance = fields.Monetary(string='Seguro')
    fee = fields.Monetary(string='Comisión')
    amount_total = fields.Monetary(string='Cuota', compute='_compute_amount_total', store=True)
    balance_end = fields.Monetary(string='Saldo final')
    grace = fields.Boolean(string='Gracia')
    state = fields.Selection([('pending', 'Pendiente'), ('paid', 'Pagada')], string='Estado', default='pending',
                             required=True)
    interest_accrued = fields.Monetary(string='Interés devengado', readonly=True, copy=False)
    interest_paid = fields.Monetary(string='Interés pagado', readonly=True, copy=False)
    paid_amount = fields.Monetary(string='Importe pagado', readonly=True, copy=False)
    paid_date = fields.Date(string='Fecha de pago', readonly=True, copy=False)
    move_id = fields.Many2one('account.move', string='Asiento', readonly=True, copy=False, check_company=True)
    notice_sent = fields.Boolean(string='Aviso enviado', readonly=True, copy=False)
    overdue = fields.Boolean(string='Vencida', compute='_compute_overdue')

    @api.depends('principal', 'interest', 'insurance', 'fee')
    def _compute_amount_total(self):
        for line in self:
            line.amount_total = line.principal + line.interest + line.insurance + line.fee

    @api.depends('date_start', 'date_due')
    def _compute_days(self):
        for line in self:
            line.days = (line.date_due - line.date_start).days if line.date_start and line.date_due else 0

    def _compute_overdue(self):
        today = fields.Date.context_today(self)
        for line in self:
            line.overdue = line.state == 'pending' and line.date_due < today

    def _l10n_pe_interest_until(self, date):
        """Interés de la cuota corrido hasta ``date`` (lineal por días; nunca más
        que el interés de la cuota)."""
        self.ensure_one()
        full = self.interest or self.capitalized
        if not full or not self.days or not date or date <= self.date_start:
            return 0.0
        elapsed = min((date - self.date_start).days, self.days)
        return self.currency_id.round(full * elapsed / self.days)
