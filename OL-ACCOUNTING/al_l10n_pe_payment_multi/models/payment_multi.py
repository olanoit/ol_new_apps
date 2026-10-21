from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

LINE_TYPES = [
    ('document', 'Comprobante'),
    ('advance', 'Anticipo'),
    ('other', 'Otro pago'),
]
#: Sentido de la contrapartida: «sale del banco» es un cargo a la cuenta de la línea.
DIRECTIONS = [('out', 'Sale del banco'), ('in', 'Entra al banco')]


class L10nPePaymentMulti(models.Model):
    """Pago múltiple: un solo movimiento de banco o caja para varios conceptos.

    Las líneas son comprobantes abiertos de cualquier socio (también parciales
    y en otra moneda), anticipos (122/422) y otros pagos a una cuenta libre.
    Al validar se crea UN ``account.payment`` con sus apuntes armados por el
    hook nativo ``line_ids`` del pago: la línea de banco (cuenta de pendientes)
    y una contrapartida por línea, cada una al cambio de la fecha del pago.
    Los comprobantes se concilian con ``reconcile()`` estándar: la diferencia
    con el cambio original la registra Odoo.
    """
    _name = 'l10n_pe.payment.multi'
    _description = 'Pago múltiple'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company)
    payment_type = fields.Selection(
        [('outbound', 'Pago'), ('inbound', 'Cobro')], string='Tipo', required=True,
        default='outbound', tracking=True)
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today, tracking=True)
    journal_id = fields.Many2one(
        'account.journal', string='Diario', required=True, check_company=True, tracking=True,
        domain="[('type', 'in', ('bank', 'cash', 'credit'))]",
        default=lambda self: self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self.env.company),
            ('type', 'in', ('bank', 'cash'))], limit=1))
    payment_method_line_id = fields.Many2one(
        'account.payment.method.line', string='Método de pago',
        compute='_compute_payment_method_line_id', store=True, readonly=False,
        domain="[('journal_id', '=', journal_id), ('payment_type', '=', payment_type)]")
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', compute='_compute_currency_id', store=True,
        help='Moneda del diario: la del movimiento de banco.')
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda de la compañía')
    memo = fields.Char(string='Concepto')
    pe_payment_method_id = fields.Many2one('pe.catalog.payment', string='Medio de pago')
    bank_operation_number = fields.Char(string='Número de operación banco')
    partner_ids = fields.Many2many(
        'res.partner', string='Socios',
        help='Socios cuyos comprobantes abiertos trae «Cargar documentos».')
    state = fields.Selection(
        [('draft', 'Borrador'), ('posted', 'Validado'), ('cancel', 'Anulado')],
        string='Estado', default='draft', required=True, readonly=True, tracking=True, copy=False)
    line_ids = fields.One2many('l10n_pe.payment.multi.line', 'multi_id', string='Líneas', copy=True)
    payment_id = fields.Many2one('account.payment', string='Pago', readonly=True, copy=False, check_company=True)
    move_id = fields.Many2one(related='payment_id.move_id', string='Asiento')
    receipt_number = fields.Char(related='payment_id.l10n_pe_receipt_number', string='Comprobante de pago')
    amount_total = fields.Monetary(
        string='Importe', currency_field='currency_id', compute='_compute_amount_total', store=True,
        help='Lo que sale del banco (pago) o entra (cobro): suma de las líneas en la moneda del diario.')
    partner_count = fields.Integer(string='N.º de socios', compute='_compute_amount_total', store=True)

    @api.depends('journal_id', 'payment_type')
    def _compute_payment_method_line_id(self):
        for multi in self:
            available = multi.journal_id._get_available_payment_method_lines(multi.payment_type)
            if multi.payment_method_line_id not in available:
                multi.payment_method_line_id = available[:1]

    @api.depends('journal_id')
    def _compute_currency_id(self):
        for multi in self:
            multi.currency_id = multi.journal_id.currency_id or multi.company_id.currency_id

    @api.depends('line_ids.amount_payment', 'line_ids.direction', 'line_ids.partner_id', 'payment_type')
    def _compute_amount_total(self):
        for multi in self:
            direction = multi._l10n_pe_direction()
            multi.amount_total = sum(
                line.amount_payment if line.direction == direction else -line.amount_payment
                for line in multi.line_ids)
            multi.partner_count = len(multi.line_ids.partner_id.commercial_partner_id)

    def _l10n_pe_direction(self):
        """Sentido del pago en el banco: un pago saca dinero, un cobro lo ingresa."""
        self.ensure_one()
        return 'out' if self.payment_type == 'outbound' else 'in'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].with_company(
                    vals.get('company_id') or self.env.company.id
                ).next_by_code('l10n_pe.payment.multi') or '/'
        return super().create(vals_list)

    def unlink(self):
        if any(multi.state != 'draft' for multi in self):
            raise UserError(_('Solo se eliminan pagos múltiples en borrador; anule los validados.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Carga de documentos
    # ------------------------------------------------------------------

    def _l10n_pe_excluded_accounts(self):
        """Cuentas que no se pagan aquí: la cuota de detracción va al Banco de
        la Nación con su propio asistente."""
        self.ensure_one()
        company = self.company_id.root_id
        accounts = self.env['account.account']
        for fname in ('l10n_pe_detraction_payable_account_id', 'l10n_pe_detraction_receivable_account_id'):
            if fname in company._fields:
                accounts |= company[fname]
        return accounts

    def _l10n_pe_open_lines_domain(self):
        self.ensure_one()
        account_type = 'liability_payable' if self.payment_type == 'outbound' else 'asset_receivable'
        domain = [
            ('company_id', 'child_of', self.company_id.root_id.id),
            ('parent_state', '=', 'posted'),
            ('account_id.reconcile', '=', True),
            ('account_id.account_type', '=', account_type),
            ('account_id', 'not in', (self._l10n_pe_excluded_accounts()
                                      | self.company_id._l10n_pe_advance_accounts()).ids),
            ('reconciled', '=', False),
            ('amount_residual', '!=', 0.0),
        ]
        if self.partner_ids:
            domain.append(('partner_id', 'child_of', self.partner_ids.commercial_partner_id.ids))
        return domain

    def action_load_documents(self):
        """Trae los comprobantes abiertos (de los socios elegidos, o de todos)."""
        for multi in self:
            if multi.state != 'draft':
                continue
            present = multi.line_ids.move_line_id
            lines = self.env['account.move.line'].search(
                multi._l10n_pe_open_lines_domain() + [('id', 'not in', present.ids)],
                order='partner_id, date_maturity, date, id')
            lines = lines.filtered(lambda l: not multi._l10n_pe_document_error(l))
            multi.line_ids = [Command.create({'line_type': 'document', 'move_line_id': line.id})
                              for line in lines]
        return True

    def action_clean(self):
        """Quita las líneas sin importe."""
        self.line_ids.filtered(lambda l: not l.amount).unlink()
        return True

    @api.model
    def _l10n_pe_open_from_moves(self, moves):
        """Pago múltiple con las cuotas abiertas de ``moves`` (acción de la lista de facturas)."""
        moves = moves.filtered(lambda m: m.state == 'posted')
        if not moves:
            raise UserError(_('Elija comprobantes publicados.'))
        payment_type = 'outbound' if all(m.is_purchase_document(True) or m.move_type == 'out_refund'
                                         for m in moves) else 'inbound'
        multi = self.with_company(moves[:1].company_id).create({
            'payment_type': payment_type,
            'company_id': moves[:1].company_id.id,
        })
        lines = moves.line_ids.filtered(
            lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
            and l.account_id.reconcile and not l.reconciled
            and l.account_id not in multi._l10n_pe_excluded_accounts())
        errors = [error for line in lines if (error := multi._l10n_pe_document_error(line))]
        if errors:
            raise UserError('\n'.join(errors))
        multi.line_ids = [Command.create({'line_type': 'document', 'move_line_id': line.id})
                          for line in lines.sorted(lambda l: (l.partner_id.id, l.date_maturity or l.date, l.id))]
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': multi.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------

    def _l10n_pe_document_error(self, move_line):
        """Motivo por el que un apunte no se paga con un pago múltiple, o ``False``."""
        self.ensure_one()
        move = move_line.move_id
        if move_line.parent_state != 'posted' or move_line.reconciled:
            return _('%s ya no está abierto.', move.display_name)
        if move_line.account_id.account_type not in ('asset_receivable', 'liability_payable') \
                or not move_line.account_id.reconcile:
            return _('%s: la cuenta %s no es por cobrar ni por pagar.',
                     move.display_name, move_line.account_id.display_name)
        if move_line.account_id in self._l10n_pe_excluded_accounts():
            return _('%s: la detracción se deposita en el Banco de la Nación con «Registrar depósito».',
                     move.display_name)
        reason = move_line._l10n_pe_payment_block_reason()
        if reason:
            return reason
        if 'l10n_pe_retention_applies' in move._fields and move.l10n_pe_retention_applies:
            return _('%s está sujeta a retención del IGV: páguela con «Registrar pago», que emite el '
                     'comprobante de retención del proveedor.', move.display_name)
        return False

    def _l10n_pe_check(self):
        self.ensure_one()
        lines = self.line_ids.filtered('amount')
        if not lines:
            raise UserError(_('Indique el importe de al menos una línea.'))
        if not self.payment_method_line_id:
            raise UserError(_('El diario %s no tiene métodos de pago para este tipo de operación.',
                              self.journal_id.display_name))
        for line in lines:
            if line.amount < 0:
                raise UserError(_('El importe de «%s» no puede ser negativo.', line.name or line.display_name))
            if not line.account_id:
                raise UserError(_('Indique la cuenta de «%s».', line.name or _('otro pago')))
            if line.line_type == 'document':
                error = self._l10n_pe_document_error(line.move_line_id)
                if error:
                    raise UserError(error)
                if line.currency_id.compare_amounts(line.amount, line.residual) > 0:
                    raise UserError(_(
                        '%(doc)s: el importe (%(amount)s) supera su saldo (%(residual)s).',
                        doc=line.move_id.display_name, amount=line.amount, residual=line.residual))
            elif line.line_type == 'advance':
                if not line.partner_id:
                    raise UserError(_('Indique el socio del anticipo.'))
                if line.account_id not in self.company_id._l10n_pe_advance_accounts():
                    raise UserError(_('Configure las cuentas de anticipos en Ajustes ▸ Perú.'))
            else:
                if line.account_id.account_type in ('asset_cash', 'liability_credit_card'):
                    raise UserError(_('«%s»: use una transferencia interna para mover dinero entre '
                                      'cuentas propias.', line.name or line.account_id.display_name))
                if line.account_id.account_type in ('asset_receivable', 'liability_payable') \
                        and not line.partner_id:
                    raise UserError(_('«%s» va a una cuenta por cobrar o por pagar: indique el socio.',
                                      line.name or line.account_id.display_name))
        if self.currency_id.compare_amounts(self.amount_total, 0.0) <= 0:
            raise UserError(_(
                'El importe del %(type)s debe ser positivo: lo que %(verb)s supera a lo que %(other)s.',
                type=_('pago') if self.payment_type == 'outbound' else _('cobro'),
                verb=_('entra') if self.payment_type == 'outbound' else _('sale'),
                other=_('sale') if self.payment_type == 'outbound' else _('entra')))

    def _l10n_pe_outstanding_account(self):
        """Cuenta de pendientes del método de pago o, si no tiene, la de Odoo
        (la misma que usa el pago nativo con ``force_payment_move``)."""
        self.ensure_one()
        account = self.payment_method_line_id.payment_account_id
        if account:
            return account
        return self.env['account.payment'].new({'company_id': self.company_id.id}) \
            ._get_outstanding_account(self.payment_type)

    def _l10n_pe_partner(self):
        """Socio del pago: el único de las líneas; con varios, ninguno."""
        self.ensure_one()
        partners = self.line_ids.filtered('amount').partner_id.commercial_partner_id
        return partners if len(partners) == 1 else self.env['res.partner']

    def _l10n_pe_move_line_vals(self):
        """Apuntes del pago: una contrapartida por línea y la línea de banco."""
        self.ensure_one()
        line_vals = []
        bank_amount = bank_balance = 0.0
        for line in self.line_ids.filtered('amount'):
            sign = 1 if line.direction == 'out' else -1
            if line.line_type == 'advance':
                label = _('Anticipo: %s', line.partner_id.name)
            else:
                label = line.name or line.move_id.name or self.name
            vals = {
                'name': label,
                'account_id': line.account_id.id,
                'partner_id': line.partner_id.id,
                'currency_id': line.currency_id.id,
                'amount_currency': sign * line.amount,
                'balance': sign * line.amount_company,
                'date_maturity': self.date,
                'l10n_pe_payment_multi_line_id': line.id,
            }
            if line.line_type == 'other' and line.analytic_distribution:
                vals['analytic_distribution'] = line.analytic_distribution
            line_vals.append(vals)
            bank_amount -= sign * line.amount_payment
            bank_balance -= sign * line.amount_company
        line_vals.append({
            'name': '%s%s' % (self.name, self.memo and ': %s' % self.memo or ''),
            'account_id': self._l10n_pe_outstanding_account().id,
            'partner_id': self._l10n_pe_partner().id,
            'currency_id': self.currency_id.id,
            'amount_currency': self.currency_id.round(bank_amount),
            'balance': self.company_currency_id.round(bank_balance),
            'date_maturity': self.date,
        })
        return line_vals

    def _l10n_pe_payment_vals(self):
        self.ensure_one()
        return {
            'payment_type': self.payment_type,
            'partner_type': 'supplier' if self.payment_type == 'outbound' else 'customer',
            'partner_id': self._l10n_pe_partner().id,
            'amount': self.amount_total,
            'currency_id': self.currency_id.id,
            'date': self.date,
            'journal_id': self.journal_id.id,
            'payment_method_line_id': self.payment_method_line_id.id,
            'company_id': self.company_id.id,
            'memo': self.memo or self.name,
            'pe_payment_method_id': self.pe_payment_method_id.id,
            'bank_operation_number': self.bank_operation_number,
            'l10n_pe_payment_multi_id': self.id,
            'line_ids': [Command.create(vals) for vals in self._l10n_pe_move_line_vals()],
        }

    def action_post(self):
        for multi in self:
            if multi.state != 'draft':
                continue
            multi._l10n_pe_check()
            multi.line_ids.filtered(lambda l: not l.amount).unlink()
            # Sin cuenta de pendientes en el método, el pago nativo no genera
            # asiento; se le pide uno como hace Odoo sin contabilidad completa.
            force = not multi.payment_method_line_id.payment_account_id
            payment = self.env['account.payment'].with_context(force_payment_move=force) \
                .create(multi._l10n_pe_payment_vals())
            payment.action_post()
            for move_line in payment.move_id.line_ids.filtered('l10n_pe_payment_multi_line_id'):
                document = move_line.l10n_pe_payment_multi_line_id.move_line_id
                if document:
                    (move_line | document).reconcile()
            multi.write({'payment_id': payment.id, 'state': 'posted'})
            multi.message_post(body=_('Validado con el pago %s.', payment._get_html_link()))
        return True

    def action_cancel(self):
        """Anula el pago (su asiento queda anulado y los comprobantes, abiertos)."""
        for multi in self.filtered(lambda m: m.state == 'posted'):
            multi.payment_id.with_context(l10n_pe_payment_multi_cancel=True).action_cancel()
            multi.state = 'cancel'
            multi.message_post(body=_('Anulado: el pago %s quedó anulado.', multi.payment_id._get_html_link()))
        return True

    def action_draft(self):
        """Un pago múltiple anulado vuelve a borrador para corregirlo; al validarlo
        otra vez se crea un pago nuevo (el anulado queda en el historial)."""
        self.filtered(lambda m: m.state == 'cancel').write({'state': 'draft', 'payment_id': False})
        return True

    def action_open_payment(self):
        self.ensure_one()
        return self.payment_id._get_records_action() if self.payment_id else False

    def action_print_receipt(self):
        self.ensure_one()
        if not self.payment_id:
            raise UserError(_('Valide el pago múltiple antes de imprimir su comprobante.'))
        return self.payment_id.action_l10n_pe_receipt_print()


class L10nPePaymentMultiLine(models.Model):
    _name = 'l10n_pe.payment.multi.line'
    _description = 'Línea de pago múltiple'
    _inherit = ['analytic.mixin']
    _order = 'sequence, id'
    _check_company_auto = True

    multi_id = fields.Many2one('l10n_pe.payment.multi', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='multi_id.company_id', store=True)
    sequence = fields.Integer(default=10)
    line_type = fields.Selection(LINE_TYPES, string='Tipo', required=True, default='document')
    move_line_id = fields.Many2one(
        'account.move.line', string='Apunte', check_company=True,
        domain="[('reconciled', '=', False), ('parent_state', '=', 'posted'),"
               " ('account_id.reconcile', '=', True),"
               " ('account_id.account_type', 'in', ('asset_receivable', 'liability_payable'))]")
    move_id = fields.Many2one(related='move_line_id.move_id', string='Comprobante')
    date_maturity = fields.Date(related='move_line_id.date_maturity', string='Vencimiento')
    partner_id = fields.Many2one(
        'res.partner', string='Socio', compute='_compute_partner_id', store=True, readonly=False,
        check_company=True)
    account_id = fields.Many2one(
        'account.account', string='Cuenta', compute='_compute_account_id', store=True, readonly=False,
        check_company=True)
    name = fields.Char(string='Descripción', compute='_compute_name', store=True, readonly=False)
    direction = fields.Selection(
        DIRECTIONS, string='Sentido', compute='_compute_direction', store=True, readonly=False,
        help='«Sale del banco»: el importe se paga (cargo a la cuenta). «Entra al banco»: se descuenta '
             'del pago (una nota de crédito del proveedor, una comisión que devuelve el banco).')
    currency_id = fields.Many2one('res.currency', string='Moneda', compute='_compute_currency_id', store=True)
    multi_currency_id = fields.Many2one(related='multi_id.currency_id', string='Moneda del pago')
    company_currency_id = fields.Many2one(related='company_id.currency_id')
    residual = fields.Monetary(string='Saldo', currency_field='currency_id', compute='_compute_residual')
    amount = fields.Monetary(
        string='Importe', currency_field='currency_id', compute='_compute_amount', store=True, readonly=False,
        help='En la moneda del comprobante (o del pago, para anticipos y otros pagos).')
    amount_payment = fields.Monetary(
        string='Importe (moneda del pago)', currency_field='multi_currency_id',
        compute='_compute_amount_payment', store=True)
    amount_company = fields.Monetary(
        string='Importe (M.N.)', currency_field='company_currency_id', compute='_compute_amount_payment',
        store=True, help='En moneda nacional al cambio de la fecha del pago.')

    @api.depends('move_line_id')
    def _compute_partner_id(self):
        for line in self.filtered('move_line_id'):
            line.partner_id = line.move_line_id.partner_id

    @api.depends('line_type', 'move_line_id', 'partner_id', 'multi_id.payment_type', 'multi_id.currency_id')
    def _compute_account_id(self):
        for line in self:
            if line.line_type == 'document':
                line.account_id = line.move_line_id.account_id
            elif line.line_type == 'advance':
                partner_type = 'supplier' if line.multi_id.payment_type == 'outbound' else 'customer'
                line.account_id = line.multi_id.company_id._l10n_pe_advance_account(
                    partner_type, line.multi_id.currency_id)
            elif line.account_id.account_type in ('asset_receivable', 'liability_payable'):
                line.account_id = False

    @api.depends('line_type', 'move_line_id')
    def _compute_name(self):
        for line in self:
            if line.line_type == 'document':
                line.name = line.move_line_id.move_id.name
            elif line.line_type == 'advance' and not line.name:
                line.name = _('Anticipo')

    @api.depends('line_type', 'move_line_id', 'multi_id.payment_type')
    def _compute_direction(self):
        for line in self:
            if line.line_type == 'document' and line.move_line_id:
                # Se le debe (saldo acreedor): pagarlo es un cargo, el dinero sale.
                line.direction = 'out' if line.move_line_id.balance < 0 else 'in'
            elif line.line_type == 'advance' or not line.direction:
                line.direction = 'out' if line.multi_id.payment_type == 'outbound' else 'in'

    @api.depends('line_type', 'move_line_id', 'multi_id.currency_id')
    def _compute_currency_id(self):
        for line in self:
            if line.line_type == 'document' and line.move_line_id:
                line.currency_id = line.move_line_id.currency_id
            else:
                line.currency_id = line.multi_id.currency_id or line.company_id.currency_id

    @api.depends('move_line_id.amount_residual_currency')
    def _compute_residual(self):
        for line in self:
            line.residual = abs(line.move_line_id.amount_residual_currency)

    @api.depends('move_line_id')
    def _compute_amount(self):
        for line in self.filtered('move_line_id'):
            line.amount = abs(line.move_line_id.amount_residual_currency)

    @api.depends('amount', 'currency_id', 'multi_id.currency_id', 'multi_id.date')
    def _compute_amount_payment(self):
        for line in self:
            line.amount_company = line._l10n_pe_convert(line.company_currency_id)
            line.amount_payment = line._l10n_pe_convert(line.multi_currency_id)

    def _l10n_pe_convert(self, currency):
        """Importe de la línea en ``currency`` al cambio de la fecha del pago."""
        self.ensure_one()
        if not currency or not self.currency_id or self.currency_id == currency:
            return self.amount
        return self.currency_id._convert(
            self.amount, currency, self.company_id or self.env.company,
            self.multi_id.date or fields.Date.context_today(self))

    @api.constrains('line_type', 'move_line_id')
    def _check_document(self):
        for line in self:
            if line.line_type == 'document' and not line.move_line_id:
                raise ValidationError(_('Elija el comprobante de la línea.'))

    @api.constrains('amount')
    def _check_amount(self):
        for line in self:
            if line.amount < 0:
                raise ValidationError(_('El importe no puede ser negativo.'))
