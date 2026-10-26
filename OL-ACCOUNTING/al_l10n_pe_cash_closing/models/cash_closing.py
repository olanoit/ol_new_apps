from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

CATEGORIES = [
    ('collection', 'Cobro'),
    ('payment', 'Pago'),
    ('transfer', 'Transferencia o depósito'),
    ('other', 'Otro movimiento'),
]
SALE_KINDS = [('cash', 'Venta al contado'), ('credit', 'Cobranza')]


class L10nPeCashClosing(models.Model):
    """Cierre diario de una caja con su arqueo.

    El saldo según libros es la suma de las cuentas de liquidez del diario
    (cuenta de la caja y cuentas de pagos pendientes de sus métodos) en los
    apuntes de ese diario. Los movimientos del día se agrupan por asiento: el
    asiento de un extracto que solo cruza una cuenta de pendientes contra la
    caja suma cero y no aparece. El arqueo cuenta el efectivo por
    denominación; la diferencia se registra al cerrar y el día queda bloqueado.
    """
    _name = 'l10n_pe.cash.closing'
    _description = 'Cierre de caja'
    _inherit = ['mail.thread']
    _order = 'date desc, journal_id, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company)
    journal_id = fields.Many2one(
        'account.journal', string='Caja', required=True, check_company=True, tracking=True,
        domain="[('type', '=', 'cash')]")
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today, tracking=True)
    user_id = fields.Many2one(
        'res.users', string='Cajero', required=True, default=lambda self: self.env.user, tracking=True)
    state = fields.Selection(
        [('open', 'Abierto'), ('closed', 'Cerrado')], string='Estado', default='open', required=True,
        readonly=True, tracking=True, copy=False)
    currency_id = fields.Many2one('res.currency', string='Moneda', compute='_compute_currency_id', store=True)
    line_ids = fields.One2many('l10n_pe.cash.closing.line', 'closing_id', string='Movimientos', copy=False)
    count_ids = fields.One2many('l10n_pe.cash.closing.count', 'closing_id', string='Arqueo', copy=False)
    balance_start = fields.Monetary(
        string='Saldo inicial', currency_field='currency_id', readonly=True, copy=False,
        help='Saldo según libros al cierre del día anterior.')
    amount_in = fields.Monetary(
        string='Ingresos', currency_field='currency_id', compute='_compute_totals', store=True)
    amount_out = fields.Monetary(
        string='Egresos', currency_field='currency_id', compute='_compute_totals', store=True)
    balance_book = fields.Monetary(
        string='Saldo según libros', currency_field='currency_id', compute='_compute_totals', store=True)
    other_values = fields.Monetary(
        string='Otros valores', currency_field='currency_id',
        help='Vales, cheques o vouchers de tarjeta que están en la caja y forman parte del saldo.')
    balance_counted = fields.Monetary(
        string='Saldo arqueado', currency_field='currency_id', compute='_compute_totals', store=True)
    difference = fields.Monetary(
        string='Diferencia', currency_field='currency_id', compute='_compute_totals', store=True,
        help='Arqueado menos libros: negativa es faltante, positiva es sobrante.')
    shortage_account_id = fields.Many2one(
        'account.account', string='Cuenta del faltante', check_company=True,
        help='Vacía: la cuenta de pérdidas por diferencias del diario. Para cargar el faltante al '
             'cajero use una cuenta por cobrar al personal (p. ej. 1413) e indique su socio.')
    shortage_partner_id = fields.Many2one('res.partner', string='Responsable del faltante')
    move_id = fields.Many2one('account.move', string='Asiento de la diferencia', readonly=True, copy=False,
                              check_company=True)
    note = fields.Text(string='Observaciones')

    _journal_date_uniq = models.Constraint(
        'unique(journal_id, date)', 'Ya existe un cierre de esa caja para ese día.')

    @api.depends('journal_id')
    def _compute_currency_id(self):
        for closing in self:
            closing.currency_id = closing.journal_id.currency_id or closing.company_id.currency_id

    @api.depends('balance_start', 'line_ids.amount', 'count_ids.subtotal', 'other_values')
    def _compute_totals(self):
        for closing in self:
            amounts = closing.line_ids.mapped('amount')
            closing.amount_in = sum(a for a in amounts if a > 0)
            closing.amount_out = -sum(a for a in amounts if a < 0)
            closing.balance_book = closing.balance_start + closing.amount_in - closing.amount_out
            closing.balance_counted = sum(closing.count_ids.mapped('subtotal')) + closing.other_values
            closing.difference = closing.currency_id.round(closing.balance_counted - closing.balance_book) \
                if closing.currency_id else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].with_company(
                    vals.get('company_id') or self.env.company.id
                ).next_by_code('l10n_pe.cash.closing') or '/'
        closings = super().create(vals_list)
        for closing in closings:
            if not closing.count_ids:
                closing.count_ids = [Command.create({'denomination_id': d.id})
                                     for d in closing._l10n_pe_denominations()]
        closings.action_refresh()
        return closings

    def unlink(self):
        if any(closing.state == 'closed' for closing in self):
            raise UserError(_('Reabra el cierre antes de eliminarlo.'))
        return super().unlink()

    @api.constrains('journal_id')
    def _check_journal(self):
        for closing in self:
            if closing.journal_id.type != 'cash':
                raise ValidationError(_('El cierre de caja es para diarios de tipo efectivo.'))

    # ------------------------------------------------------------------
    # Saldo y movimientos según libros
    # ------------------------------------------------------------------

    def _l10n_pe_denominations(self):
        self.ensure_one()
        return self.env['l10n_pe.cash.denomination'].search([('currency_id', '=', self.currency_id.id)])

    def _l10n_pe_liquidity_accounts(self):
        """Cuenta de la caja y cuentas de pagos pendientes de sus métodos de pago."""
        self.ensure_one()
        journal = self.journal_id
        return (journal.default_account_id
                | journal.inbound_payment_method_line_ids.payment_account_id
                | journal.outbound_payment_method_line_ids.payment_account_id)

    def _l10n_pe_amount_field(self):
        foreign = self.journal_id.currency_id and self.journal_id.currency_id != self.company_id.currency_id
        return 'amount_currency' if foreign else 'balance'

    def _l10n_pe_book_domain(self):
        self.ensure_one()
        return [
            ('journal_id', '=', self.journal_id.id),
            ('account_id', 'in', self._l10n_pe_liquidity_accounts().ids),
            ('parent_state', '=', 'posted'),
        ]

    def _l10n_pe_book_balance(self, before):
        """Saldo según libros antes de ``before`` (sin incluir ese día)."""
        self.ensure_one()
        field = self._l10n_pe_amount_field()
        groups = self.env['account.move.line']._read_group(
            self._l10n_pe_book_domain() + [('date', '<', before)], aggregates=[f'{field}:sum'])
        return self.currency_id.round(groups[0][0] or 0.0) if groups else 0.0

    def _l10n_pe_day_lines(self):
        """Movimientos del día, uno por asiento (sin la diferencia de este cierre)."""
        self.ensure_one()
        field = self._l10n_pe_amount_field()
        lines = self.env['account.move.line'].search(
            self._l10n_pe_book_domain() + [('date', '=', self.date)], order='move_id, id')
        per_move = defaultdict(float)
        for line in lines:
            if line.move_id != self.move_id:
                per_move[line.move_id] += line[field]
        values = []
        for move, amount in per_move.items():
            if self.currency_id.is_zero(amount):
                continue  # extracto que solo cruza pendientes contra la caja
            values.append(self._l10n_pe_line_vals(move, self.currency_id.round(amount)))
        return values

    def _l10n_pe_line_vals(self, move, amount):
        payment = move.origin_payment_id
        company = self.company_id
        category, sale_kind = 'other', False
        is_transfer = bool(move.line_ids.filtered(lambda l: l.account_id == company.transfer_account_id))
        if payment:
            if payment.paired_internal_transfer_payment_id or is_transfer:
                category = 'transfer'
            elif payment.payment_type == 'inbound':
                category = 'collection'
                invoices = payment.reconciled_invoice_ids
                if invoices:
                    sale_kind = 'cash' if all(inv.invoice_date == self.date for inv in invoices) else 'credit'
            else:
                category = 'payment'
        elif is_transfer:
            category = 'transfer'
        return {
            'move_id': move.id,
            'payment_id': payment.id,
            'partner_id': (payment.partner_id or move.partner_id).id,
            'name': payment.memo or move.ref or move.name,
            'category': category,
            'sale_kind': sale_kind,
            'pe_payment_method_id': payment.pe_payment_method_id.id,
            'amount': amount,
        }

    def action_refresh(self):
        """Vuelve a leer el saldo inicial y los movimientos del día según libros."""
        for closing in self:
            if closing.state != 'open':
                continue
            closing.balance_start = closing._l10n_pe_book_balance(closing.date)
            closing.line_ids = [Command.clear()] + [
                Command.create(vals) for vals in closing._l10n_pe_day_lines()]
        return True

    # ------------------------------------------------------------------
    # Cierre y reapertura
    # ------------------------------------------------------------------

    def _l10n_pe_draft_payments(self):
        self.ensure_one()
        return self.env['account.payment'].search([
            ('journal_id', '=', self.journal_id.id), ('date', '<=', self.date), ('state', '=', 'draft')])

    def _l10n_pe_difference_move_vals(self):
        self.ensure_one()
        journal = self.journal_id
        company = self.company_id
        difference = self.difference
        if difference < 0:
            account = self.shortage_account_id or journal.loss_account_id \
                or company.default_cash_difference_expense_account_id
            partner = self.shortage_partner_id
            label = _('Faltante de caja %s', self.name)
        else:
            account = journal.profit_account_id or company.default_cash_difference_income_account_id
            partner = self.env['res.partner']
            label = _('Sobrante de caja %s', self.name)
        if not account:
            raise UserError(_('Indique las cuentas de diferencias de caja del diario %s.', journal.display_name))
        currency = self.currency_id
        balance = currency._convert(difference, company.currency_id, company, self.date)
        common = {'name': label, 'currency_id': currency.id}
        return {
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': self.date,
            'ref': label,
            'company_id': company.id,
            'l10n_pe_cash_closing_id': self.id,
            'line_ids': [
                Command.create({**common, 'account_id': journal.default_account_id.id,
                                'amount_currency': difference, 'balance': balance}),
                Command.create({**common, 'account_id': account.id, 'partner_id': partner.id,
                                'amount_currency': -difference, 'balance': -balance}),
            ],
        }

    def action_close(self):
        for closing in self.filtered(lambda c: c.state == 'open'):
            drafts = closing._l10n_pe_draft_payments()
            if drafts:
                raise UserError(_(
                    'Confirme o elimine los pagos en borrador de la caja antes de cerrarla: %s.',
                    ', '.join(drafts.mapped('display_name'))))
            closing.action_refresh()
            if not closing.count_ids.filtered('quantity') and not closing.other_values:
                raise UserError(_('Registre el arqueo: cuente los billetes y monedas de la caja.'))
            if not closing.currency_id.is_zero(closing.difference):
                move = self.env['account.move'].create(closing._l10n_pe_difference_move_vals())
                move.action_post()
                closing.move_id = move
            closing.state = 'closed'
            closing.message_post(body=_(
                'Caja cerrada. Saldo según libros %(book)s, arqueado %(counted)s.',
                book=closing.currency_id.format(closing.balance_book),
                counted=closing.currency_id.format(closing.balance_counted)))
        return True

    def action_reopen(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_('Solo un administrador de contabilidad reabre un cierre de caja.'))
        for closing in self.filtered(lambda c: c.state == 'closed'):
            later = self.search([('journal_id', '=', closing.journal_id.id), ('date', '>', closing.date),
                                 ('state', '=', 'closed')], limit=1)
            if later:
                raise UserError(_('Reabra primero el cierre posterior %s.', later.name))
            closing.state = 'open'
            if closing.move_id:
                closing.move_id.button_cancel()
                closing.move_id = False
            closing.message_post(body=_('Cierre reabierto.'))
        return True

    def action_print(self):
        return self.env.ref('al_l10n_pe_cash_closing.action_report_cash_closing').report_action(self)

    # ------------------------------------------------------------------
    # Datos del PDF
    # ------------------------------------------------------------------

    def _l10n_pe_summary_by_method(self):
        """[(medio de pago, ingresos, egresos)] para el PDF."""
        self.ensure_one()
        totals = defaultdict(lambda: [0.0, 0.0])
        for line in self.line_ids:
            key = line.pe_payment_method_id.display_name or _('Sin medio de pago')
            totals[key][0 if line.amount > 0 else 1] += abs(line.amount)
        return sorted((name, amounts[0], amounts[1]) for name, amounts in totals.items())

    def _l10n_pe_summary_by_category(self):
        self.ensure_one()
        labels = dict(CATEGORIES)
        sale_labels = dict(SALE_KINDS)
        totals = defaultdict(float)
        for line in self.line_ids:
            label = labels[line.category]
            if line.sale_kind:
                label = '%s (%s)' % (label, sale_labels[line.sale_kind].lower())
            totals[label] += line.amount
        return sorted(totals.items())


class L10nPeCashClosingLine(models.Model):
    _name = 'l10n_pe.cash.closing.line'
    _description = 'Movimiento del cierre de caja'
    _check_company_auto = True
    _order = 'id'

    closing_id = fields.Many2one('l10n_pe.cash.closing', string='Cierre de caja', required=True, ondelete='cascade',
                                 index=True, check_company=True)
    company_id = fields.Many2one(related='closing_id.company_id', store=True)
    currency_id = fields.Many2one(related='closing_id.currency_id')
    move_id = fields.Many2one('account.move', string='Asiento', readonly=True)
    payment_id = fields.Many2one('account.payment', string='Pago', readonly=True, check_company=True)
    partner_id = fields.Many2one('res.partner', string='Socio', readonly=True)
    name = fields.Char(string='Concepto', readonly=True)
    category = fields.Selection(CATEGORIES, string='Tipo', readonly=True)
    sale_kind = fields.Selection(SALE_KINDS, string='Venta', readonly=True,
                                 help='Cobro de facturas del mismo día (contado) o de días anteriores.')
    pe_payment_method_id = fields.Many2one('pe.catalog.payment', string='Medio de pago', readonly=True)
    amount = fields.Monetary(string='Importe', currency_field='currency_id', readonly=True)


class L10nPeCashClosingCount(models.Model):
    _name = 'l10n_pe.cash.closing.count'
    _description = 'Arqueo por denominación'
    _check_company_auto = True
    _order = 'sequence, value desc, id'

    closing_id = fields.Many2one('l10n_pe.cash.closing', string='Cierre de caja', required=True, ondelete='cascade',
                                 index=True, check_company=True)
    company_id = fields.Many2one(related='closing_id.company_id', store=True)
    currency_id = fields.Many2one(related='closing_id.currency_id')
    denomination_id = fields.Many2one('l10n_pe.cash.denomination', string='Denominación', required=True)
    sequence = fields.Integer(related='denomination_id.sequence', store=True)
    value = fields.Float(related='denomination_id.value', store=True, string='Valor')
    kind = fields.Selection(related='denomination_id.kind', string='Tipo')
    quantity = fields.Integer(string='Cantidad')
    subtotal = fields.Monetary(string='Subtotal', currency_field='currency_id', compute='_compute_subtotal',
                               store=True)

    @api.depends('quantity', 'value')
    def _compute_subtotal(self):
        for count in self:
            count.subtotal = count.quantity * count.value

    @api.constrains('quantity')
    def _check_quantity(self):
        for count in self:
            if count.quantity < 0:
                raise ValidationError(_('La cantidad no puede ser negativa.'))
