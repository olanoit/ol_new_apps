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
EVENTS = [
    ('remeasurement', 'Remedición'),
    ('termination', 'Terminación anticipada'),
    ('exchange', 'Diferencia de cambio'),
]
# Cuentas del PCGE por defecto (se buscan por código en el plan de la compañía,
# en orden: la primera que exista). El plan de Odoo solo trae la 452: las
# subcuentas 4521 (largo plazo) y 4522 (corto plazo) se crean con «Crear
# subcuentas del pasivo» para que la reclasificación separe ambos plazos.
DEFAULT_ACCOUNTS = {
    'rou_account_id': ('32331',),               # Derecho de uso (arrendamiento operativo, edificaciones)
    'depreciation_account_id': ('39412',),      # Depreciación acumulada del derecho de uso
    'depreciation_expense_account_id': ('683111',),  # Depreciación del derecho de uso
    'liability_long_account_id': ('4521', '452'),
    'liability_short_account_id': ('4522', '452'),
    'interest_account_id': ('6732',),           # Intereses de contratos de arrendamiento
    'clearing_account_id': ('183',),            # Alquileres pagados por anticipado (acepta facturas)
    'rent_expense_account_id': ('6352',),       # Alquileres de edificaciones (exentos)
}
LIABILITY_SUBACCOUNTS = [
    ('liability_long_account_id', '4521', 'Pasivo por arrendamiento - largo plazo', 'liability_non_current'),
    ('liability_short_account_id', '4522', 'Pasivo por arrendamiento - corto plazo', 'liability_current'),
]


def _end_of_month(date):
    return date + relativedelta(day=31)


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
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda de la compañía')
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True, tracking=True,
        default=lambda self: self.env.company.currency_id,
        help='Moneda del contrato. En moneda extranjera el pasivo es una partida monetaria: se ajusta por '
             'diferencia de cambio; el derecho de uso queda al tipo de cambio del inicio.')
    is_foreign_currency = fields.Boolean(string='En moneda extranjera', compute='_compute_is_foreign_currency')
    partner_id = fields.Many2one('res.partner', string='Arrendador', required=True, tracking=True,
                                 check_company=True)
    property_description = fields.Char(string='Bien arrendado', required=True, tracking=True,
                                       help='Inmueble o bien: p. ej. «Oficina Av. Arequipa 123, piso 5».')
    contract_ref = fields.Char(string='Contrato', tracking=True)
    product_id = fields.Many2one(
        'product.product', string='Producto de la cuota', check_company=True,
        domain="[('type', '=', 'service')]",
        help='Servicio de alquiler que llevan las facturas del arrendador: sus impuestos de compra (IGV) y su '
             'tipo de detracción (arrendamiento de bienes) se aplican a cada cuota. Sin producto, la factura '
             'lleva el impuesto de compra por defecto de la compañía.')
    date_start = fields.Date(string='Inicio', required=True, default=fields.Date.context_today, tracking=True)
    term_months = fields.Integer(string='Plazo (meses)', required=True, default=36, tracking=True)
    date_end = fields.Date(string='Fin', compute='_compute_date_end', store=True)
    payment_amount = fields.Monetary(string='Cuota mensual', required=True, tracking=True,
                                     help='Importe mensual fijo sin IGV. Los pagos variables (por ventas, '
                                          'consumo, mantenimiento) no forman parte del pasivo: se facturan '
                                          'aparte, a gasto.')
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
    same_liability_account = fields.Boolean(string='Misma cuenta de pasivo', compute='_compute_same_liability_account')
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
    start_rate = fields.Float(string='Tipo de cambio del inicio', digits=(12, 6), readonly=True, copy=False,
                              help='Soles por unidad de la moneda del contrato al reconocer el arrendamiento: '
                                   'fija el derecho de uso.')
    rou_amount_company = fields.Monetary(string='Derecho de uso (en soles)', readonly=True, copy=False,
                                         currency_field='company_currency_id')

    line_ids = fields.One2many('l10n_pe.lease.line', 'lease_id', string='Tabla del pasivo', readonly=True)
    event_ids = fields.One2many('l10n_pe.lease.event', 'lease_id', string='Historial', readonly=True)
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
    termination_date = fields.Date(string='Fecha de terminación', readonly=True, copy=False)

    # Saldos para el seguimiento y la conciliación con el libro (a hoy).
    liability_balance = fields.Monetary(
        string='Saldo del pasivo (tabla)', compute='_compute_balances',
        help='Capital pendiente según la tabla más las cuotas vencidas que aún no tienen factura del '
             'arrendador, en la moneda del contrato.')
    liability_book_balance = fields.Monetary(
        string='Saldo del pasivo (libro)', compute='_compute_balances', currency_field='company_currency_id',
        help='Saldo de las cuentas del pasivo en los asientos del contrato (inicial, cuotas, facturas, '
             'remediciones, diferencia de cambio), en soles.')
    liability_difference = fields.Monetary(
        string='Diferencia con el libro', compute='_compute_balances', currency_field='company_currency_id',
        help='Libro − tabla (convertida a soles al tipo de cambio de hoy). En moneda extranjera es la '
             'diferencia de cambio aún no registrada; en soles debe ser cero.')
    rou_book_value = fields.Monetary(string='Valor en libros del derecho de uso', compute='_compute_balances',
                                     currency_field='company_currency_id')

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
            for field, codes in DEFAULT_ACCOUNTS.items():
                if lease[field]:
                    continue
                for code in codes:
                    account = Account.search([('code', '=', code)], limit=1) or Account.search(
                        [('code', '=like', code + '%')], order='code', limit=1)
                    if account:
                        vals[field] = account.id
                        break
            if vals:
                lease.write(vals)

    def action_create_liability_accounts(self):
        """Crea (si faltan) las subcuentas 4521 largo plazo y 4522 corto plazo
        del pasivo y las asigna: con una sola cuenta, la reclasificación entre
        plazos no se ve en el balance."""
        for lease in self:
            if lease.state != 'draft':
                raise UserError(self.env._('Las cuentas se cambian en borrador.'))
            Account = self.env['account.account'].with_company(lease.company_id)
            # Las subcuentas siguen la longitud de los códigos del plan
            # (452 → 4521 / 4522; 4520000 → 4521000 / 4522000).
            width = len(lease.liability_long_account_id.code or '') or 4
            vals = {}
            for field, prefix, name, account_type in LIABILITY_SUBACCOUNTS:
                code = prefix.ljust(max(width, len(prefix)), '0')
                account = Account.search([('code', '=', code)], limit=1)
                if not account:
                    account = Account.create({'code': code, 'name': name, 'account_type': account_type,
                                              'company_ids': [Command.link(lease.company_id.root_id.id)]})
                vals[field] = account.id
            lease.write(vals)
        return True

    @api.depends('date_start', 'term_months')
    def _compute_date_end(self):
        for lease in self:
            lease.date_end = lease.date_start and lease.term_months and (
                lease.date_start + relativedelta(months=lease.term_months, days=-1))

    @api.depends('term_months')
    def _compute_exemption(self):
        for lease in self:
            if lease.exemption == 'low_value' or (lease.state not in ('draft', False) and lease.exemption):
                # Confirmado: una remedición del plazo no cambia la exención.
                lease.exemption = lease.exemption
                continue
            lease.exemption = 'short_term' if lease.term_months and lease.term_months <= 12 else 'none'

    @api.depends('currency_id', 'company_id')
    def _compute_is_foreign_currency(self):
        for lease in self:
            lease.is_foreign_currency = lease.currency_id != lease.company_id.currency_id

    @api.depends('liability_long_account_id', 'liability_short_account_id')
    def _compute_same_liability_account(self):
        for lease in self:
            lease.same_liability_account = bool(lease.liability_long_account_id) and \
                lease.liability_long_account_id == lease.liability_short_account_id

    # ------------------------------------------------------------------
    # Cálculo (método del interés efectivo)
    # ------------------------------------------------------------------
    def _rate(self, annual_rate=None):
        annual = self.annual_rate if annual_rate is None else annual_rate
        return (1 + (annual or 0.0) / 100.0) ** (1 / 12.0) - 1

    def _build_rows(self, start, months, payment, rate, advance, first_number, payment_at_start):
        """Tabla por interés efectivo desde ``start``: ``(valor presente,
        [(n.º, fecha, cuota, interés, capital, saldo)])``.

        * Vencida: cuotas al final de cada mes 1..``months``.
        * Adelantada: cuotas al inicio de cada mes. Al reconocer el contrato
          la del mes 0 ya se pagó (no es pasivo, ``payment_at_start`` falso);
          en una remedición la del mes de la fecha sí es pasivo.
        """
        currency = self.currency_id
        offsets = []
        if advance:
            offsets = list(range(0 if payment_at_start else 1, months))
        else:
            offsets = list(range(1, months + 1))
        if not offsets:
            return 0.0, []
        pv = sum(payment / (1 + rate) ** k for k in offsets) if rate else payment * len(offsets)
        pv = currency.round(pv)
        balance, rows, previous = pv, [], None
        for index, k in enumerate(offsets):
            date = start + relativedelta(months=k)
            if not advance:
                date -= relativedelta(days=1)
            interest = 0.0 if previous is None and k == 0 else currency.round(balance * rate)
            principal = currency.round(payment - interest)
            if index == len(offsets) - 1:
                principal = balance
                interest = currency.round(payment - principal)
            balance = currency.round(balance - principal)
            rows.append((first_number + index, date, payment, interest, principal, balance))
            previous = k
        return pv, rows

    def _schedule(self):
        """Tabla del reconocimiento inicial: ``(valor presente, tasa mensual, filas)``."""
        self.ensure_one()
        rate = self._rate()
        advance = self.payment_timing == 'advance'
        pv, rows = self._build_rows(self.date_start, self.term_months, self.payment_amount, rate, advance,
                                    first_number=2 if advance else 1, payment_at_start=False)
        return pv, rate, rows

    @api.depends('term_months', 'payment_amount', 'payment_timing', 'annual_rate', 'initial_direct_costs',
                 'incentives', 'date_start', 'exemption', 'currency_id')
    def _compute_amounts(self):
        for lease in self:
            if lease.state not in ('draft', False) and lease.liability_amount:
                # Confirmado: las remediciones no cambian la medición inicial.
                lease.update({f: lease[f] for f in ('monthly_rate', 'liability_amount', 'rou_amount',
                                                    'total_payments', 'total_interest')})
                continue
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
            lease.line_ids = [Command.create(lease._line_vals(row)) for row in rows]
        return True

    @staticmethod
    def _line_vals(row):
        number, date, payment, interest, principal, balance = row
        return {'number': number, 'date': date, 'payment': payment, 'interest': interest,
                'principal': principal, 'balance': balance}

    # ------------------------------------------------------------------
    # Conversión a la moneda de la compañía
    # ------------------------------------------------------------------
    def _to_company(self, amount, date=None, rate=None):
        """Importe del contrato en soles: al tipo ``rate`` (soles por unidad)
        o al del día ``date``."""
        self.ensure_one()
        if not self.is_foreign_currency:
            return amount
        if rate:
            return self.company_currency_id.round(amount * rate)
        return self.currency_id._convert(amount, self.company_currency_id, self.company_id,
                                         date or fields.Date.context_today(self))

    def _company_rate(self, date):
        self.ensure_one()
        if not self.is_foreign_currency:
            return 1.0
        return self.env['res.currency']._get_conversion_rate(
            self.currency_id, self.company_currency_id, self.company_id, date)

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
            lease.start_rate = lease._company_rate(lease.date_start)
            lease.rou_amount_company = lease._to_company(lease.rou_amount, rate=lease.start_rate)
            lease._create_initial_move()
            lease.asset_group_id = self.env['account.asset.group'].create({
                'name': '%s - %s' % (lease.name, lease.property_description), 'company_id': lease.company_id.id})
            lease._create_asset()
            lease.loan_id = lease._create_loan(lease.line_ids, lease.date_start, lease.start_rate)
            lease.state = 'running'
            lease.message_post(body=self.env._(
                'Arrendamiento reconocido: derecho de uso %(rou)s, pasivo %(liability)s.',
                rou=lease.currency_id.format(lease.rou_amount),
                liability=lease.currency_id.format(lease.liability_amount)))
        return True

    def _move_line(self, account, amount, label, foreign_amount=None):
        """Línea de asiento en soles (``amount`` > 0 al debe); con moneda
        extranjera lleva también el importe en la moneda del contrato."""
        vals = {'account_id': account.id, 'name': label, 'partner_id': self.partner_id.id,
                'debit': amount if amount > 0 else 0.0, 'credit': -amount if amount < 0 else 0.0}
        if self.is_foreign_currency and foreign_amount is not None:
            vals.update(currency_id=self.currency_id.id, amount_currency=foreign_amount)
        return Command.create(vals)

    def _post_move(self, date, ref, lines):
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': self.journal_id.id, 'date': date, 'ref': ref,
            'company_id': self.company_id.id, 'line_ids': lines, 'l10n_pe_lease_id': self.id,
        })
        move.action_post()
        return move

    def _create_initial_move(self):
        self.ensure_one()
        label = self.env._('Reconocimiento inicial %s', self.name)
        rate = self.start_rate
        rou = self.rou_amount_company
        liability = self._to_company(self.liability_amount, rate=rate)
        lines = [self._move_line(self.rou_account_id, rou, label),
                 self._move_line(self.liability_long_account_id, -liability, label, -self.liability_amount)]
        clearing = self.currency_id.round(self.rou_amount - self.liability_amount)
        if not self.currency_id.is_zero(clearing):
            lines.append(self._move_line(
                self.clearing_account_id, -(rou - liability),
                self.env._('Cuota adelantada, costos directos e incentivos %s', self.name), -clearing))
        self.initial_move_id = self._post_move(self.date_start, label, lines)

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

    def _create_loan(self, lines, date, rate, suffix=''):
        """El pasivo va a ``account.loan`` con la tabla ya calculada (sus
        líneas admiten capital e interés propios): el préstamo genera el
        asiento de cada cuota (capital + interés contra el corto plazo) y la
        reclasificación largo/corto plazo. En moneda extranjera los importes
        van en soles al tipo ``rate``; la diferencia de cambio la ajusta
        «Diferencia de cambio»."""
        self.ensure_one()
        company_lines = []
        for line in lines:
            company_lines.append({'date': line.date, 'principal': self._to_company(line.principal, rate=rate),
                                  'interest': self._to_company(line.interest, rate=rate)})
        borrowed = self.company_currency_id.round(sum(l['principal'] for l in company_lines))
        loan = self.env['account.loan'].create({
            'name': '%s - %s%s' % (self.name, self.property_description, suffix),
            'company_id': self.company_id.id,
            'date': date,
            'amount_borrowed': borrowed,
            'interest': self.company_currency_id.round(sum(l['interest'] for l in company_lines)),
            'duration': len(company_lines),
            'long_term_account_id': self.liability_long_account_id.id,
            'short_term_account_id': self.liability_short_account_id.id,
            'expense_account_id': self.interest_account_id.id,
            'journal_id': self.journal_id.id,
            'asset_group_id': self.asset_group_id.id,
            'line_ids': [Command.create(vals) for vals in company_lines],
        })
        loan.action_confirm()
        return loan

    def action_cancel(self):
        for lease in self:
            if lease.state != 'draft':
                raise UserError(self.env._('Un contrato confirmado no se cancela: use la terminación anticipada.'))
            lease.state = 'cancelled'
        return True

    def action_draft(self):
        self.filtered(lambda l: l.state == 'cancelled').write({'state': 'draft'})
        return True

    def action_close(self):
        """Fin del plazo: el pasivo ya se canceló con las cuotas y el activo
        está depreciado; solo cambia el estado."""
        self.filtered(lambda l: l.state in ('running', 'exempt')).write({'state': 'closed'})
        return True

    # ------------------------------------------------------------------
    # Saldos del pasivo (tabla y libro)
    # ------------------------------------------------------------------
    def _loans(self):
        self.ensure_one()
        return self.loan_id | self.event_ids.mapped('old_loan_id')

    def _vendor_bills(self):
        """Facturas (y notas de crédito) del arrendador: ``bill_ids`` también
        reúne los asientos propios del contrato."""
        self.ensure_one()
        return self.bill_ids.filtered(lambda m: m.move_type in ('in_invoice', 'in_refund'))

    def _liability_moves(self):
        self.ensure_one()
        loan_moves = self._loans().line_ids.generated_move_ids
        return (self.bill_ids | loan_moves | self.initial_move_id | self.event_ids.mapped('move_ids')).filtered(
            lambda m: m.state == 'posted')

    def _liability_book(self, date):
        """Saldo acreedor de las cuentas del pasivo del contrato al ``date``, en soles."""
        self.ensure_one()
        accounts = self.liability_long_account_id | self.liability_short_account_id
        lines = self._liability_moves().line_ids.filtered(
            lambda l: l.account_id in accounts and l.date <= date)
        return -self.company_currency_id.round(sum(lines.mapped('balance')))

    def _liability_at(self, date):
        """Pasivo según la tabla al ``date`` (moneda del contrato): capital
        pendiente tras las cuotas ya devengadas (su asiento es de fin de mes)
        más las cuotas devengadas aún sin factura del arrendador."""
        self.ensure_one()
        candidates = [(self.date_start, 0, self.liability_amount)]
        candidates += [(event.date, 1, event.new_liability) for event in self.event_ids
                       if event.kind == 'remeasurement']
        due = self.line_ids.filtered(lambda l: _end_of_month(l.date) <= date)
        candidates += [(_end_of_month(line.date), 2, line.balance) for line in due]
        candidates = [c for c in candidates if c[0] <= date]
        if not candidates:
            return 0.0
        principal = max(candidates, key=lambda c: (c[0], c[1]))[2]
        billed_lines = self._vendor_bills().filtered(
            lambda m: m.state == 'posted' and m.date <= date).line_ids.filtered(
            lambda l: l.account_id in (self.liability_long_account_id | self.liability_short_account_id))
        # Las facturas cargan el pasivo (debe): reducen lo devengado sin facturar.
        billed = sum(l.amount_currency if self.is_foreign_currency else l.balance for l in billed_lines)
        unbilled = sum(due.mapped('payment')) - billed
        termination = self.event_ids.filtered(lambda e: e.kind == 'termination' and e.date <= date)
        if termination:
            principal = 0.0
            unbilled = sum(due.filtered(lambda l: l.date < termination[0].date).mapped('payment')) - billed
        return self.currency_id.round(principal + unbilled)

    def _principal_before(self, date):
        """Capital pendiente según la tabla justo antes de ``date`` (primer
        día de un mes): saldo tras las cuotas con fecha anterior; si no hay,
        el de la última remedición o el inicial."""
        self.ensure_one()
        candidates = [(self.date_start, 0, self.liability_amount)]
        candidates += [(event.date, 1, event.new_liability) for event in self.event_ids
                       if event.kind == 'remeasurement' and event.date < date]
        candidates += [(line.date, 2, line.balance) for line in self.line_ids if line.date < date]
        return max(candidates, key=lambda c: (c[0], c[1]))[2]

    @api.depends('line_ids', 'event_ids', 'bill_ids.state', 'asset_id.book_value')
    def _compute_balances(self):
        today = fields.Date.context_today(self)
        for lease in self:
            if lease.state in ('draft', 'cancelled', 'exempt') or not lease.initial_move_id:
                lease.update({'liability_balance': 0.0, 'liability_book_balance': 0.0,
                              'liability_difference': 0.0, 'rou_book_value': 0.0})
                continue
            table = lease._liability_at(today)
            book = lease._liability_book(today)
            lease.liability_balance = table
            lease.liability_book_balance = book
            lease.liability_difference = lease.company_currency_id.round(book - lease._to_company(table, today))
            lease.rou_book_value = lease.asset_id.book_value

    # ------------------------------------------------------------------
    # Diferencia de cambio (contratos en moneda extranjera)
    # ------------------------------------------------------------------
    def _exchange_difference(self, date):
        """Ajusta el pasivo en moneda extranjera al tipo de cambio de ``date``:
        pasivo según la tabla × tipo de cambio − saldo del libro. El derecho de
        uso no se ajusta (partida no monetaria, NIC 21)."""
        moves = self.env['account.move']
        for lease in self.filtered(lambda l: l.is_foreign_currency and l.state == 'running'):
            target = lease._to_company(lease._liability_at(date), date)
            book = lease._liability_book(date)
            difference = lease.company_currency_id.round(target - book)
            if lease.company_currency_id.is_zero(difference):
                continue
            company = lease.company_id
            gain_loss = company.expense_currency_exchange_account_id if difference > 0 \
                else company.income_currency_exchange_account_id
            if not gain_loss:
                raise UserError(self.env._('Configure las cuentas de diferencia de cambio de la compañía.'))
            label = self.env._('Diferencia de cambio del pasivo %(lease)s al %(date)s', lease=lease.name,
                               date=fields.Date.to_string(date))
            move = lease._post_move(date, label, [
                lease._move_line(gain_loss, difference, label),
                lease._move_line(lease.liability_long_account_id, -difference, label, 0.0),
            ])
            lease.event_ids = [Command.create({
                'kind': 'exchange', 'date': date, 'move_ids': [Command.set(move.ids)], 'amount_company': difference,
                'note': self.env._('Tipo de cambio %s', round(lease._company_rate(date), 6)),
            })]
            moves |= move
        return moves

    @api.model
    def _cron_exchange_difference(self):
        """Fin de mes: ajusta los contratos en moneda extranjera al último día
        del mes anterior (idempotente: un segundo ajuste resulta cero)."""
        date = fields.Date.context_today(self) + relativedelta(day=1, days=-1)
        for company in self.env['res.company'].search([]):
            leases = self.with_company(company).search(
                [('company_id', '=', company.id), ('state', '=', 'running')])
            leases._exchange_difference(date)

    # ------------------------------------------------------------------
    # Cuotas del arrendador
    # ------------------------------------------------------------------
    @api.depends('bill_ids.state')
    def _compute_bill_count(self):
        for lease in self:
            bills = lease._vendor_bills().filtered(lambda m: m.move_type == 'in_invoice' and m.state != 'cancel')
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

    def _installment_amount(self, period):
        """Cuota del periodo: la de la tabla vigente (cambia con una remedición)."""
        self.ensure_one()
        line = self.line_ids.filtered(lambda l: l.number == period)[:1]
        if line:
            return line.payment
        # La cuota adelantada del inicio no está en la tabla: es la original,
        # la de antes de la primera remedición.
        first = self.event_ids.filtered(lambda e: e.kind == 'remeasurement').sorted('date')[:1]
        return first.old_payment if first else self.payment_amount

    def action_register_installment(self):
        """Crea en borrador la factura del arrendador de la próxima cuota."""
        self.ensure_one()
        if self.state not in ('running', 'exempt'):
            raise UserError(self.env._('Confirme el contrato antes de registrar cuotas.'))
        period = self.next_period
        if period > self.term_months:
            raise UserError(self.env._('Ya se registraron las %s cuotas del contrato.', self.term_months))
        line_vals = {
            'name': self.env._('Alquiler %(property)s - cuota %(period)s/%(term)s',
                               property=self.property_description, period=period, term=self.term_months),
            'quantity': 1, 'price_unit': self._installment_amount(period),
        }
        if self.product_id:
            line_vals['product_id'] = self.product_id.id
        else:
            line_vals['tax_ids'] = [Command.set(self.company_id.account_purchase_tax_id.ids)]
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'invoice_date': self._installment_date(period),
            'date': self._installment_date(period),
            'ref': '%s %s/%s' % (self.name, period, self.term_months),
            'l10n_pe_lease_id': self.id,
            'l10n_pe_lease_period': period,
            'invoice_line_ids': [Command.create(line_vals)],
        })
        # El producto propone su cuenta de gasto: la cuota va al pasivo (o a la transitoria).
        bill.invoice_line_ids.account_id = self._installment_account(period)
        return {'type': 'ir.actions.act_window', 'res_model': 'account.move', 'res_id': bill.id,
                'view_mode': 'form', 'target': 'current'}

    # ------------------------------------------------------------------
    # Botones
    # ------------------------------------------------------------------
    def _open_wizard(self, model, name):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': name, 'res_model': model, 'view_mode': 'form',
                'target': 'new', 'context': {'default_lease_id': self.id}}

    def action_remeasure(self):
        return self._open_wizard('l10n_pe.lease.remeasure', self.env._('Remedición del arrendamiento'))

    def action_terminate(self):
        return self._open_wizard('l10n_pe.lease.terminate', self.env._('Terminación anticipada'))

    def action_exchange_difference(self):
        return self._open_wizard('l10n_pe.lease.exchange', self.env._('Diferencia de cambio'))

    def action_open_bills(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': self.env._('Facturas del arrendador'),
                'res_model': 'account.move', 'view_mode': 'list,form',
                'domain': [('l10n_pe_lease_id', '=', self.id), ('move_type', '=', 'in_invoice')],
                'context': {'default_move_type': 'in_invoice'}}

    def action_open_moves(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': self.env._('Asientos del arrendamiento'),
                'res_model': 'account.move', 'view_mode': 'list,form',
                'domain': [('id', 'in', (self._liability_moves() | self.asset_id.depreciation_move_ids).ids)]}

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


class L10nPeLeaseEvent(models.Model):
    """Historial de remediciones, terminación y diferencias de cambio."""
    _name = 'l10n_pe.lease.event'
    _description = 'Evento del arrendamiento'
    _order = 'lease_id, date, id'
    _check_company_auto = True

    lease_id = fields.Many2one('l10n_pe.lease', string='Contrato', required=True, ondelete='cascade', index=True,
                               check_company=True)
    company_id = fields.Many2one(related='lease_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='lease_id.currency_id')
    company_currency_id = fields.Many2one(related='lease_id.company_currency_id')
    kind = fields.Selection(EVENTS, string='Evento', required=True)
    date = fields.Date(string='Fecha', required=True)
    old_liability = fields.Monetary(string='Pasivo antes')
    new_liability = fields.Monetary(string='Pasivo después')
    difference = fields.Monetary(string='Ajuste del pasivo')
    amount_company = fields.Monetary(string='Importe en soles', currency_field='company_currency_id')
    old_payment = fields.Monetary(string='Cuota anterior')
    new_payment = fields.Monetary(string='Cuota nueva')
    old_term = fields.Integer(string='Plazo anterior (meses)')
    new_term = fields.Integer(string='Plazo nuevo (meses)')
    old_rate = fields.Float(string='Tasa anterior (%)', digits=(6, 4))
    new_rate = fields.Float(string='Tasa nueva (%)', digits=(6, 4))
    move_ids = fields.Many2many('account.move', string='Asientos', check_company=True)
    old_loan_id = fields.Many2one('account.loan', string='Préstamo cerrado', check_company=True)
    note = fields.Char(string='Motivo')
