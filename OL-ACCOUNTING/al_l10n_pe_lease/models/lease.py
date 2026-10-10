# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError

STATES = [
    ('draft', 'Borrador'),
    ('running', 'En curso'),
    ('exempt', 'Exento (gasto)'),
    ('closed', 'Terminado'),
    ('cancelled', 'Cancelado'),
]
TIMINGS = [
    ('advance', 'Al inicio del mes (adelantada)'),
    ('arrears', 'Al final del mes (vencida)'),
]
EXEMPTIONS = [
    ('none', 'No: aplica NIIF 16'),
    ('short_term', 'Corto plazo (12 meses o menos)'),
    ('low_value', 'Activo de bajo valor'),
]
# Cuentas del PCGE por defecto (se buscan por código en el plan de la compañía).
DEFAULT_ACCOUNTS = {
    'rou_account_id': '32331',              # Activo por derecho de uso (arrendamiento operativo, edificaciones)
    'depreciation_account_id': '39412',     # Depreciación acumulada del derecho de uso
    'depreciation_expense_account_id': '683111',  # Depreciación del derecho de uso
    'liability_long_account_id': '452',     # Contratos de arrendamiento financiero
    'liability_short_account_id': '452',
    'interest_account_id': '6732',          # Intereses de contratos de arrendamiento
    'clearing_account_id': '183',           # Alquileres pagados por anticipado (acepta facturas)
    'rent_expense_account_id': '6352',      # Alquileres de edificaciones (exentos)
}


class L10nPeLease(models.Model):
    _name = 'l10n_pe.lease'
    _description = 'Arrendamiento (NIIF 16)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    state = fields.Selection(STATES, string='Estado', default='draft', required=True, tracking=True, copy=False)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    partner_id = fields.Many2one('res.partner', string='Arrendador', required=True, tracking=True,
                                 check_company=True)
    property_description = fields.Char(string='Bien arrendado', required=True, tracking=True,
                                       help='Inmueble o bien: p. ej. «Oficina Av. Arequipa 123, piso 5».')
    contract_ref = fields.Char(string='Contrato', tracking=True)
    date_start = fields.Date(string='Inicio', required=True, default=fields.Date.context_today, tracking=True)
    term_months = fields.Integer(string='Plazo (meses)', required=True, default=36, tracking=True)
    date_end = fields.Date(string='Fin', compute='_compute_date_end', store=True)
    payment_amount = fields.Monetary(string='Cuota mensual', required=True, tracking=True,
                                     help='Importe mensual sin IGV.')
    payment_timing = fields.Selection(TIMINGS, string='Pago', required=True, default='advance', tracking=True)
    annual_rate = fields.Float(string='Tasa incremental anual (%)', digits=(6, 4), tracking=True,
                               help='Tasa incremental de endeudamiento del arrendatario (efectiva anual): la '
                                    'que pagaría por un préstamo a ese plazo. Se usa si el contrato no fija '
                                    'una tasa implícita.')
    initial_direct_costs = fields.Monetary(string='Costos directos iniciales',
                                           help='Comisiones o gastos para obtener el contrato: suman al activo.')
    incentives = fields.Monetary(string='Incentivos recibidos',
                                 help='Pagos o descuentos del arrendador por firmar: restan al activo.')
    guarantee_amount = fields.Monetary(string='Garantía entregada',
                                       help='Solo informativa: la garantía se registra aparte (no es parte '
                                            'del pasivo ni del activo).')
    exemption = fields.Selection(EXEMPTIONS, string='Exención NIIF 16', compute='_compute_exemption',
                                 store=True, readonly=False, required=True, precompute=True, tracking=True,
                                 help='Corto plazo o bajo valor: no se reconoce activo ni pasivo; la cuota '
                                      'va a gasto de alquiler.')
    journal_id = fields.Many2one('account.journal', string='Diario', check_company=True,
                                 domain="[('type', '=', 'general')]",
                                 default=lambda self: self.env['account.journal'].search(
                                     [('type', '=', 'general'), ('company_id', '=', self.env.company.id)], limit=1))

    rou_account_id = fields.Many2one('account.account', string='Cuenta del derecho de uso', check_company=True)
    depreciation_account_id = fields.Many2one('account.account', string='Depreciación acumulada',
                                              check_company=True)
    depreciation_expense_account_id = fields.Many2one('account.account', string='Gasto de depreciación',
                                                      check_company=True)
    liability_long_account_id = fields.Many2one('account.account', string='Pasivo a largo plazo',
                                                check_company=True)
    liability_short_account_id = fields.Many2one(
        'account.account', string='Pasivo a corto plazo', check_company=True,
        help='Las facturas del arrendador cargan esta cuenta: cancelan la cuota del mes.')
    interest_account_id = fields.Many2one('account.account', string='Gasto por intereses', check_company=True)
    clearing_account_id = fields.Many2one(
        'account.account', string='Cuenta transitoria', check_company=True,
        help='Recibe la cuota adelantada, los costos directos y los incentivos del reconocimiento inicial; '
             'la factura de la primera cuota y las de los costos la saldan.')
    rent_expense_account_id = fields.Many2one('account.account', string='Gasto de alquiler', check_company=True,
                                              help='Para contratos exentos de NIIF 16.')

    monthly_rate = fields.Float(string='Tasa mensual (%)', digits=(6, 6), compute='_compute_amounts', store=True)
    liability_amount = fields.Monetary(string='Pasivo inicial', compute='_compute_amounts', store=True,
                                       help='Valor presente de las cuotas no pagadas al inicio.')
    rou_amount = fields.Monetary(string='Derecho de uso', compute='_compute_amounts', store=True,
                                 help='Pasivo + cuota adelantada + costos directos − incentivos.')
    total_payments = fields.Monetary(string='Total de cuotas', compute='_compute_amounts', store=True)
    total_interest = fields.Monetary(string='Intereses totales', compute='_compute_amounts', store=True)

    line_ids = fields.One2many('l10n_pe.lease.line', 'lease_id', string='Tabla del pasivo', readonly=True)
    initial_move_id = fields.Many2one('account.move', string='Asiento inicial', readonly=True, copy=False,
                                      check_company=True)
    asset_id = fields.Many2one('account.asset', string='Activo', readonly=True, copy=False, check_company=True)
    loan_id = fields.Many2one('account.loan', string='Pasivo (préstamo)', readonly=True, copy=False,
                              check_company=True)
    asset_group_id = fields.Many2one('account.asset.group', string='Grupo de activos', readonly=True, copy=False,
                                     check_company=True)
    bill_ids = fields.One2many('account.move', 'l10n_pe_lease_id', string='Facturas del arrendador',
                               readonly=True)
    bill_count = fields.Integer(compute='_compute_bill_count')
    next_period = fields.Integer(string='Próxima cuota', compute='_compute_bill_count')

    _term_positive = models.Constraint('CHECK(term_months > 0)', 'El plazo debe ser de al menos un mes.')
    _payment_positive = models.Constraint('CHECK(payment_amount > 0)', 'La cuota debe ser mayor que cero.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('l10n_pe.lease') or '/'
        leases = super().create(vals_list)
        leases._set_default_accounts()
        return leases

    def _set_default_accounts(self):
        """Cuentas del PCGE (por código) en las que falten."""
        for lease in self:
            Account = self.env['account.account'].with_company(lease.company_id)
            vals = {}
            for field, code in DEFAULT_ACCOUNTS.items():
                if not lease[field]:
                    account = Account.search([('code', '=like', code + '%')], order='code', limit=1)
                    if account:
                        vals[field] = account.id
            if vals:
                lease.write(vals)

    @api.depends('date_start', 'term_months')
    def _compute_date_end(self):
        for lease in self:
            lease.date_end = lease.date_start and lease.term_months and (
                lease.date_start + relativedelta(months=lease.term_months, days=-1))

    @api.depends('term_months')
    def _compute_exemption(self):
        for lease in self:
            if lease.exemption == 'low_value':
                continue
            lease.exemption = 'short_term' if lease.term_months and lease.term_months <= 12 else 'none'

    # ------------------------------------------------------------------
    # Cálculo (método del interés efectivo)
    # ------------------------------------------------------------------
    def _schedule(self):
        """Tabla del pasivo: ``(valor presente, tasa mensual, [(n.º, fecha,
        cuota, interés, capital, saldo)])``. Con pago adelantado la primera
        cuota se paga al inicio y no forma parte del pasivo."""
        self.ensure_one()
        currency = self.currency_id
        rate = (1 + (self.annual_rate or 0.0) / 100.0) ** (1 / 12.0) - 1
        advance = self.payment_timing == 'advance'
        periods = self.term_months - 1 if advance else self.term_months
        payment = self.payment_amount
        if periods <= 0:
            return 0.0, rate, []
        pv = payment * (1 - (1 + rate) ** -periods) / rate if rate else payment * periods
        pv = currency.round(pv)
        balance, rows = pv, []
        for k in range(1, periods + 1):
            # Adelantada: la cuota k+1 se paga al empezar el mes k+1.
            # Vencida: la cuota k se paga al terminar el mes k.
            date = self.date_start + relativedelta(months=k) + (relativedelta() if advance else relativedelta(days=-1))
            interest = currency.round(balance * rate)
            principal = currency.round(payment - interest)
            if k == periods:
                principal = balance
                interest = currency.round(payment - principal)
            balance = currency.round(balance - principal)
            rows.append((k + 1 if advance else k, date, payment, interest, principal, balance))
        return pv, rate, rows

    @api.depends('term_months', 'payment_amount', 'payment_timing', 'annual_rate', 'initial_direct_costs',
                 'incentives', 'date_start', 'exemption')
    def _compute_amounts(self):
        for lease in self:
            if not (lease.term_months and lease.payment_amount and lease.date_start):
                lease.update({'monthly_rate': 0.0, 'liability_amount': 0.0, 'rou_amount': 0.0,
                              'total_payments': 0.0, 'total_interest': 0.0})
                continue
            pv, rate, rows = lease._schedule()
            prepaid = lease.payment_amount if lease.payment_timing == 'advance' else 0.0
            exempt = lease.exemption != 'none'
            lease.monthly_rate = rate * 100
            lease.total_payments = lease.payment_amount * lease.term_months
            lease.liability_amount = 0.0 if exempt else pv
            lease.rou_amount = 0.0 if exempt else lease.currency_id.round(
                pv + prepaid + lease.initial_direct_costs - lease.incentives)
            lease.total_interest = 0.0 if exempt else sum(row[3] for row in rows)

    def action_compute(self):
        for lease in self:
            if lease.state != 'draft':
                raise UserError(self.env._('Solo se recalcula un contrato en borrador.'))
            lease.line_ids.unlink()
            if lease.exemption != 'none':
                continue
            _pv, _rate, rows = lease._schedule()
            lease.line_ids = [Command.create({
                'number': number, 'date': date, 'payment': payment, 'interest': interest,
                'principal': principal, 'balance': balance,
            }) for number, date, payment, interest, principal, balance in rows]
        return True

    # ------------------------------------------------------------------
    # Confirmación
    # ------------------------------------------------------------------
    def _check_before_confirm(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(self.env._('El contrato %s ya está confirmado.', self.name))
        if self.exemption != 'none':
            if not self.rent_expense_account_id:
                raise UserError(self.env._('Indique la cuenta de gasto de alquiler.'))
            return
        missing = [self._fields[f].string for f in (
            'journal_id', 'rou_account_id', 'depreciation_account_id', 'depreciation_expense_account_id',
            'liability_long_account_id', 'liability_short_account_id', 'interest_account_id')
            if not self[f]]
        if missing:
            raise UserError(self.env._('Faltan datos del contrato: %s.', ', '.join(missing)))
        if not self.annual_rate:
            raise UserError(self.env._('Indique la tasa incremental de endeudamiento.'))
        clearing = self.rou_amount - self.liability_amount
        if not self.currency_id.is_zero(clearing) and not self.clearing_account_id:
            raise UserError(self.env._('Indique la cuenta transitoria de la cuota adelantada y los costos.'))

    def action_confirm(self):
        """Reconoce el contrato: asiento inicial (derecho de uso contra pasivo),
        activo con su depreciación y pasivo con su tabla en ``account_loans``.
        Los contratos exentos solo pasan a «Exento»."""
        for lease in self:
            lease._check_before_confirm()
            if lease.exemption != 'none':
                lease.line_ids.unlink()
                lease.state = 'exempt'
                lease.message_post(body=self.env._(
                    'Contrato exento de NIIF 16 (%s): las cuotas van a gasto de alquiler.',
                    dict(EXEMPTIONS)[lease.exemption]))
                continue
            lease.action_compute()
            lease._create_initial_move()
            lease.asset_group_id = self.env['account.asset.group'].create({
                'name': '%s - %s' % (lease.name, lease.property_description), 'company_id': lease.company_id.id})
            lease._create_asset()
            lease._create_loan()
            lease.state = 'running'
            lease.message_post(body=self.env._(
                'Arrendamiento reconocido: derecho de uso %(rou)s, pasivo %(liability)s.',
                rou=lease.currency_id.format(lease.rou_amount),
                liability=lease.currency_id.format(lease.liability_amount)))
        return True

    def _create_initial_move(self):
        self.ensure_one()
        label = self.env._('Reconocimiento inicial %s', self.name)
        lines = [
            Command.create({'account_id': self.rou_account_id.id, 'name': label, 'debit': self.rou_amount,
                            'partner_id': self.partner_id.id}),
            Command.create({'account_id': self.liability_long_account_id.id, 'name': label,
                            'credit': self.liability_amount, 'partner_id': self.partner_id.id}),
        ]
        clearing = self.currency_id.round(self.rou_amount - self.liability_amount)
        if not self.currency_id.is_zero(clearing):
            lines.append(Command.create({
                'account_id': self.clearing_account_id.id, 'partner_id': self.partner_id.id,
                'name': self.env._('Cuota adelantada, costos directos e incentivos %s', self.name),
                'credit': clearing if clearing > 0 else 0.0, 'debit': -clearing if clearing < 0 else 0.0}))
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': self.journal_id.id, 'date': self.date_start,
            'ref': label, 'company_id': self.company_id.id, 'line_ids': lines,
        })
        move.action_post()
        self.initial_move_id = move

    def _create_asset(self):
        self.ensure_one()
        rou_line = self.initial_move_id.line_ids.filtered(lambda l: l.account_id == self.rou_account_id)
        asset = self.env['account.asset'].create({
            'name': '%s - %s' % (self.name, self.property_description),
            'company_id': self.company_id.id,
            'original_move_line_ids': [Command.set(rou_line.ids)],
            'acquisition_date': self.date_start,
            'prorata_date': self.date_start,
            'method': 'linear',
            'method_number': self.term_months,
            'method_period': '1',
            'prorata_computation_type': 'constant_periods',
            'account_depreciation_id': self.depreciation_account_id.id,
            'account_depreciation_expense_id': self.depreciation_expense_account_id.id,
            'journal_id': self.journal_id.id,
            'asset_group_id': self.asset_group_id.id,
        })
        asset.validate()
        self.asset_id = asset

    def _create_loan(self):
        """El pasivo va a ``account.loan`` con la tabla ya calculada (sus
        líneas admiten capital e interés propios): el préstamo genera el
        asiento de cada cuota (capital + interés contra el corto plazo) y la
        reclasificación largo/corto plazo."""
        self.ensure_one()
        loan = self.env['account.loan'].create({
            'name': '%s - %s' % (self.name, self.property_description),
            'company_id': self.company_id.id,
            'date': self.date_start,
            'amount_borrowed': self.liability_amount,
            'interest': sum(self.line_ids.mapped('interest')),
            'duration': len(self.line_ids),
            'long_term_account_id': self.liability_long_account_id.id,
            'short_term_account_id': self.liability_short_account_id.id,
            'expense_account_id': self.interest_account_id.id,
            'journal_id': self.journal_id.id,
            'asset_group_id': self.asset_group_id.id,
            'line_ids': [Command.create({'date': line.date, 'principal': line.principal,
                                         'interest': line.interest}) for line in self.line_ids],
        })
        loan.action_confirm()
        self.loan_id = loan

    def action_cancel(self):
        for lease in self:
            if lease.state != 'draft':
                raise UserError(self.env._('Un contrato confirmado no se cancela: termínelo.'))
            lease.state = 'cancelled'
        return True

    def action_draft(self):
        self.filtered(lambda l: l.state == 'cancelled').write({'state': 'draft'})
        return True

    def action_close(self):
        self.filtered(lambda l: l.state in ('running', 'exempt')).write({'state': 'closed'})
        return True

    # ------------------------------------------------------------------
    # Cuotas del arrendador
    # ------------------------------------------------------------------
    @api.depends('bill_ids.state')
    def _compute_bill_count(self):
        for lease in self:
            bills = lease.bill_ids.filtered(lambda m: m.state != 'cancel')
            lease.bill_count = len(bills)
            lease.next_period = max(bills.mapped('l10n_pe_lease_period') or [0]) + 1

    def _installment_account(self, period):
        """Cuenta que carga la factura de la cuota ``period``."""
        self.ensure_one()
        if self.state == 'exempt':
            return self.rent_expense_account_id
        if period == 1 and self.payment_timing == 'advance':
            return self.clearing_account_id  # la cuota adelantada ya está en el activo
        return self.liability_short_account_id

    def _installment_date(self, period):
        self.ensure_one()
        if self.payment_timing == 'advance':
            return self.date_start + relativedelta(months=period - 1)
        return self.date_start + relativedelta(months=period, days=-1)

    def action_register_installment(self):
        """Crea en borrador la factura del arrendador de la próxima cuota."""
        self.ensure_one()
        if self.state not in ('running', 'exempt'):
            raise UserError(self.env._('Confirme el contrato antes de registrar cuotas.'))
        period = self.next_period
        if period > self.term_months:
            raise UserError(self.env._('Ya se registraron las %s cuotas del contrato.', self.term_months))
        tax = self.company_id.account_purchase_tax_id
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'invoice_date': self._installment_date(period),
            'date': self._installment_date(period),
            'ref': '%s %s/%s' % (self.name, period, self.term_months),
            'l10n_pe_lease_id': self.id,
            'l10n_pe_lease_period': period,
            'invoice_line_ids': [Command.create({
                'name': self.env._('Alquiler %(property)s - cuota %(period)s/%(term)s',
                                   property=self.property_description, period=period, term=self.term_months),
                'quantity': 1, 'price_unit': self.payment_amount,
                'account_id': self._installment_account(period).id,
                'tax_ids': [Command.set(tax.ids)],
            })],
        })
        return {'type': 'ir.actions.act_window', 'res_model': 'account.move', 'res_id': bill.id,
                'view_mode': 'form', 'target': 'current'}

    def action_open_bills(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': self.env._('Facturas del arrendador'),
                'res_model': 'account.move', 'view_mode': 'list,form',
                'domain': [('l10n_pe_lease_id', '=', self.id)],
                'context': {'default_move_type': 'in_invoice'}}

    def action_open_asset(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'account.asset', 'res_id': self.asset_id.id,
                'view_mode': 'form'}

    def action_open_loan(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'account.loan', 'res_id': self.loan_id.id,
                'view_mode': 'form'}

    @api.constrains('annual_rate')
    def _check_rate(self):
        for lease in self:
            if lease.annual_rate < 0:
                raise ValidationError(self.env._('La tasa no puede ser negativa.'))


class L10nPeLeaseLine(models.Model):
    _name = 'l10n_pe.lease.line'
    _description = 'Tabla del pasivo por arrendamiento'
    _order = 'lease_id, number'
    _check_company_auto = True

    lease_id = fields.Many2one('l10n_pe.lease', string='Contrato', required=True, ondelete='cascade', index=True,
                               check_company=True)
    company_id = fields.Many2one(related='lease_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='lease_id.currency_id')
    partner_id = fields.Many2one(related='lease_id.partner_id', store=True, string='Arrendador')
    number = fields.Integer(string='N.º de cuota')
    date = fields.Date(string='Fecha')
    payment = fields.Monetary(string='Cuota')
    interest = fields.Monetary(string='Interés')
    principal = fields.Monetary(string='Capital')
    balance = fields.Monetary(string='Saldo del pasivo')
