# -*- coding: utf-8 -*-
"""Percepciones que nos cobran.

Un proveedor agente de percepción (o la Aduana, en la importación) nos cobra
la percepción del IGV además del precio. Se acredita con:

* el comprobante de percepción (tipo 40) que nos entrega el proveedor;
* la factura del proveedor, cuando consigna la percepción y se pagó entera al
  entregar los bienes (R.S. 058-2006/SUNAT, numeral 10.6);
* la DUA o DAM con la liquidación de la percepción a la importación
  (R.S. 203-2003/SUNAT; aquí solo se registra lo que cobró la Aduana).

El registro genera el asiento (cargo a la cuenta de percepciones por aplicar,
abono al proveedor) y concilia el abono con lo pagado de más por la
percepción. Lo registrado en el periodo se aplica en el F.V. 621 contra el
IGV por pagar; el saldo no aplicado se arrastra a los periodos siguientes.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

RECEIVED_KINDS = [
    ('internal', 'Venta interna'),
    ('fuel', 'Combustibles'),
    ('import', 'Importación'),
]
RECEIVED_DOCUMENTS = [
    ('cpe', 'Comprobante de percepción'),
    ('invoice', 'Factura del proveedor'),
    ('dua', 'DUA o DAM'),
]


class L10nPePerceptionReceived(models.Model):
    _name = 'l10n_pe.perception.received'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Percepción del IGV que nos cobran'
    _order = 'date desc, id desc'
    _check_company_auto = True

    l10n_pe_series = fields.Char(string='Serie', size=4, tracking=True)
    l10n_pe_number = fields.Char(string='Número', size=20, tracking=True)
    name = fields.Char(
        string='Nº de documento', required=True, size=32,
        compute='_compute_name', inverse='_inverse_name', store=True, readonly=False,
        precompute=True, tracking=True,
        help='Serie y número del comprobante de percepción, de la factura o de la DUA.')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    partner_id = fields.Many2one(
        'res.partner', string='Agente de percepción', required=True, check_company=True,
        tracking=True, help='Proveedor que nos cobró la percepción, o la Aduana.')
    kind = fields.Selection(
        RECEIVED_KINDS, string='Régimen', required=True, default='internal', tracking=True)
    document_kind = fields.Selection(
        RECEIVED_DOCUMENTS, string='Documento', required=True, default='cpe', tracking=True)
    date = fields.Date(
        string='Fecha', required=True, default=fields.Date.context_today, tracking=True,
        help='Fecha del comprobante de percepción, del pago de la factura o de la '
             'liquidación de la DUA: decide el periodo del F.V. 621 en que se aplica.')
    journal_id = fields.Many2one(
        'account.journal', string='Diario', check_company=True,
        domain="[('type', '=', 'general')]")
    line_ids = fields.One2many(
        'l10n_pe.perception.received.line', 'received_id', string='Comprobantes', copy=True)
    amount = fields.Monetary(
        string='Percibido (S/)', compute='_compute_amount', store=True, tracking=True)
    move_id = fields.Many2one(
        'account.move', string='Asiento', readonly=True, copy=False, check_company=True)
    state = fields.Selection(
        [('draft', 'Borrador'), ('posted', 'Registrado'), ('cancel', 'Anulado')],
        string='Estado', required=True, default='draft', copy=False, tracking=True)

    # Registrar dos veces el mismo documento duplicaría el crédito.
    _name_partner_uniq = models.Constraint(
        'UNIQUE(company_id, partner_id, document_kind, name)',
        'Ese documento ya está registrado para el agente de percepción.')

    @api.depends('l10n_pe_series', 'l10n_pe_number')
    def _compute_name(self):
        for record in self:
            if record.l10n_pe_series and record.l10n_pe_number:
                record.name = '%s-%s' % (record.l10n_pe_series.strip().upper(),
                                         record.l10n_pe_number.strip())
            else:
                record.name = record.name  # escrito a mano

    def _inverse_name(self):
        """Un número escrito entero (P001-00000123) llena serie y número."""
        for record in self:
            series, sep, number = (record.name or '').strip().partition('-')
            if sep and series and number and len(series) <= 4:
                record.l10n_pe_series = series.upper()
                record.l10n_pe_number = number

    @api.depends('line_ids.amount')
    def _compute_amount(self):
        for record in self:
            record.amount = sum(record.line_ids.mapped('amount'))

    def _l10n_pe_check_postable(self):
        self.ensure_one()
        currency = self.company_id.currency_id
        if not self.line_ids:
            raise UserError(self.env._('Agregue la percepción de cada comprobante.'))
        partner = self.partner_id.commercial_partner_id
        for line in self.line_ids:
            bill = line.bill_id
            if bill and (bill.state != 'posted'
                         or bill.move_type not in ('in_invoice', 'in_receipt')):
                raise UserError(self.env._(
                    '%s no es una factura de proveedor publicada.', bill.display_name))
            if bill and self.document_kind != 'dua' and bill.commercial_partner_id != partner:
                raise UserError(self.env._(
                    'La factura %(bill)s no es de %(partner)s.',
                    bill=bill.display_name, partner=partner.display_name))
            if currency.compare_amounts(line.amount, 0.0) <= 0:
                raise UserError(self.env._('La percepción de cada línea debe ser mayor que cero.'))

    def action_post(self):
        for record in self:
            if record.state != 'draft':
                continue
            record._l10n_pe_check_postable()
            company = record.company_id
            account = company.l10n_pe_perception_received_account_id
            if not account:
                raise UserError(self.env._(
                    'Configure la «Cuenta de percepciones por aplicar» en Ajustes ▸ Perú ▸ '
                    'Percepciones del IGV.'))
            journal = record.journal_id or company.l10n_pe_perception_received_journal_id \
                or self.env['account.journal'].search([
                    *self.env['account.journal']._check_company_domain(company),
                    ('type', '=', 'general')], limit=1)
            partner = record.partner_id.commercial_partner_id
            payable = partner.with_company(company).property_account_payable_id
            line_vals = [(0, 0, {
                'name': self.env._('Percepción %(document)s · %(bill)s', document=record.name,
                                   bill=line.bill_id.name or line.reference or record.name),
                'account_id': account.id,
                'partner_id': partner.id,
                'debit': line.amount,
            }) for line in record.line_ids]
            line_vals.append((0, 0, {
                'name': self.env._('Percepción del IGV %s', record.name),
                'account_id': (record.line_ids.bill_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'liability_payable')[:1].account_id
                    or payable).id,
                'partner_id': partner.id,
                'credit': record.amount,
            }))
            move = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': journal.id,
                'date': record.date,
                'ref': self.env._('Percepción del IGV que nos cobran %s', record.name),
                'line_ids': line_vals,
            })
            move.action_post()
            credit = move.line_ids.filtered(lambda l: l.credit)
            debits = self.env['account.move.line'].search([
                ('account_id', '=', credit.account_id.id),
                ('partner_id', '=', partner.id),
                ('reconciled', '=', False),
                ('debit', '>', 0),
                ('parent_state', '=', 'posted'),
                ('company_id', '=', company.id),
                ('move_id.origin_payment_id', '!=', False),
            ])
            if debits:
                # lo que se pagó de más al proveedor es la percepción
                (credit | debits).reconcile()
            record.write({'move_id': move.id, 'state': 'posted'})
        return True

    def action_cancel(self):
        for record in self.filtered(lambda r: r.state != 'cancel'):
            move = record.move_id
            if move and move.state == 'posted':
                move.line_ids.remove_move_reconcile()
                move.button_draft()
                move.button_cancel()
            record.state = 'cancel'
        return True

    def action_draft(self):
        for record in self.filtered(lambda r: r.state == 'cancel'):
            record.write({'state': 'draft', 'move_id': False})
        return True

    @api.ondelete(at_uninstall=False)
    def _unlink_except_posted(self):
        if any(record.state == 'posted' for record in self):
            raise UserError(self.env._(
                'No se elimina una percepción registrada: anúlela primero.'))

    def action_view_move(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'account.move',
            'res_id': self.move_id.id, 'view_mode': 'form',
        }


class L10nPePerceptionReceivedLine(models.Model):
    _name = 'l10n_pe.perception.received.line'
    _description = 'Comprobante de una percepción que nos cobran'
    _order = 'received_id, id'
    _check_company_auto = True

    received_id = fields.Many2one(
        'l10n_pe.perception.received', string='Percepción', required=True,
        ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(
        related='received_id.company_id', string='Compañía', store=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    partner_id = fields.Many2one(
        related='received_id.partner_id', string='Agente de percepción', store=True)
    date = fields.Date(related='received_id.date', string='Fecha', store=True)
    state = fields.Selection(related='received_id.state', string='Estado', store=True)
    kind = fields.Selection(related='received_id.kind', string='Régimen', store=True)
    bill_id = fields.Many2one(
        'account.move', string='Factura de proveedor', index=True, check_company=True,
        domain="[('move_type', 'in', ('in_invoice', 'in_receipt')), ('state', '=', 'posted')]")
    reference = fields.Char(
        string='Comprobante', help='Serie y número del comprobante percibido, si no está en '
                                   'Odoo (o la DUA).')
    base_amount = fields.Monetary(
        string='Monto cobrado (S/)', help='Precio de venta con IGV sobre el que se calculó.')
    amount = fields.Monetary(string='Percepción (S/)', required=True)
