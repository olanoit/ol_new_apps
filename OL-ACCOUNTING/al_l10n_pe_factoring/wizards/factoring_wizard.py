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
                   ('repurchase', 'Recompra de facturas'),
                   ('write_off', 'Pérdida del retenido')],
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
    fee_bill_id = fields.Many2one(
        'account.move', string='Factura del factor', check_company=True,
        domain="[('move_type', '=', 'in_invoice'), ('state', '=', 'posted'), "
               "('payment_state', 'not in', ('paid', 'in_payment', 'reversed'))]",
        help='Si el factor factura su comisión (con IGV y crédito fiscal), elija su factura '
             'de proveedor: el descuento la paga y el gasto y el IGV quedan en la factura.')
    collect_amount = fields.Monetary(
        string='Importe cobrado',
        help='Cobro parcial de una sola factura: lo que el cliente pagó al factor. Se aplica '
             'primero al adelanto y luego al retenido.')
    amount = fields.Monetary(
        string='Importe', help='Devengo: intereses que pasan a gasto en esta fecha.')
    net_amount = fields.Monetary(string='Neto en el banco', compute='_compute_net_amount')
    single_line = fields.Boolean(string='Una sola factura', compute='_compute_single_line')

    @api.depends('line_ids')
    def _compute_single_line(self):
        for wizard in self:
            wizard.single_line = len(wizard.line_ids) == 1

    @api.depends('factoring_id', 'operation')
    def _compute_available_line_ids(self):
        for wizard in self:
            wizard.available_line_ids = wizard.factoring_id.line_ids.filtered(
                lambda l: l.state == 'assigned') if wizard.operation in ('settle', 'repurchase', 'write_off') else False

    def _charges(self):
        return self.interest_amount + self.fee_amount + self.expense_amount

    @api.depends('operation', 'advance_amount', 'interest_amount', 'fee_amount', 'expense_amount',
                 'line_ids', 'collect_amount')
    def _compute_net_amount(self):
        for wizard in self:
            charges = wizard._charges()
            if wizard.operation == 'disburse':
                wizard.net_amount = wizard.advance_amount - charges
            elif wizard.operation == 'settle':
                wizard.net_amount = sum(split[1] for split in wizard._collection_splits().values()) - charges
            elif wizard.operation == 'repurchase':
                wizard.net_amount = -(sum(wizard.line_ids.mapped(
                    lambda l: l.advance_amount - l.advance_applied_amount)) + charges)
            else:
                wizard.net_amount = 0.0

    @api.onchange('operation', 'factoring_id')
    def _onchange_operation(self):
        if self.operation in ('settle', 'repurchase', 'write_off'):
            self.line_ids = self.available_line_ids
        if self.operation == 'accrue':
            self.amount = self.factoring_id.interest_pending_amount
        if self.factoring_id.bank_journal_id and not self.bank_journal_id:
            self.bank_journal_id = self.factoring_id.bank_journal_id

    @api.onchange('fee_bill_id')
    def _onchange_fee_bill_id(self):
        if self.fee_bill_id:
            self.fee_amount = self.fee_bill_id.amount_residual

    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        self.collect_amount = self.line_ids.pending_amount if len(self.line_ids) == 1 else 0.0

    def _collection_splits(self):
        """``{línea: (cobrado, parte del retenido, parte del adelanto)}``. Con una
        sola factura y un importe, cobro parcial; si no, lo pendiente de cada una.
        Lo cobrado cubre primero el adelanto y después libera el retenido."""
        self.ensure_one()
        splits = {}
        for line in self.line_ids:
            collected = (self.collect_amount if len(self.line_ids) == 1 and self.collect_amount
                         else line.pending_amount)
            to_advance = min(collected, max(line.advance_amount - line.advance_applied_amount, 0.0))
            splits[line] = (collected, collected - to_advance, to_advance)
        return splits

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------
    def _check(self):
        operation = self.factoring_id
        if self.date > fields.Date.context_today(self):
            raise UserError(self.env._('La fecha no puede ser posterior a hoy.'))
        if min(self.interest_amount, self.fee_amount, self.expense_amount, self.amount,
               self.collect_amount) < 0:
            raise UserError(self.env._('Los importes no pueden ser negativos.'))
        expected = {'disburse': ('assigned',), 'accrue': ('disbursed',), 'settle': ('disbursed',),
                    'repurchase': ('disbursed',), 'write_off': ('disbursed',)}[self.operation]
        if operation.state not in expected:
            raise UserError(self.env._('La operación %(name)s está en «%(state)s».', name=operation.name,
                                       state=dict(operation._fields['state'].selection)[operation.state]))
        if self.operation in ('accrue', 'repurchase') and operation.modality != 'with_recourse':
            raise UserError(self.env._('El devengo y la recompra son del factoring con recurso.'))
        if self.operation == 'write_off' and operation.modality != 'without_recourse':
            raise UserError(self.env._(
                'La pérdida del retenido es del factoring sin recurso; con recurso use la recompra.'))
        if self.operation in ('settle', 'repurchase', 'write_off'):
            if not self.line_ids:
                raise UserError(self.env._('Seleccione las facturas.'))
            if self.line_ids.filtered(lambda l: l.state != 'assigned' or l.factoring_id != operation):
                raise UserError(self.env._('Solo se operan facturas cedidas de esta operación.'))
        if self.operation == 'settle' and len(self.line_ids) == 1 and self.collect_amount:
            if self.currency_id.compare_amounts(self.collect_amount, self.line_ids.pending_amount) > 0:
                raise UserError(self.env._('El importe cobrado supera lo pendiente de la factura (%s).',
                                           self.line_ids.pending_amount))
        if self.operation in ('disburse', 'settle', 'repurchase') and not self.bank_journal_id:
            raise UserError(self.env._('Indique el banco.'))
        if self.fee_bill_id:
            if self.fee_bill_id.commercial_partner_id != operation.factor_id.commercial_partner_id:
                raise UserError(self.env._('La factura de la comisión debe ser del factor.'))
            if self.currency_id.compare_amounts(self.fee_amount, self.fee_bill_id.amount_residual) > 0:
                raise UserError(self.env._('La comisión supera el saldo de la factura del factor (%s).',
                                           self.fee_bill_id.amount_residual))

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
        if self.fee_bill_id and self.fee_amount:
            # La comisión facturada se paga con el descuento: va contra la
            # cuenta por pagar de la factura del factor (gasto e IGV en ella).
            payable = self.fee_bill_id.line_ids.filtered(
                lambda l: l.account_id.account_type == 'liability_payable' and not l.reconciled)[:1]
            vals.append(operation._line_vals(self.date, payable.account_id, self.fee_amount,
                                             self.env._('Comisión facturada %s', self.fee_bill_id.name),
                                             partner=self.fee_bill_id.commercial_partner_id))
            if self.expense_amount:
                vals.append(operation._line_vals(self.date, config.fee_account_id, self.expense_amount,
                                                 self.env._('Gastos %s', label)))
        elif self.fee_amount + self.expense_amount:
            vals.append(operation._line_vals(self.date, config.fee_account_id,
                                             self.fee_amount + self.expense_amount,
                                             self.env._('Comisión y gastos %s', label)))
        return vals

    def _reconcile_fee_bill(self, move):
        if not self.fee_bill_id or not move:
            return
        payable = self.fee_bill_id.line_ids.filtered(
            lambda l: l.account_id.account_type == 'liability_payable' and not l.reconciled)
        mine = move.line_ids.filtered(lambda l: l.account_id in payable.account_id
                                      and l.partner_id == self.fee_bill_id.commercial_partner_id)
        (payable + mine).reconcile()

    def _write_charges(self, operation):
        operation.write({
            'interest_amount': operation.interest_amount + self.interest_amount,
            'fee_amount': operation.fee_amount + self.fee_amount,
            'expense_amount': operation.expense_amount + self.expense_amount,
        })

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
            account = config.obligation_account_id if with_recourse else config.assigned_account_id
            vals.append(operation._line_vals(self.date, account, -line.advance_amount,
                                             self.env._('Adelanto %s', line.move_id.name),
                                             partner=operation.factor_id, factoring_line=line))
        move = operation._post_move(self.bank_journal_id, self.date,
                                    self.env._('Desembolso del factor %s', label), vals)
        if not with_recourse:
            for line in operation.line_ids.filtered(lambda l: l.state == 'assigned'):
                credit = move.line_ids.filtered(lambda l: l.l10n_pe_factoring_line_id == line)
                (credit + line.assignment_line_id).reconcile()
        self._reconcile_fee_bill(move)
        self._write_charges(operation)
        operation.write({
            'state': 'disbursed',
            'disbursement_date': self.date,
            'bank_journal_id': self.bank_journal_id.id,
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
    # Cobro del factor (total o parcial)
    # ------------------------------------------------------------------
    def _apply_settle(self):
        """El cliente pagó al factor (todo o una parte). Lo cobrado cubre primero
        el adelanto y después el retenido, que el factor abona. Sin recurso, la
        factura ya se dio de baja: solo se cobra el retenido liberado. Con
        recurso, se cancela la factura por lo cobrado y la obligación por la
        parte del adelanto."""
        operation = self.factoring_id
        config = operation._config()
        with_recourse = operation.modality == 'with_recourse'
        splits = self._collection_splits()
        vals = []
        for line, (collected, to_retained, to_advance) in splits.items():
            label = line.move_id.name
            if with_recourse:
                receivable = line._open_receivable_lines()[:1]
                vals.append(operation._line_vals(self.date, receivable.account_id, -collected,
                                                 self.env._('Cobro %s', label),
                                                 partner=line.move_id.commercial_partner_id, factoring_line=line))
                if to_advance:
                    vals += operation._obligation_vals(
                        self.date, line, to_advance, self.env._('Cancelación del adelanto %s', label))
            elif to_retained:
                vals.append(operation._line_vals(self.date, line.assignment_line_id.account_id, -to_retained,
                                                 self.env._('Retenido liberado %s', label),
                                                 partner=line.assignment_line_id.partner_id, factoring_line=line))
        bank = sum(split[1] for split in splits.values()) - self._charges()
        vals.insert(0, operation._line_vals(self.date, self._bank_account(), bank,
                                            self.env._('Liquidación del factor %s', operation.name)))
        vals += self._charges_vals(operation, config, operation.name)
        move = operation._post_move(self.bank_journal_id, self.date,
                                    self.env._('Cobro del factor %s', operation.name), vals)
        for line, (collected, _retained, to_advance) in splits.items():
            mine = move.line_ids.filtered(lambda l: l.l10n_pe_factoring_line_id == line)
            if with_recourse:
                receivables = line._open_receivable_lines()
                (mine.filtered(lambda l: l.account_id in receivables.account_id) + receivables).reconcile()
            else:
                closing = mine.filtered(lambda l: l.account_id == line.assignment_line_id.account_id)
                if closing:
                    (closing + line.assignment_line_id).reconcile()
            line.write({'collected_amount': line.collected_amount + collected,
                        'advance_applied_amount': line.advance_applied_amount + to_advance})
            if line.currency_id.is_zero(line.pending_amount):
                line.state = 'collected'
            else:
                operation.message_post(body=self.env._(
                    'Cobro parcial de %(invoice)s: %(collected)s; pendiente %(pending)s.',
                    invoice=line.move_id.name, collected=collected, pending=line.pending_amount))
        self._reconcile_fee_bill(move)
        self._write_charges(operation)
        operation._update_final_state()

    # ------------------------------------------------------------------
    # Recompra (con recurso)
    # ------------------------------------------------------------------
    def _apply_repurchase(self):
        """El cliente no pagó: se devuelve al factor el adelanto que lo cobrado no
        cubrió. La factura no cambia: con recurso nunca dejó de estar pendiente."""
        operation = self.factoring_id
        config = operation._config()
        vals = []
        for line in self.line_ids:
            remaining = line.advance_amount - line.advance_applied_amount
            if remaining:
                vals += operation._obligation_vals(
                    self.date, line, remaining, self.env._('Devolución del adelanto %s', line.move_id.name))
        vals += self._charges_vals(operation, config, operation.name)
        bank = -sum(v['amount_currency'] for v in vals if v['currency_id'] == operation.currency_id.id)
        vals.insert(0, operation._line_vals(self.date, self._bank_account(), bank,
                                            self.env._('Recompra al factor %s', operation.name)))
        move = operation._post_move(self.bank_journal_id, self.date,
                                    self.env._('Recompra de facturas %s', operation.name), vals)
        for line in self.line_ids:
            line.advance_applied_amount = line.advance_amount
        self.line_ids.write({'state': 'repurchased'})
        self._reconcile_fee_bill(move)
        self._write_charges(operation)
        operation._update_final_state()

    # ------------------------------------------------------------------
    # Pérdida del retenido (sin recurso)
    # ------------------------------------------------------------------
    def _apply_write_off(self):
        """Sin recurso el riesgo de impago es del factor, pero el retenido solo se
        cobra si el cliente paga: si no paga, el retenido pendiente es una
        pérdida de la empresa (PCGE 6741)."""
        operation = self.factoring_id
        config = operation._config()
        if not config.loss_account_id:
            raise UserError(self.env._('Configure la cuenta de pérdida del retenido (sin recurso).'))
        vals, total = [], 0.0
        for line in self.line_ids:
            residual = line.assignment_line_id.amount_residual_currency
            if not residual:
                continue
            total += residual
            label = self.env._('Retenido perdido %s', line.move_id.name)
            vals += [
                operation._line_vals(self.date, config.loss_account_id, residual, label),
                operation._line_vals(self.date, line.assignment_line_id.account_id, -residual, label,
                                     partner=line.assignment_line_id.partner_id, factoring_line=line),
            ]
        move = operation._post_move(operation.journal_id, self.date,
                                    self.env._('Pérdida del retenido %s', operation.name), vals)
        for line in self.line_ids:
            closing = move.line_ids.filtered(lambda l: l.l10n_pe_factoring_line_id == line
                                             and l.account_id == line.assignment_line_id.account_id)
            if closing:
                (closing + line.assignment_line_id).reconcile()
        self.line_ids.write({'state': 'lost'})
        operation.loss_amount += total
        operation._update_final_state()
