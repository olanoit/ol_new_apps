# -*- coding: utf-8 -*-
"""Operaciones con el banco sobre letras por cobrar ya enviadas.

Asientos según el PCGE 2019 (docs/letras/REQUISITOS_LETRAS.md):

- **Liquidación del descuento**: el banco abona el neto. Debe: banco (neto),
  6734 intereses, 6391 gastos bancarios; haber: 4511 préstamo del banco por el
  valor nominal (descuento con responsabilidad: la letra sigue en 1234).
- **Cobro del banco**:
  - cobranza libre: debe banco (neto) y 6391; haber 1233 (la letra).
  - descuento: el cliente pagó al banco, que cancela el préstamo. Debe 4511;
    haber 1234 (la letra).
- **Protesto**: la letra vuelve a cobrarse al cliente. Debe la cuenta de letras
  protestadas (configurable, por defecto en cartera 1232); haber 1233 o 1234.
  En descuento, además, el banco carga la letra en cuenta: debe 4511, haber
  banco. Los gastos de protesto: debe 6391, haber banco.
"""
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

#: Ley 27287, art. 72: protesto de la letra a fecha fija dentro de los 15 días
#: siguientes al vencimiento (texto original; contrastar con el SPIJ).
PROTEST_DAYS = 15


class L10nPeLetterBankWizard(models.TransientModel):
    _name = 'l10n_pe.letter.bank.wizard'
    _description = 'Operación del banco con letras'

    letter_id = fields.Many2one('l10n_pe.letter', string='Canje', required=True)
    operation = fields.Selection(
        selection=[('settle_discount', 'Liquidación del descuento'),
                   ('collected', 'Cobro del banco'),
                   ('protest', 'Protesto')],
        string='Operación', required=True)
    letter_line_ids = fields.Many2many(
        'l10n_pe.letter.line', string='Letras', required=True,
        domain="[('id', 'in', available_line_ids)]")
    available_line_ids = fields.Many2many(
        'l10n_pe.letter.line', compute='_compute_available_line_ids')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    bank_journal_id = fields.Many2one(
        'account.journal', string='Banco',
        domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]")
    company_id = fields.Many2one(related='letter_id.company_id')
    currency_id = fields.Many2one(related='letter_id.currency_id')
    nominal_amount = fields.Monetary(
        string='Valor nominal', compute='_compute_nominal_amount', currency_field='currency_id')
    interest_amount = fields.Monetary(string='Intereses del descuento', currency_field='currency_id')
    fee_amount = fields.Monetary(
        string='Comisiones y gastos', currency_field='currency_id',
        help='Comisión de cobranza o de descuento, portes o gastos de protesto.')
    net_amount = fields.Monetary(
        string='Neto en el banco', compute='_compute_net_amount', currency_field='currency_id')

    # ------------------------------------------------------------------
    # Cómputos
    # ------------------------------------------------------------------
    @api.depends('letter_id', 'operation')
    def _compute_available_line_ids(self):
        for wizard in self:
            wizard.available_line_ids = wizard.letter_id.letter_line_ids.filtered(
                lambda l: l._l10n_pe_bank_operation_allowed(wizard.operation))

    @api.depends('letter_line_ids')
    def _compute_nominal_amount(self):
        for wizard in self:
            wizard.nominal_amount = sum(wizard.letter_line_ids.mapped('imp_div'))

    @api.depends('nominal_amount', 'interest_amount', 'fee_amount', 'operation')
    def _compute_net_amount(self):
        for wizard in self:
            if wizard.operation == 'settle_discount':
                wizard.net_amount = wizard.nominal_amount - wizard.interest_amount - wizard.fee_amount
            elif wizard.operation == 'collected':
                billing = wizard.letter_line_ids.filtered(lambda l: l.letter_type == 'billing')
                wizard.net_amount = sum(billing.mapped('imp_div')) - wizard.fee_amount
            else:
                wizard.net_amount = 0.0

    # ------------------------------------------------------------------
    # Asiento
    # ------------------------------------------------------------------
    def _line(self, account, amount_currency, name, partner=False, letter_line=False):
        """Apunte en la moneda del canje con su contravalor a la fecha."""
        company = self.company_id
        currency = self.currency_id or company.currency_id
        balance = currency._convert(amount_currency, company.currency_id, company, self.date)
        vals = {
            'name': name,
            'account_id': account.id,
            'partner_id': partner.id if partner else False,
            'currency_id': currency.id,
            'amount_currency': amount_currency,
            'balance': balance,
        }
        if letter_line:
            vals['l10n_pe_letter_line_id'] = letter_line.id
        return vals

    def _post(self, journal, ref, lines):
        lines = [vals for vals in lines if vals['amount_currency']]
        # Cada apunte se convierte por separado: el céntimo de diferencia en
        # moneda extranjera va al primero sin letra (banco o préstamo).
        difference = self.company_id.currency_id.round(sum(vals['balance'] for vals in lines))
        if difference:
            target = next((vals for vals in lines if 'l10n_pe_letter_line_id' not in vals), lines[0])
            target['balance'] -= difference
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': journal.id, 'date': self.date, 'ref': ref,
            'line_ids': [(0, 0, vals) for vals in lines],
        })
        move.action_post()
        self.letter_id.bank_move_ids = [(4, move.id)]
        return move

    def _require(self, field_value, label):
        if not field_value:
            raise UserError(_('Configure %s en Ajustes ▸ Contabilidad ▸ Letras de cambio.', label))
        return field_value

    def action_apply(self):
        self.ensure_one()
        letter = self.letter_id
        if letter.type != 'out_invoice':
            raise UserError(_('Las operaciones con el banco son para letras por cobrar.'))
        if not self.letter_line_ids:
            raise UserError(_('Seleccione las letras.'))
        not_allowed = self.letter_line_ids.filtered(
            lambda l: not l._l10n_pe_bank_operation_allowed(self.operation))
        if not_allowed:
            raise UserError(_('Estas letras no admiten la operación: %s.',
                              ', '.join(not_allowed.mapped('nro_letter'))))
        if self.date > fields.Date.context_today(self):
            raise UserError(_('La fecha no puede ser posterior a hoy.'))
        if self.interest_amount < 0 or self.fee_amount < 0:
            raise UserError(_('Los intereses y los gastos no pueden ser negativos.'))
        if self.operation == 'settle_discount':
            self._apply_settle_discount()
        elif self.operation == 'collected':
            self._apply_collected()
        else:
            self._apply_protest()
        letter.letter_line_ids.invalidate_recordset(['adeudado', 'payment_state'])
        return {'type': 'ir.actions.act_window_close'}

    def _split(self, amount, records):
        """Reparte ``amount`` entre ``records``; la última absorbe el redondeo."""
        currency = self.currency_id
        share = currency.round(amount / len(records)) if records else 0.0
        result = {record: share for record in records}
        if records:
            result[records[-1]] = currency.round(amount - share * (len(records) - 1))
        return result

    def _bank_account(self):
        journal = self._require(self.bank_journal_id, _('el banco'))
        return journal, journal.default_account_id

    def _apply_settle_discount(self):
        company = self.company_id
        journal, bank_account = self._bank_account()
        if self.currency_id.compare_amounts(self.net_amount, 0.0) <= 0:
            raise UserError(_('Los intereses y gastos no pueden ser mayores que el valor nominal.'))
        loan = self._require(company.l10n_pe_letter_loan_account_id, _('la cuenta de la obligación'))
        lines = [self._line(bank_account, self.net_amount, _('Abono del descuento'))]
        if self.interest_amount:
            lines.append(self._line(self._require(company.l10n_pe_letter_interest_account_id,
                                                  _('la cuenta de intereses')),
                                    self.interest_amount, _('Intereses del descuento')))
        if self.fee_amount:
            lines.append(self._line(self._require(company.l10n_pe_letter_fee_account_id,
                                                  _('la cuenta de gastos bancarios')),
                                    self.fee_amount, _('Gastos del descuento')))
        lines.append(self._line(loan, -self.nominal_amount, _('Letras en descuento')))
        move = self._post(journal, _('Liquidación del descuento %s', self.letter_id.name), lines)
        self.letter_line_ids.write({'discount_move_id': move.id})

    def _close_destination(self, letter_line, counter_account, journal, label):
        """Cancela el apunte de la letra en el banco (1233/1234) contra ``counter_account``."""
        destination = letter_line._l10n_pe_open_bank_line()
        amount = destination.amount_residual_currency
        lines = [
            self._line(counter_account, amount, label),
            self._line(destination.account_id, -amount, letter_line.nro_letter,
                       partner=letter_line.partner_id, letter_line=letter_line),
        ]
        return destination, lines

    def _apply_collected(self):
        company = self.company_id
        billing = self.letter_line_ids.filtered(lambda l: l.letter_type == 'billing')
        if self.fee_amount and not billing:
            raise UserError(_('La comisión de cobranza solo se registra en letras en cobranza libre.'))
        fees = self._split(self.fee_amount, billing)
        for letter_line in self.letter_line_ids:
            if letter_line.letter_type == 'billing':
                journal, bank_account = self._bank_account()
                destination, lines = self._close_destination(
                    letter_line, bank_account, journal, _('Cobranza de la letra'))
                fee = fees[letter_line]
                if fee:
                    lines[0]['amount_currency'] -= fee
                    lines[0]['balance'] = self.currency_id._convert(
                        lines[0]['amount_currency'], company.currency_id, company, self.date)
                    lines.append(self._line(self._require(company.l10n_pe_letter_fee_account_id,
                                                          _('la cuenta de gastos bancarios')),
                                            fee, _('Comisión de cobranza')))
            else:
                journal = self.bank_journal_id or self.letter_id.journal_id
                loan = self._require(company.l10n_pe_letter_loan_account_id,
                                     _('la cuenta de la obligación'))
                destination, lines = self._close_destination(
                    letter_line, loan, journal, _('Cancelación del descuento'))
            move = self._post(journal, _('Cobro de la letra %s', letter_line.nro_letter), lines)
            new_line = move.line_ids.filtered(lambda l: l.l10n_pe_letter_line_id == letter_line)
            (new_line + destination).reconcile()
            letter_line.write({'collection_move_id': move.id})

    def _apply_protest(self):
        company = self.company_id
        fees = self._split(self.fee_amount, self.letter_line_ids)
        for letter_line in self.letter_line_ids:
            protested_account = letter_line._l10n_pe_protested_account()
            destination = letter_line._l10n_pe_open_bank_line()
            amount = destination.amount_residual_currency
            journal = self.bank_journal_id or self.letter_id.journal_id
            lines = [
                self._line(protested_account, amount, _('Letra protestada %s', letter_line.nro_letter),
                           partner=letter_line.partner_id, letter_line=letter_line),
                self._line(destination.account_id, -amount, letter_line.nro_letter,
                           partner=letter_line.partner_id, letter_line=letter_line),
            ]
            if letter_line.letter_type == 'discount' and letter_line.discount_move_id:
                # El banco carga en cuenta la letra que descontó y no cobró.
                journal, bank_account = self._bank_account()
                loan = self._require(company.l10n_pe_letter_loan_account_id,
                                     _('la cuenta de la obligación'))
                lines += [self._line(loan, amount, _('Cargo del banco por la letra protestada')),
                          self._line(bank_account, -amount, _('Cargo del banco por la letra protestada'))]
            fee = fees[letter_line]
            if fee:
                journal, bank_account = self._bank_account()
                lines += [self._line(self._require(company.l10n_pe_letter_fee_account_id,
                                                   _('la cuenta de gastos bancarios')),
                                     fee, _('Gastos de protesto')),
                          self._line(bank_account, -fee, _('Gastos de protesto'))]
            move = self._post(journal, _('Protesto de la letra %s', letter_line.nro_letter), lines)
            closing = move.line_ids.filtered(
                lambda l: l.l10n_pe_letter_line_id == letter_line and l.account_id == destination.account_id
                and l.amount_currency < 0)
            (closing + destination).reconcile()
            letter_line.write({'letter_type': 'protested', 'protest_date': self.date,
                               'protest_move_id': move.id})
            limit = letter_line.expiration_date + timedelta(days=PROTEST_DAYS)
            if self.date > limit:
                self.letter_id.message_post(body=_(
                    'La letra %(letter)s se protestó el %(date)s, más de %(days)s días después de su '
                    'vencimiento (%(due)s). Verifique el plazo del art. 72 de la Ley 27287.',
                    letter=letter_line.nro_letter, date=self.date, days=PROTEST_DAYS,
                    due=letter_line.expiration_date))
