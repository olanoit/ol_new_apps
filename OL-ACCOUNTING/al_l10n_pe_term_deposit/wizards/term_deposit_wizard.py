# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nPeTermDepositWizard(models.TransientModel):
    _name = 'l10n_pe.term.deposit.wizard'
    _description = 'Operación sobre un depósito o garantía'
    _check_company_auto = True

    deposit_id = fields.Many2one('l10n_pe.term.deposit', string='Depósito', required=True,
                                 check_company=True)
    operation = fields.Selection([
        ('close', 'Cancelar el depósito'),
        ('renew', 'Renovar el depósito'),
        ('release', 'Liberar la garantía'),
    ], string='Operación', required=True)
    company_id = fields.Many2one(related='deposit_id.company_id')
    currency_id = fields.Many2one(related='deposit_id.currency_id')
    deposit_type = fields.Selection(related='deposit_id.deposit_type')
    date = fields.Date(string='Fecha', required=True)
    remaining_amount = fields.Monetary(related='deposit_id.remaining_amount', string='Saldo')
    interest_due = fields.Monetary(string='Intereses a la fecha', compute='_compute_interest_due',
                                   help='Intereses devengados hasta la fecha que aún no se cobran.')
    interest_received = fields.Monetary(
        string='Intereses cobrados', compute='_compute_interest_received', store=True, readonly=False,
        help='Lo que abona el banco; si difiere de lo devengado (p. ej. por cancelación '
             'anticipada), la diferencia ajusta el ingreso por intereses.')
    amount = fields.Monetary(string='Importe a liberar')
    term_days = fields.Integer(string='Nuevo plazo (días)')
    rate = fields.Float(string='Nueva TEA (%)', digits=(6, 4))
    capitalize = fields.Boolean(string='Capitalizar intereses')
    penalty_amount = fields.Monetary(
        string='Penalidad',
        help='Lo que descuenta el banco por cancelar antes del vencimiento. Va a la cuenta de '
             'penalidad configurada o, si no hay, rebaja el ingreso por intereses.')
    itf_applies = fields.Boolean(related='deposit_id.itf_applies')
    itf_amount = fields.Monetary(
        string='ITF', compute='_compute_itf_amount', store=True, readonly=False,
        help='ITF del capital que vuelve al banco (los intereses están exonerados), propuesto '
             'con la tasa de Ajustes; corríjalo si el banco cobró otro importe.')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        deposit = self.env['l10n_pe.term.deposit'].browse(res.get('deposit_id') or
                                                         self.env.context.get('default_deposit_id'))
        if deposit:
            today = fields.Date.context_today(self)
            # Al vencimiento si ya pasó; si no, hoy (cancelación anticipada o liberación).
            res.setdefault('date', deposit.date_end if deposit.date_end and deposit.date_end <= today else today)
            res.setdefault('amount', deposit.remaining_amount)
            res.setdefault('term_days', deposit.term_days)
            res.setdefault('rate', deposit.rate)
            res.setdefault('capitalize', deposit.capitalize_interest)
        return res

    @api.depends('deposit_id', 'date')
    def _compute_interest_due(self):
        for wizard in self:
            deposit = wizard.deposit_id
            due = 0.0
            if deposit and wizard.date:
                due = deposit.currency_id.round(
                    max(deposit._l10n_pe_interest_until(wizard.date), deposit.interest_accrued)
                    - deposit.interest_collected)
            wizard.interest_due = due

    # Cálculo aparte: interest_received se guarda y es editable; interest_due no
    # (un mismo método para los dos hace que Odoo avise de 'store' inconsistente).
    @api.depends('deposit_id', 'date')
    def _compute_interest_received(self):
        for wizard in self:
            wizard.interest_received = wizard.interest_due

    @api.depends('deposit_id', 'operation', 'amount', 'interest_received', 'penalty_amount')
    def _compute_itf_amount(self):
        for wizard in self:
            deposit = wizard.deposit_id
            itf = 0.0
            # Solo el capital paga ITF: el abono de intereses está exonerado
            # (Informe SUNAT 025-2004-SUNAT/2B0000).
            if deposit and wizard.operation == 'close':
                itf = deposit._l10n_pe_itf(deposit.remaining_amount - wizard.penalty_amount)
            elif deposit and wizard.operation == 'release':
                itf = deposit._l10n_pe_itf(wizard.amount)
            wizard.itf_amount = itf

    def action_apply(self):
        self.ensure_one()
        deposit = self.deposit_id
        if deposit.state not in ('open', 'expired'):
            raise UserError(self.env._('El depósito %s no está vigente ni vencido.', deposit.name))
        if self.date < deposit.date_start or self.date > fields.Date.context_today(self):
            raise UserError(self.env._('La fecha debe estar entre la apertura y hoy.'))
        if self.operation == 'close':
            deposit._l10n_pe_close(self.date, self.interest_received, self.penalty_amount, self.itf_amount)
        elif self.operation == 'renew':
            new = deposit._l10n_pe_renew(self.date, self.term_days, self.rate, self.capitalize)
            return {'type': 'ir.actions.act_window', 'res_model': deposit._name, 'res_id': new.id,
                    'view_mode': 'form', 'target': 'current'}
        else:
            deposit._l10n_pe_release(self.date, self.amount, self.itf_amount)
        return {'type': 'ir.actions.act_window_close'}
