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
                   ('company_collect', 'Cobro recibido por la empresa'),
                   ('transfer', 'Transferencia al factor'),
                   ('extend', 'Prórroga del vencimiento'),
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
    new_due_date = fields.Date(string='Nueva fecha de pago',
                               help='Prórroga: nuevo vencimiento acordado con el factor.')
    estimated_charges = fields.Monetary(
        string='Cargos simulados', compute='_compute_estimated_charges',
        help='Intereses, comisión (con IGV si el factor la factura) y gastos según el contrato.')
    estimate_difference = fields.Monetary(
        string='Diferencia con la simulación', compute='_compute_estimated_charges',
        help='Cargos de la liquidación real menos los simulados con el contrato.')

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        # Sin facturas elegidas, se proponen todas las que admiten la operación.
        for wizard, vals in zip(wizards, vals_list):
            if 'line_ids' not in vals and wizard.operation != 'accrue':
                wizard.line_ids = wizard.available_line_ids
        return wizards

    @api.depends('line_ids')
    def _compute_single_line(self):
        for wizard in self:
            wizard.single_line = len(wizard.line_ids) == 1

    @api.depends('factoring_id', 'operation')
    def _compute_available_line_ids(self):
        for wizard in self:
            lines = wizard.factoring_id.line_ids
            if wizard.operation == 'disburse':
                lines = lines.filtered(lambda l: l.state == 'assigned' and not l.disbursed)
            elif wizard.operation in ('settle', 'repurchase', 'write_off', 'company_collect', 'extend'):
                lines = lines.filtered(lambda l: l.state == 'assigned' and l.disbursed)
            elif wizard.operation == 'transfer':
                lines = lines.filtered(lambda l: not l.currency_id.is_zero(l.transfer_pending_amount))
            else:
                lines = lines.browse()
            wizard.available_line_ids = lines

    def _simulation(self):
        """Cargos que propone el contrato para las facturas elegidas."""
        self.ensure_one()
        contract = self.factoring_id.contract_id
        if not contract or not self.line_ids:
            return {}
        if self.operation == 'disburse':
            by_line, totals = contract._simulate(self.line_ids, self.date)
            return {'interest': totals['interest'], 'fee': totals['fee'] + totals['fee_igv'],
                    'expense': totals['expense']}
        if self.operation == 'extend' and self.new_due_date:
            interest = 0.0
            for line in self.line_ids:
                days = (self.new_due_date - (line.due_date or self.date)).days
                interest += contract._interest(line.advance_amount - line.advance_applied_amount, days)
            return {'interest': interest, 'fee': 0.0, 'expense': 0.0}
        return {}

    @api.depends('line_ids', 'date', 'new_due_date', 'interest_amount', 'fee_amount', 'expense_amount')
    def _compute_estimated_charges(self):
        for wizard in self:
            simulation = wizard._simulation()
            wizard.estimated_charges = sum(simulation.values())
            wizard.estimate_difference = wizard._charges() - wizard.estimated_charges if simulation else 0.0

    def _fill_from_simulation(self):
        simulation = self._simulation()
        if simulation:
            self.interest_amount = simulation['interest']
            self.fee_amount = simulation['fee']
            self.expense_amount = simulation['expense']

    def _charges(self):
        return self.interest_amount + self.fee_amount + self.expense_amount

    @api.depends('operation', 'advance_amount', 'interest_amount', 'fee_amount', 'expense_amount',
                 'line_ids', 'collect_amount')
    def _compute_net_amount(self):
        for wizard in self:
            charges = wizard._charges()
            if wizard.operation == 'disburse':
                wizard.net_amount = sum(wizard.line_ids.mapped('advance_amount')) - charges
            elif wizard.operation == 'company_collect':
                wizard.net_amount = sum(split[0] for split in wizard._collection_splits().values())
            elif wizard.operation == 'transfer':
                wizard.net_amount = -sum(wizard.line_ids.mapped('transfer_pending_amount'))
            elif wizard.operation == 'extend':
                wizard.net_amount = -charges
            elif wizard.operation == 'settle':
                wizard.net_amount = sum(split[1] for split in wizard._collection_splits().values()) - charges
            elif wizard.operation == 'repurchase':
                wizard.net_amount = -(sum(wizard.line_ids.mapped(
                    lambda l: l.advance_amount - l.advance_applied_amount)) + charges)
            else:
                wizard.net_amount = 0.0

    @api.onchange('operation', 'factoring_id')
    def _onchange_operation(self):
        if self.operation in ('disburse', 'settle', 'repurchase', 'write_off', 'company_collect',
                              'transfer', 'extend'):
            self.line_ids = self.available_line_ids
        if self.operation == 'disburse':
            self._fill_from_simulation()
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
        if self.operation == 'disburse':
            self._fill_from_simulation()

    @api.onchange('new_due_date')
    def _onchange_new_due_date(self):
        if self.operation == 'extend':
            self._fill_from_simulation()

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
        expected = {'disburse': ('assigned', 'disbursed'), 'accrue': ('disbursed',),
                    'settle': ('disbursed',), 'repurchase': ('disbursed',), 'write_off': ('disbursed',),
                    'company_collect': ('disbursed',), 'transfer': ('disbursed',),
                    'extend': ('disbursed',)}[self.operation]
        if operation.state not in expected:
            raise UserError(self.env._('La operación %(name)s está en «%(state)s».', name=operation.name,
                                       state=dict(operation._fields['state'].selection)[operation.state]))
        if self.operation in ('accrue', 'repurchase') and operation.modality != 'with_recourse':
            raise UserError(self.env._('El devengo y la recompra son del factoring con recurso.'))
        if self.operation == 'write_off' and operation.modality != 'without_recourse':
            raise UserError(self.env._(
                'La pérdida del retenido es del factoring sin recurso; con recurso use la recompra.'))
        if self.operation != 'accrue':
            if not self.line_ids:
                raise UserError(self.env._('Seleccione las facturas.'))
            if self.line_ids - self.available_line_ids:
                raise UserError(self.env._('Estas facturas no admiten «%(operation)s»: %(invoices)s.',
                                           operation=dict(self._fields['operation'].selection)[self.operation],
                                           invoices=', '.join((self.line_ids - self.available_line_ids
                                                               ).move_id.mapped('name'))))
        if self.operation == 'extend':
            if not self.new_due_date:
                raise UserError(self.env._('Indique la nueva fecha de pago.'))
            late = self.line_ids.filtered(lambda l: l.due_date and l.due_date >= self.new_due_date)
            if late:
                raise UserError(self.env._('La nueva fecha de pago debe ser posterior al vencimiento de %s.',
                                           ', '.join(late.move_id.mapped('name'))))
        if self.operation in ('settle', 'company_collect') and len(self.line_ids) == 1 and self.collect_amount:
            if self.currency_id.compare_amounts(self.collect_amount, self.line_ids.pending_amount) > 0:
                raise UserError(self.env._('El importe cobrado supera lo pendiente de la factura (%s).',
                                           self.line_ids.pending_amount))
        if self.operation in ('disburse', 'settle', 'repurchase', 'company_collect', 'transfer', 'extend') \
                and not self.bank_journal_id:
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
        lines = self.line_ids
        for line in lines:
            account = config.obligation_account_id if with_recourse else config.assigned_account_id
            vals.append(operation._line_vals(self.date, account, -line.advance_amount,
                                             self.env._('Adelanto %s', line.move_id.name),
                                             partner=operation.factor_id, factoring_line=line))
        move = operation._post_move(self.bank_journal_id, self.date,
                                    self.env._('Desembolso del factor %s', label), vals)
        if not with_recourse:
            for line in lines:
                credit = move.line_ids.filtered(lambda l: l.l10n_pe_factoring_line_id == line)
                (credit + line.assignment_line_id).reconcile()
        self._reconcile_fee_bill(move)
        self._write_charges(operation)
        lines.write({'disbursed': True, 'disbursement_date': self.date})
        operation.write({
            'state': 'disbursed',
            'disbursement_date': operation.disbursement_date or self.date,
            'bank_journal_id': self.bank_journal_id.id,
            'net_amount': operation.net_amount + self.net_amount,
            'interest_deferred_amount': operation.interest_deferred_amount
            + (self.interest_amount if deferred else 0.0),
        })
        if operation.has_undisbursed:
            operation.message_post(body=self.env._(
                'Desembolso parcial: %(invoices)s. Quedan por desembolsar: %(pending)s.',
                invoices=', '.join(lines.move_id.mapped('name')),
                pending=', '.join(operation.line_ids.filtered(
                    lambda l: l.state == 'assigned' and not l.disbursed).move_id.mapped('name'))))

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
                line._negotiable_event('paid', self.date, amount=line.nominal_amount)
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
        for line in self.line_ids:
            line._negotiable_event('repurchased', self.date, amount=line.nominal_amount)
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

    # ------------------------------------------------------------------
    # Cobro recibido por la empresa (el cliente pagó al cedente)
    # ------------------------------------------------------------------
    def _apply_company_collect(self):
        """El cliente pagó a la empresa en vez de al factor. Lo cobrado cubre
        primero el adelanto, que se debe al factor (queda «por transferir»), y
        después el retenido, que es de la empresa.

        Sin recurso: debe banco / haber cobros por transferir (factor) por la
        parte del adelanto y 1214 (factor) por el retenido.
        Con recurso: debe banco / haber 1212 (cliente), conciliado con la
        factura; la obligación 4512 se cancela al transferir."""
        operation = self.factoring_id
        config = operation._config()
        with_recourse = operation.modality == 'with_recourse'
        if not with_recourse and not config.transfer_account_id:
            raise UserError(self.env._('Configure la cuenta de cobros por transferir al factor (sin recurso).'))
        splits = self._collection_splits()
        vals = []
        for line, (collected, to_retained, to_advance) in splits.items():
            label = self.env._('Cobro de %s recibido por la empresa', line.move_id.name)
            if with_recourse:
                receivable = line._open_receivable_lines()[:1]
                vals.append(operation._line_vals(self.date, receivable.account_id, -collected, label,
                                                 partner=line.move_id.commercial_partner_id, factoring_line=line))
                continue
            if to_advance:
                vals.append(operation._line_vals(self.date, config.transfer_account_id, -to_advance, label,
                                                 partner=operation.factor_id, factoring_line=line))
            if to_retained:
                vals.append(operation._line_vals(self.date, line.assignment_line_id.account_id, -to_retained,
                                                 label, partner=line.assignment_line_id.partner_id,
                                                 factoring_line=line))
        total = sum(split[0] for split in splits.values())
        vals.insert(0, operation._line_vals(self.date, self._bank_account(), total,
                                            self.env._('Cobro de facturas cedidas %s', operation.name)))
        move = operation._post_move(self.bank_journal_id, self.date,
                                    self.env._('Cobro recibido por la empresa %s', operation.name), vals)
        for line, (collected, _retained, to_advance) in splits.items():
            mine = move.line_ids.filtered(lambda l: l.l10n_pe_factoring_line_id == line)
            if with_recourse:
                receivables = line._open_receivable_lines()
                (mine.filtered(lambda l: l.account_id in receivables.account_id) + receivables).reconcile()
            else:
                closing = mine.filtered(lambda l: l.account_id == line.assignment_line_id.account_id)
                if closing:
                    (closing + line.assignment_line_id).reconcile()
            line.write({
                'collected_amount': line.collected_amount + collected,
                'company_collected_amount': line.company_collected_amount + collected,
                'advance_applied_amount': line.advance_applied_amount + to_advance,
                'transfer_pending_amount': line.transfer_pending_amount + to_advance,
            })
            if line.currency_id.is_zero(line.pending_amount):
                line.state = 'collected'
                line._negotiable_event('paid', self.date, amount=line.nominal_amount,
                                       note=self.env._('El cliente pagó a la empresa.'))
        operation.message_post(body=self.env._(
            'El cliente pagó a la empresa %(amount)s; por transferir al factor: %(pending)s.',
            amount=total, pending=operation.transfer_pending_amount))
        operation._update_final_state()

    # ------------------------------------------------------------------
    # Transferencia al factor de lo cobrado por la empresa
    # ------------------------------------------------------------------
    def _apply_transfer(self):
        operation = self.factoring_id
        config = operation._config()
        with_recourse = operation.modality == 'with_recourse'
        vals = []
        for line in self.line_ids:
            pending = line.transfer_pending_amount
            label = self.env._('Transferencia al factor %s', line.move_id.name)
            if with_recourse:
                vals += operation._obligation_vals(self.date, line, pending, label)
            else:
                vals.append(operation._line_vals(self.date, config.transfer_account_id, pending, label,
                                                 partner=operation.factor_id, factoring_line=line))
        total = sum(self.line_ids.mapped('transfer_pending_amount'))
        vals.insert(0, operation._line_vals(self.date, self._bank_account(), -total,
                                            self.env._('Transferencia al factor %s', operation.name)))
        move = operation._post_move(self.bank_journal_id, self.date,
                                    self.env._('Transferencia al factor %s', operation.name), vals)
        if not with_recourse:
            for line in self.line_ids:
                lines = operation.move_ids.line_ids.filtered(
                    lambda l: l.l10n_pe_factoring_line_id == line and l.account_id == config.transfer_account_id
                    and not l.reconciled)
                if len(lines) > 1:
                    lines.reconcile()
        self.line_ids.write({'transfer_pending_amount': 0.0})
        operation._update_final_state()

    # ------------------------------------------------------------------
    # Prórroga del vencimiento con el factor
    # ------------------------------------------------------------------
    def _apply_extend(self):
        """El factor prorroga el vencimiento: cobra intereses (y comisión) por los
        días adicionales, que la empresa paga. La factura negociable registra
        la nueva fecha de pago (reprogramación en CAVALI)."""
        operation = self.factoring_id
        config = operation._config()
        if self.currency_id.is_zero(self._charges()):
            vals = []
        else:
            vals = self._charges_vals(operation, config, operation.name)
            vals.insert(0, operation._line_vals(self.date, self._bank_account(), -self._charges(),
                                                self.env._('Prórroga %s', operation.name)))
        move = operation._post_move(self.bank_journal_id, self.date,
                                    self.env._('Prórroga del vencimiento %s', operation.name), vals) \
            if vals else self.env['account.move']
        self._reconcile_fee_bill(move)
        self._write_charges(operation)
        for line in self.line_ids:
            previous = line.due_date
            line.due_date = self.new_due_date
            line._negotiable_event('extended', self.date, due_date=self.new_due_date,
                                   amount=line.pending_amount)
            operation.message_post(body=self.env._(
                'Prórroga de %(invoice)s: del %(old)s al %(new)s.', invoice=line.move_id.name,
                old=previous or '—', new=self.new_due_date))
