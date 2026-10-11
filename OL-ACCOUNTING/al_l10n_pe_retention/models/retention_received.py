# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nPeRetentionReceived(models.Model):
    """Retenciones SUFRIDAS: un cliente agente de retención nos retuvo el
    IGV y entregó su comprobante de retención (CRE). El CRE puede cubrir una
    o varias facturas (líneas); al registrarlo se genera el asiento (IGV
    retenido contra el cliente) y se concilia con cada factura, dejando el
    crédito listo para aplicar contra el IGV del periodo (formulario 621)."""
    _name = 'l10n_pe.retention.received'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'PE - Retención de IGV sufrida (cliente agente)'
    _order = 'date desc, id desc'
    _check_company_auto = True

    l10n_pe_series = fields.Char(
        string='Serie', size=4, tracking=True,
        help='Serie del comprobante de retención del cliente (R001, E001…).')
    l10n_pe_number = fields.Char(
        string='Número', size=8, tracking=True,
        help='Número correlativo del comprobante de retención.')
    name = fields.Char(
        string='N.º de comprobante', required=True, size=24,
        compute='_compute_name', inverse='_inverse_name', store=True, readonly=False,
        help='Serie y número del comprobante emitido por el cliente (R001-00000123).',
        tracking=True)
    date = fields.Date(
        string='Fecha del comprobante', required=True,
        default=fields.Date.context_today,
        tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True,
        check_company=True,
        tracking=True,
        help='Cliente agente de retención que emitió el comprobante.')
    line_ids = fields.One2many(
        'l10n_pe.retention.received.line', 'retention_id', string='Comprobantes retenidos',
        copy=True)
    amount = fields.Monetary(
        string='Monto retenido', compute='_compute_amount', store=True,
        help='Suma de lo retenido en las facturas del comprobante.',
        tracking=True)
    entry_id = fields.Many2one(
        'account.move', string='Asiento', readonly=True, copy=False,
        check_company=True)
    state = fields.Selection(
        [('draft', 'Borrador'), ('posted', 'Registrado')],
        default='draft', string='Estado', copy=False,
        tracking=True)

    # Registrar dos veces el mismo comprobante duplicaría el crédito.
    _name_partner_uniq = models.Constraint(
        'UNIQUE(company_id, partner_id, name)',
        'Ese comprobante de retención ya está registrado para el cliente.')

    @api.depends('l10n_pe_series', 'l10n_pe_number')
    def _compute_name(self):
        for record in self:
            if record.l10n_pe_series and record.l10n_pe_number:
                record.name = '%s-%s' % (record.l10n_pe_series.strip().upper(),
                                         record.l10n_pe_number.strip())
            else:
                record.name = record.name  # escrito a mano o migrado

    def _inverse_name(self):
        """Un número escrito entero (R001-00000123) llena serie y número."""
        for record in self:
            series, sep, number = (record.name or '').strip().partition('-')
            if sep and series and number:
                record.l10n_pe_series = series.upper()
                record.l10n_pe_number = number

    @api.depends('line_ids.amount')
    def _compute_amount(self):
        for record in self:
            record.amount = sum(record.line_ids.mapped('amount'))

    def _l10n_pe_check_postable(self):
        """El dominio de la vista no basta: la acción llega también por RPC."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(self.env._(
                'Agregue al comprobante %(number)s las facturas a las que se aplicó la '
                'retención.', number=self.name))
        currency = self.company_id.currency_id
        for line in self.line_ids:
            move = line.move_id
            if move.move_type != 'out_invoice' or move.state != 'posted':
                raise UserError(self.env._(
                    'La retención sufrida %(number)s debe vincularse a facturas de venta '
                    'publicadas: %(move)s no lo es.', number=self.name,
                    move=move.display_name))
            if move.commercial_partner_id != self.partner_id.commercial_partner_id:
                raise UserError(self.env._(
                    'La factura %(move)s no es del cliente %(partner)s.',
                    move=move.display_name, partner=self.partner_id.display_name))
            if currency.compare_amounts(line.amount, 0.0) <= 0:
                raise UserError(self.env._(
                    'El monto retenido de %(move)s debe ser mayor a cero.',
                    move=move.display_name))
            if not line._l10n_pe_open_receivable():
                raise UserError(self.env._(
                    'La factura %(move)s ya no tiene saldo por cobrar: no hay '
                    'dónde aplicar la retención.', move=move.display_name))

    def action_post(self):
        for record in self:
            if record.state != 'draft':
                continue
            record._l10n_pe_check_postable()
            company = record.company_id
            account = company.l10n_pe_retention_received_account_id
            if not account:
                raise UserError(self.env._(
                    'Configure la «Cuenta de retenciones sufridas» '
                    '(40114) en Ajustes ▸ Perú.'))
            journal = (company.l10n_pe_retention_received_journal_id
                       or self.env['account.journal'].search(
                           [('company_id', '=', company.id),
                            ('type', '=', 'general')], limit=1))
            # Una línea de IGV retenido por el total y un abono por factura,
            # que se concilia con su cuenta por cobrar.
            line_vals = [(0, 0, {'account_id': account.id,
                                 'partner_id': record.partner_id.id,
                                 'name': record.name,
                                 'debit': record.amount, 'credit': 0.0})]
            for line in record.line_ids:
                receivable = line._l10n_pe_open_receivable()
                line_vals.append((0, 0, {
                    'account_id': receivable[:1].account_id.id
                    or record.partner_id.with_company(company)
                    .property_account_receivable_id.id,
                    'partner_id': record.partner_id.id,
                    'name': '%s · %s' % (record.name, line.move_id.name),
                    'debit': 0.0, 'credit': line.amount}))
            entry = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': journal.id,
                'date': record.date,
                'ref': self.env._('Retención sufrida %(number)s',
                                  number=record.name),
                'line_ids': line_vals})
            entry.action_post()
            credits = entry.line_ids.filtered(lambda l: l.credit > 0)
            for line, credit in zip(record.line_ids, credits):
                receivable = line._l10n_pe_open_receivable()
                if receivable:
                    (receivable + credit).reconcile()
            record.write({'entry_id': entry.id, 'state': 'posted'})
        return True

    @api.ondelete(at_uninstall=False)
    def _unlink_except_posted(self):
        if any(record.state == 'posted' for record in self):
            raise UserError(self.env._(
                'No se puede eliminar una retención sufrida registrada: '
                'pásela primero a borrador.'))

    def action_draft(self):
        for record in self.filtered(lambda r: r.state == 'posted'):
            if record.entry_id:
                record.entry_id.button_draft()
                record.entry_id.button_cancel()
            record.write({'state': 'draft', 'entry_id': False})
        return True


class L10nPeRetentionReceivedLine(models.Model):
    """Factura a la que el cliente agente aplicó la retención, dentro de su
    comprobante de retención."""
    _name = 'l10n_pe.retention.received.line'
    _description = 'PE - Factura de una retención sufrida'
    _order = 'retention_id, id'
    _check_company_auto = True

    retention_id = fields.Many2one(
        'l10n_pe.retention.received', string='Comprobante de retención', required=True,
        ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(
        related='retention_id.company_id', string='Compañía', store=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    partner_id = fields.Many2one(
        related='retention_id.partner_id', string='Cliente', store=True, index=True)
    date = fields.Date(related='retention_id.date', string='Fecha', store=True)
    state = fields.Selection(related='retention_id.state', string='Estado', store=True)
    move_id = fields.Many2one(
        'account.move', string='Factura de venta', required=True, index=True,
        check_company=True,
        domain="[('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),"
               " ('commercial_partner_id', '=', partner_id)]")
    invoice_amount = fields.Monetary(
        string='Total de la factura (S/)', compute='_compute_invoice_amount')
    amount = fields.Monetary(
        string='Monto retenido', required=True,
        help='Lo retenido a esta factura según el comprobante del cliente, en soles.')

    @api.depends('move_id')
    def _compute_invoice_amount(self):
        for line in self:
            line.invoice_amount = abs(line.move_id.amount_total_signed)

    @api.onchange('move_id')
    def _onchange_move_id(self):
        company = self.retention_id.company_id or self.env.company
        for line in self:
            if line.move_id and not line.amount:
                line.amount = company.currency_id.round(
                    abs(line.move_id.amount_total_signed)
                    * company.l10n_pe_retention_rate / 100.0)

    def _l10n_pe_open_receivable(self):
        self.ensure_one()
        return self.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled)
