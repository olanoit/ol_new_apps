# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class L10nPeLetterLine(models.Model):
    _name = 'l10n_pe.letter.line'
    _description = 'Letras por cobrar'

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
    )
    letter_id = fields.Many2one(
        'l10n_pe.letter',
        string='Canje',
        ondelete='cascade',
    )
    journal_id = fields.Many2one(related='letter_id.journal_id', store=True)
    related_invoice_names = fields.Char(related='letter_id.related_invoice_names', store=True)
    letter_name = fields.Char(related='letter_id.name', store=True, string='Código de canje')

    partner_id = fields.Many2one(
        'res.partner',
        string='Socio',
        related='letter_id.partner_id',
    )
    move_invoice_type = fields.Selection(
        string='Tipo',
        related='letter_id.type',
    )
    state = fields.Selection(
        string='Estado',
        related='letter_id.state',
    )
    letter_user_id = fields.Many2one(
        'res.users',
        string='Vendedor',
        default=lambda self: self.env.user
    )
    nro_letter = fields.Char(
        string='Nro. de letra',
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        related='letter_id.company_currency_id',
        string='Moneda',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        related='letter_id.currency_id',
    )
    bank_id = fields.Many2one(
        'res.bank',
        string='Banco',
    )
    code = fields.Char(
        string='Código',
    )
    letter_type = fields.Selection(
        selection=[
            ('portfolio', 'En cartera'),
            ('billing', 'Cobranza libre'),
            ('discount', 'Descuento'),
            ('protested', 'Protestada'),
        ],
        string='Tipo de letra',
    )

    account_id = fields.Many2one(
        'account.account',
        string='Cuenta',
        index=True, store=True,
        compute='_compute_account_id',
    )
    expiration_date = fields.Date(
        string='Fecha vencimiento',
        required=True,
    )
    payment_state = fields.Selection(
        selection=[
            ('pending', 'No pagado'),
            ('paid', 'Pagado'),
            ('partial', 'Pago parcial')
        ],
        string='Estado de pago',
        default='pending',
        compute='_compute_payment_state',
    )
    exchange_rate = fields.Float(
        string='Tipo de cambio',
        digits=(12, 4),
        related='letter_id.exchange_rate', store=True
    )
    imp_div = fields.Monetary(
        string='Importe div',
        currency_field='currency_id',
    )
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
        compute='_compute_debit_credit', default=0.0)
    adeudado = fields.Monetary(
        string='Adeudado',
        currency_field='currency_id',
        default=0.0,
        compute='compute_adeudado',
        store=True)

    # Cambio del monto adeudado
    @api.depends('letter_id.account_id.line_ids.amount_residual_currency')
    def compute_adeudado(self):
        for line in self:
            if line.letter_id.account_id:
                name = line.nro_letter
                partner_id = line.partner_id.id
                move_name = line.letter_id.account_id.name
                move_line_id = line.letter_id.account_id.line_ids.search(
                    [('name', '=', name), ('partner_id', '=', partner_id), ('move_name', '=', move_name)])
                if move_line_id:
                    line.adeudado = abs(move_line_id.amount_residual_currency)
                else:
                    line.adeudado = line.imp_div
            else:
                line.adeudado = line.imp_div

    @api.onchange('imp_div')
    def _onchange_adeudado(self):
        for record in self:
            if record.imp_div:
                record.adeudado = record.imp_div
            else:
                record.adeudado = 0.0

    # Método computado para el estado de pago
    @api.depends('adeudado')
    def _compute_payment_state(self):
        for record in self:
            if record.adeudado == record.imp_div:
                record.payment_state = 'pending'
            elif record.adeudado == 0.0:
                record.payment_state = 'paid'
            elif record.adeudado > 0.0:
                record.payment_state = 'partial'
            else:
                record.payment_state = 'pending'

    # Configuración de nombre
    @api.depends('nro_letter')
    def _compute_name(self):
        for record in self:
            if record.nro_letter:
                record.name = record.nro_letter
            else:
                record.name = 'Nueva letra'

    # Cálculo del debe y haber
    @api.depends('imp_div', 'exchange_rate')
    def _compute_debit_credit(self):
        for record in self:
            if record.move_invoice_type == 'out_invoice':
                record.debit = record.imp_div * record.exchange_rate
                record.credit = 0.0
            else:
                record.debit = 0.0
                record.credit = record.imp_div * record.exchange_rate

    # Configuración de Cuentas
    @api.depends('move_invoice_type')
    def _compute_account_id(self):
        for record in self:
            if record.move_invoice_type == 'in_invoice':
                account_type = 'liability_payable'
            elif record.move_invoice_type == 'out_invoice':
                account_type = 'asset_receivable'
            else:
                continue
            invoice_account = self.env['l10n_pe.letter.account.config'].search([
                ('account_type', '=', account_type),
                ('document_type', '=', 'letter'),
                ('letter_type', '=', record.letter_type),
                ('currency_id', '=', record.currency_id.id)
            ], limit=1)
            # Cuenta por defecto en Portafolio
            if invoice_account:
                record.account_id = invoice_account.account_id.id
            else:
                invoice_account = self.env['l10n_pe.letter.account.config'].search([
                    ('account_type', '=', account_type),
                    ('document_type', '=', 'letter'),
                    ('currency_id', '=', record.currency_id.id),
                    ('letter_type', '=', 'portfolio')
                ], limit=1)
                if invoice_account:
                    record.account_id = invoice_account.account_id.id
                else:
                    raise UserError('No se encontró una cuenta para la letra')

    # Guarda el tipo de cambio al momento de la creación
    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            letter_id = values.get('letter_id')
            if letter_id:
                letter = self.env['l10n_pe.letter'].browse(letter_id)
                values['exchange_rate'] = letter.exchange_rate
        return super().create(vals_list)

    # Evitar crear letras con el mismo número para el mismo partner
    @api.constrains('nro_letter')
    def _check_nro_letter(self):
        for record in self:
            if record.nro_letter:
                letter = self.env['l10n_pe.letter.line'].search([
                    ('nro_letter', '=', record.nro_letter),
                    ('partner_id', '=', record.partner_id.id),
                    ('id', '!=', record.id)
                ])
                if letter:
                    raise UserError(f'Ya existe la letra: {letter.name} para el socio: {letter.partner_id.name}')
