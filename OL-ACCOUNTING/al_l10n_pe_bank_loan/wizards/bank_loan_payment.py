# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nPeBankLoanPayment(models.TransientModel):
    _name = 'l10n_pe.bank.loan.payment'
    _description = 'Pago de cuota o prepago de préstamo'

    loan_id = fields.Many2one('l10n_pe.bank.loan', string='Préstamo', required=True)
    currency_id = fields.Many2one(related='loan_id.currency_id')
    operation = fields.Selection([('installment', 'Pagar cuota'), ('prepay', 'Prepagar capital')],
                                 string='Operación', required=True, default='installment')
    line_id = fields.Many2one('l10n_pe.bank.loan.line', string='Cuota', domain="[('loan_id', '=', loan_id)]")
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    principal = fields.Monetary(string='Capital', compute='_compute_amounts', store=True, readonly=False)
    interest = fields.Monetary(string='Interés', compute='_compute_amounts', store=True, readonly=False,
                               help='Interés que cobró el banco; la diferencia con el cronograma va al gasto.')
    insurance = fields.Monetary(string='Seguro', compute='_compute_amounts', store=True, readonly=False)
    fee = fields.Monetary(string='Comisión', compute='_compute_amounts', store=True, readonly=False)
    prepay_mode = fields.Selection([('installment', 'Reducir la cuota'), ('term', 'Reducir el plazo')],
                                   string='Después del prepago', default='installment')
    total = fields.Monetary(string='Total', compute='_compute_total')

    @api.depends('line_id', 'operation', 'date')
    def _compute_amounts(self):
        for wizard in self:
            line = wizard.line_id
            if wizard.operation == 'installment' and line:
                wizard.principal = line.principal
                wizard.interest = line.interest
                wizard.insurance = line.insurance
                wizard.fee = line.fee
            elif wizard.operation == 'prepay' and line:
                wizard.principal = line.balance_start
                wizard.interest = line._l10n_pe_interest_until(wizard.date)
                wizard.insurance = wizard.fee = 0.0
            else:
                wizard.principal = wizard.interest = wizard.insurance = wizard.fee = 0.0

    @api.depends('principal', 'interest', 'insurance', 'fee')
    def _compute_total(self):
        for wizard in self:
            wizard.total = wizard.principal + wizard.interest + wizard.insurance + wizard.fee

    def action_confirm(self):
        self.ensure_one()
        if not self.line_id:
            raise UserError(self.env._('El préstamo no tiene cuotas pendientes.'))
        if self.operation == 'installment':
            self.loan_id._l10n_pe_pay_line(self.line_id, self.date, interest=self.interest,
                                           insurance=self.insurance, fee=self.fee)
        else:
            self.loan_id._l10n_pe_prepay(self.date, self.principal, mode=self.prepay_mode)
        return {'type': 'ir.actions.act_window_close'}
