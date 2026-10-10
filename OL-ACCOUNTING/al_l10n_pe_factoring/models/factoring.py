# -*- coding: utf-8 -*-
"""Operaciones de factoring (cesión de facturas a un factor).

Asientos (cuentas en ``l10n_pe.factoring.account.config``, PCGE por defecto):

Sin recurso (el factor asume el riesgo; NIIF 9: baja de la cuenta por cobrar)
- Cesión: debe 1214 (factor) / haber 1212 (cliente), conciliado con la factura:
  la factura queda pagada y la deuda pasa al factor.
- Desembolso: debe banco (neto), 6734 (intereses), 6391 (comisión y gastos) /
  haber 1214 (factor) por el adelanto. El saldo de la 1214 es el retenido.
- Cobro del factor: debe banco / haber 1214 (factor) por el retenido.

- Pérdida del retenido (el cliente no pagó y el factor no libera el
  retenido): debe 6741 / haber 1214 (factor).

Con recurso (el riesgo sigue en la empresa; NIIF 9: la cuenta por cobrar no
se da de baja y el adelanto es una obligación)
- Cesión: sin asiento; la factura sigue pendiente en 1212 y se marca cedida.
- Desembolso: debe banco (neto), 3731 (intereses por devengar) o 6734,
  6391 / haber 4512 (factor) por el adelanto.
- Devengo: debe 6734 / haber 3731.
- Cobro del factor al cliente (total o parcial): debe 4512 (lo cobrado hasta
  cubrir el adelanto, al tipo de cambio histórico) y banco (el resto) /
  haber 1212 (cliente), conciliado con la factura.
- Recompra (el cliente no pagó): debe 4512 / haber banco por el adelanto no
  cubierto; la factura sigue pendiente.

Lo que paga el cliente se aplica primero al adelanto y luego al retenido.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from datetime import timedelta

from .factoring_account_config import MODALITIES

#: DU 013-2020 (art. 7): el adquirente tiene 8 días calendario desde que la
#: factura electrónica se pone a su disposición para dar su conformidad; si no
#: la objeta, se presume conforme (sin prueba en contrario).
CONFORMITY_DAYS = 8
CONFORMITY_STATES = [
    ('pending', 'Pendiente'),
    ('accepted', 'Conforme (expresa)'),
    ('presumed', 'Conforme (presunta)'),
    ('rejected', 'Disconforme'),
]

STATES = [
    ('draft', 'Borrador'),
    ('assigned', 'Cedida'),
    ('disbursed', 'Desembolsada'),
    ('done', 'Liquidada'),
    ('repurchased', 'Recomprada'),
    ('cancelled', 'Cancelada'),
]
LINE_STATES = [
    ('draft', 'Borrador'),
    ('assigned', 'Cedida'),
    ('collected', 'Cobrada'),
    ('repurchased', 'Recomprada'),
    ('lost', 'Retenido perdido'),
    ('cancelled', 'Cancelada'),
]
#: Una factura en una línea con estos estados no se puede volver a ceder.
ACTIVE_LINE_STATES = ('draft', 'assigned', 'collected', 'lost')


class L10nPeFactoring(models.Model):
    _name = 'l10n_pe.factoring'
    _description = 'Operación de factoring'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'date desc, id desc'

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    state = fields.Selection(STATES, string='Estado', default='draft', required=True,
                             readonly=True, copy=False, tracking=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    factor_id = fields.Many2one(
        'res.partner', string='Factor', tracking=True, check_company=True,
        help='Banco o empresa de factoring que compra las facturas.')
    contract_ref = fields.Char(string='Contrato', tracking=True)
    modality = fields.Selection(
        MODALITIES, string='Modalidad', required=True, default='without_recourse', tracking=True,
        help='Sin recurso: el factor asume el riesgo y la factura se da de baja. Con recurso: '
             'si el cliente no paga, la empresa devuelve el adelanto.')
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                  default=lambda self: self.env.company.currency_id)
    date = fields.Date(string='Fecha de cesión', required=True, default=fields.Date.context_today,
                       tracking=True)
    journal_id = fields.Many2one(
        'account.journal', string='Diario', required=True, check_company=True,
        domain="[('type', '=', 'general')]",
        default=lambda self: self.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', self.env.company.id)], limit=1),
        help='Diario de la cesión y del devengo de intereses.')
    default_advance_percent = fields.Float(
        string='% de adelanto', default=100.0, digits=(5, 2),
        help='Porcentaje del valor nominal que adelanta el factor; el resto queda retenido '
             'hasta que el cliente paga. Se propone en cada factura.')
    line_ids = fields.One2many('l10n_pe.factoring.line', 'factoring_id', string='Facturas', copy=True)
    note = fields.Html(string='Notas')

    # Importes
    nominal_amount = fields.Monetary(string='Valor nominal', compute='_compute_amounts', store=True)
    advance_amount = fields.Monetary(string='Adelanto', compute='_compute_amounts', store=True)
    retained_amount = fields.Monetary(
        string='Retenido', compute='_compute_amounts', store=True,
        help='Parte del nominal que el factor paga cuando el cliente cancela la factura.')
    interest_amount = fields.Monetary(string='Intereses', readonly=True, copy=False)
    fee_amount = fields.Monetary(string='Comisión', readonly=True, copy=False)
    expense_amount = fields.Monetary(string='Gastos', readonly=True, copy=False)
    net_amount = fields.Monetary(
        string='Neto desembolsado', readonly=True, copy=False,
        help='Adelanto menos intereses, comisión y gastos: lo que entra al banco.')
    disbursement_date = fields.Date(string='Fecha de desembolso', readonly=True, copy=False)
    bank_journal_id = fields.Many2one('account.journal', string='Banco', readonly=True, copy=False,
                                      check_company=True)
    interest_deferred_amount = fields.Monetary(
        string='Intereses por devengar', readonly=True, copy=False,
        help='Con recurso: intereses del desembolso enviados a la cuenta de intereses diferidos.')
    interest_accrued_amount = fields.Monetary(string='Intereses devengados', readonly=True, copy=False)
    interest_pending_amount = fields.Monetary(
        string='Intereses pendientes de devengo', compute='_compute_interest_pending')
    loss_amount = fields.Monetary(
        string='Retenido perdido', readonly=True, copy=False,
        help='Sin recurso: retenido que el factor no liberó porque el cliente no pagó.')
    financial_cost = fields.Monetary(
        string='Costo financiero', compute='_compute_financial_cost', store=True,
        help='Intereses, comisión, gastos y retenido perdido de la operación.')
    collected_amount = fields.Monetary(
        string='Cobrado por el factor', compute='_compute_amounts', store=True)

    move_ids = fields.Many2many('account.move', string='Asientos', readonly=True, copy=False,
                                check_company=True)
    move_count = fields.Integer(string='N.º de asientos', compute='_compute_move_count')
    line_count = fields.Integer(string='N.º de facturas', compute='_compute_amounts', store=True)

    _positive_percent = models.Constraint(
        'CHECK(default_advance_percent >= 0 AND default_advance_percent <= 100)',
        'El porcentaje de adelanto debe estar entre 0 y 100.')

    @api.depends('line_ids.nominal_amount', 'line_ids.advance_amount', 'line_ids.state',
                 'line_ids.collected_amount')
    def _compute_amounts(self):
        for operation in self:
            lines = operation.line_ids.filtered(lambda l: l.state != 'cancelled')
            operation.nominal_amount = sum(lines.mapped('nominal_amount'))
            operation.advance_amount = sum(lines.mapped('advance_amount'))
            operation.retained_amount = operation.nominal_amount - operation.advance_amount
            operation.collected_amount = sum(lines.mapped('collected_amount'))
            operation.line_count = len(lines)

    @api.depends('interest_amount', 'fee_amount', 'expense_amount', 'loss_amount')
    def _compute_financial_cost(self):
        for operation in self:
            operation.financial_cost = (operation.interest_amount + operation.fee_amount
                                        + operation.expense_amount + operation.loss_amount)

    @api.depends('interest_deferred_amount', 'interest_accrued_amount')
    def _compute_interest_pending(self):
        for operation in self:
            operation.interest_pending_amount = (
                operation.interest_deferred_amount - operation.interest_accrued_amount)

    def _compute_move_count(self):
        for operation in self:
            operation.move_count = len(operation.move_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('l10n_pe.factoring') or '/'
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        if self.filtered(lambda o: o.state not in ('draft', 'cancelled')):
            raise UserError(self.env._('Solo se eliminan operaciones en borrador o canceladas.'))

    # ------------------------------------------------------------------
    # Configuración y asientos
    # ------------------------------------------------------------------
    def _config(self):
        self.ensure_one()
        config = self.env['l10n_pe.factoring.account.config']._l10n_pe_get(
            self.company_id, self.modality, self.currency_id)
        if not config:
            raise UserError(self.env._(
                'Configure las cuentas del factoring (%(modality)s) en Perú ▸ Configuración ▸ '
                'Cuentas de la localización ▸ Factoring.',
                modality=dict(MODALITIES)[self.modality]))
        if self.modality == 'with_recourse' and not config.obligation_account_id:
            raise UserError(self.env._('Falta la cuenta de la obligación con el factor (factoring con recurso).'))
        return config

    def _line_vals(self, date, account, amount_currency, name, partner=False, factoring_line=False):
        """Apunte en la moneda de la operación con su contravalor a la fecha."""
        company = self.company_id
        currency = self.currency_id
        return {
            'name': name,
            'account_id': account.id,
            'partner_id': partner.id if partner else False,
            'currency_id': currency.id,
            'amount_currency': amount_currency,
            'balance': currency._convert(amount_currency, company.currency_id, company, date),
            'l10n_pe_factoring_line_id': factoring_line.id if factoring_line else False,
        }

    def _post_move(self, journal, date, ref, lines):
        """Crea y publica el asiento. Cada apunte se convierte por separado: el
        céntimo de diferencia va al primero sin factura (banco u obligación)."""
        lines = [vals for vals in lines if not self.currency_id.is_zero(vals['amount_currency'])]
        if not lines:
            return self.env['account.move']
        difference = self.company_id.currency_id.round(sum(vals['balance'] for vals in lines))
        if difference:
            target = next((vals for vals in lines if not vals['l10n_pe_factoring_line_id']), lines[0])
            target['balance'] -= difference
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': journal.id, 'date': date, 'ref': ref,
            'line_ids': [(0, 0, vals) for vals in lines],
        })
        move.action_post()
        self.move_ids = [(4, move.id)]
        return move

    # ------------------------------------------------------------------
    # Cesión
    # ------------------------------------------------------------------
    def _check_before_assign(self):
        self.ensure_one()
        if not self.factor_id:
            raise UserError(self.env._('Indique el factor.'))
        if not self.line_ids:
            raise UserError(self.env._('Agregue las facturas que cede.'))
        for line in self.line_ids:
            invoice = line.move_id
            if invoice.state != 'posted' or invoice.move_type != 'out_invoice':
                raise UserError(self.env._('%s no es una factura de cliente publicada.', invoice.display_name))
            if invoice.currency_id != self.currency_id:
                raise UserError(self.env._(
                    'La factura %(invoice)s está en %(currency)s y la operación en %(operation)s.',
                    invoice=invoice.display_name, currency=invoice.currency_id.name,
                    operation=self.currency_id.name))
            if self.currency_id.compare_amounts(line.nominal_amount, 0.0) <= 0:
                raise UserError(self.env._('El valor nominal de %s debe ser mayor que cero.', invoice.display_name))
            if self.currency_id.compare_amounts(line.nominal_amount, invoice.amount_residual) > 0:
                raise UserError(self.env._(
                    'El valor nominal de %(invoice)s supera su saldo pendiente (%(residual)s).',
                    invoice=invoice.display_name, residual=invoice.amount_residual))
            if line.conformity_state == 'rejected':
                raise UserError(self.env._(
                    'El cliente dio su disconformidad con %s: no se puede ceder hasta que se subsane '
                    '(nota de crédito o débito o nuevo comprobante).', invoice.display_name))

    def _assignment_warnings(self):
        """Avisos que no impiden ceder: factura al contado (la factura negociable
        nace de una venta al crédito) y conformidad aún pendiente."""
        self.ensure_one()
        notes = []
        cash = self.line_ids.filtered(lambda l: not l.is_credit)
        if cash:
            notes.append(self.env._('Facturas al contado (sin plazo de pago): %s.',
                                    ', '.join(cash.move_id.mapped('name'))))
        pending = self.line_ids.filtered(lambda l: l.conformity_state == 'pending')
        if pending:
            notes.append(self.env._('Conformidad del cliente pendiente: %s.', ', '.join(
                '%s (presunta desde %s)' % (l.move_id.name, l.presumed_conformity_date or '—')
                for l in pending)))
        return notes

    def action_assign(self):
        """Cede las facturas. Sin recurso, la deuda pasa al factor (1212 →
        1214) y la factura queda pagada. Con recurso no hay asiento: la cuenta
        por cobrar no se da de baja (NIIF 9) y la factura sigue pendiente
        hasta que el cliente paga al factor."""
        for operation in self:
            if operation.state != 'draft':
                raise UserError(operation.env._('Solo se ceden operaciones en borrador.'))
            operation._check_before_assign()
            config = operation._config()
            without_recourse = operation.modality == 'without_recourse'
            for note in operation._assignment_warnings():
                operation.message_post(body=note)
            if not without_recourse:
                operation.line_ids.write({'state': 'assigned'})
                operation.state = 'assigned'
                operation.message_post(body=operation.env._(
                    'Facturas cedidas a %(factor)s (%(modality)s): siguen pendientes hasta el cobro.',
                    factor=operation.factor_id.name, modality=dict(MODALITIES)[operation.modality]))
                continue
            vals = []
            for line in operation.line_ids:
                invoice = line.move_id
                receivable = line._open_receivable_lines()[:1]
                customer = invoice.commercial_partner_id
                label = operation.env._('Cesión %(invoice)s a %(factor)s',
                                        invoice=invoice.name, factor=operation.factor_id.name)
                vals += [
                    operation._line_vals(operation.date, config.assigned_account_id, line.nominal_amount, label,
                                         partner=operation.factor_id if without_recourse else customer,
                                         factoring_line=line),
                    operation._line_vals(operation.date, receivable.account_id, -line.nominal_amount, label,
                                         partner=customer, factoring_line=line),
                ]
            move = operation._post_move(operation.journal_id, operation.date,
                                        operation.env._('Cesión de facturas %s', operation.name), vals)
            for line in operation.line_ids:
                lines = move.line_ids.filtered(lambda l: l.l10n_pe_factoring_line_id == line)
                credit = lines.filtered(lambda l: l.amount_currency < 0)
                (credit + line._open_receivable_lines().filtered(
                    lambda l: l.account_id == credit.account_id)).reconcile()
                line.write({'state': 'assigned', 'assignment_line_id': (lines - credit).id,
                            'receivable_line_id': credit.id})
            operation.state = 'assigned'
            operation.message_post(body=operation.env._(
                'Facturas cedidas a %(factor)s (%(modality)s).', factor=operation.factor_id.name,
                modality=dict(MODALITIES)[operation.modality]))
        return True

    # ------------------------------------------------------------------
    # Cancelación
    # ------------------------------------------------------------------
    def action_cancel(self):
        """Anula una operación antes del desembolso: la factura vuelve al cliente."""
        for operation in self:
            if operation.state not in ('draft', 'assigned'):
                raise UserError(operation.env._(
                    'Con desembolso registrado no se cancela: use el cobro o la recompra.'))
            for move in operation.move_ids.filtered(lambda m: m.state == 'posted'):
                move.line_ids.remove_move_reconcile()
                move.button_draft()
                move.button_cancel()
            operation.line_ids.write({'state': 'cancelled'})
            operation.state = 'cancelled'
        return True

    def action_draft(self):
        for operation in self.filtered(lambda o: o.state == 'cancelled'):
            operation.line_ids.write({'state': 'draft', 'assignment_line_id': False,
                                      'receivable_line_id': False})
            operation.line_ids._check_unique_invoice()
            operation.state = 'draft'
        return True

    # ------------------------------------------------------------------
    # Estado final
    # ------------------------------------------------------------------
    def _update_final_state(self):
        for operation in self:
            lines = operation.line_ids.filtered(lambda l: l.state != 'cancelled')
            if lines.filtered(lambda l: l.state == 'assigned'):
                continue
            operation._accrue_pending_interest(fields.Date.context_today(operation))
            operation.state = 'repurchased' if all(l.state == 'repurchased' for l in lines) else 'done'

    def _obligation_vals(self, date, line, amount_currency, label):
        """Con recurso: cancela ``amount_currency`` de la obligación con el factor
        al contravalor histórico del adelanto (la 4512 no es conciliable, no
        recibe diferencia de cambio). La diferencia con el cambio del día va a
        las cuentas de diferencia de cambio de la compañía."""
        config = self._config()
        vals = self._line_vals(date, config.obligation_account_id, amount_currency, label,
                               partner=self.factor_id, factoring_line=line)
        company = self.company_id
        if self.currency_id == company.currency_id:
            return [vals]
        origin = self.move_ids.filtered(lambda m: m.state == 'posted').line_ids.filtered(
            lambda l: l.l10n_pe_factoring_line_id == line and l.account_id == config.obligation_account_id
            and l.amount_currency < 0)
        if not origin or self.currency_id.is_zero(sum(origin.mapped('amount_currency'))):
            return [vals]
        rate = abs(sum(origin.mapped('balance')) / sum(origin.mapped('amount_currency')))
        historic = company.currency_id.round(amount_currency * rate)
        difference = vals['balance'] - historic
        vals['balance'] = historic
        if company.currency_id.is_zero(difference):
            return [vals]
        # Diferencia al debe (el adelanto vale más hoy): pérdida; al haber: ganancia.
        account = (company.expense_currency_exchange_account_id if difference > 0
                   else company.income_currency_exchange_account_id)
        return [vals, {
            'name': self.env._('Diferencia de cambio %s', label),
            'account_id': account.id,
            'currency_id': company.currency_id.id,
            'amount_currency': difference,
            'balance': difference,
            'l10n_pe_factoring_line_id': False,
        }]

    def _accrue_pending_interest(self, date, amount=None):
        """Con recurso: pasa a gasto los intereses diferidos (todo lo pendiente
        si ``amount`` es None)."""
        self.ensure_one()
        amount = self.interest_pending_amount if amount is None else amount
        if self.currency_id.is_zero(amount):
            return self.env['account.move']
        config = self._config()
        if not config.deferred_interest_account_id:
            return self.env['account.move']
        label = self.env._('Devengo de intereses %s', self.name)
        move = self._post_move(self.journal_id, date, label, [
            self._line_vals(date, config.interest_account_id, amount, label),
            self._line_vals(date, config.deferred_interest_account_id, -amount, label),
        ])
        self.interest_accrued_amount += amount
        return move

    # ------------------------------------------------------------------
    # Botones
    # ------------------------------------------------------------------
    def _open_wizard(self, operation):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': dict(self.env['l10n_pe.factoring.wizard']._fields['operation'].selection)[operation],
            'res_model': 'l10n_pe.factoring.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_factoring_id': self.id, 'default_operation': operation},
        }

    def action_disburse(self):
        return self._open_wizard('disburse')

    def action_accrue(self):
        return self._open_wizard('accrue')

    def action_settle(self):
        return self._open_wizard('settle')

    def action_repurchase(self):
        return self._open_wizard('repurchase')

    def action_write_off(self):
        return self._open_wizard('write_off')

    def action_open_moves(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Asientos de %s', self.name),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.move_ids.ids)],
            'context': {'create': False},
        }

    def action_open_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Facturas de %s', self.name),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.line_ids.move_id.ids)],
            'context': {'create': False},
        }


class L10nPeFactoringLine(models.Model):
    _name = 'l10n_pe.factoring.line'
    _description = 'Factura cedida'
    _check_company_auto = True
    _order = 'factoring_id, due_date, id'

    factoring_id = fields.Many2one('l10n_pe.factoring', string='Operación', required=True,
                                   ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(related='factoring_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='factoring_id.currency_id', store=True)
    factor_id = fields.Many2one(related='factoring_id.factor_id', store=True, string='Factor')
    modality = fields.Selection(related='factoring_id.modality', store=True)
    move_id = fields.Many2one(
        'account.move', string='Factura', required=True, check_company=True, index=True,
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted'), "
               "('payment_state', 'not in', ('paid', 'in_payment', 'reversed'))]")
    partner_id = fields.Many2one(related='move_id.commercial_partner_id', store=True, string='Cliente')
    invoice_date = fields.Date(related='move_id.invoice_date', string='Fecha de la factura')
    nominal_amount = fields.Monetary(string='Valor nominal', required=True)
    advance_percent = fields.Float(string='% de adelanto', digits=(5, 2), default=100.0)
    advance_amount = fields.Monetary(string='Adelanto', compute='_compute_advance', store=True)
    retained_amount = fields.Monetary(string='Retenido', compute='_compute_advance', store=True)
    due_date = fields.Date(string='Vencimiento')
    cavali_number = fields.Char(
        string='Anotación CAVALI',
        help='Código de la anotación en cuenta de la factura negociable en CAVALI.')
    cavali_date = fields.Date(
        string='Fecha de anotación',
        help='Fecha de la anotación en cuenta en CAVALI: desde ella la factura negociable '
             'electrónica se puede transferir.')
    is_credit = fields.Boolean(
        string='Al crédito', compute='_compute_is_credit',
        help='La factura tiene plazo de pago (forma de pago «crédito»): la factura negociable '
             'nace de una venta al crédito.')
    conformity_state = fields.Selection(
        CONFORMITY_STATES, string='Conformidad', default='pending', required=True,
        help='Conformidad del cliente con la factura (DU 013-2020, art. 7): expresa, presunta '
             'a los 8 días calendario sin objeción, o disconformidad (impide ceder).')
    conformity_date = fields.Date(string='Fecha de conformidad')
    presumed_conformity_date = fields.Date(
        string='Conformidad presunta', compute='_compute_presumed_conformity_date', store=True,
        help='8 días calendario desde la emisión de la factura (la norma los cuenta desde que '
             'se pone a disposición del cliente y de SUNAT, hasta 2 días después).')
    collected_amount = fields.Monetary(
        string='Cobrado', readonly=True, copy=False,
        help='Lo que el cliente ya pagó al factor por esta factura.')
    advance_applied_amount = fields.Monetary(
        string='Aplicado al adelanto', readonly=True, copy=False,
        help='Parte de lo cobrado que cubrió el adelanto (el resto libera el retenido).')
    pending_amount = fields.Monetary(
        string='Por cobrar', compute='_compute_pending_amount', store=True,
        help='Valor nominal menos lo que el cliente ya pagó al factor.')
    state = fields.Selection(LINE_STATES, string='Estado', default='draft', required=True,
                             readonly=True, copy=False)
    assignment_line_id = fields.Many2one(
        'account.move.line', string='Apunte de la cesión', readonly=True, copy=False, check_company=True,
        help='Apunte en la cuenta de facturas cedidas (1214).')
    receivable_line_id = fields.Many2one(
        'account.move.line', string='Baja de la factura', readonly=True, copy=False, check_company=True,
        help='Apunte que saldó la cuenta por cobrar de la factura.')

    _percent = models.Constraint(
        'CHECK(advance_percent >= 0 AND advance_percent <= 100)',
        'El porcentaje de adelanto debe estar entre 0 y 100.')

    @api.depends('move_id.invoice_date', 'move_id.invoice_date_due')
    def _compute_is_credit(self):
        for line in self:
            invoice = line.move_id
            line.is_credit = bool(invoice.invoice_date_due and invoice.invoice_date
                                  and invoice.invoice_date_due > invoice.invoice_date)

    @api.depends('move_id.invoice_date')
    def _compute_presumed_conformity_date(self):
        for line in self:
            date = line.move_id.invoice_date
            line.presumed_conformity_date = date + timedelta(days=CONFORMITY_DAYS) if date else False

    @api.depends('nominal_amount', 'collected_amount')
    def _compute_pending_amount(self):
        for line in self:
            line.pending_amount = line.nominal_amount - line.collected_amount

    @api.onchange('conformity_state')
    def _onchange_conformity_state(self):
        for line in self:
            if line.conformity_state == 'presumed' and not line.conformity_date:
                line.conformity_date = line.presumed_conformity_date
            elif line.conformity_state == 'accepted' and not line.conformity_date:
                line.conformity_date = fields.Date.context_today(line)

    @api.depends('nominal_amount', 'advance_percent', 'currency_id')
    def _compute_advance(self):
        for line in self:
            currency = line.currency_id or line.company_id.currency_id
            line.advance_amount = currency.round(line.nominal_amount * line.advance_percent / 100.0)
            line.retained_amount = line.nominal_amount - line.advance_amount

    @api.onchange('move_id')
    def _onchange_move_id(self):
        for line in self:
            if line.move_id:
                line.nominal_amount = line.move_id._l10n_pe_factoring_net_pending()
                line.due_date = line.move_id.invoice_date_due
                line.advance_percent = line.factoring_id.default_advance_percent

    @api.model_create_multi
    def create(self, vals_list):
        # Sin importe ni vencimiento se proponen los de la factura.
        for vals in vals_list:
            if vals.get('move_id') and (not vals.get('nominal_amount') or not vals.get('due_date')):
                invoice = self.env['account.move'].browse(vals['move_id'])
                vals.setdefault('due_date', invoice.invoice_date_due)
                if not vals.get('nominal_amount'):
                    vals['nominal_amount'] = invoice._l10n_pe_factoring_net_pending()
        lines = super().create(vals_list)
        lines._check_unique_invoice()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if 'move_id' in vals:
            self._check_unique_invoice()
        return res

    def _check_unique_invoice(self):
        """Una factura no se cede dos veces (salvo que la operación anterior se
        cancelara o se recomprara)."""
        for line in self.filtered(lambda l: l.state in ACTIVE_LINE_STATES):
            other = self.search([('move_id', '=', line.move_id.id), ('id', '!=', line.id),
                                 ('state', 'in', ACTIVE_LINE_STATES)], limit=1)
            if other:
                raise ValidationError(self.env._(
                    'La factura %(invoice)s ya está en la operación de factoring %(operation)s.',
                    invoice=line.move_id.display_name, operation=other.factoring_id.name))

    def _open_receivable_lines(self):
        self.ensure_one()
        return self.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled)
