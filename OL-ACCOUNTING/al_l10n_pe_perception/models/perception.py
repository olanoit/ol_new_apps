# -*- coding: utf-8 -*-
"""Comprobante de percepción electrónico (tipo 40).

El agente de percepción lo emite al cobrar (art. 4 de la R.S. 058-2006/SUNAT),
uno por cliente y por tasa (art. 10.4), desde el sistema del contribuyente
con la serie P### (R.S. 274-2015/SUNAT; electrónico obligatorio desde el
1/1/2018). Cada línea cita un comprobante cobrado:

* monto cobrado = lo pagado de la parte sujeta del comprobante, en soles al
  tipo de cambio de la fecha de cobro (art. 8), más la percepción;
* percepción = monto cobrado × factor, con factor = tasa / (100 + tasa)
  redondeado a seis decimales (art. 10.1, numeral 2.6);
* con bienes sujetos y no sujetos en el comprobante, lo pagado se atribuye
  en proporción (art. 11.2).

Al emitirlo se numera, se genera el asiento (cargo al cliente, abono al IGV
percibido por pagar) y se concilia con lo que el cliente pagó de más por la
percepción. El XML, la firma, el envío y la reversión los da el mismo motor
que el comprobante de retención (``l10n_pe.retention.edi.mixin``).
"""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round

from odoo.addons.al_l10n_pe_retention.models.account_payment import CRE_STATES, SEND_DEADLINE_DAYS

from .account_move import PERCEPTION_REGIMES

CPE_CODES = [
    ('01', 'Venta interna (2 %)'),
    ('02', 'Combustibles (1 %)'),
    ('03', 'Agente de percepción, tasa especial (0,5 %)'),
]
CPE_RATES = {values['cpe_code']: values['rate'] for values in PERCEPTION_REGIMES.values()}
INVOICE_TO_CPE = {code: values['cpe_code'] for code, values in PERCEPTION_REGIMES.items()}


def perception_factor(rate):
    """Factor de seis decimales del art. 10.1, numeral 2.6 (2 % → 0.019608)."""
    return float_round(rate / (100.0 + rate), precision_digits=6)


class L10nPePerception(models.Model):
    _name = 'l10n_pe.perception'
    _description = 'Comprobante de percepción'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'l10n_pe.retention.edi.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True, index=True,
        default=lambda self: self.env.company)
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True, tracking=True, check_company=True,
        domain="[('parent_id', '=', False)]")
    date = fields.Date(
        string='Fecha de cobro', required=True, tracking=True, default=fields.Date.context_today,
        help='Fecha en que se cobró: la de emisión del comprobante de percepción y la del tipo '
             'de cambio (art. 8 de la R.S. 058-2006/SUNAT).')
    perception_code = fields.Selection(
        CPE_CODES, string='Régimen', required=True, default='01', tracking=True,
        help='Régimen y tasa de la percepción (catálogo 22). Un comprobante por tasa.')
    rate = fields.Float(string='Tasa (%)', digits=(5, 2), compute='_compute_rate', store=True)
    payment_id = fields.Many2one(
        'account.payment', string='Cobro', check_company=True, copy=False,
        domain="[('partner_type', '=', 'customer'), ('payment_type', '=', 'inbound')]",
        help='Cobro del cliente que incluye la percepción. Vacío: cobro fuera de Odoo.')
    note = fields.Text(string='Nota', help='Se informa en el comprobante (cbc:Note).')
    journal_id = fields.Many2one(
        'account.journal', string='Diario', required=True, check_company=True,
        domain="[('type', '=', 'general')]",
        default=lambda self: self.env.company.l10n_pe_perception_journal_id or self.env[
            'account.journal'].search([
                *self.env['account.journal']._check_company_domain(self.env.company),
                ('type', '=', 'general')], limit=1))
    state = fields.Selection(
        [('draft', 'Borrador'), ('posted', 'Emitido'), ('cancel', 'Anulado')],
        string='Estado', required=True, default='draft', copy=False, tracking=True)
    line_ids = fields.One2many(
        'l10n_pe.perception.line', 'perception_id', string='Comprobantes cobrados', copy=True)
    move_id = fields.Many2one(
        'account.move', string='Asiento', readonly=True, copy=False, check_company=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    amount_collected = fields.Monetary(
        string='Cobrado con la percepción (S/)', compute='_compute_amounts', store=True,
        help='Monto total cobrado incluida la percepción (casilla 502 del F.V. 697).')
    amount_perception = fields.Monetary(
        string='Percibido (S/)', compute='_compute_amounts', store=True,
        help='Percepciones efectuadas (casilla 401 del F.V. 697).')

    l10n_pe_edi_perception_number = fields.Char(
        string='Nº comprobante de percepción', readonly=True, copy=False, tracking=True)
    l10n_pe_edi_status = fields.Selection(
        selection=CRE_STATES, string='Estado ante SUNAT', copy=False, tracking=True)
    l10n_pe_edi_warnings = fields.Json(string='Avisos del comprobante', readonly=True, copy=False)
    l10n_pe_edi_attachment_file = fields.Binary(
        string='Comprobante firmado y CDR', attachment=True, copy=False)
    l10n_pe_edi_is_required = fields.Boolean(
        string='Comprobante por enviar', compute='_compute_l10n_pe_edi_is_required')
    l10n_pe_edi_deadline = fields.Date(
        string='Enviar hasta', compute='_compute_l10n_pe_edi_deadline', store=True)
    l10n_pe_edi_error_message = fields.Char(
        string='Error del envío', compute='_compute_l10n_pe_edi_error_message')

    @api.depends('l10n_pe_edi_perception_number')
    def _compute_name(self):
        for perception in self:
            perception.name = perception.l10n_pe_edi_perception_number or self.env._('Borrador')

    @api.depends('perception_code')
    def _compute_rate(self):
        for perception in self:
            perception.rate = CPE_RATES.get(perception.perception_code, 0.0)

    @api.depends('line_ids.collected_pen', 'line_ids.perception_pen')
    def _compute_amounts(self):
        for perception in self:
            perception.amount_collected = sum(perception.line_ids.mapped('collected_pen'))
            perception.amount_perception = sum(perception.line_ids.mapped('perception_pen'))

    @api.depends('state', 'l10n_pe_edi_perception_number', 'l10n_pe_edi_status')
    def _compute_l10n_pe_edi_is_required(self):
        for perception in self:
            perception.l10n_pe_edi_is_required = bool(
                perception.state == 'posted' and perception.l10n_pe_edi_perception_number
                and perception.l10n_pe_edi_status not in ('sent', 'reversing', 'cancelled'))

    @api.depends('date', 'l10n_pe_edi_perception_number')
    def _compute_l10n_pe_edi_deadline(self):
        for perception in self:
            perception.l10n_pe_edi_deadline = (
                perception.date + timedelta(days=SEND_DEADLINE_DAYS)
                if perception.date and perception.l10n_pe_edi_perception_number else False)

    @api.depends('l10n_pe_edi_warnings')
    def _compute_l10n_pe_edi_error_message(self):
        for perception in self:
            error = (perception.l10n_pe_edi_warnings or {}).get('edi_error') or {}
            perception.l10n_pe_edi_error_message = error.get('message') or False

    # ------------------------------------------------------------------
    # Comprobante electrónico (l10n_pe.retention.edi.mixin)
    # ------------------------------------------------------------------
    def _l10n_pe_edi_cpe_type(self):
        return '40'

    def _l10n_pe_edi_cpe_label(self):
        return 'comprobante de percepción'

    def _l10n_pe_edi_cpe_number(self):
        self.ensure_one()
        return self.l10n_pe_edi_perception_number

    def _l10n_pe_edi_cpe_export(self):
        self.ensure_one()
        return self.env['account.edi.xml.ubl_pe_perception']._export_perception(self)

    def _l10n_pe_edi_cpe_accepted_message(self):
        self.ensure_one()
        return self.env._('Comprobante de percepción %(number)s aceptado por SUNAT.',
                          number=self.l10n_pe_edi_perception_number)

    def _l10n_pe_retention_bills(self):
        self.ensure_one()
        return self.line_ids.invoice_id

    def _l10n_pe_retention_note(self):
        self.ensure_one()
        return self.note or False

    def _l10n_pe_retention_check_ready(self):
        self.ensure_one()
        if self.state != 'posted' or not self.l10n_pe_edi_perception_number:
            raise UserError(self.env._(
                'Emita el comprobante de percepción %s antes de generar su XML.',
                self.display_name))

    def _l10n_pe_edi_get_retention_breakdown(self):
        """Mismas claves que el comprobante de retención, para quien las use."""
        self.ensure_one()
        return [{
            'bill': line.invoice_id,
            'bill_paid_currency': line.paid_amount,
            'bill_paid_pen': line.subject_paid_pen,
            'bill_retention_pen': line.perception_pen,
            'net_total_paid_pen': line.collected_pen,
            'exchange_rate': line.exchange_rate,
        } for line in self.line_ids]

    def _l10n_pe_perception_payment_index(self, invoice):
        """Número del cobro a ``invoice`` que informa este comprobante
        (``cac:Payment/cbc:ID``): 1 para el primero, 2 para el segundo…
        contando los comprobantes de percepción emitidos y no anulados."""
        self.ensure_one()
        previous = self.env['l10n_pe.perception.line'].search([
            ('invoice_id', '=', invoice.id),
            ('perception_id.state', '=', 'posted'),
            ('perception_id', '!=', self.id),
        ]).perception_id
        key = (self.date, self.id)
        return 1 + len(previous.filtered(lambda p: (p.date, p.id) < key))

    def _l10n_pe_edi_reversal_done_message(self):
        self.ensure_one()
        return self.env._(
            'SUNAT aceptó la reversión del comprobante de percepción %(number)s: el comprobante '
            'y su asiento quedan anulados.', number=self.l10n_pe_edi_perception_number)

    def _l10n_pe_edi_after_reversal(self):
        for perception in self:
            perception._l10n_pe_perception_cancel_move()
            perception.state = 'cancel'
        return True

    # ------------------------------------------------------------------
    # Emisión
    # ------------------------------------------------------------------
    def _l10n_pe_perception_check_lines(self):
        """Compañía agente, un solo cliente, comprobantes de venta publicados
        del cliente y sujetos a percepción con la misma tasa del comprobante
        (art. 10.4), y lo cobrado mayor que cero sin superar el total."""
        self.ensure_one()
        company = self.company_id
        fuel = self.perception_code == '02'
        if not (company.l10n_pe_perception_fuel_agent if fuel else company.l10n_pe_perception_agent):
            raise UserError(self.env._(
                '%s no es agente de percepción de este régimen (Ajustes ▸ Perú ▸ Percepciones '
                'del IGV).', company.display_name))
        if not self.line_ids:
            raise UserError(self.env._('Agregue los comprobantes cobrados.'))
        partner = self.partner_id.commercial_partner_id
        for line in self.line_ids:
            invoice = line.invoice_id
            if invoice.state != 'posted' or invoice.move_type != 'out_invoice' \
                    or invoice.commercial_partner_id != partner:
                raise UserError(self.env._(
                    '%(invoice)s no es una factura de venta publicada de %(partner)s.',
                    invoice=invoice.display_name, partner=partner.display_name))
            if INVOICE_TO_CPE.get(invoice.l10n_pe_perception_code) != self.perception_code:
                raise UserError(self.env._(
                    '%(invoice)s no está sujeta a percepción con la tasa de este comprobante '
                    '(%(note)s). Emita un comprobante por cada tasa.',
                    invoice=invoice.display_name,
                    note=invoice.l10n_pe_perception_note or invoice.l10n_pe_perception_code
                    or self.env._('sin percepción')))
            if invoice.currency_id.compare_amounts(line.paid_amount, 0.0) <= 0 \
                    or invoice.currency_id.compare_amounts(line.paid_amount, invoice.amount_total) > 0:
                raise UserError(self.env._(
                    'Lo cobrado de %s debe ser mayor que cero y no superar su total.',
                    invoice.display_name))

    def _l10n_pe_perception_account(self):
        self.ensure_one()
        account = self.company_id.l10n_pe_perception_account_id
        if not account:
            raise UserError(self.env._(
                'Configure la «Cuenta del IGV percibido por pagar» en Ajustes ▸ Perú ▸ '
                'Percepciones del IGV.'))
        return account

    def action_post(self):
        for perception in self:
            if perception.state != 'draft':
                raise UserError(self.env._('Solo se emite un comprobante en borrador.'))
            perception._l10n_pe_perception_check_lines()
            account = perception._l10n_pe_perception_account()
            # sudo: secuencia del RUC en la compañía raíz (ver res.company)
            sequence_sudo = perception.company_id._l10n_pe_perception_sequence()
            perception.l10n_pe_edi_perception_number = sequence_sudo.next_by_id(
                sequence_date=perception.date)
            perception.move_id = perception._l10n_pe_perception_create_move(account)
            perception.write({'state': 'posted', 'l10n_pe_edi_status': 'to_send'})
        return True

    def _l10n_pe_perception_create_move(self, account):
        """Asiento: cargo al cliente (cuenta por cobrar de la factura) y abono a
        la cuenta del IGV percibido. El cargo se concilia con lo que el
        cliente pagó de más por la percepción (el cobro), si lo hay."""
        self.ensure_one()
        partner = self.partner_id.commercial_partner_id
        lines_vals = []
        for line in self.line_ids:
            receivable = line.invoice_id.line_ids.filtered(
                lambda l: l.account_id.account_type == 'asset_receivable')[:1]
            lines_vals.append({
                'name': self.env._('Percepción IGV %(number)s · %(invoice)s',
                                   number=self.l10n_pe_edi_perception_number,
                                   invoice=line.invoice_id.name),
                'account_id': (receivable.account_id or partner.property_account_receivable_id).id,
                'partner_id': partner.id,
                'debit': line.perception_pen,
            })
        lines_vals.append({
            'name': self.env._('Comprobante de percepción %s', self.l10n_pe_edi_perception_number),
            'account_id': account.id,
            'partner_id': partner.id,
            'credit': self.amount_perception,
        })
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': self.env._('Comprobante de percepción %s', self.l10n_pe_edi_perception_number),
            'line_ids': [(0, 0, vals) for vals in lines_vals],
        })
        move.action_post()
        debits = move.line_ids.filtered(lambda l: l.debit)
        credits = self._l10n_pe_perception_open_credits(debits.account_id)
        if credits:
            (debits | credits).reconcile()
        return move

    def _l10n_pe_perception_open_credits(self, accounts):
        """Saldo a favor del cliente que deja el cobro (lo pagado por encima de
        las facturas: la percepción)."""
        self.ensure_one()
        domain = [
            ('account_id', 'in', accounts.ids),
            ('partner_id', '=', self.partner_id.commercial_partner_id.id),
            ('reconciled', '=', False),
            ('credit', '>', 0),
            ('parent_state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]
        if self.payment_id:
            domain.append(('move_id', '=', self.payment_id.move_id.id))
        else:
            domain.append(('move_id.origin_payment_id', '!=', False))
        return self.env['account.move.line'].search(domain)

    def action_cancel(self):
        for perception in self:
            if perception.l10n_pe_edi_status in ('sent', 'reversing'):
                raise UserError(self.env._(
                    'El comprobante de percepción %s fue aceptado por SUNAT: reviértalo primero '
                    '(botón «Revertir»).', perception.display_name))
            perception._l10n_pe_perception_cancel_move()
            values = {'state': 'cancel'}
            if perception.l10n_pe_edi_perception_number:
                values['l10n_pe_edi_status'] = 'cancelled'
            perception.write(values)
        return True

    def action_draft(self):
        for perception in self:
            if perception.state != 'cancel' or perception.l10n_pe_edi_perception_number:
                raise UserError(self.env._(
                    'Un comprobante ya numerado no vuelve a borrador: emita uno nuevo.'))
            perception.state = 'draft'
        return True

    def _l10n_pe_perception_cancel_move(self):
        self.ensure_one()
        move = self.move_id
        if move and move.state == 'posted':
            move.line_ids.remove_move_reconcile()
            move.button_draft()
            move.button_cancel()

    def unlink(self):
        if any(p.state != 'draft' or p.l10n_pe_edi_perception_number for p in self):
            raise UserError(self.env._('Solo se eliminan comprobantes en borrador.'))
        return super().unlink()

    def action_view_move(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'account.move',
            'res_id': self.move_id.id, 'view_mode': 'form',
        }

    @api.model
    def _l10n_pe_perception_open(self, perception):
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': perception.id,
            'view_mode': 'form', 'target': 'current',
        }

    @api.model
    def action_create_from_invoices(self):
        """«Emitir comprobante de percepción» desde la lista de facturas de venta:
        borrador con lo que queda por cobrar de cada factura."""
        invoices = self.env['account.move'].browse(self.env.context.get('active_ids', []))
        partners = invoices.commercial_partner_id
        if len(partners) != 1:
            raise UserError(self.env._('Elija facturas de un solo cliente.'))
        codes = set(invoices.mapped('l10n_pe_perception_code'))
        if len(codes) != 1 or not next(iter(codes)):
            raise UserError(self.env._(
                'Elija facturas sujetas a percepción con la misma tasa (un comprobante por '
                'tasa).'))
        perception = self.create({
            'partner_id': partners.id,
            'company_id': invoices.company_id[:1].id or self.env.company.id,
            'perception_code': INVOICE_TO_CPE[next(iter(codes))],
            'line_ids': [(0, 0, {
                'invoice_id': invoice.id,
                'paid_amount': invoice.amount_residual or invoice.amount_total,
            }) for invoice in invoices],
        })
        return self._l10n_pe_perception_open(perception)


class L10nPePerceptionLine(models.Model):
    _name = 'l10n_pe.perception.line'
    _description = 'Comprobante cobrado en un comprobante de percepción'
    _order = 'perception_id, id'
    _check_company_auto = True

    perception_id = fields.Many2one(
        'l10n_pe.perception', string='Comprobante de percepción', required=True,
        ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(
        related='perception_id.company_id', string='Compañía', store=True, index=True)
    invoice_id = fields.Many2one(
        'account.move', string='Factura', required=True, index=True, check_company=True,
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted'), "
               "('l10n_pe_perception_code', '!=', False)]")
    invoice_currency_id = fields.Many2one(
        related='invoice_id.currency_id', string='Moneda de la factura')
    invoice_total = fields.Monetary(
        related='invoice_id.amount_total', string='Total de la factura',
        currency_field='invoice_currency_id')
    paid_amount = fields.Monetary(
        string='Cobrado', currency_field='invoice_currency_id', required=True,
        help='Importe cobrado de la factura en su moneda, sin la percepción.')
    subject_ratio = fields.Float(
        string='Parte sujeta', digits=(6, 4), compute='_compute_amounts', store=True,
        help='Proporción del precio de los bienes sujetos en el total de la factura '
             '(art. 11.2: el pago se atribuye en proporción).')
    exchange_rate = fields.Float(
        string='Tipo de cambio', digits=(12, 6), compute='_compute_amounts', store=True,
        help='Soles por unidad de la moneda de la factura en la fecha de cobro.')
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Soles')
    subject_paid_pen = fields.Monetary(
        string='Cobrado sujeto (S/)', currency_field='company_currency_id',
        compute='_compute_amounts', store=True)
    collected_pen = fields.Monetary(
        string='Cobrado con la percepción (S/)', currency_field='company_currency_id',
        compute='_compute_amounts', store=True)
    perception_pen = fields.Monetary(
        string='Percepción (S/)', currency_field='company_currency_id',
        compute='_compute_amounts', store=True)

    @api.depends('paid_amount', 'invoice_id', 'perception_id.date', 'perception_id.rate')
    def _compute_amounts(self):
        for line in self:
            invoice = line.invoice_id
            company = line.perception_id.company_id or invoice.company_id or self.env.company
            pen = company.currency_id
            rate = line.perception_id.rate
            day = line.perception_id.date or fields.Date.context_today(line)
            if not invoice or not invoice.amount_total:
                line.update({'subject_ratio': 0.0, 'exchange_rate': 1.0, 'subject_paid_pen': 0.0,
                             'collected_pen': 0.0, 'perception_pen': 0.0})
                continue
            ratio = min(1.0, invoice.l10n_pe_perception_base / invoice.amount_total)
            exchange = 1.0 if invoice.currency_id == pen else invoice.currency_id._get_conversion_rate(
                invoice.currency_id, pen, company, day)
            subject_pen = pen.round(line.paid_amount * ratio * exchange)
            collected = pen.round(subject_pen * (1 + rate / 100.0))
            line.subject_ratio = ratio
            line.exchange_rate = exchange
            line.subject_paid_pen = subject_pen
            line.collected_pen = collected
            line.perception_pen = pen.round(collected * perception_factor(rate))
