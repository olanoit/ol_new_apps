# -*- coding: utf-8 -*-
"""Cartas fianza.

* **Emitidas**: el banco garantiza a un tercero (una entidad pública en una
  licitación, un cliente) que la empresa cumplirá. No es deuda mientras no se
  ejecute: se controla con su vigencia, consume la línea de crédito y genera
  una comisión (6391). Opcionalmente se registra en cuentas de orden.
* **Recibidas**: un proveedor o contratista entrega a la empresa la fianza de un
  banco (fiel cumplimiento, adelanto). Hay que vigilar su vencimiento: el fiador
  queda libre si no se le requiere dentro de los 15 días siguientes (art. 1898
  del Código Civil).

Se rigen por la Ley 26702 (art. 221) y, en la contratación pública, por la Ley
30225 y su reglamento (solidarias, irrevocables, incondicionales y de
realización automática).
"""
import math
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

STATES = [
    ('draft', 'Borrador'),
    ('active', 'Vigente'),
    ('expired', 'Vencida'),
    ('renewed', 'Renovada'),
    ('released', 'Liberada'),
    ('executed', 'Ejecutada'),
    ('cancel', 'Anulada'),
]
DIRECTIONS = [('issued', 'Emitida a nuestro pedido'), ('received', 'Recibida de un tercero')]
GUARANTEE_TYPES = [
    ('performance', 'Fiel cumplimiento'),
    ('advance', 'Adelanto directo'),
    ('materials', 'Adelanto de materiales'),
    ('bid', 'Seriedad de oferta'),
    ('payment', 'Pago o crédito comercial'),
    ('customs', 'Aduanera'),
    ('other', 'Otra'),
]
#: Días del art. 1898 del Código Civil para requerir al fiador tras el vencimiento.
CLAIM_DAYS = 15


class L10nPeBankGuarantee(models.Model):
    _name = 'l10n_pe.bank.guarantee'
    _description = 'Carta fianza'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'date_end, id'

    name = fields.Char(string='Número interno', readonly=True, copy=False, default='/')
    number = fields.Char(string='N.º de carta fianza', tracking=True, copy=False)
    state = fields.Selection(STATES, string='Estado', default='draft', required=True, readonly=True,
                             copy=False, tracking=True)
    direction = fields.Selection(DIRECTIONS, string='Sentido', required=True, default='issued', tracking=True)
    guarantee_type = fields.Selection(GUARANTEE_TYPES, string='Tipo', required=True, default='performance',
                                      tracking=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda de la compañía')
    bank_id = fields.Many2one('res.partner', string='Banco emisor', required=True, check_company=True,
                              tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Beneficiario / afianzado', required=True, check_company=True, tracking=True,
        help='Emitida: a favor de quién (la entidad o el cliente). Recibida: quién la entrega (el proveedor '
             'o contratista afianzado).')
    contract_reference = fields.Char(string='Contrato o proceso', tracking=True,
                                     help='Contrato, orden de compra o proceso de selección que garantiza.')
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                  default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary(string='Importe', required=True, tracking=True)
    date_issue = fields.Date(string='Emisión', required=True, default=fields.Date.context_today, tracking=True)
    date_end = fields.Date(string='Vencimiento', required=True, tracking=True)
    claim_deadline = fields.Date(string='Requerir al banco hasta', compute='_compute_claim_deadline', store=True,
                                 help='Vencimiento + 15 días (art. 1898 del Código Civil): después, el banco '
                                      'queda liberado si no se le requirió.')
    is_solidary = fields.Boolean(string='Solidaria', default=True)
    is_irrevocable = fields.Boolean(string='Irrevocable', default=True)
    is_unconditional = fields.Boolean(string='Incondicional', default=True)
    is_automatic = fields.Boolean(string='De realización automática', default=True,
                                  help='El banco la honra a simple requerimiento del beneficiario.')
    no_excussion = fields.Boolean(string='Sin beneficio de excusión', default=True)
    user_id = fields.Many2one('res.users', string='Responsable', default=lambda self: self.env.user)
    credit_line_id = fields.Many2one(
        'l10n_pe.treasury.credit.line', string='Línea de crédito', check_company=True,
        domain="[('partner_id', '=', bank_id), ('line_type', 'in', ('global', 'guarantee'))]")
    deposit_id = fields.Many2one(
        'l10n_pe.term.deposit', string='Fondo en garantía', check_company=True,
        domain="[('deposit_type', '=', 'guarantee_fund')]",
        help='Depósito que el banco retiene como respaldo de la carta fianza (Depósitos y garantías).')
    # Comisión (solo emitidas)
    journal_id = fields.Many2one('account.journal', string='Banco de la empresa', check_company=True,
                                 domain="[('type', '=', 'bank')]",
                                 help='Cuenta de la que el banco debita la comisión.')
    commission_rate = fields.Float(string='Comisión (% trimestral)', digits=(6, 4),
                                   help='Tasa por trimestre o fracción sobre el importe.')
    commission_min = fields.Monetary(string='Comisión mínima')
    commission_amount = fields.Monetary(string='Comisión', compute='_compute_commission', store=True,
                                        readonly=False)
    commission_account_id = fields.Many2one(
        'account.account', string='Cuenta de la comisión', check_company=True,
        default=lambda self: self.env.ref('account.%s_chart6391' % self.env.company.id, raise_if_not_found=False),
        help='Gasto por la comisión (6391 gastos bancarios).')
    itf_applies = fields.Boolean(string='ITF en la comisión')
    renewed_from_id = fields.Many2one('l10n_pe.bank.guarantee', string='Renueva a', readonly=True, copy=False,
                                      check_company=True)
    renewal_id = fields.Many2one('l10n_pe.bank.guarantee', string='Renovada en', readonly=True, copy=False,
                                 check_company=True)
    move_ids = fields.Many2many('account.move', string='Asientos', readonly=True, copy=False)
    move_count = fields.Integer(string='N.º de asientos', compute='_compute_move_count')
    notice_sent = fields.Boolean(string='Aviso enviado', readonly=True, copy=False)
    due_soon = fields.Boolean(string='Por vencer', compute='_compute_due_soon')
    days_to_end = fields.Integer(string='Días para el vencimiento', compute='_compute_due_soon')
    notes = fields.Html(string='Notas')

    _positive_amount = models.Constraint('CHECK(amount > 0)', 'El importe debe ser mayor que cero.')

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------
    @api.depends('date_end')
    def _compute_claim_deadline(self):
        for guarantee in self:
            guarantee.claim_deadline = guarantee.date_end + timedelta(days=CLAIM_DAYS) if guarantee.date_end else False

    @api.depends('amount', 'commission_rate', 'commission_min', 'date_issue', 'date_end', 'direction')
    def _compute_commission(self):
        for guarantee in self:
            if guarantee.direction != 'issued' or not guarantee.commission_rate or \
                    not (guarantee.date_issue and guarantee.date_end):
                guarantee.commission_amount = guarantee.commission_min if guarantee.direction == 'issued' else 0.0
                continue
            quarters = max(math.ceil((guarantee.date_end - guarantee.date_issue).days / 90.0), 1)
            amount = guarantee.amount * guarantee.commission_rate / 100.0 * quarters
            guarantee.commission_amount = guarantee.currency_id.round(max(amount, guarantee.commission_min))

    def _compute_move_count(self):
        for guarantee in self:
            guarantee.move_count = len(guarantee.move_ids)

    @api.depends('date_end', 'state', 'company_id.l10n_pe_treasury_notice_days')
    def _compute_due_soon(self):
        today = fields.Date.context_today(self)
        for guarantee in self:
            days = (guarantee.date_end - today).days if guarantee.date_end else 0
            guarantee.days_to_end = days
            guarantee.due_soon = guarantee.state == 'active' and days <= guarantee.company_id.l10n_pe_treasury_notice_days

    @api.constrains('date_issue', 'date_end')
    def _check_dates(self):
        for guarantee in self:
            if guarantee.date_end and guarantee.date_issue and guarantee.date_end <= guarantee.date_issue:
                raise ValidationError(self.env._('El vencimiento debe ser posterior a la emisión.'))

    # ------------------------------------------------------------------
    # Asientos
    # ------------------------------------------------------------------
    def _line(self, date, account, amount_currency, name, partner=None):
        company = self.company_id
        return {
            'name': name,
            'account_id': account.id,
            'partner_id': (partner or self.partner_id).id,
            'currency_id': self.currency_id.id,
            'amount_currency': amount_currency,
            'balance': self.currency_id._convert(amount_currency, company.currency_id, company, date),
        }

    def _post_move(self, journal, date, ref, lines):
        lines = [vals for vals in lines if not self.currency_id.is_zero(vals['amount_currency'])]
        if not lines:
            return self.env['account.move']
        difference = self.company_id.currency_id.round(sum(vals['balance'] for vals in lines))
        if difference:
            lines[0]['balance'] -= difference
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': journal.id, 'date': date, 'ref': ref,
            'l10n_pe_bank_guarantee_id': self.id,
            'line_ids': [fields.Command.create(vals) for vals in lines],
        })
        move.action_post()
        self.move_ids = [fields.Command.link(move.id)]
        return move

    def _l10n_pe_memo(self, date, sign, label):
        """Cuentas de orden de la fianza emitida o recibida (si están activadas)."""
        self.ensure_one()
        company = self.company_id.root_id
        if not company.l10n_pe_guarantee_memo:
            return
        debit, credit = company._l10n_pe_guarantee_memo_accounts(self.direction)
        journal = company.l10n_pe_guarantee_memo_journal_id or self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self.company_id), ('type', '=', 'general')], limit=1)
        if not (debit and credit and journal):
            raise UserError(self.env._('Configure las cuentas de orden de las cartas fianza en Ajustes ▸ Perú.'))
        self._post_move(journal, date, label, [
            self._line(date, debit, sign * self.amount, label),
            self._line(date, credit, -sign * self.amount, label),
        ])

    def _l10n_pe_charge_commission(self, date, amount, label):
        """Comisión debitada por el banco: gasto contra los pagos pendientes del banco."""
        self.ensure_one()
        if self.direction != 'issued' or self.currency_id.is_zero(amount or 0.0):
            return
        if not (self.journal_id and self.commission_account_id):
            raise UserError(self.env._('Indique el banco de la empresa y la cuenta de la comisión.'))
        bank = self.journal_id._l10n_pe_treasury_outstanding_account('outbound')
        lines = [
            self._line(date, self.commission_account_id, amount, label, partner=self.bank_id),
            self._line(date, bank, -amount, label, partner=self.bank_id),
        ]
        if self.itf_applies:
            from odoo.addons.al_l10n_pe_itf.models.res_company import itf_amount
            itf = itf_amount(amount, self.company_id.root_id.l10n_pe_itf_rate)
            if itf:
                itf_label = self.env._('ITF %s', label)
                lines += [self._line(date, self.company_id._l10n_pe_itf_account(), itf, itf_label, self.bank_id),
                          self._line(date, bank, -itf, itf_label, self.bank_id)]
        self._post_move(self.journal_id, date, label, lines)

    # ------------------------------------------------------------------
    # Flujo
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('l10n_pe.bank.guarantee') or '/'
        return super().create(vals_list)

    def unlink(self):
        if self.filtered(lambda g: g.state not in ('draft', 'cancel')):
            raise UserError(self.env._('Solo se eliminan cartas fianza en borrador o anuladas.'))
        return super().unlink()

    def write(self, vals):
        credit_lines = self.credit_line_id
        res = super().write(vals)
        if {'state', 'credit_line_id', 'amount'} & set(vals):
            (credit_lines | self.credit_line_id)._l10n_pe_invalidate_usage()
        return res

    def _check_state(self, states):
        for guarantee in self:
            if guarantee.state not in states:
                raise UserError(self.env._('La carta fianza %(name)s está en estado «%(state)s».',
                                           name=guarantee.display_name, state=dict(STATES)[guarantee.state]))

    def _check_credit_line(self):
        for guarantee in self.filtered(lambda g: g.credit_line_id and g.direction == 'issued'):
            line = guarantee.credit_line_id
            needed = line._l10n_pe_convert(guarantee.amount, guarantee.currency_id)
            if line.currency_id.compare_amounts(line.amount_available, needed) < 0:
                raise UserError(self.env._('La carta fianza supera el disponible de la línea %(line)s (%(available)s).',
                                           line=line.name, available=line.amount_available))

    def action_activate(self):
        """Emitida o recibida: queda vigente (comisión y cuentas de orden si corresponde)."""
        self._check_state(('draft',))
        for guarantee in self:
            if not guarantee.number:
                raise UserError(self.env._('Indique el número de la carta fianza.'))
            guarantee._check_credit_line()
            label = self.env._('Carta fianza %(number)s %(type)s', number=guarantee.number,
                               type=dict(GUARANTEE_TYPES)[guarantee.guarantee_type])
            guarantee._l10n_pe_charge_commission(guarantee.date_issue, guarantee.commission_amount,
                                                 self.env._('Comisión %s', label))
            guarantee._l10n_pe_memo(guarantee.date_issue, 1, label)
            guarantee.state = 'active'
        return True

    def _l10n_pe_close(self, state, date, body):
        self.ensure_one()
        self._l10n_pe_memo(date, -1, self.env._('%(state)s carta fianza %(number)s',
                                                state=dict(STATES)[state], number=self.number))
        self.write({'state': state})
        self.activity_ids.action_done()
        self.message_post(body=body)

    def action_release(self):
        """Devuelta al banco (emitida) o al afianzado (recibida) al cumplirse lo garantizado."""
        self._check_state(('active', 'expired'))
        today = fields.Date.context_today(self)
        for guarantee in self:
            guarantee._l10n_pe_close('released', today, self.env._('Carta fianza liberada.'))
        return True

    def action_cancel(self):
        self._check_state(('draft',))
        self.write({'state': 'cancel'})
        return True

    def action_draft(self):
        self._check_state(('cancel',))
        self.write({'state': 'draft'})
        return True

    def _l10n_pe_renew(self, date_end, amount=None, commission=None, date=None):
        """Renueva la fianza hasta ``date_end``: una nueva carta fianza enlazada
        (mismo número salvo que el banco emita otro) con su comisión."""
        self.ensure_one()
        self._check_state(('active', 'expired'))
        date = date or self.date_end
        if date_end <= date:
            raise UserError(self.env._('El nuevo vencimiento debe ser posterior al %s.', date))
        new = self.copy({
            'date_issue': date, 'date_end': date_end, 'amount': amount or self.amount,
            'number': self.number, 'renewed_from_id': self.id,
        })
        if commission is not None:
            new.commission_amount = commission
        # La línea de crédito ya tiene tomado el importe de la fianza anterior.
        self.write({'state': 'renewed', 'renewal_id': new.id})
        self.activity_ids.action_done()
        label = self.env._('Renovación carta fianza %s', new.number)
        new._l10n_pe_charge_commission(date, new.commission_amount, self.env._('Comisión %s', label))
        if self.currency_id.compare_amounts(new.amount, self.amount) != 0:
            # Las cuentas de orden siguen la diferencia de importe.
            difference = new.amount - self.amount
            company = self.company_id.root_id
            if company.l10n_pe_guarantee_memo:
                debit, credit = company._l10n_pe_guarantee_memo_accounts(self.direction)
                journal = company.l10n_pe_guarantee_memo_journal_id or self.env['account.journal'].search([
                    *self.env['account.journal']._check_company_domain(self.company_id), ('type', '=', 'general')],
                    limit=1)
                new._post_move(journal, date, label, [new._line(date, debit, difference, label),
                                                      new._line(date, credit, -difference, label)])
        new.state = 'active'
        self.message_post(body=self.env._('Renovada en %s.', new._get_html_link()))
        return new

    def _l10n_pe_execute(self, date, amount, journal, account):
        """Ejecución: emitida, el banco paga al beneficiario y lo carga a la
        empresa; recibida, la empresa cobra al banco."""
        self.ensure_one()
        self._check_state(('active', 'expired'))
        if self.currency_id.compare_amounts(amount, 0.0) <= 0 or self.currency_id.compare_amounts(amount, self.amount) > 0:
            raise UserError(self.env._('El importe ejecutado debe ser mayor que cero y no superar la fianza.'))
        label = self.env._('Ejecución carta fianza %s', self.number)
        if self.direction == 'issued':
            bank = journal._l10n_pe_treasury_outstanding_account('outbound')
            lines = [self._line(date, account, amount, label), self._line(date, bank, -amount, label, self.bank_id)]
        else:
            bank = journal._l10n_pe_treasury_outstanding_account('inbound')
            lines = [self._line(date, bank, amount, label, self.bank_id), self._line(date, account, -amount, label)]
        self._post_move(journal, date, label, lines)
        self._l10n_pe_close('executed', date, self.env._('Ejecutada por %(amount)s %(currency)s.', amount=amount,
                                                         currency=self.currency_id.name))
        return True

    def _open_wizard(self, operation):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': dict(self.env['l10n_pe.bank.guarantee.wizard']._fields['operation'].selection)[operation],
            'res_model': 'l10n_pe.bank.guarantee.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_guarantee_id': self.id, 'default_operation': operation},
        }

    def action_renew(self):
        return self._open_wizard('renew')

    def action_execute(self):
        return self._open_wizard('execute')

    def action_open_moves(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Asientos'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.move_ids.ids)],
            'context': {'create': False},
        }

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_l10n_pe_bank_guarantees(self):
        """Diario: avisa antes del vencimiento y marca las vencidas; en las
        recibidas, el aviso vence con el plazo del art. 1898."""
        today = fields.Date.context_today(self)
        for company in self.env['res.company'].search([]):
            notice = company.l10n_pe_treasury_notice_days
            guarantees = self.with_company(company).search([
                ('company_id', '=', company.id), ('state', 'in', ('active', 'expired'))])
            for guarantee in guarantees:
                if guarantee.state == 'active' and not guarantee.notice_sent and \
                        guarantee.date_end - timedelta(days=notice) <= today:
                    if guarantee.direction == 'received':
                        deadline = guarantee.claim_deadline
                        note = self.env._(
                            'La carta fianza de %(partner)s vence el %(date)s. Si la obligación no está cumplida, '
                            'pida su renovación o requiera al banco antes del %(deadline)s (art. 1898 del '
                            'Código Civil).', partner=guarantee.partner_id.name, date=guarantee.date_end,
                            deadline=deadline)
                    else:
                        deadline = guarantee.date_end
                        note = self.env._('Vence el %(date)s: renuévela con el banco o solicite su devolución '
                                          'al beneficiario.', date=guarantee.date_end)
                    guarantee.activity_schedule(
                        'mail.mail_activity_data_todo', date_deadline=deadline,
                        summary=self.env._('Vence la carta fianza %s', guarantee.number), note=note,
                        user_id=(guarantee.user_id or self.env.user).id)
                    guarantee.notice_sent = True
                if guarantee.state == 'active' and guarantee.date_end < today:
                    guarantee.state = 'expired'
        return True
