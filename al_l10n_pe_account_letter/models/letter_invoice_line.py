# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class L10nPeLetterInvoiceLine(models.Model):
    _name = 'l10n_pe.letter.invoice.line'
    _description = 'Facturas por cobrar'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
    )
    letter_id = fields.Many2one(
        'l10n_pe.letter',
        string='Letra',
        ondelete='cascade',
    )
    move_invoice_type = fields.Selection(
        string='Tipo',
        related='letter_id.type',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Socio',
        related='letter_id.partner_id',
    )

    document_type_id = fields.Many2one(
        'l10n_latam.document.type',
        string='Tipo de documento',
        domain="[('country_id.code', '=', 'PE')]",
    )

    @api.onchange('document_type_id')
    def onchange_document_type_id(self):
        self.move_line_id = False
        self.onchange_invoice_account()

    move_line_id = fields.Many2one('account.move.line', string='Factura')
    domain_move_line_id = fields.One2many('account.move.line', 'id', string='Domain',
                                          compute='_compute_domain_move_line_id')
    date_em = fields.Date('Fecha emisión', compute='_compute_date_em')

    @api.depends(
        'move_line_id', 'move_line_id.date', 'move_line_id.move_id.invoice_date',
        'letter_id.invoice_date', 'document_type_id.code', 'letter_id.is_refinance_children'
    )
    def _compute_date_em(self):
        for record in self:
            if (record.document_type_id.code == '99' and record.letter_id
                    and record.letter_id.is_refinance_children and record.letter_id.invoice_date):
                record.date_em = record.letter_id.invoice_date
            elif record.move_line_id:
                if record.move_id.invoice_date and record.move_id.move_type != 'entry':
                    record.date_em = record.move_id.invoice_date
                else:
                    record.date_em = record.move_line_id.date
            else:
                record.date_em = False

    @api.depends('document_type_id.code', 'partner_id', 'move_invoice_type', 'currency_id', 'letter_id.invoice_line_ids')
    def _compute_domain_move_line_id(self):
        for record in self:
            code = record.document_type_id.code

            domain = [
                ('partner_id', '=', record.partner_id.id),
                ('currency_id', '=', record.currency_id.id),
                ('parent_state', '=', 'posted'),
                ('id', 'not in', record.letter_id.invoice_line_ids.move_line_id.ids),
            ]
            if code == '00':
                domain += [
                    ('journal_id.name', 'ilike', 'apertura'),
                    ('move_type', '=', 'entry'),
                    ('account_id.reconcile', '=', True),
                    ('reconciled', '=', False),
                    ('amount_residual_currency', '!=', 0.0),
                ]

            elif code == '99':
                origin_letters = record.letter_id._get_refinance_origins() if record.letter_id else self.env['l10n_pe.letter']
                account_moves = origin_letters.mapped('account_id')
                if account_moves:
                    domain += [
                        ('move_id', 'in', account_moves.ids),
                        ('move_type', '=', 'entry'),
                        ('display_type', '=', False),
                        ('l10n_pe_letter_invoice_line_id', '=', False),
                    ]
                else:
                    domain = [('id', '=', 0)]

            else:
                domain += [
                    ('l10n_latam_document_type_id.code', '=', code),
                    ('move_type', '=', record.move_invoice_type),
                    ('display_type', '=', 'payment_term'),
                    ('reconciled', '=', False),
                ]
                if record.move_invoice_type == 'in_invoice':
                    domain += [('amount_residual_currency', '<', 0.0)]
                else:
                    domain += [('amount_residual_currency', '>', 0.0)]

            data = self.env['account.move.line'].search(domain).ids
            record.domain_move_line_id = [(6, 0, data)]

    move_id = fields.Many2one(
        'account.move',
        string='Asiento contable',
        related='move_line_id.move_id',
    )
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta',
        index=True, store=True,
    )

    @api.onchange('move_line_id')
    def onchange_invoice_account(self):
        for record in self:
            if record.move_line_id:
                record.account_id = record.move_line_id.account_id.id
            else:
                record.account_id = False

    invoice_name = fields.Char(
        string='Nro comprobante',
        related='move_line_id.name',
    )
    # Moneda
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='letter_id.currency_id',
        readonly=True,
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda de la compañía',
        related='letter_id.company_currency_id',
        readonly=True,
    )
    balance = fields.Monetary(
        string='Total',
        related='move_line_id.amount_currency',
        readonly=True,
    )
    amount_currency = fields.Monetary(
        string='Saldo',
        related='move_line_id.amount_residual_currency',
        readonly=True,
    )
    exchange_rate = fields.Float(
        string='T.C.',
        related='letter_id.exchange_rate',
        readonly=True,
    )
    imp_div = fields.Monetary(
        string='Importe div',
        currency_field='currency_id')

    refinance_base_amount = fields.Monetary(
        string='Importe base refinanciado',
        currency_field='currency_id',
        help=(
            'Monto máximo permitido para la línea cuando proviene de un refinanciamiento. '
            'Se establece con el adeudado de la letra original y se usa para validar '
            'los importes ingresados.'
        ),
        readonly=True,
    )

    @api.onchange('amount_currency')
    def _compute_imp_div(self):
        if self.letter_id.state in ['draft', 'checked']:
            self.imp_div = abs(self.amount_currency)
        else:
            self.imp_div = self.imp_div

    debit = fields.Monetary(
        string='Debe',
        currency_field='company_currency_id',
        readonly=True,
        compute='_compute_debit_credit', default=0.0
    )
    credit = fields.Monetary(
        string='Haber',
        currency_field='company_currency_id',
        readonly=True,
        compute='_compute_debit_credit', default=0.0
    )

    @api.depends('imp_div', 'move_invoice_type')
    def _compute_debit_credit(self):
        for line in self:
            debit = credit = 0.0
            if line.move_invoice_type == 'in_invoice':
                debit = line.imp_div * line.exchange_rate
            elif line.move_invoice_type == 'out_invoice':
                credit = line.imp_div * line.exchange_rate

            if line.exchange_rate != 1.0:
                # Aplicar redondeo si el tipo de cambio es diferente a 1
                debit = line.currency_id and line.currency_id.round(debit) or 0.0
                credit = line.currency_id and line.currency_id.round(credit) or 0.0

            line.debit = debit
            line.credit = credit

    # Método para el nombre
    @api.depends('invoice_name')
    def _compute_name(self):
        for record in self:
            if record.invoice_name:
                record.name = record.invoice_name
            else:
                record.name = 'Factura#'

    @api.constrains('imp_div', 'move_line_id')
    def _check_imp_div_not_greater_than_residual(self):
        for line in self:
            if not line.move_line_id or not line.letter_id or line.letter_id.state not in ('draft', 'checked'):
                continue

            entered = abs(line.imp_div or 0.0)

            if entered <= 0:
                raise UserError('El importe div debe ser mayor que 0.')

            if line.letter_id.is_refinance_children and line.document_type_id.code == '99':
                residual = abs(line.refinance_base_amount or 0.0)
            else:
                residual = abs(line.amount_currency or 0.0)

            precision = line.currency_id.rounding if line.currency_id else 0.01

            if float_compare(entered, residual, precision_digits=None, precision_rounding=precision) == 1:
                raise UserError(
                    f'El importe div ({entered}) no puede ser mayor que el saldo pendiente ({residual}) '
                    f'en {line.currency_id.name}.'
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for rec, val in zip(records, vals_list):
            if not rec.letter_id or not rec.letter_id.is_refinance_children:
                continue
            if rec.refinance_base_amount:
                continue

            base = abs(val.get('refinance_base_amount')
                       or val.get('imp_div')
                       or rec.imp_div
                       or rec.amount_currency
                       or 0.0)
            if not base:
                continue

            super(L10nPeLetterInvoiceLine, rec).write({'refinance_base_amount': base})

        return records

    def write(self, vals):
        res = super().write(vals)

        if any(field in vals for field in ('imp_div', 'letter_id', 'refinance_base_amount')):
            refinance_children = self.filtered(lambda r: r.letter_id and r.letter_id.is_refinance_children)
            for rec in refinance_children.filtered(lambda r: not r.refinance_base_amount and r.imp_div):
                super(L10nPeLetterInvoiceLine, rec).write({'refinance_base_amount': abs(rec.imp_div)})

        return res

    def _clear_move_line_links(self):
        """Detach journal items that reference these invoice lines."""
        if not self:
            return

        move_line_env = self.env['account.move.line'].sudo().with_context(
            active_test=False,
            check_move_validity=False,
        )
        move_lines = move_line_env.search([
            ('l10n_pe_letter_invoice_line_id', 'in', self.ids)
        ])
        if move_lines:
            move_lines.write({'l10n_pe_letter_invoice_line_id': False})

        ids_tuple = tuple(self.ids)
        if ids_tuple:
            query = (
                "UPDATE account_move_line SET l10n_pe_letter_invoice_line_id = NULL "
                "WHERE l10n_pe_letter_invoice_line_id IN %s"
            )
            self.env.cr.execute(query, [ids_tuple])

    def unlink(self):
        self._clear_move_line_links()
        return super().unlink()
