# -*- coding: utf-8 -*-
"""Rendición de un fondo: los comprobantes pagados con el dinero del fondo
y la planilla de gastos de movilidad.

Al confirmarla, un asiento carga la cuenta por pagar de cada comprobante (y
lo deja pagado) y el gasto de movilidad, y abona la cuenta del fondo.
"""
from collections import defaultdict

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError


class L10nPeCashSettlement(models.Model):
    _name = 'l10n_pe.cash.settlement'
    _description = 'Rendición de entrega a rendir o caja chica'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', default='/', readonly=True, copy=False, tracking=True)
    fund_id = fields.Many2one(
        'l10n_pe.cash.fund', string='Fondo', required=True, index=True, check_company=True,
        domain="[('state', '=', 'open')]", tracking=True)
    fund_type = fields.Selection(related='fund_id.fund_type', string='Tipo')
    partner_id = fields.Many2one(related='fund_id.partner_id', string='Responsable')
    company_id = fields.Many2one(related='fund_id.company_id', string='Compañía', store=True,
                                 index=True)
    currency_id = fields.Many2one(related='fund_id.currency_id', string='Moneda')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today,
                       tracking=True)
    state = fields.Selection(
        [('draft', 'Borrador'), ('posted', 'Confirmada'), ('cancel', 'Anulada')],
        string='Estado', default='draft', required=True, tracking=True, copy=False)
    move_id = fields.Many2one('account.move', string='Asiento', readonly=True, copy=False,
                              check_company=True)
    document_line_ids = fields.One2many(
        'l10n_pe.cash.settlement.document', 'settlement_id', string='Comprobantes', copy=True)
    mobility_line_ids = fields.One2many(
        'l10n_pe.cash.settlement.mobility', 'settlement_id', string='Planilla de movilidad',
        copy=True)
    amount_documents = fields.Monetary(string='Comprobantes', compute='_compute_amounts',
                                       store=True)
    amount_mobility = fields.Monetary(string='Movilidad', compute='_compute_amounts', store=True)
    amount_total = fields.Monetary(string='Total rendido', compute='_compute_amounts', store=True)
    amount_mobility_excess = fields.Monetary(
        string='Movilidad sobre el tope', compute='_compute_mobility_excess',
        help='Exceso del tope diario por trabajador (4 % de la RMV): no es deducible para el '
             'Impuesto a la Renta (art. 37 a1 de la Ley).')
    mobility_number = fields.Char(
        string='Número de planilla', readonly=True, copy=False,
        help='Correlativo de la planilla de gastos de movilidad (requisito del art. 21 inciso '
             'v del Reglamento de la Ley del Impuesto a la Renta).')
    note = fields.Text(string='Notas')

    @api.depends('document_line_ids.amount', 'mobility_line_ids.amount')
    def _compute_amounts(self):
        for settlement in self:
            settlement.amount_documents = sum(settlement.document_line_ids.mapped('amount'))
            settlement.amount_mobility = sum(settlement.mobility_line_ids.mapped('amount'))
            settlement.amount_total = settlement.amount_documents + settlement.amount_mobility

    @api.depends('mobility_line_ids.amount', 'mobility_line_ids.date', 'company_id')
    def _compute_mobility_excess(self):
        for settlement in self:
            limit = settlement.company_id._l10n_pe_mobility_daily_limit() \
                if settlement.company_id else 0.0
            by_day = defaultdict(float)
            for line in settlement.mobility_line_ids:
                by_day[line.date] += line.amount
            settlement.amount_mobility_excess = sum(
                max(0.0, total - limit) for total in by_day.values()) if limit else 0.0

    @api.depends('name', 'fund_id')
    def _compute_display_name(self):
        for settlement in self:
            settlement.display_name = settlement.name if settlement.name != '/' else \
                self.env._('Rendición de %s', settlement.fund_id.display_name or '')

    # ------------------------------------------------------------------
    # Flujo
    # ------------------------------------------------------------------
    def action_post(self):
        for settlement in self:
            if settlement.state != 'draft':
                raise UserError(self.env._('La rendición %s ya está confirmada o anulada.',
                                           settlement.display_name))
            if settlement.fund_id.state != 'open':
                raise UserError(self.env._('El fondo %s no está entregado.',
                                           settlement.fund_id.display_name))
            if not settlement.document_line_ids and not settlement.mobility_line_ids:
                raise UserError(self.env._('La rendición no tiene comprobantes ni movilidad.'))
            settlement.document_line_ids._check_documents()
            move = self.env['account.move'].create(settlement._prepare_move_vals())
            move.action_post()
            settlement.move_id = move
            settlement._reconcile_documents()
            sequence = self.env['ir.sequence'].with_company(settlement.company_id)
            # Una rendición anulada y vuelta a confirmar conserva su número.
            if settlement.name in (False, '/'):
                settlement.name = sequence.next_by_code(
                    'l10n_pe.cash.settlement', sequence_date=settlement.date) or '/'
            if settlement.mobility_line_ids and not settlement.mobility_number:
                settlement.mobility_number = sequence.next_by_code(
                    'l10n_pe.cash.mobility', sequence_date=settlement.date) or False
            settlement.state = 'posted'
            settlement.fund_id._reconcile_fund_lines()

    def action_cancel(self):
        for settlement in self:
            if settlement.fund_id.state == 'closed':
                raise UserError(self.env._(
                    'El fondo %s está cerrado: reábralo antes de anular la rendición.',
                    settlement.fund_id.display_name))
            move = settlement.move_id
            if move:
                move.line_ids.remove_move_reconcile()
                move.button_draft()
                move.button_cancel()
            settlement.state = 'cancel'

    def action_draft(self):
        if any(settlement.state != 'cancel' for settlement in self):
            raise UserError(self.env._('Solo una rendición anulada vuelve a borrador.'))
        self.write({'state': 'draft', 'move_id': False})

    def unlink(self):
        if any(settlement.state == 'posted' for settlement in self):
            raise UserError(self.env._('Anule la rendición antes de borrarla.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Asiento
    # ------------------------------------------------------------------
    def _prepare_move_vals(self):
        self.ensure_one()
        fund = self.fund_id
        company = self.company_id
        journal = company._l10n_pe_cash_settlement_journal()
        if not journal:
            raise UserError(self.env._('Configure el diario de rendiciones en Ajustes.'))
        currency = self.currency_id
        lines = []

        def amounts(amount_currency):
            balance = currency._convert(amount_currency, company.currency_id, company, self.date)
            return {'amount_currency': amount_currency, 'balance': balance,
                    'currency_id': currency.id}

        for doc in self.document_line_ids:
            payable = doc._payable_line()
            lines.append(Command.create(dict(
                amounts(doc.amount), name=self.env._('Pago de %s con %s', doc.move_id.name, fund.name),
                account_id=payable.account_id.id, partner_id=payable.partner_id.id)))
        if self.mobility_line_ids:
            account = company._l10n_pe_mobility_account()
            if not account:
                raise UserError(self.env._(
                    'Configure la cuenta de gastos de movilidad en Ajustes ▸ Perú.'))
            for mobility in self.mobility_line_ids:
                lines.append(Command.create(dict(
                    amounts(mobility.amount),
                    name=self.env._('Movilidad %(date)s: %(reason)s', date=mobility.date,
                                    reason=mobility.reason),
                    account_id=account.id, partner_id=fund.partner_id.id,
                    analytic_distribution=mobility.analytic_distribution)))
        # El abono al fondo cierra el asiento: su saldo en soles es la suma de
        # los cargos (sin diferencias de redondeo de la conversión).
        lines.append(Command.create({
            'name': self.env._('Rendición de %s', fund.name),
            'account_id': fund.account_id.id, 'partner_id': fund.partner_id.id,
            'currency_id': currency.id, 'amount_currency': -self.amount_total,
            'balance': -sum(line[2]['balance'] for line in lines),
        }))
        return {
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': self.date,
            'ref': self.env._('Rendición de %(fund)s · %(purpose)s', fund=fund.name,
                              purpose=fund.purpose),
            'line_ids': lines,
        }

    def _reconcile_documents(self):
        """Deja pagado cada comprobante: su cuenta por pagar contra la línea
        de la rendición (parcial si se rindió una parte)."""
        self.ensure_one()
        debit_lines = self.move_id.line_ids.filtered(lambda l: l.balance > 0)
        for doc in self.document_line_ids:
            payable = doc._payable_line()
            mine = debit_lines.filtered(
                lambda l: l.account_id == payable.account_id and l.partner_id == payable.partner_id
                and not l.reconciled)[:1]
            if mine:
                (payable | mine).reconcile()

    def action_print_mobility(self):
        return self.env.ref('al_l10n_pe_cash_fund.action_report_mobility_sheet').report_action(self)


class L10nPeCashSettlementDocument(models.Model):
    _name = 'l10n_pe.cash.settlement.document'
    _description = 'Comprobante de una rendición'
    _check_company_auto = True

    settlement_id = fields.Many2one('l10n_pe.cash.settlement', string='Rendición', required=True,
                                    ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(related='settlement_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='settlement_id.currency_id')
    move_id = fields.Many2one(
        'account.move', string='Comprobante', required=True, check_company=True,
        domain="[('move_type', '=', 'in_invoice'), ('state', '=', 'posted'), "
               "('payment_state', 'in', ('not_paid', 'partial')), ('currency_id', '=', currency_id)]",
        help='Factura, boleta o recibo por honorarios del proveedor, ya registrado y publicado.')
    partner_id = fields.Many2one(related='move_id.partner_id', string='Proveedor')
    invoice_date = fields.Date(related='move_id.invoice_date', string='Fecha del comprobante')
    amount_residual = fields.Monetary(related='move_id.amount_residual', string='Saldo')
    amount = fields.Monetary(
        string='Monto rendido', compute='_compute_amount', store=True, readonly=False,
        help='Lo pagado con el fondo; por defecto, el saldo del comprobante.')

    @api.depends('move_id')
    def _compute_amount(self):
        for line in self:
            line.amount = line.move_id.amount_residual

    def _payable_line(self):
        self.ensure_one()
        return self.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == 'liability_payable' and not l.reconciled)[:1]

    def _check_documents(self):
        for line in self:
            move = line.move_id
            if move.currency_id != line.currency_id:
                raise ValidationError(self.env._(
                    'El comprobante %(doc)s está en %(cur)s y el fondo en %(fund)s: ríndalo en un '
                    'fondo de la misma moneda.', doc=move.name, cur=move.currency_id.name,
                    fund=line.currency_id.name))
            if not line._payable_line():
                raise ValidationError(self.env._('El comprobante %s ya está pagado.', move.name))
            if line.currency_id.compare_amounts(line.amount, 0.0) <= 0 \
                    or line.currency_id.compare_amounts(line.amount, move.amount_residual) > 0:
                raise ValidationError(self.env._(
                    'El monto rendido de %s debe ser mayor que cero y no superar su saldo.',
                    move.name))
        moves = self.mapped('move_id')
        if len(moves) != len(self):
            raise ValidationError(self.env._('Un comprobante aparece dos veces en la rendición.'))


class L10nPeCashSettlementMobility(models.Model):
    _name = 'l10n_pe.cash.settlement.mobility'
    _description = 'Gasto de movilidad de una rendición'
    _inherit = ['analytic.mixin']
    _order = 'date, id'
    _check_company_auto = True

    settlement_id = fields.Many2one('l10n_pe.cash.settlement', string='Rendición', required=True,
                                    ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(related='settlement_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='settlement_id.currency_id')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    reason = fields.Char(string='Motivo', required=True)
    destination = fields.Char(string='Destino', required=True,
                              help='Lugar o trayecto del desplazamiento.')
    amount = fields.Monetary(string='Monto', required=True)

    _amount_positive = models.Constraint('CHECK(amount > 0)',
                                         'El monto de movilidad debe ser mayor que cero.')
