# -*- coding: utf-8 -*-
"""Operaciones con el factor sobre una operación de factoring (asientos en
``models/factoring.py``). Mismo patrón que el asistente de banco de las
letras: importes en la moneda de la operación, contravalor a la fecha y el
céntimo de diferencia en el banco."""
from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nPeFactoringWizard(models.TransientModel):
    _name = 'l10n_pe.factoring.wizard'
    _description = 'Operación con el factor'
    _check_company_auto = True

    factoring_id = fields.Many2one('l10n_pe.factoring', string='Operación', required=True,
                                   check_company=True)
    operation = fields.Selection(
        selection=[('disburse', 'Desembolso del factor'),
                   ('accrue', 'Devengo de intereses'),
                   ('settle', 'Cobro del factor'),
                   ('repurchase', 'Recompra de facturas')],
        string='Operación con el factor', required=True)
    company_id = fields.Many2one(related='factoring_id.company_id')
    currency_id = fields.Many2one(related='factoring_id.currency_id')
    modality = fields.Selection(related='factoring_id.modality')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    bank_journal_id = fields.Many2one(
        'account.journal', string='Banco', check_company=True,
        domain="[('type', '=', 'bank')]")
    line_ids = fields.Many2many(
        'l10n_pe.factoring.line', string='Facturas', check_company=True,
        domain="[('id', 'in', available_line_ids)]")
    available_line_ids = fields.Many2many(
        'l10n_pe.factoring.line', string='Facturas disponibles',
        compute='_compute_available_line_ids', check_company=True)
    advance_amount = fields.Monetary(related='factoring_id.advance_amount', string='Adelanto')
    interest_amount = fields.Monetary(string='Intereses')
    fee_amount = fields.Monetary(string='Comisión')
    expense_amount = fields.Monetary(string='Gastos')
    amount = fields.Monetary(
        string='Importe', help='Devengo: intereses que pasan a gasto en esta fecha.')
    net_amount = fields.Monetary(string='Neto en el banco', compute='_compute_net_amount')

    @api.depends('factoring_id', 'operation')
    def _compute_available_line_ids(self):
        for wizard in self:
            wizard.available_line_ids = wizard.factoring_id.line_ids.filtered(
                lambda l: l.state == 'assigned') if wizard.operation in ('settle', 'repurchase') else False

    @api.depends('operation', 'advance_amount', 'interest_amount', 'fee_amount', 'expense_amount',
                 'line_ids')
    def _compute_net_amount(self):
        for wizard in self:
            charges = wizard.interest_amount + wizard.fee_amount + wizard.expense_amount
            if wizard.operation == 'disburse':
                wizard.net_amount = wizard.advance_amount - charges
            elif wizard.operation == 'settle':
                wizard.net_amount = sum(wizard.line_ids.mapped('retained_amount')) - charges
            elif wizard.operation == 'repurchase':
                wizard.net_amount = -(sum(wizard.line_ids.mapped('advance_amount')) + charges)
            else:
                wizard.net_amount = 0.0

    @api.onchange('operation', 'factoring_id')
    def _onchange_operation(self):
        if self.operation in ('settle', 'repurchase'):
            self.line_ids = self.available_line_ids
        if self.operation == 'accrue':
            self.amount = self.factoring_id.interest_pending_amount
        if self.factoring_id.bank_journal_id and not self.bank_journal_id:
            self.bank_journal_id = self.factoring_id.bank_journal_id

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------
    def _check(self):
        operation = self.factoring_id
        if self.date > fields.Date.context_today(self):
            raise UserError(self.env._('La fecha no puede ser posterior a hoy.'))
        if min(self.interest_amount, self.fee_amount, self.expense_amount, self.amount) < 0:
            raise UserError(self.env._('Los importes no pueden ser negativos.'))
        expected = {'disburse': ('assigned',), 'accrue': ('disbursed',),
                    'settle': ('disbursed',), 'repurchase': ('disbursed',)}[self.operation]
        if operation.state not in expected:
            raise UserError(self.env._('La operación %(name)s está en «%(state)s».', name=operation.name,
                                       state=dict(operation._fields['state'].selection)[operation.state]))
        if self.operation in ('accrue', 'repurchase') and operation.modality != 'with_recourse':
            raise UserError(self.env._('El devengo y la recompra son del factoring con recurso.'))
        if self.operation in ('settle', 'repurchase'):
            if not self.line_ids:
                raise UserError(self.env._('Seleccione las facturas.'))
            if self.line_ids.filtered(lambda l: l.state != 'assigned' or l.factoring_id != operation):
                raise UserError(self.env._('Solo se cobran o recompran facturas cedidas de esta operación.'))
        if self.operation in ('disburse', 'settle', 'repurchase') and not self.bank_journal_id:
            raise UserError(self.env._('Indique el banco.'))

    def action_apply(self):
        self.ensure_one()
        self._check()
        getattr(self, '_apply_%s' % self.operation)()
        return {'type': 'ir.actions.act_window_close'}

    def _bank_account(self):
        return self.bank_journal_id.default_account_id

    def _charges_vals(self, operation, config, label, interest_account=None):
        vals = []
        if self.interest_amount:
            vals.append(operation._line_vals(self.date, interest_account or config.interest_account_id,
                                             self.interest_amount, self.env._('Intereses %s', label)))
        if self.fee_amount + self.expense_amount:
            vals.append(operation._line_vals(self.date, config.fee_account_id,
                                             self.fee_amount + self.expense_amount,
                                             self.env._('Comisión y gastos %s', label)))
        return vals

    # ------------------------------------------------------------------
    # Desembolso
    # ------------------------------------------------------------------
    def _apply_disburse(self):
        operation = self.factoring_id
        config = operation._config()
        if operation.currency_id.compare_amounts(self.net_amount, 0.0) <= 0:
            raise UserError(self.env._('Los intereses, la comisión y los gastos no pueden superar el adelanto.'))
        with_recourse = operation.modality == 'with_recourse'
        deferred = with_recourse and config.deferred_interest_account_id
        label = operation.name
        vals = [operation._line_vals(self.date, self._bank_account(), self.net_amount,
                                     self.env._('Desembolso del factor %s', label))]
        vals += self._charges_vals(operation, config, label, interest_account=deferred or None)
        for line in operation.line_ids.filtered(lambda l: l.state == 'assigned'):
            if with_recourse:
                vals.append(operation._line_vals(self.date, config.obligation_account_id, -line.advance_amount,
                                                 self.env._('Adelanto %s', line.move_id.name),
                                                 partner=operation.factor_id, factoring_line=line))
            else:
                vals.append(operation._line_vals(self.date, config.assigned_account_id, -line.advance_amount,
                                                 self.env._('Adelanto %s', line.move_id.name),
                                                 partner=operation.factor_id, factoring_line=line))
        move = operation._post_move(self.bank_journal_id, self.date,
                                    self.env._('Desembolso del factor %s', label), vals)
        if not with_recourse:
            for line in operation.line_ids.filtered(lambda l: l.state == 'assigned'):
                credit = move.line_ids.filtered(lambda l: l.l10n_pe_factoring_line_id == line)
                (credit + line.assignment_line_id).reconcile()
        operation.write({
            'state': 'disbursed',
            'disbursement_date': self.date,
            'bank_journal_id': self.bank_journal_id.id,
            'interest_amount': self.interest_amount,
            'fee_amount': self.fee_amount,
            'expense_amount': self.expense_amount,
            'net_amount': self.net_amount,
            'interest_deferred_amount': self.interest_amount if deferred else 0.0,
        })

    # ------------------------------------------------------------------
    # Devengo de intereses (con recurso)
    # ------------------------------------------------------------------
    def _apply_accrue(self):
        operation = self.factoring_id
        if operation.currency_id.compare_amounts(self.amount, operation.interest_pending_amount) > 0:
            raise UserError(self.env._('El devengo supera los intereses pendientes (%s).',
                                       operation.interest_pending_amount))
        if not self.amount:
            raise UserError(self.env._('Indique el importe a devengar.'))
        operation._accrue_pending_interest(self.date, self.amount)

    # ------------------------------------------------------------------
    # Cobro del factor
    # ------------------------------------------------------------------
    def _apply_settle(self):
        """El cliente pagó al factor. Sin recurso, el factor paga el retenido;
        con recurso, además se cancela la obligación del adelanto."""
        operation = self.factoring_id
        config = operation._config()
        with_recourse = operation.modality == 'with_recourse'
        vals = []
        for line in self.line_ids:
            if with_recourse:
                # La factura sigue en la cuenta del cliente: se cancela aquí.
                receivable = line._open_receivable_lines()[:1]
                vals.append(operation._line_vals(self.date, receivable.account_id, -line.nominal_amount,
                                                 self.env._('Cobro %s', line.move_id.name),
                                                 partner=line.move_id.commercial_partner_id, factoring_line=line))
                vals.append(operation._line_vals(self.date, config.obligation_account_id, line.advance_amount,
                                                 self.env._('Cancelación del adelanto %s', line.move_id.name),
                                                 partner=operation.factor_id))
            else:
                residual = line.assignment_line_id.amount_residual_currency
                vals.append(operation._line_vals(self.date, line.assignment_line_id.account_id, -residual,
                                                 self.env._('Cobro %s', line.move_id.name),
                                                 partner=line.assignment_line_id.partner_id, factoring_line=line))
        bank = -sum(v['amount_currency'] for v in vals) - (
            self.interest_amount + self.fee_amount + self.expense_amount)
        vals.insert(0, operation._line_vals(self.date, self._bank_account(), bank,
                                            self.env._('Liquidación del factor %s', operation.name)))
        vals += self._charges_vals(operation, config, operation.name)
        move = operation._post_move(self.bank_journal_id, self.date,
                                    self.env._('Cobro del factor %s', operation.name), vals)
        for line in self.line_ids:
            mine = move.line_ids.filtered(lambda l: l.l10n_pe_factoring_line_id == line)
            if with_recourse:
                receivables = line._open_receivable_lines()
                (mine.filtered(lambda l: l.account_id in receivables.account_id) + receivables).reconcile()
            else:
                closing = mine.filtered(lambda l: l.account_id == line.assignment_line_id.account_id)
                if closing:
                    (closing + line.assignment_line_id).reconcile()
        self.line_ids.write({'state': 'collected'})
        operation._update_final_state()

    # ------------------------------------------------------------------
    # Recompra (con recurso)
    # ------------------------------------------------------------------
    def _apply_repurchase(self):
        """El cliente no pagó: se devuelve el adelanto al factor. La factura
        no cambia: con recurso nunca dejó de estar pendiente."""
        operation = self.factoring_id
        config = operation._config()
        vals = [operation._line_vals(self.date, config.obligation_account_id, line.advance_amount,
                                     self.env._('Devolución del adelanto %s', line.move_id.name),
                                     partner=operation.factor_id, factoring_line=line)
                for line in self.line_ids]
        vals += self._charges_vals(operation, config, operation.name)
        bank = -sum(v['amount_currency'] for v in vals)
        vals.insert(0, operation._line_vals(self.date, self._bank_account(), bank,
                                            self.env._('Recompra al factor %s', operation.name)))
        operation._post_move(self.bank_journal_id, self.date,
                             self.env._('Recompra de facturas %s', operation.name), vals)
        self.line_ids.write({'state': 'repurchased'})
        operation._update_final_state()
