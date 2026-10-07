# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class L10nPeLetterLine(models.Model):
    _name = 'l10n_pe.letter.line'
    _description = 'Letras por cobrar'
    _check_company_auto = True

    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
    )
    letter_id = fields.Many2one(
        'l10n_pe.letter',
        string='Canje',
        ondelete='cascade', check_company=True
    )
    journal_id = fields.Many2one(related='letter_id.journal_id', store=True)
    # Compañía del canje, guardada: sin ella las listas de letras y la
    # búsqueda de documentos no podían filtrarse por compañía (reglas).
    company_id = fields.Many2one(
        related='letter_id.company_id', store=True, index=True, string='Compañía')
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
        string='Moneda de la compañía',
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
        default='portfolio',
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
    discount_move_id = fields.Many2one(
        'account.move', string='Liquidación del descuento', readonly=True, copy=False,
        check_company=True)
    collection_move_id = fields.Many2one(
        'account.move', string='Asiento de cobro', readonly=True, copy=False,
        check_company=True)
    protest_move_id = fields.Many2one(
        'account.move', string='Asiento de protesto', readonly=True, copy=False,
        check_company=True)
    protest_date = fields.Date(string='Fecha de protesto', readonly=True, copy=False)
    adeudado = fields.Monetary(
        string='Adeudado',
        currency_field='currency_id',
        default=0.0,
        compute='compute_adeudado',
        store=True)

    # Cambio del monto adeudado: saldo del apunte de la letra en el asiento
    # del canje (enlazado por ``l10n_pe_letter_line_id``) o, sin asiento, el
    # importe de la letra.
    @api.depends('imp_div', 'nro_letter',
                 'letter_id.account_id.line_ids.amount_residual_currency',
                 'letter_id.account_id.line_ids.l10n_pe_letter_line_id',
                 'letter_id.canje_move_id.line_ids.amount_residual_currency',
                 'letter_id.canje_move_ids.line_ids.amount_residual_currency',
                 'letter_id.bank_move_ids.line_ids.amount_residual_currency')
    def compute_adeudado(self):
        """Lo que falta cobrar o pagar de la letra: el saldo de sus apuntes en el
        canje, en el envío al banco y en las operaciones del banco (protesto)."""
        for line in self:
            letter = line.letter_id
            moves = letter.account_id | letter.canje_move_id | letter.canje_move_ids | letter.bank_move_ids
            move_lines = moves.filtered(lambda m: m.state == 'posted').line_ids.filtered(
                lambda move_line: move_line.l10n_pe_letter_line_id == line)
            if move_lines:
                line.adeudado = abs(sum(move_lines.mapped('amount_residual_currency')))
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
    @api.depends('adeudado', 'imp_div')
    def _compute_payment_state(self):
        for record in self:
            currency = record.currency_id or record.company_currency_id
            if currency.is_zero(record.adeudado - record.imp_div) or currency.compare_amounts(record.adeudado, 0.0) < 0:
                record.payment_state = 'pending'
            elif currency.is_zero(record.adeudado):
                record.payment_state = 'paid'
            else:
                record.payment_state = 'partial'

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
            company = record.letter_id.company_id or self.env.company
            invoice_account = self.env['l10n_pe.letter.account.config'].search([
                ('account_type', '=', account_type),
                ('document_type', '=', 'letter'),
                ('letter_type', '=', record.letter_type),
                ('currency_id', '=', record.currency_id.id),
                ('company_id', '=', company.id),
            ], limit=1)
            # Cuenta por defecto en Portafolio
            if invoice_account:
                record.account_id = invoice_account.account_id.id
            else:
                invoice_account = self.env['l10n_pe.letter.account.config'].search([
                    ('account_type', '=', account_type),
                    ('document_type', '=', 'letter'),
                    ('currency_id', '=', record.currency_id.id),
                    ('letter_type', '=', 'portfolio'),
                    ('company_id', '=', company.id),
                ], limit=1)
                if invoice_account:
                    record.account_id = invoice_account.account_id.id
                else:
                    raise UserError(self.env._(
                        'No se encontró una cuenta para la letra en la compañía %s.', company.name))

    # ------------------------------------------------------------------
    # Operaciones con el banco (asistente l10n_pe.letter.bank.wizard)
    # ------------------------------------------------------------------
    def _l10n_pe_open_bank_line(self):
        """Apunte abierto de la letra en la cuenta de cobranza (1233) o
        descuento (1234), creado al enviarla al banco."""
        self.ensure_one()
        letter = self.letter_id
        return (letter.canje_move_id | letter.canje_move_ids).filtered(
            lambda m: m.state == 'posted').line_ids.filtered(
            lambda l: l.l10n_pe_letter_line_id == self and not l.reconciled
            and l.currency_id.compare_amounts(l.amount_residual_currency, 0.0) > 0)[:1]

    def _l10n_pe_open_line(self, exclude_move=None):
        """Apunte que hoy sostiene el saldo de la letra: el del canje (cartera),
        el del envío al banco (cobranza/descuento) o el del protesto. Una
        renovación tiene que cerrar este, no siempre el de cartera."""
        self.ensure_one()
        letter = self.letter_id
        moves = (letter.account_id | letter.canje_move_id | letter.canje_move_ids
                 | letter.bank_move_ids | self.protest_move_id).filtered(
            lambda m: m.state == 'posted')
        if exclude_move:
            moves -= exclude_move
        sign = 1 if self.move_invoice_type == 'out_invoice' else -1
        lines = moves.line_ids.filtered(
            lambda l: l.l10n_pe_letter_line_id == self and not l.reconciled
            and l.account_id.reconcile
            and l.currency_id.compare_amounts(sign * l.amount_residual_currency, 0.0) > 0)
        return lines.sorted('id')[-1:]

    def _l10n_pe_bank_operation_allowed(self, operation):
        self.ensure_one()
        if self.move_invoice_type != 'out_invoice' or self.letter_type not in ('billing', 'discount'):
            return False
        if not self._l10n_pe_open_bank_line():
            return False
        if operation == 'settle_discount':
            return self.letter_type == 'discount' and not self.discount_move_id
        if operation == 'collected':
            # En descuento, el banco cancela el préstamo: antes debe haberlo dado.
            return self.letter_type == 'billing' or bool(self.discount_move_id)
        return operation == 'protest'

    def _l10n_pe_config_account(self, letter_type):
        """Cuenta configurada para ``letter_type`` (o la de cartera)."""
        self.ensure_one()
        account_type = 'asset_receivable' if self.move_invoice_type == 'out_invoice' else 'liability_payable'
        Config = self.env['l10n_pe.letter.account.config']
        domain = [('account_type', '=', account_type), ('document_type', '=', 'letter'),
                  ('currency_id', '=', self.currency_id.id),
                  ('company_id', '=', self.letter_id.company_id.id)]
        config = Config.search(domain + [('letter_type', '=', letter_type)], limit=1) or \
            Config.search(domain + [('letter_type', '=', 'portfolio')], limit=1)
        if not config:
            raise UserError(self.env._('Configure la cuenta de letras «%s» de la compañía %s.',
                                       letter_type, self.letter_id.company_id.name))
        return config.account_id

    def _l10n_pe_protested_account(self):
        """Letras protestadas: la cuenta configurada o, sin ella, la de cartera
        (el PCGE no tiene una subcuenta propia)."""
        return self._l10n_pe_config_account('protested')

    BANK_FIELDS = ('bank_id', 'code', 'letter_type')

    def write(self, vals):
        result = super().write(vals)
        if any(field in vals for field in self.BANK_FIELDS):
            self.letter_id._update_banked_state()
            # Las letras de un canje masivo cuelgan de él por many2many.
            self.env['l10n_pe.letter.massive'].search(
                [('letter_move_ids', 'in', self.ids)])._update_banked_state()
        return result

    # Evitar crear letras con el mismo número para el mismo partner
    @api.constrains('nro_letter')
    def _check_nro_letter(self):
        for record in self:
            if record.nro_letter:
                letter = self.env['l10n_pe.letter.line'].search([
                    ('nro_letter', '=', record.nro_letter),
                    ('partner_id', '=', record.partner_id.id),
                    ('company_id', '=', record.company_id.id),
                    ('id', '!=', record.id)
                ])
                if letter:
                    raise ValidationError(f'Ya existe la letra: {letter.name} para el socio: {letter.partner_id.name}')
