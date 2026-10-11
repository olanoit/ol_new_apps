# -*- coding: utf-8 -*-
"""Comprobante de retención sin pago de Odoo.

La retención se efectúa en el momento del pago, cualquiera que sea su forma
(art. 7 de la R.S. 037-2002/SUNAT): el pago de una letra de cambio, una
compensación o un pago registrado fuera de Odoo también llevan su CRE. Este
documento lo emite sin un ``account.payment``: elige el proveedor, las
facturas y lo pagado de cada una, numera el CRE con la misma serie que los
pagos y genera el asiento que rebaja la cuenta por pagar (de la factura o de
la letra) contra la cuenta de retenciones del IGV.

El XML, la firma, el envío y la reversión son los del pago
(``l10n_pe.retention.edi.mixin``); el reparto por comprobante tiene las mismas
claves que el del pago, así que el PDF y el resumen 626 lo usan igual.
"""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .account_move import ALLOWED_DOCUMENT_CODES
from .account_payment import CRE_STATES, SEND_DEADLINE_DAYS


class L10nPeRetentionDocument(models.Model):
    _name = 'l10n_pe.retention.document'
    _description = 'Comprobante de retención sin pago'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'l10n_pe.retention.edi.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', compute='_compute_name', store=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True, index=True,
        default=lambda self: self.env.company)
    partner_id = fields.Many2one(
        'res.partner', string='Proveedor', required=True, tracking=True, check_company=True,
        domain="[('parent_id', '=', False)]")
    date = fields.Date(
        string='Fecha de pago', required=True, tracking=True,
        default=fields.Date.context_today,
        help='Fecha en que se pagó (vencimiento de la letra, fecha de la compensación…): es '
             'la fecha de emisión del comprobante de retención y la del tipo de cambio.')
    origin = fields.Selection(
        [('letter', 'Pago de letras de cambio'), ('compensation', 'Compensación'),
         ('other', 'Otro pago fuera de Odoo')],
        string='Forma de pago', required=True, default='letter', tracking=True)
    reference = fields.Char(
        string='Referencia del pago', tracking=True,
        help='Número de la letra, del acta de compensación o de la operación bancaria.')
    note = fields.Text(string='Nota', help='Se informa en el comprobante (cbc:Note).')
    journal_id = fields.Many2one(
        'account.journal', string='Diario', required=True, check_company=True,
        domain="[('type', '=', 'general')]",
        default=lambda self: self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self.env.company),
            ('type', '=', 'general')], limit=1))
    state = fields.Selection(
        [('draft', 'Borrador'), ('posted', 'Emitido'), ('cancel', 'Anulado')],
        string='Estado', required=True, default='draft', copy=False, tracking=True)
    line_ids = fields.One2many(
        'l10n_pe.retention.document.line', 'document_id', string='Comprobantes pagados',
        copy=True)
    move_id = fields.Many2one(
        'account.move', string='Asiento', readonly=True, copy=False, check_company=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    amount_paid = fields.Monetary(
        string='Pagado (S/)', compute='_compute_amounts', store=True)
    amount_retention = fields.Monetary(
        string='Retenido (S/)', compute='_compute_amounts', store=True,
        help='Importe retenido después de descontar las notas de crédito.')
    deduction_ids = fields.One2many(
        'l10n_pe.retention.credit.deduction', 'document_id',
        string='Notas de crédito descontadas', readonly=True)

    l10n_pe_edi_retention_number = fields.Char(
        string='Nº comprobante de retención', readonly=True, copy=False, tracking=True)
    l10n_pe_edi_status = fields.Selection(
        selection=CRE_STATES, string='Estado del CRE', copy=False, tracking=True)
    l10n_pe_edi_warnings = fields.Json(string='Avisos del CRE', readonly=True, copy=False)
    l10n_pe_edi_attachment_file = fields.Binary(
        string='CRE firmado y CDR', attachment=True, copy=False)
    l10n_pe_edi_is_required = fields.Boolean(
        string='CRE por enviar', compute='_compute_l10n_pe_edi_is_required')
    l10n_pe_edi_deadline = fields.Date(
        string='Enviar el CRE hasta', compute='_compute_l10n_pe_edi_deadline', store=True)
    l10n_pe_edi_error_message = fields.Char(
        string='Error del CRE', compute='_compute_l10n_pe_edi_error_message')

    @api.depends('l10n_pe_edi_retention_number', 'partner_id')
    def _compute_name(self):
        for document in self:
            document.name = document.l10n_pe_edi_retention_number or self.env._('Borrador')

    @api.depends('line_ids.paid_pen', 'line_ids.retention_pen', 'deduction_ids.amount')
    def _compute_amounts(self):
        for document in self:
            document.amount_paid = sum(document.line_ids.mapped('paid_pen'))
            document.amount_retention = document.currency_id.round(
                sum(document.line_ids.mapped('retention_pen'))
                - sum(document.deduction_ids.mapped('amount')))

    @api.depends('state', 'l10n_pe_edi_retention_number', 'l10n_pe_edi_status')
    def _compute_l10n_pe_edi_is_required(self):
        for document in self:
            document.l10n_pe_edi_is_required = bool(
                document.state == 'posted' and document.l10n_pe_edi_retention_number
                and document.l10n_pe_edi_status not in ('sent', 'reversing', 'cancelled'))

    @api.depends('date', 'l10n_pe_edi_retention_number')
    def _compute_l10n_pe_edi_deadline(self):
        for document in self:
            document.l10n_pe_edi_deadline = (
                document.date + timedelta(days=SEND_DEADLINE_DAYS)
                if document.date and document.l10n_pe_edi_retention_number else False)

    @api.depends('l10n_pe_edi_warnings')
    def _compute_l10n_pe_edi_error_message(self):
        for document in self:
            error = (document.l10n_pe_edi_warnings or {}).get('edi_error') or {}
            document.l10n_pe_edi_error_message = error.get('message') or False

    # ------------------------------------------------------------------
    # Lo que el documento aporta al CRE (l10n_pe.retention.edi.mixin)
    # ------------------------------------------------------------------
    def _l10n_pe_retention_bills(self):
        self.ensure_one()
        return self.line_ids.bill_id

    def _l10n_pe_retention_note(self):
        self.ensure_one()
        parts = [self.note, self.reference and self.env._('Referencia: %s', self.reference)]
        return ' '.join(part for part in parts if part) or False

    def _l10n_pe_retention_check_ready(self):
        self.ensure_one()
        if self.state != 'posted' or not self.l10n_pe_edi_retention_number:
            raise UserError(self.env._(
                'Emita el comprobante de retención %s antes de generar su XML.',
                self.display_name))

    def _l10n_pe_edi_get_retention_breakdown(self):
        """Mismas claves que el del pago. Cada comprobante lleva el 3 % de lo
        pagado; las notas de crédito descontadas van como documento 07 con la
        retención en negativo (y ese importe sumado al neto pagado)."""
        self.ensure_one()
        breakdown = [{
            'bill': line.bill_id,
            'bill_paid_currency': line.paid_amount,
            'bill_paid_pen': line.paid_pen,
            'bill_retention_pen': line.retention_pen,
            'net_total_paid_pen': line.paid_pen - line.retention_pen,
            'exchange_rate': line.exchange_rate,
        } for line in self.line_ids]
        return breakdown + self._l10n_pe_retention_deduction_entries(
            self.deduction_ids)

    # ------------------------------------------------------------------
    # Emisión
    # ------------------------------------------------------------------
    def _l10n_pe_retention_check_lines(self):
        """Las mismas reglas que al pagar: comprobantes comprendidos en el
        régimen, lo pagado no excede el total y, entre todos, superan el
        monto mínimo (art. 12)."""
        self.ensure_one()
        company = self.company_id
        if not company.l10n_pe_retention_agent:
            raise UserError(self.env._(
                '%s no es agente de retención (Ajustes ▸ Perú ▸ Retenciones IGV).',
                company.display_name))
        if not self.line_ids:
            raise UserError(self.env._('Agregue los comprobantes pagados.'))
        partner = self.partner_id.commercial_partner_id
        if partner.is_retention_agent or partner.is_good_taxpayer \
                or partner.l10n_pe_is_perception_agent:
            raise UserError(self.env._(
                '%s es agente de retención, buen contribuyente o agente de percepción: sus '
                'operaciones no se retienen (art. 5 de la R.S. 037-2002/SUNAT).',
                partner.display_name))
        for line in self.line_ids:
            bill = line.bill_id
            if bill.state != 'posted' or bill.move_type != 'in_invoice' \
                    or bill.commercial_partner_id != partner:
                raise UserError(self.env._(
                    '%(bill)s no es una factura publicada de %(partner)s.',
                    bill=bill.display_name, partner=partner.display_name))
            if not bill.l10n_pe_retention_eligible \
                    or (bill.l10n_latam_document_type_id.code or '01') not in ALLOWED_DOCUMENT_CODES:
                raise UserError(self.env._(
                    '%s no está comprendida en el régimen de retenciones (sin IGV, con '
                    'detracción o comprobante que no admite el CRE).', bill.display_name))
            if bill.currency_id.compare_amounts(line.paid_amount, 0.0) <= 0 \
                    or bill.currency_id.compare_amounts(line.paid_amount, bill.amount_total) > 0:
                raise UserError(self.env._(
                    'Lo pagado de %s debe ser mayor que cero y no superar su total.',
                    bill.display_name))
        total = sum(bill._l10n_pe_retention_base(self.date) for bill in self.line_ids.bill_id)
        if company.currency_id.compare_amounts(total, company.l10n_pe_retention_min_amount) <= 0:
            raise UserError(self.env._(
                'Los comprobantes suman %(total)s soles: no superan el monto mínimo de '
                'retención (S/ %(minimum)s).', total='%.2f' % total,
                minimum='%.2f' % company.l10n_pe_retention_min_amount))

    def _l10n_pe_retention_account(self):
        self.ensure_one()
        tax = self.company_id.l10n_pe_retention_tax_id
        account = tax.invoice_repartition_line_ids.filtered(
            lambda r: r.repartition_type == 'tax').account_id[:1]
        if not (tax and account and tax.withholding_sequence_id):
            raise UserError(self.env._(
                'Configure el «Impuesto de retención IGV» con su cuenta y su secuencia en '
                'Ajustes ▸ Perú ▸ Retenciones IGV.'))
        return tax, account

    def action_post(self):
        for document in self:
            if document.state != 'draft':
                raise UserError(self.env._('Solo se emite un comprobante en borrador.'))
            document._l10n_pe_retention_check_lines()
            tax, account = document._l10n_pe_retention_account()
            document.deduction_ids.unlink()
            retention = sum(document.line_ids.mapped('retention_pen'))
            for note, amount in self.env['account.move']._l10n_pe_retention_plan_deductions(
                    document.company_id, document.partner_id, retention):
                self.env['l10n_pe.retention.credit.deduction'].create({
                    'company_id': document.company_id.id, 'credit_note_id': note.id,
                    'amount': amount, 'document_id': document.id})
            document.l10n_pe_edi_retention_number = tax.withholding_sequence_id.next_by_id(
                sequence_date=document.date)
            document.move_id = document._l10n_pe_retention_create_move(account)
            document.write({'state': 'posted', 'l10n_pe_edi_status': 'to_send'})
        return True

    def _l10n_pe_retention_create_move(self, account):
        """Asiento: cargo a la cuenta por pagar de cada comprobante (o de la
        letra) por lo retenido, abono a la cuenta de retenciones del IGV; cada
        cargo se concilia con su partida abierta."""
        self.ensure_one()
        company = self.company_id
        currency = company.currency_id
        retained = self.amount_retention
        gross = sum(self.line_ids.mapped('retention_pen'))
        lines_vals = []
        left = retained
        for index, line in enumerate(self.line_ids):
            # El descuento de notas de crédito rebaja la retención en proporción.
            if index == len(self.line_ids) - 1:
                amount = left
            else:
                amount = currency.round(line.retention_pen * retained / gross) if gross else 0.0
                left = currency.round(left - amount)
            counterpart = line._l10n_pe_counterpart_line()
            vals = {
                'name': self.env._('Retención IGV %(number)s · %(bill)s',
                                   number=self.l10n_pe_edi_retention_number,
                                   bill=line.bill_id.ref or line.bill_id.name),
                'account_id': counterpart.account_id.id,
                'partner_id': self.partner_id.commercial_partner_id.id,
                'debit': amount,
            }
            if counterpart.currency_id != currency:
                vals.update(currency_id=counterpart.currency_id.id,
                            amount_currency=counterpart.currency_id.round(
                                amount / (line.exchange_rate or 1.0)))
            lines_vals.append(vals)
        lines_vals.append({
            'name': self.env._('Comprobante de retención %s', self.l10n_pe_edi_retention_number),
            'account_id': account.id,
            'partner_id': self.partner_id.commercial_partner_id.id,
            'credit': retained,
        })
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': self.env._('Comprobante de retención %(number)s (%(origin)s)',
                              number=self.l10n_pe_edi_retention_number,
                              origin=dict(self._fields['origin']._description_selection(
                                  self.env))[self.origin]),
            'line_ids': [(0, 0, vals) for vals in lines_vals],
        })
        move.action_post()
        debit_lines = move.line_ids.filtered(lambda l: l.debit)
        for line, debit_line in zip(self.line_ids, debit_lines):
            (debit_line | line._l10n_pe_counterpart_line()).reconcile()
        return move

    def action_cancel(self):
        for document in self:
            if document.l10n_pe_edi_status in ('sent', 'reversing'):
                raise UserError(self.env._(
                    'El comprobante de retención %s fue aceptado por SUNAT: reviértalo primero '
                    '(botón «Revertir CRE»).', document.display_name))
            document._l10n_pe_retention_cancel_move()
            values = {'state': 'cancel'}
            if document.l10n_pe_edi_retention_number:
                values['l10n_pe_edi_status'] = 'cancelled'
            document.write(values)
        return True

    def action_draft(self):
        for document in self:
            if document.state != 'cancel' or document.l10n_pe_edi_retention_number:
                raise UserError(self.env._(
                    'Un comprobante ya numerado no vuelve a borrador: emita uno nuevo.'))
            document.state = 'draft'
        return True

    def _l10n_pe_retention_cancel_move(self):
        self.ensure_one()
        move = self.move_id
        if move and move.state == 'posted':
            move.button_draft()
            move.button_cancel()

    def _l10n_pe_edi_reversal_done_message(self):
        self.ensure_one()
        return self.env._(
            'SUNAT aceptó la reversión del CRE %(number)s: el comprobante y su asiento quedan '
            'anulados.', number=self.l10n_pe_edi_retention_number)

    def _l10n_pe_edi_after_reversal(self):
        for document in self:
            document._l10n_pe_retention_cancel_move()
            document.state = 'cancel'
        return True

    def unlink(self):
        if any(document.state != 'draft' or document.l10n_pe_edi_retention_number
               for document in self):
            raise UserError(self.env._('Solo se eliminan comprobantes en borrador.'))
        return super().unlink()

    def action_view_move(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'account.move',
            'res_id': self.move_id.id, 'view_mode': 'form',
        }

    @api.model
    def action_create_from_bills(self):
        """«Emitir CRE sin pago» desde la lista de facturas de proveedor."""
        bills = self.env['account.move'].browse(self.env.context.get('active_ids', []))
        partners = bills.commercial_partner_id
        if len(partners) != 1:
            raise UserError(self.env._('Elija facturas de un solo proveedor.'))
        document = self.create({
            'partner_id': partners.id,
            'company_id': bills.company_id[:1].id or self.env.company.id,
            'line_ids': [(0, 0, {'bill_id': bill.id, 'paid_amount': bill.amount_total})
                         for bill in bills],
        })
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': document.id,
            'view_mode': 'form', 'target': 'current',
        }


class L10nPeRetentionDocumentLine(models.Model):
    _name = 'l10n_pe.retention.document.line'
    _description = 'Comprobante pagado en un CRE sin pago'
    _order = 'document_id, id'
    _check_company_auto = True

    document_id = fields.Many2one(
        'l10n_pe.retention.document', string='Comprobante de retención', required=True,
        ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(
        related='document_id.company_id', string='Compañía', store=True, index=True)
    bill_id = fields.Many2one(
        'account.move', string='Factura', required=True, check_company=True,
        domain="[('move_type', '=', 'in_invoice'), ('state', '=', 'posted'), "
               "('l10n_pe_retention_eligible', '=', True)]")
    bill_currency_id = fields.Many2one(related='bill_id.currency_id', string='Moneda de la factura')
    bill_total = fields.Monetary(
        related='bill_id.amount_total', string='Total de la factura',
        currency_field='bill_currency_id')
    paid_amount = fields.Monetary(
        string='Pagado', currency_field='bill_currency_id', required=True,
        help='Importe pagado de la factura en su moneda, antes de la retención.')
    counterpart_line_id = fields.Many2one(
        'account.move.line', string='Partida por pagar', check_company=True,
        domain="[('partner_id', 'child_of', parent.partner_id), "
               "('account_type', '=', 'liability_payable'), ('reconciled', '=', False), "
               "('parent_state', '=', 'posted')]",
        help='Partida abierta que rebaja la retención: la de la factura o, si se canjeó por '
             'letras, la de la letra. Vacía, se usa la de la factura.')
    exchange_rate = fields.Float(
        string='Tipo de cambio', digits=(12, 6), compute='_compute_amounts', store=True)
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Soles')
    paid_pen = fields.Monetary(
        string='Pagado (S/)', currency_field='company_currency_id',
        compute='_compute_amounts', store=True)
    retention_pen = fields.Monetary(
        string='Retención (S/)', currency_field='company_currency_id',
        compute='_compute_amounts', store=True)

    @api.depends('paid_amount', 'bill_id.currency_id', 'document_id.date',
                 'company_id.l10n_pe_retention_rate')
    def _compute_amounts(self):
        """T.C. venta oficial de la fecha del pago (art. 7), como en el pago."""
        for line in self:
            company = line.company_id or self.env.company
            currency = company.currency_id
            bill_currency = line.bill_id.currency_id or currency
            rate = 1.0 if bill_currency == currency else self.env['res.currency']._get_conversion_rate(
                bill_currency, currency, company, line.document_id.date or fields.Date.context_today(line))
            line.exchange_rate = rate
            line.paid_pen = currency.round(line.paid_amount * rate)
            line.retention_pen = currency.round(line.paid_pen * company.l10n_pe_retention_rate / 100.0)

    @api.onchange('bill_id')
    def _onchange_bill_id(self):
        if self.bill_id and not self.paid_amount:
            self.paid_amount = self.bill_id.amount_total

    @api.constrains('bill_id', 'document_id')
    def _check_partner(self):
        for line in self:
            if line.bill_id.commercial_partner_id != line.document_id.partner_id.commercial_partner_id:
                raise ValidationError(self.env._(
                    'La factura %s no es del proveedor del comprobante.', line.bill_id.display_name))

    def _l10n_pe_counterpart_line(self):
        """La partida por pagar que se rebaja: la elegida o la de la factura."""
        self.ensure_one()
        if self.counterpart_line_id:
            return self.counterpart_line_id
        open_lines = self.bill_id.line_ids.filtered(
            lambda l: l.account_type == 'liability_payable' and not l.reconciled)
        if not open_lines:
            raise UserError(self.env._(
                '%s no tiene saldo por pagar: si se canjeó por letras, elija la partida de la '
                'letra en «Partida por pagar».', self.bill_id.display_name))
        return open_lines[:1]
