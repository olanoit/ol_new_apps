# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api
from datetime import timedelta
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero

_logger = logging.getLogger(__name__)


class L10nPeLetterCanjeWizard(models.TransientModel):
    _name = 'l10n_pe.letter.canje.wizard'
    _description = 'Asistente de canje de letras'

    letter_id = fields.Many2one('l10n_pe.letter', 'Canje', required=True)
    letter_line_ids = fields.One2many('l10n_pe.letter.line', compute='_compute_letter_line_ids')

    @api.depends('letter_id', 'date_canje')
    def _compute_letter_line_ids(self):
        for record in self:
            lines = record.letter_id.letter_line_ids.filtered(lambda line: line.payment_state == 'pending')
            record.letter_line_ids = [(6, 0, lines.ids)]

    date_canje = fields.Date('Fecha de canje', required=True)
    min_date = fields.Date('Fecha letra', related='letter_id.account_id.date', store=True)
    letter_type = fields.Selection(
        selection=[
            ('billing', 'Cobranza libre'),
            ('discount', 'Descuento'),
        ],
        string='Tipo de letra',
        default='billing',
        required=True,
    )
    canje_type = fields.Selection(
        selection=[
            ('all', 'Todas las letras'),
            ('one', 'Por letra'),
        ],
        string='Tipo de canje',
        default='all',
        required=True,
    )
    show_canje_type = fields.Boolean(default=True)
    letter_line_id = fields.Many2one('l10n_pe.letter.line', 'Letra', required=False)

    bank_id = fields.Many2one(
        'res.bank',
        string='Banco',
        required=True,
    )
    code = fields.Char(
        string='Código',
        required=True,
    )

    def action_canje(self):
        if self.date_canje > fields.Date.context_today(self):
            raise UserError('La fecha de canje no puede ser mayor a la fecha actual.')
        if self.min_date and self.date_canje < self.min_date:
            raise UserError('La fecha de canje no puede ser menor a la fecha de la letra.')
        letter_line_id = False
        if self.canje_type == 'one':
            if not self.letter_line_id:
                raise UserError('Necesitas seleccionar una letra.')
            letter_line_id = self.letter_line_id
        self.letter_id.action_canje_create(self.letter_type, self.date_canje, letter_line_id)
        letter_line_ids = self.letter_id.letter_line_ids
        if self.canje_type == 'one':
            letter_line_ids = self.letter_line_id
        for letter_line in letter_line_ids:
            letter_line.bank_id = self.bank_id.id
            letter_line.code = self.code
            letter_line.letter_type = self.letter_type
        return True


class L10nPeLetter(models.Model):
    _name = 'l10n_pe.letter'
    _description = 'Gestión de letras'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    type = fields.Selection([
        ('out_invoice', 'Cliente'),
        ('in_invoice', 'Proveedor')],
        string='Tipo'
    )
    name = fields.Char(
        string=u'Nro. canje',
        index=True, default=lambda self: ('Borrador'), readonly=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Socio',
        tracking=True
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        tracking=True,
        domain="[('name', 'ilike', 'letra')]",
    )

    domain_letter_ids = fields.Many2many(
        'account.journal',
        string='Domain letter journals',
        compute='_compute_domain_letter_ids'
    )

    @api.depends('type')
    def _compute_domain_letter_ids(self):
        for record in self:
            # Filtrar por la compañía actual
            domain = [
                ('company_id', '=', self.env.company.id),
                ('name', 'ilike', 'letra')
            ]

            if record.type == 'out_invoice':
                domain += ['|', ('name', 'ilike', 'Cobrar'), ('name', 'ilike', 'cobrar')]
            else:
                domain += ['|', ('name', 'ilike', 'Pagar'), ('name', 'ilike', 'pagar')]

            # Buscar los journals de la compañía actual
            journals = self.env['account.journal'].search(domain)
            record.domain_letter_ids = journals

    exchange_rate = fields.Float(
        string='Tipo de cambio',
        tracking=True,
        compute='_compute_tipo_cambio_usd',
        digits=(12, 4), store=True,
    )
    invoice_date = fields.Date(
        string='Fecha canje',
        tracking=True,
    )
    payment_reference = fields.Char(
        string='Referencia',
        index='trigram',
        tracking=True,
    )
    glosa = fields.Char(
        string='Glosa',
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('checked', 'Comprobado'),
            ('redeemed', 'Canjeado'),
            ('banked', 'Bancarizado'),
            ('cancel', 'Cancelado'),
        ],
        string='Estado',
        default='draft',
        required=True, readonly=True, tracking=True,
    )
    invoice_line_ids = fields.One2many(
        'l10n_pe.letter.invoice.line',
        'letter_id',
        string='Facturas',
    )
    letter_line_ids = fields.One2many(
        'l10n_pe.letter.line',
        'letter_id',
        string='Letra',
    )
    letter_residual_ids = fields.One2many(
        'l10n_pe.letter.residual',
        'letter_id',
        string='Redondeo',
    )
    account_move_line_ids = fields.Many2many(
        'account.move.line',
        string='Apunte contable',
    )
    account_id = fields.Many2one(
        'account.move',
        string='Asiento contable',
        readonly=True,
        ondelete='set null'
    )

    # Campo para calcular las letras
    number_letter = fields.Integer(
        string='Cantidad de letras',
        tracking=True,
    )
    letter_end_date = fields.Date(
        string='Fecha de venc. letra',
        tracking=True,
    )
    range_date = fields.Integer(
        string='Rango de días',
        tracking=True,
        default=1,
    )
    type_payment = fields.Selection(
        selection=[
            ('partial', 'Parcial'),
            ('total', 'Total'),
        ],
        string='Pago', default='total',
        tracking=True,
    )
    partial_amount = fields.Monetary(
        string='Importe parcial',
        currency_field='currency_id',
    )
    rest_amount = fields.Monetary(
        string='Monto restante',
        currency_field='company_currency_id',
        compute='_compute_rest_amount',
    )
    rest_amount_currency = fields.Monetary(
        string='Monto restante en moneda',
        currency_field='currency_id',
        compute='_compute_rest_amount',
    )
    rest_amount_adeudado = fields.Monetary(
        string='Monto adeudado',
        currency_field='currency_id',
    )
    # Campos extras
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
    )
    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Moneda de la compañía', store=True
    )
    currency_id = fields.Many2one(
        'res.currency', string='Moneda',
        tracking=True,
        related='journal_id.currency_id',
    )

    @api.depends('invoice_line_ids', 'letter_line_ids', 'letter_residual_ids',
                 'exchange_rate', 'rest_amount_adeudado', 'is_refinance_children')
    def _compute_rest_amount(self):
        """
        Calcula el monto restante considerando:
        - Líneas de factura (débitos/créditos)
        - Líneas de carta (débitos/créditos)
        - Residuales (si existen)
        - Tipo de cambio para valor en moneda
        - Caso especial para refinanciamiento
        """
        for record in self:
            try:
                # Inicializar variables
                invoice_total = 0.0
                letter_total = 0.0
                residual_amount = 0.0
                exchange_rate = record.exchange_rate or 1.0

                # 1. Calcular totales de factura
                if record.invoice_line_ids:
                    invoice_total = sum(line.debit + line.credit for line in record.invoice_line_ids)

                    refinance_invoice_total = sum(
                        line.debit + line.credit
                        for line in record.invoice_line_ids
                        if line.document_type_id.code == '99'
                    )
                else:
                    refinance_invoice_total = 0.0

                # 2. Calcular totales de carta
                if record.letter_line_ids:
                    letter_total = sum(line.debit + line.credit for line in record.letter_line_ids)

                # 3. Calcular residuales
                if record.letter_residual_ids:
                    residual_amount = record.letter_residual_ids.amount

                # 4. Calcular diferencia base
                if record.is_refinance_children:
                    base_amount = (
                        (record.rest_amount_adeudado or 0.0) * exchange_rate
                        + (invoice_total - refinance_invoice_total)
                    )
                    diference = base_amount - letter_total
                else:
                    diference = invoice_total - letter_total

                # 5. Ajustar por residuales
                diference += residual_amount

                # 6. Asignar valores finales
                record.rest_amount = diference
                if exchange_rate != 0:
                    record.rest_amount_currency = diference / exchange_rate
                else:
                    record.rest_amount_currency = 0.0

            except Exception as e:
                _logger.error("Error computing rest amount: %s", str(e))
                record.rest_amount = 0.0
                record.rest_amount_currency = 0.0

    # Método para autogeneracion de letras
    def create_letters(self):
        if not self.number_letter:
            raise UserError('Necesitas añadir la cantidad de letras.')
        if not self.letter_end_date:
            raise UserError('Necesitas añadir la fecha de vencimiento.')
        if not self.range_date:
            raise UserError('Necesitas añadir el rango de días.')
        if self.number_letter > 0:
            letter_imp_div = self.calculate_letter_imp_div()
            if letter_imp_div > 0:
                # Calculo de la fecha de vencimiento de la primera letra
                if self.letter_line_ids and self.range_date:
                    expiration_date = self.letter_line_ids[-1].expiration_date + timedelta(days=self.range_date)
                elif self.letter_end_date and self.range_date:
                    expiration_date = self.letter_end_date
                for i in range(self.number_letter):
                    self.letter_line_ids = [(0, 0, {
                        'currency_id': self.currency_id.id,
                        'expiration_date': expiration_date,
                        'imp_div': letter_imp_div,
                        'adeudado': letter_imp_div,
                        'letter_id': self.id,
                    })]
                    expiration_date += timedelta(days=self.range_date)

    # Método para calcular el importe de la letra
    def calculate_letter_imp_div(self):
        letter_imp_div = 0.0
        if self.type_payment == 'total':
            letter_imp_div = self.rest_amount_currency / self.number_letter
        elif self.type_payment == 'partial':
            if self.partial_amount > 0 and self.partial_amount <= self.rest_amount_currency:
                letter_imp_div = self.partial_amount / self.number_letter
        return letter_imp_div

    # Método para botón borrador
    def action_draft(self):
        if self.account_id:
            if self.account_id.state == 'posted':
                self.account_id.button_draft()
        if self.canje_move_id:
            self.canje_move_id.button_cancel()
            self.canje_move_id = False
        if self.canje_move_ids:
            for move in self.canje_move_ids:
                move.button_cancel()
            self.canje_move_ids = [(6, 0, [])]
        for line in self.invoice_line_ids:
            letter_id = False
            redeemed_state = 'not_redeemed'
            old_ids = line.move_line_id.move_id.l10n_pe_letter_ids.ids
            if self.id in old_ids:
                old_ids.remove(self.id)
            letter_ids = [(6, 0, old_ids)]
            if line.move_line_id.move_id.move_type != 'entry':
                letter_id = False
                redeemed_state = 'not_redeemed'
                letter_ids = [(6, 0, [])]
            line.move_id.write({
                'l10n_pe_letter_redeemed_state': redeemed_state,
                'l10n_pe_letter_id': letter_id,
                'l10n_pe_letter_ids': letter_ids,
            })
        if self.letter_residual_ids:
            self.letter_residual_ids.unlink()
        if self.is_refinance_parent:
            self.is_refinance_parent = False
            self.refinance_id.unlink()
        self.name = f"{'Borrador'}*{self.id}"
        self.state = 'draft'

    # Método para botón de confirmar
    confirmed_reference = fields.Char(
        string='Referencia de nombre',
    )

    def action_checked(self):
        if not self.invoice_line_ids:
            raise UserError('Necesitas añadir documentos antes de validar.')
        if not self.invoice_date:
            raise UserError('Necesitas añadir la fecha de canje.')
        if not self.confirmed_reference:
            self.confirmed_reference = self.name
        else:
            self.name = self.confirmed_reference
        self.state = 'checked'

    def action_cancel(self):
        for letter in self:
            # Si la letra es un refinanciamiento (hijo), limpiar las referencias
            # hacia los canjes de origen para permitir un nuevo refinanciamiento.
            if letter.is_refinance_children:
                origins = letter._get_refinance_origins()
                if origins:
                    origins.write({
                        'is_refinance_parent': False,
                        'refinance_id': False,
                    })

                # Eliminar los apuntes de l10n_pe.letter.invoice.line asociados al hijo
                # y limpiar los enlaces con apuntes contables.
                if letter.invoice_line_ids:
                    letter.invoice_line_ids._clear_move_line_links()
                    letter.invoice_line_ids.unlink()

                # Si el canje refinanciado ya había generado asiento contable,
                # cancelarlo y borrar el vínculo para evitar residuos contables.
                if letter.account_id:
                    account_move = letter.account_id
                    if account_move.state == 'posted':
                        account_move.button_draft()
                    account_move.button_cancel()
                    letter.account_id = False
                    letter.account_move_line_ids = [(6, 0, [])]

                # Eliminar las letras creadas por el refinanciamiento para que el
                # canje padre pueda generarlas nuevamente en un nuevo proceso.
                if letter.letter_line_ids:
                    letter.letter_line_ids.unlink()

                letter.write({
                    'refinance_origin_ids': [(6, 0, [])],
                    'inverse_id': False,
                    'is_refinance_children': False,
                })

            # Si la letra tiene un refinanciamiento hijo vinculado, eliminar la relación
            # para que pueda ser refinanciada nuevamente.
            if letter.is_refinance_parent and letter.refinance_id:
                letter.refinance_id.write({
                    'refinance_origin_ids': [(6, 0, [])],
                    'inverse_id': False,
                    'is_refinance_children': False,
                })
                letter.refinance_id = False
                letter.is_refinance_parent = False
        self.state = 'cancel'

    def action_open_account_move(self):
        self.ensure_one()
        return {
            'name': 'Asiento contable',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.account_id.id,
        }

    def _build_letter_move_line_vals(self, name, account_id, partner_id, amount_currency,
                                      currency_id, date_maturity=False, exchange_rate=1.0, **extra):
        """Construye un dict listo para ``account.move.line`` (create/(0,0,...)).

        Centraliza el cómputo de debe/haber en moneda de la compañía, repetido
        de forma casi idéntica en ``action_redeemed``, ``action_canje_create``
        y ``action_redeemed_refinance``.
        """
        self.ensure_one()
        vals = {
            'name': name,
            'account_id': account_id,
            'partner_id': partner_id,
            'amount_currency': amount_currency,
            'currency_id': currency_id,
            'date_maturity': date_maturity,
        }
        vals.update(extra)
        if currency_id != self.company_id.currency_id.id:
            debit_credit = amount_currency * exchange_rate
            vals['debit'] = debit_credit if debit_credit > 0 else 0.0
            vals['credit'] = -debit_credit if debit_credit < 0 else 0.0
        return vals

    # Método para botón de canjear
    def action_redeemed(self):
        self.ensure_one()
        if not self.letter_line_ids:
            raise UserError('Necesitas añadir letras antes de canjear.')
        self.state = 'redeemed'
        if any(not letter.nro_letter for letter in self.letter_line_ids):
            raise UserError('Se necesita ingresar el número de letra de referencia.')
        if self.is_refinance_children:
            self.action_redeemed_refinance()
        else:
            account_move_lines = []
            # Apunte contable del comprobante
            for invoice_line in self.invoice_line_ids:
                amount_currency = invoice_line.imp_div * (-1 if invoice_line.move_invoice_type == 'out_invoice' else 1)
                account_move_lines.append(self._build_letter_move_line_vals(
                    invoice_line.invoice_name,
                    invoice_line.account_id.id,
                    invoice_line.move_line_id.partner_id.id,
                    amount_currency,
                    invoice_line.currency_id.id,
                    date_maturity=invoice_line.move_line_id.date_maturity,
                    exchange_rate=self.exchange_rate,
                ))

            # Apunte contable de las letras
            for letter_line in self.letter_line_ids:
                amount_currency = letter_line.imp_div * (1 if letter_line.move_invoice_type == 'out_invoice' else -1)
                account_move_lines.append(self._build_letter_move_line_vals(
                    letter_line.nro_letter,
                    letter_line.account_id.id,
                    letter_line.partner_id.id,
                    amount_currency,
                    letter_line.currency_id.id,
                    date_maturity=letter_line.expiration_date,
                    exchange_rate=self.exchange_rate,
                    l10n_pe_letter_line_id=letter_line.id,
                ))

            # Apunte contable del redondeo
            letter_residual = self.create_residual()
            if letter_residual:
                account_move_lines.append({
                    'name': 'Redondeo',
                    'account_id': letter_residual.account_id.id,
                    'partner_id': self.partner_id.id,
                    'balance': letter_residual.amount,
                })
            move_line_commands = [(0, 0, line.copy()) for line in account_move_lines]
            update_line_commands = [(5, 0, 0)] + [(0, 0, line.copy()) for line in account_move_lines]

            move_vals = {
                'ref': self.name,
                'date': self.invoice_date,
                'journal_id': self.journal_id.id,
                'partner_id': self.partner_id.id,
                'line_ids': move_line_commands,
            }

            if self.account_id:
                account_move = self.account_id
                if account_move.state == 'posted':
                    account_move.button_draft()
                account_move.write({
                    'ref': self.name,
                    'date': self.invoice_date,
                    'journal_id': self.journal_id.id,
                    'partner_id': self.partner_id.id,
                    'line_ids': update_line_commands,
                })
            else:
                account_move = self.env['account.move'].create(move_vals)

            account_move.action_post()
            self.account_id = account_move.id
            self.account_move_line(account_move)
            self.action_reconcile_related_invoices(account_move)

            for invoice_line in self.invoice_line_ids:
                invoice_move = invoice_line.move_line_id.move_id
                payment_term_lines = invoice_move.line_ids.filtered(lambda l: l.display_type == 'payment_term')
                residual = sum(payment_term_lines.mapped('amount_residual_currency'))
                is_zero = float_is_zero(
                    residual,
                    precision_rounding=invoice_move.currency_id.rounding if invoice_move.currency_id else 0.01
                )
                redeemed_state = 'redeemed' if is_zero else 'not_redeemed'

                if invoice_move.move_type != 'entry':
                    values = {'l10n_pe_letter_redeemed_state': redeemed_state}
                    if redeemed_state == 'redeemed':
                        values.update({'l10n_pe_letter_id': self.id, 'l10n_pe_letter_ids': [(6, 0, [])]})
                    else:
                        values.update({
                            'l10n_pe_letter_ids': [(6, 0, list(set(self.ids + invoice_move.l10n_pe_letter_ids.ids)))],
                            'l10n_pe_letter_id': False
                        })
                    invoice_move.write(values)
                else:
                    invoice_move.write({'l10n_pe_letter_redeemed_state': redeemed_state})

    canje_move_id = fields.Many2one('account.move', string='Asiento de canje', readonly=True)
    canje_move_ids = fields.Many2many('account.move', 'account_letter_move_canje_rel', 'letter_id', 'move_id',
                                      string='Asientos de canje', readonly=True)

    def action_canje(self):
        date_canje = fields.Date.context_today(self)
        show_canje_type = False
        letter_line_ids = self.letter_line_ids.filtered(lambda line: line.payment_state == 'pending')
        canje_type = 'all'
        if len(letter_line_ids) > 1:
            show_canje_type = True
        if self.canje_move_ids:
            canje_type = 'one'
        return {
            'name': 'Canje',
            'view_mode': 'form',
            'res_model': 'l10n_pe.letter.canje.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'default_letter_id': self.id,
                'default_date_canje': date_canje,
                'default_show_canje_type': show_canje_type,
                'default_canje_type': canje_type,
            }
        }

    def action_canje_create(self, letter_type, letter_date, letter_line_id=False):
        self.ensure_one()
        account_move_lines = []
        company_currency = self.company_id.currency_id
        exchange_rate = 1
        letter_line_ids = self.letter_line_ids
        if letter_line_id:
            letter_line_ids = letter_line_id
        if self.currency_id != company_currency:
            exchange_rate = self.currency_id._convert(1, company_currency, self.company_id, letter_date, round=False)
        for letter_line in letter_line_ids:
            amount_currency = letter_line.imp_div * (1 if letter_line.move_invoice_type == 'out_invoice' else -1)
            amount_currency = amount_currency * -1
            account_move_lines.append(self._build_letter_move_line_vals(
                letter_line.nro_letter,
                letter_line.account_id.id,
                letter_line.partner_id.id,
                amount_currency,
                letter_line.currency_id.id,
                exchange_rate=exchange_rate,
                l10n_pe_letter_line_id=letter_line.id,
            ))
        if self.type == 'in_invoice':
            account_type = 'liability_payable'
        elif self.type == 'out_invoice':
            account_type = 'asset_receivable'
        else:
            return
        invoice_account = self.env['l10n_pe.letter.account.config'].search([
            ('account_type', '=', account_type),
            ('document_type', '=', 'letter'),
            ('letter_type', '=', letter_type),
            ('currency_id', '=', self.currency_id.id)
        ], limit=1)
        # Cuenta por defecto en Portafolio
        if invoice_account:
            account_id = invoice_account.account_id.id
        else:
            raise UserError('No se ha configurado la cuenta contable para el tipo de letra seleccionado.')

        for letter_line in letter_line_ids:
            amount_currency = letter_line.imp_div * (1 if letter_line.move_invoice_type == 'out_invoice' else -1)
            account_move_lines.append(self._build_letter_move_line_vals(
                letter_line.nro_letter,
                account_id,
                letter_line.partner_id.id,
                amount_currency,
                letter_line.currency_id.id,
                exchange_rate=exchange_rate,
            ))
        name = self.name
        if letter_line_id:
            name = f'{self.name} - {letter_line_id.nro_letter}'
        if letter_type == 'discount':
            ref = 'Letra en descuento ' + name
        elif letter_type == 'billing':
            ref = 'Cobranza libre ' + name
        else:
            raise UserError('No se ha encontrado el tipo de letra seleccionado.')
        account_move = self.env['account.move'].create({
            'ref': ref,
            'date': self.invoice_date,
            'journal_id': self.journal_id.id,
            'partner_id': self.partner_id.id,
            'line_ids': [(0, 0, line) for line in account_move_lines],
        })
        account_move.action_post()
        if letter_line_id:
            self.canje_move_ids = [(4, account_move.id)]
        else:
            self.canje_move_id = account_move.id

        for line in account_move.line_ids.filtered(lambda line: line.l10n_pe_letter_line_id):
            letter_line_id_rec = line.l10n_pe_letter_line_id
            counter_line = self.account_id.line_ids.filtered(
                lambda line: line.l10n_pe_letter_line_id == letter_line_id_rec)
            if not counter_line:
                raise UserError('No se ha encontrado el apunte contable relacionado a conciliar.')
            (line + counter_line).reconcile()

    # Método para conciliar las facturas relacionadas
    def action_reconcile_related_invoices(self, move_id):
        debit_lines = []
        credit_lines = []
        for move_line in move_id.line_ids:
            if self.type == 'out_invoice':
                debit_lines.extend(move_line.filtered(lambda line: line.account_id.account_type in ['asset_receivable',
                                                                                                    'liability_payable'] and line.amount_currency < 0.0))
            else:
                debit_lines.extend(move_line.filtered(lambda line: line.account_id.account_type in ['asset_receivable',
                                                                                                    'liability_payable'] and line.amount_currency > 0.0))
        if self.is_refinance_children:
            # Conciliar las facturas adicionales contra sus comprobantes originales
            extra_invoices = self.invoice_line_ids.filtered(
                lambda l: l.document_type_id.code != '99' and l.move_line_id and not l.move_line_id.reconciled)
            for invoice in extra_invoices:
                new_line = move_id.line_ids.filtered(
                    lambda ml: ml.l10n_pe_letter_invoice_line_id == invoice.id and not ml.reconciled)

                # Si la relación directa no existe (p.ej. líneas añadidas manualmente),
                # buscar una línea compatible por cuenta/partner para forzar la conciliación.
                if not new_line:
                    new_line = move_id.line_ids.filtered(
                        lambda ml: ml.account_id == invoice.account_id
                        and ml.partner_id == invoice.partner_id
                        and not ml.reconciled)

                if new_line:
                    (new_line + invoice.move_line_id).reconcile()

            origins = self._get_refinance_origins()
            for origin in origins:
                if not origin.account_id:
                    continue
                for letter in origin.letter_line_ids:
                    original_line = origin.account_id.line_ids.filtered(
                        lambda ml: ml.l10n_pe_letter_line_id == letter and not ml.reconciled)
                    closing_line = move_id.line_ids.filtered(
                        lambda ml: ml.l10n_pe_letter_line_id == letter and not ml.reconciled)
                    if original_line and closing_line:
                        (original_line + closing_line).reconcile()
            return
        else:
            for invoice_line in self.invoice_line_ids.move_line_id:
                credit_lines.extend(invoice_line)
            for debit_line, credit_line in zip(debit_lines, credit_lines):
                (debit_line + credit_line).reconcile()

    # Método para el estado de bancarizar
    @api.onchange('letter_line_ids')
    def _compute_is_banked(self):
        if self.state in ['redeemed', 'banked']:
            for record in self:
                has_banked = any(letter.bank_id for letter in record.letter_line_ids)
                has_code = any(letter.code for letter in record.letter_line_ids)
                has_letter_type = any(letter.letter_type for letter in record.letter_line_ids)
                if has_banked and has_code and has_letter_type:
                    record.state = 'banked'
                else:
                    record.state = 'redeemed'

    # Canje Masivo
    is_massive_letter = fields.Boolean(
        string='Canje masivo'
    )

    # Método para botón de canje masivo
    def action_multi_redeemed(self, letter_type):
        selected_invoices = self.env['l10n_pe.letter'].browse(self.env.context.get('active_ids', []))
        if len(selected_invoices) < 2:
            raise UserError('Necesitas seleccionar al menos dos canjes para continuar.')
        partner_ids = set(invoice.partner_id.id for invoice in selected_invoices)
        if len(partner_ids) > 1:
            raise UserError('Las facturas seleccionadas no pertenecen al mismo socio.')
        # extrae el partner_id de la ultima factura seleccionada
        partner_id = selected_invoices[-1].partner_id
        journal_id = selected_invoices[-1].journal_id
        type = selected_invoices[-1].type
        for letter in selected_invoices:
            if letter.state not in ['redeemed', 'banked']:
                raise UserError(f'La letra {letter.name} no está canjeada.')
            letter.is_massive_letter = True
            # Modificar el tipo de letra
            if letter.letter_line_ids:
                letter.letter_line_ids.write({
                    'letter_type': letter_type,
                })

        # Crear un nuevo registro en l10n_pe.letter.massive
        massive_letter = self.env['l10n_pe.letter.massive'].create({
            'partner_id': partner_id.id,
            'journal_id': journal_id.id,
            'type': type,
            'state': 'redeemed',
            'is_massive_letter': True,
        })
        # Obtener los registros de las facturas seleccionadas
        invoice_lines = selected_invoices.mapped('invoice_line_ids')
        # Obtener los registros de las letras seleccionadas
        letter_lines = selected_invoices.mapped('letter_line_ids')
        # Agregar los registros de invoice_line_ids a letter_invoices_ids en la carta masiva
        massive_letter.write({
            'letter_invoices_ids': [(6, 0, invoice_lines.ids)],
            'letter_move_ids': [(6, 0, letter_lines.ids)],
        })
        return massive_letter

    def action_link_account_move_by_ref(self):
        invalid_state = self.filtered(lambda letter: letter.state != 'redeemed')
        if invalid_state:
            raise UserError('Solo se puede vincular asientos para canjes en estado "Canjeado".')

        pending_letters = self.filtered(lambda letter: not letter.account_id)

        if not pending_letters:
            raise UserError('Todos los canjes seleccionados ya tienen un asiento contable vinculado.')

        not_found = []
        duplicates = []
        already_linked = []
        linked = []

        for letter in self:
            if letter.account_id:
                already_linked.append(letter.name)
                continue

            domain = [
                ('ref', '=', letter.name),
                ('company_id', '=', letter.company_id.id),
                ('state', '!=', 'cancel'),
            ]
            moves = self.env['account.move'].search(domain)

            if not moves:
                not_found.append(letter.name)
                continue

            if len(moves) > 1:
                duplicates.append(letter.name)
                continue

            letter.account_id = moves.id
            linked.append(letter.name)

        message_parts = [
            'Registros procesados: %s' % len(self),
        ]
        if linked:
            message_parts.append('Vinculados (%s): %s' % (len(linked), ', '.join(linked)))
        if already_linked:
            message_parts.append('Ya tenían asiento (%s): %s' % (len(already_linked), ', '.join(already_linked)))
        if not_found:
            message_parts.append('Sin coincidencias (%s): %s' % (len(not_found), ', '.join(not_found)))
        if duplicates:
            message_parts.append('Múltiples asientos (%s): %s' % (len(duplicates), ', '.join(duplicates)))

        summary_action = None
        if message_parts:
            message = '\n'.join(message_parts)
            if not_found or duplicates:
                self._notify_link_account_move(message, notification_type='warning')
            else:
                self._notify_link_account_move(message, notification_type='success')

            summary_wizard = self.env['l10n_pe.letter.link.summary'].create({
                'summary': message,
            })
            summary_action = {
                'type': 'ir.actions.act_window',
                'name': 'Resumen de vinculación',
                'res_model': 'l10n_pe.letter.link.summary',
                'view_mode': 'form',
                'target': 'new',
                'res_id': summary_wizard.id,
                'context': {
                    'reload_on_close': True,
                },
            }

        unresolved_letters = pending_letters.filtered(lambda l: l.name in not_found or l.name in duplicates)
        if unresolved_letters and not linked:
            detail = []
            if not_found:
                detail.append('Sin coincidencias por referencia: %s' % ', '.join(not_found))
            if duplicates:
                detail.append('Múltiples asientos encontrados: %s' % ', '.join(duplicates))
            raise UserError('No se pudo vincular ningún asiento.\n%s' % '\n'.join(detail))

        if summary_action:
            return summary_action

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def _notify_link_account_move(self, message, notification_type='success'):
        """Send a user notification compatible with environments lacking notify helpers."""

        notify_method = getattr(self.env.user, f'notify_{notification_type}', None)
        if callable(notify_method):
            notify_method(message=message, title='Vinculación de asientos')
            return

        partner = self.env.user.partner_id
        if partner:
            self.env['bus.bus']._sendone(partner, 'simple_notification', {
                'title': 'Vinculación de asientos',
                'message': message,
                'type': notification_type,
                'sticky': False,
            })

    # Método para el cálculo del nombre de la letra
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'type' in vals:
                if vals['type'] == 'out_invoice':
                    prefix = 'CLC'
                else:
                    prefix = 'CLP'
                sequence = self.env['ir.sequence'].next_by_code('l10n_pe.letter')
                vals['name'] = f'{prefix}{sequence}' if sequence else f"{prefix}{vals.get('id', '')}"

        return super().create(vals_list)

    def copy_data(self, default=None):
        default = dict(default or {})
        default.setdefault('confirmed_reference', False)
        return super().copy_data(default)

    # Método para el tipo de cambio (compra/venta SUNAT vía al_l10n_pe_currency)
    @api.depends('currency_id', 'invoice_date')
    def _compute_tipo_cambio_usd(self):
        """Obtiene el tipo de cambio publicado (PEN por unidad de divisa) para la
        fecha del canje usando compra/venta SUNAT (``al_l10n_pe_currency``).

        - Canje de cliente (out_invoice): usa la tasa de compra.
        - Canje de proveedor (in_invoice): usa la tasa de venta.
        Si no hay tasa para esa fecha, cae al rate estándar de Odoo.
        """
        for record in self:
            rate = 1.0
            currency = record.currency_id
            company = record.company_id or self.env.company
            if currency and currency != company.currency_id:
                rate_date = record.invoice_date or fields.Date.context_today(record)
                field = 'rate_purchase' if record.type == 'out_invoice' else 'rate_sale'
                rate_rec = self.env['res.currency.rate'].sudo().search([
                    ('currency_id', '=', currency.id),
                    ('company_id', '=', company.root_id.id),
                    ('name', '<=', rate_date),
                ], order='name desc', limit=1)
                pe_rate = rate_rec[field] if rate_rec else 0.0
                if pe_rate:
                    rate = pe_rate
                else:
                    # Fallback al tipo de cambio estándar de Odoo (compañía por divisa)
                    rate = currency._convert(1.0, company.currency_id, company, rate_date, round=False)
            record.exchange_rate = rate or 1.0

    def delete_all_invoices(self):
        invoices_to_delete = self.env['l10n_pe.letter.invoice.line'].search([])
        invoices_to_delete.unlink()

    def delete_all_residual(self):
        residual_to_delete = self.env['l10n_pe.letter.residual'].search([])
        residual_to_delete.unlink()

    # Método para evitar la eliminación de registros en estado canjeado y bancarizado
    def unlink(self):
        # Verificar si el contexto permite forzar la eliminación
        force_unlink = self.env.context.get('force_unlink', False)

        for letter in self:
            # Validación solo si no se forzó el unlink
            if not force_unlink:
                raise UserError('No se puede eliminar la letra manualmente. Contacte al administrador.')
            # Limpiar relaciones de refinanciamiento si existen
            if letter.is_refinance_children:
                origins = letter.refinance_origin_ids
                if not origins and letter.inverse_id:
                    origins = letter.inverse_id
                if origins:
                    origins.write({
                        'is_refinance_parent': False,
                        'refinance_id': False,
                    })
            if letter.is_refinance_parent and letter.refinance_id:
                letter.refinance_id.action_draft()
                letter.refinance_id.with_context(force_unlink=True).unlink()

        return super().unlink()

    # Refinanciamiento
    refinance_id = fields.Many2one(
        'l10n_pe.letter',
        string='Canje refinanciado',
    )
    inverse_id = fields.Many2one(
        'l10n_pe.letter',
        string='Canje relacionado',
    )

    refinance_origin_ids = fields.Many2many(
        'l10n_pe.letter',
        'account_letter_refinance_origin_rel',
        'child_letter_id',
        'origin_letter_id',
        string='Canjes de origen',
        copy=False,
        readonly=True,
    )
    refinance_origin_display = fields.Char(
        string='Canjes relacionados',
        compute='_compute_refinance_origin_display',
        store=False,
    )

    is_refinance_children = fields.Boolean(
        string='Es refinanciado',
        default=False,
    )
    is_refinance_parent = fields.Boolean(
        string='Es refinanciador',
        default=False,
    )

    @api.onchange('refinance_id')
    def _onchange_refinance_id(self):
        if not self.refinance_id:
            self.is_refinance_parent = False

    def _prepare_refinance_invoice_lines(self):
        """Builds the duplicated invoice lines for refinancing purposes."""
        self.ensure_one()

        letter_move_map = {}
        if self.account_id:
            for move_line in self.account_id.line_ids:
                if move_line.l10n_pe_letter_line_id:
                    letter_move_map[move_line.l10n_pe_letter_line_id.id] = move_line

        refinance_doc_type = self.env.ref('al_l10n_pe_account_letter.document_type_letter_99')
        duplicated_invoice_lines = []
        total_adeudado = 0.0
        precision = (
            self.currency_id.rounding
            or self.company_currency_id.rounding
            or self.env.company.currency_id.rounding
            or 0.01
        )

        for letter_line in self.letter_line_ids:
            move_line = letter_move_map.get(letter_line.id)
            base_amount = abs(
                letter_line.adeudado
                or (move_line.amount_residual_currency if move_line else 0.0)
                or letter_line.imp_div
                or 0.0
            )
            if float_is_zero(base_amount, precision_rounding=precision):
                continue

            total_adeudado += base_amount
            line_vals = {
                'document_type_id': refinance_doc_type.id,
                'imp_div': base_amount,
                'refinance_base_amount': base_amount,
                'move_line_id': move_line.id if move_line else False,
                'account_id': move_line.account_id.id if move_line else letter_line.account_id.id,
            }
            duplicated_invoice_lines.append((0, 0, line_vals))

        return total_adeudado, duplicated_invoice_lines

    def create_refinance(self, letter_id, refinance_date):
        letter_record = self.browse(letter_id.id)
        total_adeudado, duplicated_invoice_lines = letter_record._prepare_refinance_invoice_lines()
        letter_values = {
            'partner_id': letter_record.partner_id.id,
            'type': letter_record.type,
            'journal_id': letter_record.journal_id.id,
            'invoice_date': refinance_date,
            'glosa': letter_record.glosa,
            'payment_reference': letter_record.payment_reference,
            'state': 'draft',
            'is_refinance_children': True,
            'inverse_id': letter_record.id,
            'refinance_origin_ids': [(6, 0, [letter_record.id])],
            'rest_amount_adeudado': total_adeudado,
            'rest_amount_currency': total_adeudado,
            'invoice_line_ids': duplicated_invoice_lines,
        }

        new_letter = letter_record.create(letter_values)
        for invoice_line in new_letter.invoice_line_ids.filtered('move_line_id'):
            invoice_line.move_line_id.with_context(check_move_validity=False).write({
                'l10n_pe_letter_invoice_line_id': invoice_line.id,
            })
        letter_record.is_refinance_parent = True
        letter_record.is_refinance_children = False
        letter_record.refinance_id = new_letter.id
        return new_letter

    def _get_refinance_origins(self):
        self.ensure_one()
        origins = self.refinance_origin_ids
        if not origins and self.inverse_id:
            origins = self.inverse_id
        return origins

    @api.depends('refinance_origin_ids', 'inverse_id', 'refinance_origin_ids.name', 'inverse_id.name')
    def _compute_refinance_origin_display(self):
        for letter in self:
            origins = letter.refinance_origin_ids
            if not origins and letter.inverse_id:
                origins = letter.inverse_id
            if not origins:
                letter.refinance_origin_display = False
                continue
            names = origins.mapped('name')
            letter.refinance_origin_display = ', '.join(filter(None, names)) or False

    def _validate_massive_refinance_selection(self):
        if not self:
            raise UserError('Seleccione al menos un canje para refinanciar.')

        if any(letter.type != 'out_invoice' for letter in self):
            raise UserError('Solo se pueden refinanciar canjes de clientes.')

        blocked_parents = self.filtered(lambda l: l.is_refinance_parent and not l.is_refinance_children)
        if blocked_parents:
            raise UserError('El canje %s ya tiene un refinanciamiento relacionado.' % blocked_parents[0].name)

        partners = {letter.partner_id.id for letter in self}
        if len(partners) != 1:
            raise UserError('Todos los canjes deben pertenecer al mismo socio.')

        journals = {letter.journal_id.id for letter in self}
        if len(journals) != 1:
            raise UserError('Todos los canjes deben usar el mismo diario.')

        company_ids = {letter.company_id.id for letter in self}
        if len(company_ids) != 1:
            raise UserError('Todos los canjes deben pertenecer a la misma compañía.')

        currencies = {letter.currency_id.id for letter in self if letter.currency_id}
        if len(currencies) > 1:
            raise UserError('Todos los canjes deben tener la misma moneda.')

    @api.model
    def create_massive_refinance(self, letters, refinance_date):
        if not letters:
            raise UserError('Debe seleccionar al menos un canje para refinanciar.')

        letters._validate_massive_refinance_selection()

        total_amount = 0.0
        duplicated_invoice_lines = []
        for letter in letters:
            subtotal, line_commands = letter._prepare_refinance_invoice_lines()
            if not line_commands:
                raise UserError('El canje %s no tiene letras pendientes para refinanciar.' % letter.name)
            total_amount += subtotal
            duplicated_invoice_lines.extend(line_commands)

        template_letter = letters[0]
        inverse_id = letters[0].id if len(letters) == 1 else False

        letter_values = {
            'partner_id': template_letter.partner_id.id,
            'type': template_letter.type,
            'journal_id': template_letter.journal_id.id,
            'company_id': template_letter.company_id.id,
            'invoice_date': refinance_date,
            'glosa': template_letter.glosa,
            'payment_reference': template_letter.payment_reference,
            'state': 'draft',
            'is_refinance_children': True,
            'inverse_id': inverse_id,
            'refinance_origin_ids': [(6, 0, letters.ids)],
            'rest_amount_adeudado': total_amount,
            'rest_amount_currency': total_amount,
            'invoice_line_ids': duplicated_invoice_lines,
        }
        new_letter = self.create(letter_values)

        for invoice_line in new_letter.invoice_line_ids.filtered('move_line_id'):
            invoice_line.move_line_id.with_context(check_move_validity=False).write({
                'l10n_pe_letter_invoice_line_id': invoice_line.id,
            })

        letters.write({
            'is_refinance_parent': True,
            'is_refinance_children': False,
            'refinance_id': new_letter.id,
        })

        return new_letter

    def action_open_massive_refinance_wizard(self):
        self._validate_massive_refinance_selection()

        action = self.env.ref(
            'al_l10n_pe_account_letter.account_massive_refinance_wizard_action'
        ).sudo().read()[0]
        action['context'] = {
            'default_refinance_date': fields.Date.context_today(self),
            'active_model': 'l10n_pe.letter',
            'active_ids': self.ids,
        }
        return action

    # Método para el canje de refinanciamiento
    def action_redeemed_refinance(self):
        self.ensure_one()

        account_move_lines = []
        exchange_rate = self.exchange_rate or 1.0
        # Ensure journal entries from previous canjes no longer point to invoice lines
        # that will be reused during this refinancing.
        invoice_lines_to_clear = self.invoice_line_ids
        origins = self._get_refinance_origins()
        if origins:
            invoice_lines_to_clear |= origins.mapped('invoice_line_ids')
        invoice_lines_to_clear._clear_move_line_links()

        # Añade las facturas asociadas al refinanciamiento (excepto la letra duplicada)
        refinance_invoices = self.invoice_line_ids.filtered(lambda l: l.document_type_id.code != '99')
        for invoice_line in refinance_invoices:
            residual_currency = invoice_line.imp_div
            if invoice_line.move_line_id:
                residual_currency = abs(invoice_line.move_line_id.amount_residual_currency)

            amount_currency = residual_currency * (-1 if invoice_line.move_invoice_type == 'out_invoice' else 1)
            partner = invoice_line.move_line_id.partner_id if invoice_line.move_line_id else self.partner_id
            maturity = invoice_line.move_line_id.date_maturity if invoice_line.move_line_id else self.invoice_date
            account_move_lines.append(self._build_letter_move_line_vals(
                invoice_line.invoice_name,
                invoice_line.account_id.id,
                partner.id,
                amount_currency,
                invoice_line.currency_id.id,
                date_maturity=maturity,
                exchange_rate=exchange_rate,
                l10n_pe_letter_invoice_line_id=invoice_line.id,
            ))

        # Añade las letras refinanciadas
        for invoice_line in self.letter_line_ids:
            amount_currency = invoice_line.imp_div * (1 if invoice_line.move_invoice_type == 'out_invoice' else -1)
            account_move_lines.append(self._build_letter_move_line_vals(
                invoice_line.nro_letter,
                invoice_line.account_id.id,
                invoice_line.partner_id.id,
                amount_currency,
                invoice_line.currency_id.id,
                date_maturity=invoice_line.expiration_date,
                exchange_rate=exchange_rate,
                l10n_pe_letter_line_id=invoice_line.id,
            ))
        # Añade los apunte de las letras anteriores
        for origin_letter in origins:
            for invoice_line in origin_letter.letter_line_ids:
                amount_currency = invoice_line.adeudado * (-1 if invoice_line.move_invoice_type == 'out_invoice' else 1)
                account_move_lines.append(self._build_letter_move_line_vals(
                    invoice_line.nro_letter,
                    invoice_line.account_id.id,
                    invoice_line.partner_id.id,
                    amount_currency,
                    invoice_line.currency_id.id,
                    date_maturity=invoice_line.expiration_date,
                    exchange_rate=exchange_rate,
                    l10n_pe_letter_line_id=invoice_line.id,
                ))
        move_vals = {
            'ref': self.name,
            'journal_id': self.journal_id.id,
            'date': self.invoice_date,
            'partner_id': self.partner_id.id,
            'line_ids': [(0, 0, line) for line in account_move_lines],
        }
        account_move = self.env['account.move'].create(move_vals)
        account_move.action_post()
        self.account_id = account_move.id
        self.account_move_line(account_move)
        self.action_reconcile_related_invoices(account_move)

    # Método para el redondeo
    def create_residual(self):
        for record in self:
            reference = '-'.join(record.invoice_line_ids.mapped('invoice_name'))
        if self.rest_amount != 0.0 or self.rest_amount_currency != 0.0:
            self.letter_residual_ids.unlink()
            if self.type == 'out_invoice':
                amount = self.rest_amount
                amount_currency = self.rest_amount_currency
            else:
                amount = self.rest_amount * -1
                amount_currency = self.rest_amount_currency * -1
            letter_residual_ids = self.letter_residual_ids.create({
                'letter_id': self.id,
                'amount': amount,
                'amount_currency': amount_currency,
                'name': reference,
            })
            return letter_residual_ids
        else:
            self.letter_residual_ids.unlink()

    # Método para el apunte contable
    def account_move_line(self, account_move_line_ids):
        if account_move_line_ids:
            move_line_ids = []
            for record in account_move_line_ids.line_ids:
                move_line_ids.append(record.id)
            self.account_move_line_ids = [(6, 0, move_line_ids)]

    related_invoice_names = fields.Char(
        string='Facturas relacionadas',
        compute='_compute_related_invoice_names',
        store=True
    )

    @api.depends('invoice_line_ids.invoice_name')
    def _compute_related_invoice_names(self):
        for record in self:
            if record.invoice_line_ids:
                invoice_names = record.invoice_line_ids.mapped('invoice_name')
                record.related_invoice_names = '-'.join(invoice_names)

    # Método para el botón de abrir facturas relacionadas
    def action_open_related_invoices(self):
        self.ensure_one()
        invoices = self.mapped('invoice_line_ids.move_line_id.move_id')
        if self.type == 'out_invoice':
            action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        else:
            action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_in_invoice_type")
        if len(invoices) > 0:
            action['domain'] = [('id', 'in', invoices.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    related_invoice_count = fields.Integer(
        string='N.º de facturas relacionadas',
        compute='_compute_related_invoice_count',
        store=True
    )

    @api.depends('invoice_line_ids')
    def _compute_related_invoice_count(self):
        for record in self:
            record.related_invoice_count = len(record.invoice_line_ids)

    # Relacion con los pagos de las letras
    payment_ids = fields.Many2many(
        'account.payment',
        string='Pagos',
        compute='compute_payment_ids',
        store=True
    )

    @api.depends('account_id.line_ids.amount_residual_currency')
    def compute_payment_ids(self):
        total_adeudado = sum(line.adeudado for line in self.letter_line_ids)
        total_imp_div = sum(line.imp_div for line in self.invoice_line_ids)
        if total_adeudado == total_imp_div:
            self.payment_ids = False
            return
        if self.account_id:
            for record in self:
                name = record.account_id.name
                payments = self.env['account.payment'].search([('move_id.line_ids.name', '=', name)])
                if payments:
                    record.payment_ids = [(6, 0, payments.ids)]
                else:
                    record.payment_ids = False

    # Método para el botón de abrir pagos relacionados
    def action_open_related_payments(self):
        self.ensure_one()
        payments = self.mapped('payment_ids')
        if self.type == 'out_invoice':
            action = self.env["ir.actions.actions"]._for_xml_id("account.action_account_payments")
        else:
            action = self.env["ir.actions.actions"]._for_xml_id("account.action_account_payments_payable")
        if len(payments) > 0:
            action['domain'] = [('id', 'in', payments.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    related_payment_count = fields.Integer(
        string='Pagos relacionados',
        compute='_compute_related_payment_count',
        store=True
    )

    @api.depends('payment_ids')
    def _compute_related_payment_count(self):
        for record in self:
            record.related_payment_count = len(record.payment_ids)

    # Verificación si todas las letras estan pagadas
    is_all_paid = fields.Boolean(
        string='Todas las letras pagadas',
        compute='_compute_is_all_paid',
        store=True
    )

    @api.depends('account_id.line_ids.amount_residual_currency')
    def _compute_is_all_paid(self):
        for record in self:
            total_adeudado = sum(line.adeudado for line in record.letter_line_ids)
            if total_adeudado == 0.0:
                record.is_all_paid = True
            else:
                record.is_all_paid = False

    # ------------------------------------------ Validaciónes de fechas ------------------------------------------
    @api.constrains('invoice_date')
    def _check_invoice_date_not_future(self):
        """Valida que la fecha de canje no sea futura"""
        today = fields.Date.context_today(self)
        for record in self:
            if record.invoice_date and record.invoice_date > today:
                raise ValidationError(
                    'La fecha de canje no puede ser futura. '
                    f'Fecha máxima permitida: {today.strftime("%d/%m/%Y")}'
                )

    @api.constrains('invoice_date', 'letter_end_date')
    def _check_end_date_after_invoice_date(self):
        """Valida que la fecha de vencimiento sea posterior o igual a la fecha de canje"""
        for record in self:
            if record.invoice_date and record.letter_end_date:
                if record.letter_end_date < record.invoice_date:
                    raise ValidationError(
                        'La fecha de vencimiento debe ser igual o posterior a la fecha de canje. '
                        f'Fecha canje: {record.invoice_date.strftime("%d/%m/%Y")}, '
                        f'Fecha vencimiento: {record.letter_end_date.strftime("%d/%m/%Y")}'
                    )

    @api.onchange('invoice_date')
    def _onchange_invoice_date(self):
        """Validación en tiempo real para fecha de canje"""
        today = fields.Date.context_today(self)
        if self.invoice_date and self.invoice_date > today:
            return {
                'warning': {
                    'title': 'Fecha inválida',
                    'message': f'La fecha de canje no puede ser futura. Fecha máxima: {today.strftime("%d/%m/%Y")}',
                },
                'value': {'invoice_date': today}
            }

    @api.onchange('letter_end_date')
    def _onchange_letter_end_date(self):
        """Validación en tiempo real para fecha de vencimiento"""
        if self.invoice_date and self.letter_end_date:
            if self.letter_end_date < self.invoice_date:
                return {
                    'warning': {
                        'title': 'Fecha inválida',
                        'message': 'La fecha de vencimiento debe ser igual o posterior a la fecha de canje',
                    },
                    'value': {'letter_end_date': self.invoice_date}
                }


class L10nPeLetterLinkSummary(models.TransientModel):
    _name = 'l10n_pe.letter.link.summary'
    _description = 'Resumen de vinculación de asientos'

    summary = fields.Text(readonly=True)

    def action_close(self):
        if self.env.context.get('reload_on_close'):
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        return {'type': 'ir.actions.act_window_close'}
