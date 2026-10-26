# -*- coding: utf-8 -*-
"""Programación de pagos con aprobación.

Tesorería arma la lista de documentos a pagar en una fecha desde un banco, la
somete a aprobación y, aprobada, la paga con el asistente nativo
``account.payment.register``: así actúan la retención del IGV, el ITF, el T.C.
pactado y el medio de pago de la suite exactamente como en un pago manual.
"""
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

STATES = [
    ('draft', 'Borrador'),
    ('to_approve', 'Por aprobar'),
    ('approved', 'Aprobada'),
    ('paid', 'Pagada'),
    ('cancel', 'Anulada'),
]
OPEN_STATES = ('draft', 'to_approve', 'approved')


class L10nPeTreasuryPaymentPlan(models.Model):
    _name = 'l10n_pe.treasury.payment.plan'
    _description = 'Programación de pagos'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'date desc, id desc'

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    state = fields.Selection(STATES, string='Estado', default='draft', required=True, readonly=True,
                             copy=False, tracking=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda de la compañía')
    date = fields.Date(string='Fecha de pago', required=True, default=fields.Date.context_today, tracking=True)
    journal_id = fields.Many2one(
        'account.journal', string='Banco', required=True, check_company=True, tracking=True,
        domain="[('type', 'in', ('bank', 'cash'))]", help='Cuenta desde la que se paga.')
    currency_id = fields.Many2one('res.currency', string='Moneda', compute='_compute_currency_id', store=True)
    payment_method_line_id = fields.Many2one(
        'account.payment.method.line', string='Método de pago', check_company=True,
        domain="[('journal_id', '=', journal_id), ('payment_type', '=', 'outbound')]",
        help='Vacío: el primero del banco. Con el archivo TXT del banco, los pagos se agrupan en un lote.')
    line_ids = fields.One2many('l10n_pe.treasury.payment.plan.line', 'plan_id', string='Documentos', copy=False)
    line_count = fields.Integer(string='N.º de documentos', compute='_compute_totals', store=True)
    partner_count = fields.Integer(string='Proveedores', compute='_compute_totals', store=True)
    amount_total = fields.Monetary(string='Total a pagar', compute='_compute_totals', store=True)
    amount_company = fields.Monetary(string='Total (S/)', currency_field='company_currency_id',
                                     compute='_compute_totals', store=True)
    journal_available = fields.Monetary(
        string='Disponible en el banco', compute='_compute_journal_available',
        help='Disponible de la cuenta a la fecha (posición de tesorería) sin contar esta programación.')
    over_available = fields.Boolean(string='Supera el disponible', compute='_compute_journal_available')
    user_id = fields.Many2one('res.users', string='Preparado por', default=lambda self: self.env.user,
                              readonly=True, copy=False)
    approval_level = fields.Selection(
        [('none', 'Sin aprobación'), ('single', 'Una aprobación'), ('double', 'Dos aprobaciones')],
        string='Aprobación requerida', compute='_compute_approval_level')
    first_approver_id = fields.Many2one('res.users', string='Aprobado por', readonly=True, copy=False)
    first_approval_date = fields.Datetime(string='Fecha de aprobación', readonly=True, copy=False)
    second_approver_id = fields.Many2one('res.users', string='Segunda aprobación', readonly=True, copy=False)
    second_approval_date = fields.Datetime(string='Fecha de la segunda aprobación', readonly=True, copy=False)
    payment_ids = fields.Many2many('account.payment', string='Pagos', readonly=True, copy=False)
    payment_count = fields.Integer(string='N.º de pagos', compute='_compute_payment_count')
    note = fields.Html(string='Notas')

    @api.depends('journal_id')
    def _compute_currency_id(self):
        for plan in self:
            plan.currency_id = plan.journal_id._l10n_pe_treasury_currency() if plan.journal_id \
                else plan.company_id.currency_id

    @api.depends('line_ids.amount', 'line_ids.partner_id', 'currency_id', 'date')
    def _compute_totals(self):
        for plan in self:
            plan.line_count = len(plan.line_ids)
            plan.partner_count = len(plan.line_ids.partner_id)
            plan.amount_total = sum(plan.line_ids.mapped('amount'))
            company = plan.company_id
            plan.amount_company = plan.currency_id._convert(
                plan.amount_total, company.currency_id, company, plan.date or fields.Date.context_today(plan)) \
                if plan.currency_id and plan.currency_id != company.currency_id else plan.amount_total

    @api.depends('amount_company', 'company_id.l10n_pe_treasury_plan_approval_amount',
                 'company_id.l10n_pe_treasury_plan_double_amount')
    def _compute_approval_level(self):
        for plan in self:
            company = plan.company_id
            currency = company.currency_id
            single = company.l10n_pe_treasury_plan_approval_amount
            double = company.l10n_pe_treasury_plan_double_amount
            if double and currency.compare_amounts(plan.amount_company, double) >= 0:
                plan.approval_level = 'double'
            elif not single or currency.compare_amounts(plan.amount_company, single) >= 0:
                plan.approval_level = 'single'
            else:
                plan.approval_level = 'none'

    @api.depends('journal_id', 'date', 'amount_total', 'state')
    def _compute_journal_available(self):
        Position = self.env['l10n_pe.treasury.position']
        for plan in self:
            if not plan.journal_id or plan.state in ('paid', 'cancel'):
                plan.journal_available = 0.0
                plan.over_available = False
                continue
            position = Position.new({'date': plan.date or fields.Date.context_today(plan),
                                     'company_id': plan.company_id.id})
            # Lo ya aprobado de otras programaciones, sin contar esta.
            scheduled = position._l10n_pe_scheduled_amounts(plan.journal_id)
            if plan.state == 'approved':
                own = sum(plan.line_ids.filtered(lambda l: not l.payment_id).mapped('amount'))
                scheduled[plan.journal_id.id] = scheduled.get(plan.journal_id.id, 0.0) - own
            vals = position._l10n_pe_line_values(plan.journal_id, scheduled)
            available = 0.0 if vals['restricted'] else (
                vals['balance'] + vals['receipts_transit'] + vals['payments_transit'] - vals['scheduled']
                - vals['min_balance'] + vals['overdraft'])
            plan.journal_available = available
            plan.over_available = plan.currency_id.compare_amounts(plan.amount_total, available) > 0

    def _compute_payment_count(self):
        for plan in self:
            plan.payment_count = len(plan.payment_ids)

    # ------------------------------------------------------------------
    # Flujo
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('l10n_pe.treasury.payment.plan') or '/'
        return super().create(vals_list)

    def unlink(self):
        if self.filtered(lambda p: p.state not in ('draft', 'cancel')):
            raise UserError(self.env._('Solo se eliminan programaciones en borrador o anuladas.'))
        return super().unlink()

    def _check_state(self, states):
        for plan in self:
            if plan.state not in states:
                raise UserError(self.env._('La programación %(name)s está en estado «%(state)s».',
                                           name=plan.name, state=dict(STATES)[plan.state]))

    def action_propose(self):
        self.ensure_one()
        self._check_state(('draft',))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Proponer documentos'),
            'res_model': 'l10n_pe.treasury.payment.plan.propose',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_plan_id': self.id, 'default_date_due': self.date},
        }

    def action_submit(self):
        self._check_state(('draft',))
        for plan in self:
            if not plan.line_ids:
                raise UserError(self.env._('Agregue los documentos a pagar.'))
            plan.line_ids._check_amounts()
            if plan.approval_level == 'none':
                plan.state = 'approved'
                plan.message_post(body=self.env._('Aprobada sin firma: el total es menor que el importe de '
                                                  'aprobación de Ajustes.'))
            else:
                plan.state = 'to_approve'
                plan._l10n_pe_request_approval('al_l10n_pe_treasury.group_treasury_approver')
        return True

    def _l10n_pe_request_approval(self, group_xmlid):
        # sudo: quien prepara no puede leer las compañías de los demás usuarios;
        # solo se usan para elegir a quién asignar la actividad de aprobación.
        group_sudo = self.env.ref(group_xmlid).sudo()
        for plan in self:
            approvers = group_sudo.all_user_ids.filtered(
                lambda u: plan.company_id in u.company_ids and not u.share
                and u not in (plan.user_id | plan.first_approver_id))
            for approver in approvers[:5]:
                plan.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=approver.id, date_deadline=plan.date,
                    summary=self.env._('Aprobar %s', plan.name),
                    note=self.env._('%(count)s documentos por %(amount)s %(currency)s desde %(journal)s.',
                                    count=plan.line_count, amount=plan.amount_total,
                                    currency=plan.currency_id.name, journal=plan.journal_id.name))

    def action_approve(self):
        self._check_state(('to_approve',))
        user = self.env.user
        for plan in self:
            if plan.user_id == user and not self.env.su:
                raise UserError(self.env._('Quien prepara la programación no puede aprobarla.'))
            if not plan.first_approver_id:
                if not user.has_group('al_l10n_pe_treasury.group_treasury_approver'):
                    raise UserError(self.env._('Solo un aprobador de tesorería puede aprobar la programación.'))
                plan.write({'first_approver_id': user.id, 'first_approval_date': fields.Datetime.now()})
                plan.activity_ids.action_done()
                if plan.approval_level == 'double':
                    plan.message_post(body=self.env._('Primera aprobación de %s; falta la del administrador.',
                                                      user.name))
                    plan._l10n_pe_request_approval('al_l10n_pe_treasury.group_treasury_manager')
                    continue
            else:
                if not user.has_group('al_l10n_pe_treasury.group_treasury_manager'):
                    raise UserError(self.env._('La segunda aprobación es de un administrador de tesorería.'))
                if plan.first_approver_id == user and not self.env.su:
                    raise UserError(self.env._('La segunda aprobación debe ser de otra persona.'))
                plan.write({'second_approver_id': user.id, 'second_approval_date': fields.Datetime.now()})
                plan.activity_ids.action_done()
            plan.state = 'approved'
        return True

    def action_reject(self):
        self._check_state(('to_approve', 'approved'))
        self.activity_ids.unlink()
        self.write({'state': 'draft', 'first_approver_id': False, 'first_approval_date': False,
                    'second_approver_id': False, 'second_approval_date': False})
        for plan in self:
            plan.message_post(body=self.env._('Devuelta a borrador por %s.', self.env.user.name))
        return True

    def action_cancel(self):
        self._check_state(OPEN_STATES)
        self.activity_ids.unlink()
        self.state = 'cancel'
        return True

    def action_draft(self):
        self._check_state(('cancel',))
        self.write({'state': 'draft', 'first_approver_id': False, 'first_approval_date': False,
                    'second_approver_id': False, 'second_approval_date': False})
        return True

    # ------------------------------------------------------------------
    # Pago
    # ------------------------------------------------------------------
    def _l10n_pe_register_vals(self, amount=None):
        self.ensure_one()
        vals = {
            'journal_id': self.journal_id.id,
            'payment_date': self.date,
            'group_payment': True,
        }
        if self.payment_method_line_id:
            vals['payment_method_line_id'] = self.payment_method_line_id.id
        if amount is not None:
            vals['amount'] = amount
        return vals

    def _l10n_pe_register(self, lines, amount=None):
        """Paga ``lines`` (de un solo proveedor) con el asistente nativo."""
        self.ensure_one()
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move.line', active_ids=lines.move_line_id.ids,
            l10n_pe_treasury_plan_id=self.id,
        ).create(self._l10n_pe_register_vals(amount))
        return wizard._create_payments()

    def action_pay(self):
        self._check_state(('approved',))
        for plan in self:
            pending = plan.line_ids.filtered(lambda l: not l.payment_id)
            pending._check_amounts()
            payments = self.env['account.payment']
            by_partner = defaultdict(lambda: self.env['l10n_pe.treasury.payment.plan.line'])
            for line in pending:
                by_partner[line.partner_id] |= line
            for lines in by_partner.values():
                if all(line.is_full for line in lines):
                    created = plan._l10n_pe_register(lines)
                    for line in lines:
                        line.payment_id = created.filtered(lambda p, l=line: l.move_id in p.invoice_ids)[:1] \
                            or created[:1]
                    payments |= created
                else:
                    for line in lines:
                        created = plan._l10n_pe_register(line, amount=line.amount)
                        line.payment_id = created[:1]
                        payments |= created
            # El asistente omite sin avisar a los proveedores sin cuenta bancaria
            # validada cuando el método la exige (p. ej. el TXT del banco).
            unpaid = pending.filtered(lambda l: not l.payment_id)
            if unpaid:
                raise UserError(self.env._(
                    'No se pudo pagar a %s: revise que su cuenta bancaria esté registrada y validada '
                    'para pagos.', ', '.join(unpaid.partner_id.mapped('display_name'))))
            payments.write({'l10n_pe_treasury_plan_id': plan.id})
            plan.write({'payment_ids': [(4, p.id) for p in payments], 'state': 'paid'})
            plan._l10n_pe_after_pay(payments)
            plan.activity_ids.action_done()
            plan.message_post(body=self.env._('Pagada: %s pagos.', len(payments)))
        return True

    def _l10n_pe_after_pay(self, payments):
        """Gancho tras registrar los pagos (p. ej. agruparlos en un lote bancario)."""
        return payments

    def action_open_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Pagos'),
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.payment_ids.ids)],
            'context': {'create': False},
        }


class L10nPeTreasuryPaymentPlanLine(models.Model):
    _name = 'l10n_pe.treasury.payment.plan.line'
    _description = 'Documento programado para pago'
    _check_company_auto = True
    _order = 'plan_id, partner_id, date_maturity, id'

    plan_id = fields.Many2one('l10n_pe.treasury.payment.plan', string='Programación', required=True,
                              ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(related='plan_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='plan_id.currency_id', store=True)
    plan_state = fields.Selection(related='plan_id.state', string='Estado de la programación', store=True)
    move_line_id = fields.Many2one(
        'account.move.line', string='Apunte por pagar', required=True, check_company=True, index=True,
        ondelete='restrict',
        domain="[('account_id.account_type', '=', 'liability_payable'), ('reconciled', '=', False), "
               "('parent_state', '=', 'posted'), ('amount_residual', '<', 0)]")
    move_id = fields.Many2one(related='move_line_id.move_id', string='Documento', store=True)
    partner_id = fields.Many2one(related='move_line_id.partner_id', string='Proveedor', store=True)
    date_maturity = fields.Date(related='move_line_id.date_maturity', string='Vencimiento', store=True,
                                help='Fecha de vencimiento del documento.')
    days_overdue = fields.Integer(string='Días de atraso', compute='_compute_residual')
    amount_residual = fields.Monetary(string='Saldo', compute='_compute_residual',
                                      help='Saldo pendiente del documento en la moneda de la programación.')
    amount = fields.Monetary(string='A pagar', help='Importe a pagar; menor que el saldo para un pago parcial.')
    is_full = fields.Boolean(string='Pago total', compute='_compute_residual')
    payment_id = fields.Many2one('account.payment', string='Pago', readonly=True, copy=False, check_company=True)
    note = fields.Char(string='Observación')

    _positive_amount = models.Constraint('CHECK(amount >= 0)', 'El importe a pagar no puede ser negativo.')

    @api.depends('move_line_id.amount_residual', 'move_line_id.amount_residual_currency', 'currency_id',
                 'amount', 'plan_id.date')
    def _compute_residual(self):
        for line in self:
            aml = line.move_line_id
            line.amount_residual = line._l10n_pe_residual(aml)
            line.is_full = line.currency_id.compare_amounts(line.amount, line.amount_residual) >= 0
            reference = line.plan_id.date or fields.Date.context_today(line)
            line.days_overdue = max((reference - aml.date_maturity).days, 0) if aml.date_maturity else 0

    def _l10n_pe_residual(self, aml):
        """Saldo positivo del apunte por pagar en la moneda de la programación."""
        self.ensure_one()
        if not aml:
            return 0.0
        currency = self.currency_id or self.plan_id.currency_id
        if aml.currency_id == currency and currency != aml.company_currency_id:
            return -aml.amount_residual_currency
        if currency == aml.company_currency_id:
            return -aml.amount_residual
        return aml.company_currency_id._convert(-aml.amount_residual, currency, aml.company_id,
                                                self.plan_id.date or fields.Date.context_today(self))

    @api.onchange('move_line_id')
    def _onchange_move_line_id(self):
        if self.move_line_id:
            self.amount = self._l10n_pe_residual(self.move_line_id)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines.filtered(lambda l: not l.amount):
            line.amount = line.amount_residual
        return lines

    @api.constrains('move_line_id', 'plan_id')
    def _check_unique_open(self):
        for line in self:
            duplicate = self.search([
                ('id', '!=', line.id), ('move_line_id', '=', line.move_line_id.id),
                ('plan_id.state', 'in', OPEN_STATES), ('payment_id', '=', False)], limit=1)
            if duplicate and line.plan_id.state in OPEN_STATES:
                raise ValidationError(self.env._(
                    '%(doc)s ya está en la programación %(plan)s.',
                    doc=line.move_id.display_name, plan=duplicate.plan_id.name))
            if line.move_line_id.currency_id != line.plan_id.currency_id and \
                    line.move_line_id.currency_id != line.move_line_id.company_currency_id:
                raise ValidationError(self.env._(
                    '%(doc)s está en %(currency)s: prográmelo desde un banco en esa moneda.',
                    doc=line.move_id.display_name, currency=line.move_line_id.currency_id.name))

    def _check_amounts(self):
        for line in self:
            if line.move_line_id.reconciled:
                raise UserError(self.env._('%s ya está pagado.', line.move_id.display_name))
            if line.currency_id.compare_amounts(line.amount, 0.0) <= 0:
                raise UserError(self.env._('Indique el importe a pagar de %s.', line.move_id.display_name))
            if line.currency_id.compare_amounts(line.amount, line.amount_residual) > 0:
                raise UserError(self.env._('El importe a pagar de %(doc)s supera su saldo (%(residual)s).',
                                           doc=line.move_id.display_name, residual=line.amount_residual))
