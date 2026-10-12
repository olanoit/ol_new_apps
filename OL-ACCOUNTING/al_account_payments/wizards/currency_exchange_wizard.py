# -*- coding: utf-8 -*-
"""Compra y venta de moneda entre dos cuentas de la empresa.

El banco aplica su tipo de cambio (compra o venta); la contabilidad usa el de
Odoo (el de SUNAT con la localización). Se registran dos pagos por la cuenta
de transferencias de liquidez —uno que sale de la cuenta de origen y otro que
entra en la de destino, conciliables cada uno con su extracto— y la diferencia
entre ambos tipos de cambio queda como ganancia o pérdida por diferencia de
cambio.
"""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class L10nPeCurrencyExchangeWizard(models.TransientModel):
    _name = 'l10n_pe.currency.exchange.wizard'
    _description = 'Compra y venta de moneda'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Compañía', required=True,
                                 default=lambda self: self.env.company)
    journal_from_id = fields.Many2one(
        'account.journal', string='Sale de', required=True, check_company=True,
        domain="[('type', 'in', ('bank', 'cash'))]")
    journal_to_id = fields.Many2one(
        'account.journal', string='Entra a', required=True, check_company=True,
        domain="[('type', 'in', ('bank', 'cash')), ('id', '!=', journal_from_id)]")
    currency_from_id = fields.Many2one('res.currency', string='Moneda de origen',
                                       compute='_compute_currencies')
    currency_to_id = fields.Many2one('res.currency', string='Moneda de destino',
                                     compute='_compute_currencies')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    amount_from = fields.Monetary(string='Monto que sale', currency_field='currency_from_id',
                                  required=True)
    bank_rate = fields.Float(
        string='Tipo de cambio del banco', digits=(12, 6), required=True,
        help='Soles por unidad de la moneda extranjera que aplicó el banco.')
    amount_to = fields.Monetary(
        string='Monto que entra', currency_field='currency_to_id', compute='_compute_amount_to',
        store=True, readonly=False)
    system_rate = fields.Float(string='Tipo de cambio del sistema', digits=(12, 6),
                               compute='_compute_difference')
    difference = fields.Monetary(
        string='Diferencia de cambio', currency_field='company_currency_id',
        compute='_compute_difference',
        help='Positiva: ganancia; negativa: pérdida, frente al tipo de cambio del sistema.')
    company_currency_id = fields.Many2one(related='company_id.currency_id')
    bank_operation_number = fields.Char(string='Número de operación banco')
    memo = fields.Char(string='Glosa')

    @api.depends('journal_from_id', 'journal_to_id')
    def _compute_currencies(self):
        for wizard in self:
            company_currency = wizard.company_id.currency_id
            wizard.currency_from_id = wizard.journal_from_id.currency_id or company_currency
            wizard.currency_to_id = wizard.journal_to_id.currency_id or company_currency

    @api.depends('amount_from', 'bank_rate', 'currency_from_id', 'currency_to_id')
    def _compute_amount_to(self):
        for wizard in self:
            company_currency = wizard.company_id.currency_id
            rate = wizard.bank_rate
            if not rate or wizard.currency_from_id == wizard.currency_to_id:
                wizard.amount_to = wizard.amount_from
            elif wizard.currency_from_id == company_currency:
                wizard.amount_to = wizard.currency_to_id.round(wizard.amount_from / rate)
            else:
                wizard.amount_to = wizard.currency_to_id.round(wizard.amount_from * rate)

    @api.depends('amount_from', 'amount_to', 'date', 'currency_from_id', 'currency_to_id')
    def _compute_difference(self):
        for wizard in self:
            company = wizard.company_id
            to_company = lambda amount, currency: currency._convert(
                amount, company.currency_id, company, wizard.date or fields.Date.today())
            foreign = wizard.currency_to_id if wizard.currency_from_id == company.currency_id \
                else wizard.currency_from_id
            wizard.system_rate = to_company(1.0, foreign) if foreign != company.currency_id else 1.0
            if not wizard.currency_from_id or not wizard.currency_to_id:
                wizard.difference = 0.0
                continue
            wizard.difference = company.currency_id.round(
                to_company(wizard.amount_to, wizard.currency_to_id)
                - to_company(wizard.amount_from, wizard.currency_from_id))

    def _prepare_payment(self, journal, amount, currency, payment_type):
        self.ensure_one()
        company = self.company_id
        return {
            'payment_type': payment_type,
            'partner_type': 'supplier' if payment_type == 'outbound' else 'customer',
            'partner_id': company.partner_id.id,
            'journal_id': journal.id,
            'company_id': company.id,
            'amount': amount,
            'currency_id': currency.id,
            'date': self.date,
            'memo': self.memo or self.env._('Compra y venta de moneda'),
            'bank_operation_number': self.bank_operation_number,
            'destination_account_id': company.transfer_account_id.id,
        }

    def action_confirm(self):
        self.ensure_one()
        company = self.company_id
        if self.currency_from_id == self.currency_to_id:
            raise UserError(self.env._('Las dos cuentas están en la misma moneda: no es una '
                                       'compra o venta de moneda.'))
        if company.currency_id not in (self.currency_from_id | self.currency_to_id):
            raise UserError(self.env._('Una de las dos cuentas debe estar en %s.',
                                       company.currency_id.name))
        if self.amount_from <= 0 or self.amount_to <= 0 or self.bank_rate <= 0:
            raise UserError(self.env._('Indique los montos y el tipo de cambio del banco.'))
        transfer = company.transfer_account_id
        if not transfer:
            raise UserError(self.env._('Configure la cuenta de transferencias de liquidez de la '
                                       'compañía.'))
        Payment = self.env['account.payment'].with_context(force_payment_move=True)
        payments = Payment.create([
            self._prepare_payment(self.journal_from_id, self.amount_from, self.currency_from_id,
                                  'outbound'),
            self._prepare_payment(self.journal_to_id, self.amount_to, self.currency_to_id,
                                  'inbound'),
        ])
        payments.action_post()
        lines = payments.move_id.line_ids.filtered(lambda l: l.account_id == transfer)
        residual = sum(lines.mapped('balance'))
        if not company.currency_id.is_zero(residual):
            exchange = self.env['account.move'].create(self._prepare_exchange_move(residual))
            exchange.action_post()
            lines |= exchange.line_ids.filtered(lambda l: l.account_id == transfer)
        if transfer.reconcile:
            lines.reconcile()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Compra y venta de moneda'),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', payments.ids)],
        }

    def _prepare_exchange_move(self, residual):
        """Cierra la cuenta de transferencias: residual deudor (salió más en
        soles de lo que entró) es pérdida; acreedor, ganancia."""
        company = self.company_id
        loss = residual > 0
        account = company.expense_currency_exchange_account_id if loss \
            else company.income_currency_exchange_account_id
        if not account:
            raise UserError(self.env._('Configure las cuentas de diferencia de cambio de la '
                                       'compañía.'))
        journal = company.currency_exchange_journal_id or self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(company),
            ('type', '=', 'general')], limit=1)
        label = self.env._('Diferencia de cambio en la compra y venta de moneda (T.C. banco %s)',
                           self.bank_rate)
        return {
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': self.date,
            'ref': label,
            'line_ids': [
                Command.create({'name': label, 'account_id': account.id, 'balance': residual}),
                Command.create({'name': label, 'account_id': company.transfer_account_id.id,
                                'balance': -residual}),
            ],
        }
