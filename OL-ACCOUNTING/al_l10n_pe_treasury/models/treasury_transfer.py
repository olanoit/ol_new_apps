# -*- coding: utf-8 -*-
"""Transferencias entre cuentas propias y operaciones de cambio.

Odoo 19 ya no tiene la transferencia interna como pago: el movimiento entre dos
cuentas se concilia contra la cuenta de transferencias de la compañía (1051 en
el plan peruano). Aquí la operación genera esos dos pagos (salida del origen y
entrada al destino, ambos contra la cuenta de transferencias), así cada uno se
concilia con su extracto y los módulos de la suite actúan sobre ellos (ITF,
T.C. pactado).

En una compra o venta de moneda extranjera, la parte en dólares se valoriza:

* **al T.C. pactado** (por defecto): los dos pagos valen lo mismo en soles y la
  cuenta de transferencias queda en cero;
* **al T.C. contable del día**: la diferencia en soles que queda en la cuenta de
  transferencias se lleva a 676 (pérdida) o 776 (ganancia) con un asiento que se
  concilia con los dos pagos.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

STATES = [
    ('draft', 'Borrador'),
    ('to_approve', 'Por aprobar'),
    ('approved', 'Aprobada'),
    ('done', 'Realizada'),
    ('cancel', 'Anulada'),
]
VALUATIONS = [
    ('agreed', 'Al T.C. pactado'),
    ('official', 'Al T.C. contable del día (diferencia a 676/776)'),
]


class L10nPeTreasuryTransfer(models.Model):
    _name = 'l10n_pe.treasury.transfer'
    _description = 'Transferencia entre cuentas propias'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'date desc, id desc'

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    state = fields.Selection(STATES, string='Estado', default='draft', required=True, readonly=True,
                             copy=False, tracking=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda de la compañía')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today, tracking=True)
    journal_from_id = fields.Many2one(
        'account.journal', string='Cuenta de origen', required=True, check_company=True, tracking=True,
        domain="[('type', 'in', ('bank', 'cash'))]")
    journal_to_id = fields.Many2one(
        'account.journal', string='Cuenta de destino', required=True, check_company=True, tracking=True,
        domain="[('type', 'in', ('bank', 'cash')), ('id', '!=', journal_from_id)]")
    currency_from_id = fields.Many2one('res.currency', string='Moneda de origen',
                                       compute='_compute_currencies', store=True)
    currency_to_id = fields.Many2one('res.currency', string='Moneda de destino',
                                     compute='_compute_currencies', store=True)
    is_exchange = fields.Boolean(string='Operación de cambio', compute='_compute_currencies', store=True)
    exchange_type = fields.Selection(
        [('buy', 'Compra de moneda extranjera'), ('sell', 'Venta de moneda extranjera'),
         ('cross', 'Entre monedas extranjeras')],
        string='Operación', compute='_compute_currencies', store=True)
    amount = fields.Monetary(string='Importe enviado', currency_field='currency_from_id', required=True,
                             tracking=True)
    amount_to = fields.Monetary(string='Importe recibido', currency_field='currency_to_id',
                                compute='_compute_amount_to', store=True, readonly=False, tracking=True,
                                help='En la misma moneda, igual al enviado. En una operación de cambio, '
                                     'lo que entra a la cuenta de destino según el T.C. pactado.')
    agreed_rate = fields.Float(
        string='T.C. pactado', digits=(12, 4), tracking=True,
        help='Soles por unidad de la moneda extranjera acordados con el banco o la casa de cambio.')
    official_rate = fields.Float(string='T.C. contable', digits=(12, 4), compute='_compute_official_rate',
                                 help='Tipo de cambio de la contabilidad a la fecha.')
    valuation = fields.Selection(VALUATIONS, string='Valorización', required=True, default='agreed',
                                 help='Cómo se valoriza en soles la parte en moneda extranjera.')
    counterpart_id = fields.Many2one(
        'res.partner', string='Banco o casa de cambio', check_company=True,
        help='Con quién se pactó el tipo de cambio (informativo).')
    reference = fields.Char(string='N.º de operación', tracking=True)
    memo = fields.Char(string='Concepto')
    itf_from = fields.Boolean(
        string='ITF en el origen',
        help='Las transferencias entre cuentas del mismo titular no están gravadas con el ITF '
             '(Informe SUNAT 143-2010). Márquelo si el banco lo cobró.')
    itf_to = fields.Boolean(string='ITF en el destino', help='Ídem para el abono en la cuenta de destino.')
    user_id = fields.Many2one('res.users', string='Preparado por', default=lambda self: self.env.user,
                              readonly=True, copy=False)
    approved_by_id = fields.Many2one('res.users', string='Aprobado por', readonly=True, copy=False)
    needs_approval = fields.Boolean(string='Requiere aprobación', compute='_compute_needs_approval')
    amount_company = fields.Monetary(string='Importe (S/)', currency_field='company_currency_id',
                                     compute='_compute_amount_company', store=True)
    payment_from_id = fields.Many2one('account.payment', string='Pago de salida', readonly=True, copy=False,
                                      check_company=True)
    payment_to_id = fields.Many2one('account.payment', string='Cobro de entrada', readonly=True, copy=False,
                                    check_company=True)
    exchange_move_id = fields.Many2one('account.move', string='Diferencia de cambio', readonly=True,
                                       copy=False, check_company=True)
    exchange_difference = fields.Monetary(string='Diferencia de cambio (S/)', currency_field='company_currency_id',
                                          readonly=True, copy=False,
                                          help='Positiva: ganancia (776). Negativa: pérdida (676).')

    _positive_amount = models.Constraint('CHECK(amount > 0)', 'El importe enviado debe ser mayor que cero.')

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------
    @api.depends('journal_from_id', 'journal_to_id')
    def _compute_currencies(self):
        for transfer in self:
            company_currency = transfer.company_id.currency_id
            source = transfer.journal_from_id._l10n_pe_treasury_currency() if transfer.journal_from_id else company_currency
            target = transfer.journal_to_id._l10n_pe_treasury_currency() if transfer.journal_to_id else company_currency
            transfer.currency_from_id = source
            transfer.currency_to_id = target
            transfer.is_exchange = source != target
            if source == target:
                transfer.exchange_type = False
            elif source == company_currency:
                transfer.exchange_type = 'buy'
            elif target == company_currency:
                transfer.exchange_type = 'sell'
            else:
                transfer.exchange_type = 'cross'

    @api.depends('amount', 'agreed_rate', 'is_exchange', 'exchange_type')
    def _compute_amount_to(self):
        for transfer in self:
            if not transfer.is_exchange:
                transfer.amount_to = transfer.amount
            elif transfer.agreed_rate and transfer.exchange_type == 'buy':
                transfer.amount_to = transfer.currency_to_id.round(transfer.amount / transfer.agreed_rate)
            elif transfer.agreed_rate and transfer.exchange_type == 'sell':
                transfer.amount_to = transfer.currency_to_id.round(transfer.amount * transfer.agreed_rate)
            else:
                transfer.amount_to = transfer.amount_to

    @api.onchange('amount_to')
    def _onchange_amount_to(self):
        # Quien registra lo que el banco abonó recalcula el T.C. pactado.
        if self.is_exchange and self.amount and self.amount_to and self.exchange_type in ('buy', 'sell'):
            rate = self.amount / self.amount_to if self.exchange_type == 'buy' else self.amount_to / self.amount
            if abs(rate - (self.agreed_rate or 0.0)) >= 0.00005:
                self.agreed_rate = round(rate, 4)

    @api.depends('currency_from_id', 'currency_to_id', 'date', 'exchange_type')
    def _compute_official_rate(self):
        for transfer in self:
            foreign = transfer._l10n_pe_foreign_currency()
            company = transfer.company_id
            transfer.official_rate = foreign._convert(
                1.0, company.currency_id, company, transfer.date or fields.Date.context_today(transfer),
                round=False) if foreign else 0.0

    def _l10n_pe_foreign_currency(self):
        self.ensure_one()
        if self.exchange_type == 'buy':
            return self.currency_to_id
        if self.exchange_type == 'sell':
            return self.currency_from_id
        return self.env['res.currency']

    @api.depends('amount', 'currency_from_id', 'date', 'agreed_rate', 'exchange_type')
    def _compute_amount_company(self):
        for transfer in self:
            company = transfer.company_id
            if transfer.currency_from_id == company.currency_id or not transfer.currency_from_id:
                transfer.amount_company = transfer.amount
            elif transfer.exchange_type == 'sell' and transfer.agreed_rate:
                transfer.amount_company = company.currency_id.round(transfer.amount * transfer.agreed_rate)
            else:
                transfer.amount_company = transfer.currency_from_id._convert(
                    transfer.amount, company.currency_id, company, transfer.date or fields.Date.context_today(transfer))

    @api.depends('amount_company', 'company_id.l10n_pe_treasury_transfer_approval_amount')
    def _compute_needs_approval(self):
        for transfer in self:
            threshold = transfer.company_id.l10n_pe_treasury_transfer_approval_amount
            transfer.needs_approval = bool(threshold) and \
                transfer.company_id.currency_id.compare_amounts(transfer.amount_company, threshold) >= 0

    @api.constrains('journal_from_id', 'journal_to_id')
    def _check_journals(self):
        for transfer in self:
            if transfer.journal_from_id == transfer.journal_to_id:
                raise ValidationError(self.env._('El origen y el destino deben ser cuentas distintas.'))

    @api.constrains('agreed_rate', 'exchange_type')
    def _check_agreed_rate(self):
        for transfer in self:
            if transfer.exchange_type in ('buy', 'sell') and transfer.agreed_rate < 0:
                raise ValidationError(self.env._('El T.C. pactado no puede ser negativo.'))

    # ------------------------------------------------------------------
    # Flujo
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('l10n_pe.treasury.transfer') or '/'
        return super().create(vals_list)

    def unlink(self):
        if self.filtered(lambda t: t.state not in ('draft', 'cancel')):
            raise UserError(self.env._('Solo se eliminan transferencias en borrador o anuladas.'))
        return super().unlink()

    def _check_state(self, states):
        for transfer in self:
            if transfer.state not in states:
                raise UserError(self.env._('La operación %(name)s está en estado «%(state)s».', name=transfer.name,
                                           state=dict(STATES)[transfer.state]))

    def _check_ready(self):
        for transfer in self:
            if transfer.currency_from_id.compare_amounts(transfer.amount, 0.0) <= 0 or \
                    transfer.currency_to_id.compare_amounts(transfer.amount_to, 0.0) <= 0:
                raise UserError(self.env._('Indique el importe enviado y el recibido.'))
            if transfer.exchange_type in ('buy', 'sell') and not transfer.agreed_rate:
                raise UserError(self.env._('Indique el T.C. pactado de la operación de cambio.'))
            if not transfer.company_id.transfer_account_id:
                raise UserError(self.env._(
                    'Configure la cuenta de transferencias internas en Contabilidad ▸ Ajustes (PCGE 1051).'))

    def action_confirm(self):
        """Envía a aprobar o, si no hace falta, realiza la operación."""
        self._check_state(('draft',))
        self._check_ready()
        for transfer in self:
            if transfer.needs_approval:
                transfer.state = 'to_approve'
                transfer._l10n_pe_request_approval()
            else:
                transfer.state = 'approved'
                transfer._l10n_pe_execute()
        return True

    def _l10n_pe_request_approval(self):
        # sudo: quien prepara no puede leer las compañías de los demás usuarios;
        # solo se usan para elegir a quién asignar la actividad de aprobación.
        group_sudo = self.env.ref('al_l10n_pe_treasury.group_treasury_approver').sudo()
        for transfer in self:
            approvers = group_sudo.all_user_ids.filtered(
                lambda u: transfer.company_id in u.company_ids and u != transfer.user_id and not u.share)
            for approver in approvers[:5]:
                transfer.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=approver.id,
                    summary=self.env._('Aprobar %s', transfer.name),
                    note=self.env._('Transferencia de %(amount)s %(currency)s de %(origin)s a %(target)s.',
                                    amount=transfer.amount, currency=transfer.currency_from_id.name,
                                    origin=transfer.journal_from_id.name, target=transfer.journal_to_id.name))

    def action_approve(self):
        self._check_state(('to_approve',))
        if not self.env.user.has_group('al_l10n_pe_treasury.group_treasury_approver'):
            raise UserError(self.env._('Solo un aprobador de tesorería puede aprobar la operación.'))
        for transfer in self:
            if transfer.user_id == self.env.user and not self.env.su:
                raise UserError(self.env._('Quien prepara la operación no puede aprobarla.'))
            transfer.write({'state': 'approved', 'approved_by_id': self.env.user.id})
            transfer.activity_ids.action_done()
            transfer._l10n_pe_execute()
        return True

    def action_reject(self):
        self._check_state(('to_approve',))
        self.write({'state': 'draft'})
        self.activity_ids.unlink()
        for transfer in self:
            transfer.message_post(body=self.env._('Devuelta a borrador por %s.', self.env.user.name))
        return True

    def _l10n_pe_payment_vals(self, journal, payment_type, amount, currency, itf):
        self.ensure_one()
        method_lines = journal._get_available_payment_method_lines(payment_type)
        if not method_lines:
            raise UserError(self.env._('El diario %s no tiene un método de pago para esta operación.',
                                       journal.display_name))
        vals = {
            'payment_type': payment_type,
            'partner_type': 'supplier' if payment_type == 'outbound' else 'customer',
            'partner_id': self.company_id.partner_id.id,
            'journal_id': journal.id,
            'payment_method_line_id': method_lines[:1].id,
            'amount': amount,
            'currency_id': currency.id,
            'date': self.date,
            'memo': self.memo or self.env._('Transferencia %s', self.name),
            'destination_account_id': self.company_id.transfer_account_id.id,
            'l10n_pe_treasury_transfer_id': self.id,
            'l10n_pe_itf_exempt': not itf,
            'bank_operation_number': self.reference,
        }
        foreign = self._l10n_pe_foreign_currency()
        if self.valuation == 'agreed' and foreign and currency == foreign:
            vals['l10n_pe_agreed_rate'] = self.agreed_rate
        return vals

    def _l10n_pe_execute(self):
        """Crea, confirma y concilia los dos pagos (y la diferencia de cambio)."""
        Payment = self.env['account.payment']
        for transfer in self:
            payment_from = Payment.create(transfer._l10n_pe_payment_vals(
                transfer.journal_from_id, 'outbound', transfer.amount, transfer.currency_from_id, transfer.itf_from))
            payment_to = Payment.create(transfer._l10n_pe_payment_vals(
                transfer.journal_to_id, 'inbound', transfer.amount_to, transfer.currency_to_id, transfer.itf_to))
            transfer_account = transfer.company_id.transfer_account_id
            if transfer_account in (payment_from | payment_to).outstanding_account_id:
                raise UserError(self.env._(
                    'Los métodos de pago de %s no tienen cuenta de pagos o cobros pendientes y Odoo usaría '
                    'la cuenta de transferencias: indíquela en el diario (pestañas de pagos entrantes y '
                    'salientes).', ', '.join((payment_from | payment_to).filtered(
                        lambda p: p.outstanding_account_id == transfer_account).journal_id.mapped('name'))))
            (payment_from | payment_to).action_post()
            if not payment_from.move_id or not payment_to.move_id:
                raise UserError(self.env._(
                    'Los diarios de una transferencia necesitan cuenta de pagos y cobros pendientes en sus '
                    'métodos de pago: sin ella Odoo no registra el asiento hasta conciliar el extracto.'))
            transfer.write({'payment_from_id': payment_from.id, 'payment_to_id': payment_to.id, 'state': 'done'})
            transfer._l10n_pe_reconcile_transfer_lines()
            transfer.message_post(body=self.env._('Realizada: %(outbound)s y %(inbound)s.',
                                                  outbound=payment_from._get_html_link(),
                                                  inbound=payment_to._get_html_link()))
        return True

    def _l10n_pe_transfer_lines(self):
        self.ensure_one()
        account = self.company_id.transfer_account_id
        moves = self.payment_from_id.move_id | self.payment_to_id.move_id | self.exchange_move_id
        return moves.line_ids.filtered(lambda line: line.account_id == account)

    def _l10n_pe_reconcile_transfer_lines(self):
        """Lleva la diferencia en soles de la cuenta de transferencias a 676/776 y
        concilia los apuntes si la cuenta es conciliable."""
        self.ensure_one()
        company = self.company_id
        lines = self._l10n_pe_transfer_lines()
        residual = company.currency_id.round(sum(lines.mapped('balance')))
        if not company.currency_id.is_zero(residual):
            # Saldo deudor en la cuenta de transferencias: salió más (en soles) de lo
            # que entró → pérdida; saldo acreedor → ganancia.
            if residual > 0:
                account = company.expense_currency_exchange_account_id
            else:
                account = company.income_currency_exchange_account_id
            journal = company.currency_exchange_journal_id
            if not account or not journal:
                raise UserError(self.env._(
                    'Configure el diario y las cuentas de diferencia de cambio en Contabilidad ▸ Ajustes.'))
            label = self.env._('Diferencia de cambio %s', self.name)
            move = self.env['account.move'].create({
                'move_type': 'entry', 'journal_id': journal.id, 'date': self.date, 'ref': label,
                'line_ids': [
                    fields.Command.create({'name': label, 'account_id': company.transfer_account_id.id,
                                           'partner_id': company.partner_id.id, 'balance': -residual,
                                           'currency_id': company.currency_id.id, 'amount_currency': -residual}),
                    fields.Command.create({'name': label, 'account_id': account.id, 'balance': residual,
                                           'currency_id': company.currency_id.id, 'amount_currency': residual}),
                ],
            })
            move.action_post()
            self.write({'exchange_move_id': move.id, 'exchange_difference': -residual})
            lines = self._l10n_pe_transfer_lines()
        if company.transfer_account_id.reconcile:
            lines.filtered(lambda line: not line.reconciled).with_context(no_exchange_difference=True).reconcile()

    def action_cancel(self):
        """Anula la operación: los pagos vuelven a borrador y se anulan; la
        diferencia de cambio se revierte."""
        self._check_state(('draft', 'to_approve', 'approved', 'done'))
        for transfer in self:
            payments = transfer.payment_from_id | transfer.payment_to_id
            if payments.filtered('is_matched'):
                raise UserError(self.env._('No se anula una transferencia con pagos conciliados con el extracto.'))
            payments.move_id.line_ids.remove_move_reconcile()
            if transfer.exchange_move_id.state == 'posted':
                transfer.exchange_move_id._reverse_moves(cancel=True)
            payments.filtered(lambda p: p.state != 'draft').action_draft()
            payments.action_cancel()
            transfer.activity_ids.unlink()
            transfer.state = 'cancel'
        return True

    def action_draft(self):
        self._check_state(('cancel',))
        self.write({'state': 'draft', 'payment_from_id': False, 'payment_to_id': False,
                    'exchange_move_id': False, 'exchange_difference': 0.0, 'approved_by_id': False})
        return True

    def action_open_payments(self):
        self.ensure_one()
        payments = self.payment_from_id | self.payment_to_id
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Pagos'),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', payments.ids)],
            'context': {'create': False},
        }
