from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

APPLICATION_TYPES = [
    ('advance', 'Aplicar anticipo'),
    ('netting', 'Compensar cobrar y pagar'),
    ('credit_note', 'Aplicar nota de crédito'),
    ('free', 'Libre'),
]


class L10nPePaymentApplication(models.Model):
    """Aplicación de documentos: cancela saldos abiertos de un socio entre sí.

    Cada línea toma un apunte abierto (factura, anticipo, nota de crédito,
    cuenta por pagar) y el importe a aplicar en su moneda. Al validar se crea
    un asiento en el diario de aplicaciones con la contrapartida de cada línea,
    valorada al cambio de la fecha de la aplicación, y se concilia con su
    apunte: la diferencia con el cambio original la registra Odoo al conciliar.
    """
    _name = 'l10n_pe.payment.application'
    _description = 'Aplicación de documentos'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, readonly=True,
        default=lambda self: self.env.company)
    partner_id = fields.Many2one(
        'res.partner', string='Socio', required=True, tracking=True, check_company=True,
        domain="['|', ('parent_id', '=', False), ('is_company', '=', True)]")
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today, tracking=True)
    application_type = fields.Selection(
        APPLICATION_TYPES, string='Tipo', required=True, default='advance', tracking=True)
    journal_id = fields.Many2one(
        'account.journal', string='Diario', required=True, check_company=True,
        domain="[('type', '=', 'general')]",
        default=lambda self: self.env.company.root_id.l10n_pe_application_journal_id)
    state = fields.Selection(
        [('draft', 'Borrador'), ('posted', 'Aplicado'), ('cancel', 'Revertido')],
        string='Estado', default='draft', required=True, readonly=True, tracking=True, copy=False)
    line_ids = fields.One2many(
        'l10n_pe.payment.application.line', 'application_id', string='Documentos', copy=False)
    move_id = fields.Many2one('account.move', string='Asiento', readonly=True, copy=False, check_company=True)
    reversal_move_id = fields.Many2one(
        'account.move', string='Asiento de reversión', readonly=True, copy=False, check_company=True)
    note = fields.Text(string='Notas')
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda de la compañía')
    amount_debit = fields.Monetary(
        string='Saldos deudores aplicados', currency_field='company_currency_id', compute='_compute_amounts')
    amount_credit = fields.Monetary(
        string='Saldos acreedores aplicados', currency_field='company_currency_id', compute='_compute_amounts')
    amount_difference = fields.Monetary(
        string='Diferencia', currency_field='company_currency_id', compute='_compute_amounts')

    @api.depends('line_ids.amount_company', 'line_ids.side')
    def _compute_amounts(self):
        for application in self:
            debit = sum(application.line_ids.filtered(lambda l: l.side == 'debit').mapped('amount_company'))
            credit = sum(application.line_ids.filtered(lambda l: l.side == 'credit').mapped('amount_company'))
            application.amount_debit = debit
            application.amount_credit = credit
            application.amount_difference = debit - credit

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].with_company(
                    vals.get('company_id') or self.env.company.id
                ).next_by_code('l10n_pe.payment.application') or '/'
        return super().create(vals_list)

    def unlink(self):
        if any(application.state != 'draft' for application in self):
            raise UserError(_('Solo se eliminan aplicaciones en borrador; revierta las aplicadas.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Carga y reparto
    # ------------------------------------------------------------------

    def _l10n_pe_open_lines_domain(self):
        self.ensure_one()
        return [
            ('company_id', 'child_of', self.company_id.root_id.id),
            ('partner_id', 'child_of', self.partner_id.commercial_partner_id.id),
            ('parent_state', '=', 'posted'),
            ('account_id.reconcile', '=', True),
            ('account_id.account_type', 'in', ('asset_receivable', 'liability_payable')),
            ('reconciled', '=', False),
            ('amount_residual', '!=', 0.0),
        ]

    def action_load_documents(self):
        """Trae los saldos abiertos del socio que aún no están en la aplicación."""
        for application in self:
            if application.state != 'draft':
                continue
            present = application.line_ids.move_line_id
            lines = self.env['account.move.line'].search(
                application._l10n_pe_open_lines_domain() + [('id', 'not in', present.ids)],
                order='date_maturity, date, id')
            application.line_ids = [Command.create({'move_line_id': line.id}) for line in lines]
        return True

    def action_distribute(self):
        """Reparte el menor de los dos lados (deudor/acreedor) por antigüedad."""
        for application in self:
            if application.state != 'draft':
                continue
            lines = application.line_ids.sorted(lambda l: (l.move_line_id.date_maturity or l.move_line_id.date, l.id))
            debit = lines.filtered(lambda l: l.side == 'debit')
            credit = lines.filtered(lambda l: l.side == 'credit')
            target = min(sum(debit.mapped('residual_company')), sum(credit.mapped('residual_company')))
            for side_lines in (debit, credit):
                remaining = target
                for line in side_lines:
                    share = min(remaining, line.residual_company)
                    remaining -= share
                    line.amount = line._l10n_pe_from_company(share)
        return True

    def action_clean(self):
        """Quita las líneas sin importe."""
        self.line_ids.filtered(lambda l: not l.amount).unlink()
        return True

    @api.model
    def _l10n_pe_open_new(self, partner, application_type, lines, with_open_documents=False):
        """Crea una aplicación con ``lines`` y la abre (botones de factura y anticipo)."""
        application = self.create({
            'partner_id': partner.commercial_partner_id.id,
            'application_type': application_type,
            'company_id': lines[:1].company_id.root_id.id or self.env.company.id,
            'line_ids': [Command.create({'move_line_id': line.id}) for line in lines],
        })
        if with_open_documents:
            application.action_load_documents()
        application.action_distribute()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': application.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------

    def _l10n_pe_check(self):
        self.ensure_one()
        lines = self.line_ids.filtered('amount')
        if not lines:
            raise UserError(_('Indique el importe a aplicar en al menos dos documentos.'))
        if not lines.filtered(lambda l: l.side == 'debit') or not lines.filtered(lambda l: l.side == 'credit'):
            raise UserError(_('Una aplicación cancela saldos deudores contra saldos acreedores: '
                              'faltan documentos de uno de los dos lados.'))
        commercial = self.partner_id.commercial_partner_id
        for line in lines:
            move_line = line.move_line_id
            if move_line.partner_id.commercial_partner_id != commercial:
                raise UserError(_('%s es de otro socio.', move_line.move_id.display_name))
            if move_line.reconciled or move_line.parent_state != 'posted':
                raise UserError(_('%s ya no está abierto.', move_line.move_id.display_name))
            if line.amount < 0 or line.currency_id.compare_amounts(line.amount, line.residual) > 0:
                raise UserError(_(
                    '%(doc)s: el importe a aplicar (%(amount)s) supera su saldo (%(residual)s).',
                    doc=move_line.move_id.display_name, amount=line.amount, residual=line.residual))
        # Tolerancia: el redondeo de cada conversión (va a diferencia de cambio).
        tolerance = self.company_currency_id.rounding * len(lines)
        if abs(self.amount_difference) > tolerance + 1e-9:
            raise UserError(_(
                'Lo aplicado a los saldos deudores (%(debit)s) debe ser igual a lo aplicado a los '
                'saldos acreedores (%(credit)s).', debit=self.amount_debit, credit=self.amount_credit))
        if not self.journal_id:
            raise UserError(_('Configure el diario de aplicaciones en Ajustes ▸ Perú.'))

    def _l10n_pe_move_vals(self):
        """Asiento que cancela lo aplicado: cada línea, al revés de su apunte."""
        self.ensure_one()
        line_vals = []
        for line in self.line_ids.filtered('amount'):
            move_line = line.move_line_id
            sign = -1 if line.side == 'debit' else 1
            line_vals.append({
                'name': _('Aplicación %(name)s: %(doc)s', name=self.name, doc=move_line.move_id.name),
                'account_id': move_line.account_id.id,
                'partner_id': move_line.partner_id.id,
                'currency_id': line.currency_id.id,
                'amount_currency': sign * line.amount,
                'balance': sign * line.amount_company,
                'l10n_pe_application_line_id': line.id,
            })
        difference = self.company_currency_id.round(sum(vals['balance'] for vals in line_vals))
        if difference:
            # Céntimos del redondeo al convertir varias monedas.
            company = self.company_id.root_id
            account = company.income_currency_exchange_account_id if difference > 0 \
                else company.expense_currency_exchange_account_id
            if not account:
                raise UserError(_('Configure las cuentas de diferencia de cambio de la compañía.'))
            line_vals.append({
                'name': _('Diferencia de cambio %s', self.name),
                'account_id': account.id,
                'partner_id': self.partner_id.commercial_partner_id.id,
                'balance': -difference,
                'amount_currency': -difference,
                'currency_id': self.company_currency_id.id,
            })
        return {
            'move_type': 'entry',
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': self.name,
            'company_id': self.company_id.id,
            'line_ids': [Command.create(vals) for vals in line_vals],
        }

    def action_post(self):
        for application in self:
            if application.state != 'draft':
                continue
            application._l10n_pe_check()
            application.line_ids.filtered(lambda l: not l.amount).unlink()
            move = self.env['account.move'].create(application._l10n_pe_move_vals())
            move.action_post()
            for line in move.line_ids.filtered('l10n_pe_application_line_id'):
                (line | line.l10n_pe_application_line_id.move_line_id).reconcile()
            application.write({'move_id': move.id, 'state': 'posted'})
            application.message_post(body=_('Aplicado con el asiento %s.', move._get_html_link()))
        return True

    def action_cancel(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_('Solo un administrador de contabilidad revierte aplicaciones.'))
        for application in self.filtered(lambda a: a.state == 'posted'):
            move = application.move_id
            move.line_ids.remove_move_reconcile()
            reversal = move._reverse_moves(
                [{'date': fields.Date.context_today(self), 'ref': _('Reversión de %s', application.name)}],
                cancel=True)
            application.write({'state': 'cancel', 'reversal_move_id': reversal.id})
            application.message_post(body=_('Revertido con el asiento %s.', reversal._get_html_link()))
        return True

    def action_open_move(self):
        self.ensure_one()
        return self.move_id._get_records_action() if self.move_id else False

    # ------------------------------------------------------------------
    # Anticipos pendientes
    # ------------------------------------------------------------------

    @api.model
    def action_open_pending_advances(self, partner_type=None):
        accounts = self.env['account.account']
        for company in self.env.companies.root_id:
            if partner_type in (None, 'customer'):
                accounts |= company.l10n_pe_advance_customer_account_id \
                    | company.l10n_pe_advance_customer_fc_account_id
            if partner_type in (None, 'supplier'):
                accounts |= company.l10n_pe_advance_supplier_account_id \
                    | company.l10n_pe_advance_supplier_fc_account_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Anticipos pendientes'),
            'res_model': 'account.move.line',
            'view_mode': 'list,pivot',
            'views': [(self.env.ref('al_l10n_pe_payment_application.view_pending_advances_list').id, 'list'),
                      (False, 'pivot')],
            'domain': [('account_id', 'in', accounts.ids), ('reconciled', '=', False),
                       ('parent_state', '=', 'posted'), ('amount_residual', '!=', 0.0)],
            'context': {'search_default_group_by_partner': 1, 'create': False, 'edit': False},
        }


class L10nPePaymentApplicationLine(models.Model):
    _name = 'l10n_pe.payment.application.line'
    _description = 'Documento de la aplicación'
    _check_company_auto = True

    application_id = fields.Many2one(
        'l10n_pe.payment.application', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='application_id.company_id', store=True)
    move_line_id = fields.Many2one(
        'account.move.line', string='Apunte', required=True, check_company=True,
        domain="[('reconciled', '=', False), ('parent_state', '=', 'posted'),"
               " ('account_id.reconcile', '=', True)]")
    move_id = fields.Many2one(related='move_line_id.move_id', string='Documento')
    account_id = fields.Many2one(related='move_line_id.account_id', string='Cuenta')
    date = fields.Date(related='move_line_id.date', string='Fecha')
    date_maturity = fields.Date(related='move_line_id.date_maturity', string='Vencimiento')
    currency_id = fields.Many2one(related='move_line_id.currency_id', string='Moneda')
    company_currency_id = fields.Many2one(related='company_id.currency_id')
    side = fields.Selection(
        [('debit', 'Saldo deudor'), ('credit', 'Saldo acreedor')], string='Lado',
        compute='_compute_side', store=True)
    residual = fields.Monetary(
        string='Saldo', currency_field='currency_id', compute='_compute_residual')
    residual_company = fields.Monetary(
        string='Saldo (M.N. al día)', currency_field='company_currency_id', compute='_compute_residual',
        help='Saldo en moneda nacional al cambio de la fecha de la aplicación.')
    amount = fields.Monetary(string='Importe a aplicar', currency_field='currency_id')
    amount_company = fields.Monetary(
        string='Importe (M.N.)', currency_field='company_currency_id', compute='_compute_amount_company')

    _move_line_uniq = models.Constraint(
        'unique(application_id, move_line_id)', 'El documento ya está en la aplicación.')

    @api.depends('move_line_id.balance')
    def _compute_side(self):
        for line in self:
            line.side = 'debit' if line.move_line_id.balance > 0 else 'credit'

    @api.depends('move_line_id.amount_residual', 'move_line_id.amount_residual_currency',
                 'application_id.date')
    def _compute_residual(self):
        for line in self:
            line.residual = abs(line.move_line_id.amount_residual_currency)
            line.residual_company = line._l10n_pe_to_company(line.residual)

    @api.depends('amount', 'application_id.date', 'currency_id')
    def _compute_amount_company(self):
        for line in self:
            line.amount_company = line._l10n_pe_to_company(line.amount)

    def _l10n_pe_rate_date(self):
        return self.application_id.date or fields.Date.context_today(self)

    def _l10n_pe_to_company(self, amount):
        """Importe en moneda nacional al cambio de la fecha de la aplicación."""
        self.ensure_one()
        if not self.currency_id or self.currency_id == self.company_currency_id:
            return amount
        return self.currency_id._convert(
            amount, self.company_currency_id, self.company_id, self._l10n_pe_rate_date())

    def _l10n_pe_from_company(self, amount_company):
        self.ensure_one()
        if not self.currency_id or self.currency_id == self.company_currency_id:
            return amount_company
        if self.company_currency_id.compare_amounts(amount_company, self.residual_company) == 0:
            return self.residual
        return self.company_currency_id._convert(
            amount_company, self.currency_id, self.company_id, self._l10n_pe_rate_date())

    @api.constrains('amount')
    def _check_amount(self):
        for line in self:
            if line.amount < 0:
                raise ValidationError(_('El importe a aplicar no puede ser negativo.'))
