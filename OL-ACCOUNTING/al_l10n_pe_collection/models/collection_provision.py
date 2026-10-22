from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

PROVISION_STATES = [('draft', 'Borrador'), ('posted', 'Contabilizada'), ('cancel', 'Anulada')]


class L10nPeCollectionProvision(models.Model):
    """Provisión de cobranza dudosa (art. 21 f) del Reglamento de la LIR).

    Propone las cuotas vencidas hace más de N meses (12 por defecto) y exige que
    la morosidad esté acreditada con gestiones de cobro registradas después del
    vencimiento o con un proceso judicial: la Casación 15840-2025 pide documentar
    acciones concretas, no basta un recordatorio automático. El asiento carga el
    gasto (68711) y abona la estimación (19x) por documento y deudor, como pide
    el Libro de Inventarios (PLE 3.6).

    Desde las líneas se registran después la **recuperación** (cobros de lo
    provisionado: 19x contra 7551) y el **castigo** (art. 21 g): 19x contra la
    cuenta por cobrar, conciliado con la factura, para deudas por deudor de hasta
    3 UIT o con las acciones judiciales agotadas.
    """
    _name = 'l10n_pe.collection.provision'
    _description = 'Provisión de cobranza dudosa'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    date = fields.Date(string='Fecha de la provisión', required=True, default=fields.Date.context_today,
                       tracking=True)
    months = fields.Integer(string='Vencidas hace más de (meses)', required=True,
                            default=lambda self: self.env.company.root_id.l10n_pe_collection_provision_months)
    min_actions = fields.Integer(string='Gestiones mínimas', required=True,
                                 default=lambda self: self.env.company.root_id.l10n_pe_collection_provision_min_actions)
    journal_id = fields.Many2one(
        'account.journal', string='Diario', check_company=True, domain="[('type', '=', 'general')]",
        default=lambda self: self.env.company.root_id.l10n_pe_collection_provision_journal_id)
    line_ids = fields.One2many('l10n_pe.collection.provision.line', 'provision_id', string='Documentos')
    move_id = fields.Many2one('account.move', string='Asiento', readonly=True, copy=False, check_company=True)
    state = fields.Selection(PROVISION_STATES, string='Estado', default='draft', required=True, readonly=True,
                             tracking=True, copy=False)
    amount = fields.Monetary(string='Provisionado', compute='_compute_amounts')
    recovered_amount = fields.Monetary(string='Recuperado', compute='_compute_amounts')
    written_off_amount = fields.Monetary(string='Castigado', compute='_compute_amounts')
    note = fields.Text(string='Notas')

    @api.depends('line_ids.amount', 'line_ids.selected', 'line_ids.recovered_amount', 'line_ids.write_off_amount')
    def _compute_amounts(self):
        for provision in self:
            lines = provision.line_ids.filtered('selected')
            provision.amount = sum(lines.mapped('amount'))
            provision.recovered_amount = sum(lines.mapped('recovered_amount'))
            provision.written_off_amount = sum(lines.mapped('write_off_amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].with_company(
                    vals.get('company_id') or self.env.company.id).next_by_code('l10n_pe.collection.provision') or '/'
        return super().create(vals_list)

    def unlink(self):
        if self.filtered(lambda p: p.state == 'posted'):
            raise UserError(_('Anule la provisión antes de eliminarla.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Propuesta
    # ------------------------------------------------------------------

    def _provisioned_line_ids(self):
        """Cuotas ya provisionadas en otra provisión vigente."""
        lines = self.env['l10n_pe.collection.provision.line'].search([
            ('provision_id.state', '=', 'posted'), ('selected', '=', True),
            ('provision_id.company_id', 'child_of', self.company_id.root_id.id)])
        return set(lines.move_line_id.ids)

    def action_load(self):
        """Propone las cuotas vencidas hace más de N meses, sin reclamo abierto,
        con las gestiones de cobro que las sustentan."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Solo se recalcula una provisión en borrador.'))
        company = self.company_id
        limit = self.date - relativedelta(months=self.months)
        aml_domain = [
            ('company_id', 'child_of', company.root_id.id),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('account_id', 'not in', company._l10n_pe_collection_excluded_accounts().ids),
            ('reconciled', '=', False),
            ('amount_residual', '>', 0),
            ('partner_id', '!=', False),
            ('date_maturity', '<', limit),
            ('l10n_pe_collection_in_dispute', '=', False),
        ]
        done = self._provisioned_line_ids()
        amls = self.env['account.move.line'].search(aml_domain, order='partner_id, date_maturity')
        amls = amls.filtered(lambda l: l.id not in done)
        Action = self.env['l10n_pe.collection.action']
        commands = [Command.clear()]
        for aml in amls:
            partner = aml.partner_id.commercial_partner_id
            actions = Action.search([
                ('partner_id', '=', partner.id), ('date', '>=', fields.Datetime.to_datetime(aml.date_maturity)),
                ('company_id', 'child_of', company.root_id.id),
                '|', ('line_ids', '=', False), ('line_ids', 'in', aml.ids)])
            commands.append(Command.create({
                'move_line_id': aml.id,
                'partner_id': partner.id,
                'amount': aml.amount_residual,
                'action_count': len(actions),
                'days': (self.date - aml.date_maturity).days,
                'selected': len(actions) >= self.min_actions,
            }))
        self.line_ids = commands
        return True

    # ------------------------------------------------------------------
    # Asientos
    # ------------------------------------------------------------------

    def _accounts(self):
        company = self.company_id
        expense = company._l10n_pe_collection_account('l10n_pe_collection_provision_expense_account_id')
        provision = company._l10n_pe_collection_account('l10n_pe_collection_provision_account_id')
        if not expense or not provision:
            raise UserError(_('Configure en Ajustes las cuentas de gasto y de estimación de cobranza dudosa.'))
        return expense, provision

    def action_post(self):
        self.ensure_one()
        lines = self.line_ids.filtered('selected')
        if not lines:
            raise UserError(_('No hay documentos seleccionados.'))
        if not self.journal_id:
            raise UserError(_('Indique el diario de la provisión.'))
        unsupported = lines.filtered(lambda l: not l.supported)
        if unsupported:
            raise UserError(_(
                'Sin gestiones de cobro ni proceso judicial, SUNAT no acepta la provisión de: %s. Registre las '
                'gestiones o desmarque esos documentos.', ', '.join(unsupported.move_id.mapped('name'))))
        expense, provision = self._accounts()
        move_lines = []
        for line in lines:
            label = _('Provisión de cobranza dudosa %s', line.move_id.name)
            move_lines += [
                Command.create({'name': label, 'account_id': expense.id, 'partner_id': line.partner_id.id,
                                'debit': line.amount}),
                Command.create({'name': label, 'account_id': provision.id, 'partner_id': line.partner_id.id,
                                'credit': line.amount}),
            ]
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': self.journal_id.id, 'date': self.date,
            'ref': _('Provisión de cobranza dudosa %s', self.name), 'line_ids': move_lines,
        })
        move.action_post()
        self.write({'move_id': move.id, 'state': 'posted'})
        return True

    def action_cancel(self):
        for provision in self:
            if provision.line_ids.filtered(lambda l: l.write_off_move_id or l.recovery_move_ids):
                raise UserError(_('La provisión %s tiene castigos o recuperaciones: anúlelos primero.',
                                  provision.name))
            if provision.move_id:
                provision.move_id._reverse_moves(
                    [{'ref': _('Anulación de %s', provision.name), 'date': fields.Date.context_today(self)}],
                    cancel=True)
            provision.state = 'cancel'
        return True

    def action_draft(self):
        self.filtered(lambda p: p.state == 'cancel').write({'state': 'draft', 'move_id': False})
        return True

    def action_recover(self):
        """Recupera lo cobrado de los documentos provisionados: 19x contra 7551."""
        self.ensure_one()
        _expense, provision = self._accounts()
        income = self.env.ref('account.%s_chart7551' % self.company_id.root_id.id, raise_if_not_found=False)
        if not income:
            raise UserError(_('No se encontró la cuenta 7551 Recuperación de cobranza dudosa.'))
        pending = [(line, line.recoverable_amount) for line in self.line_ids.filtered('selected')
                   if not line.write_off_move_id and self.currency_id.compare_amounts(line.recoverable_amount, 0) > 0]
        if not pending:
            raise UserError(_('No hay cobros de documentos provisionados que recuperar.'))
        moves = self.env['account.move']
        for line, amount in pending:
            label = _('Recuperación de cobranza dudosa %s', line.move_id.name)
            move = self.env['account.move'].create({
                'move_type': 'entry', 'journal_id': self.journal_id.id,
                'date': fields.Date.context_today(self), 'ref': label,
                'line_ids': [
                    Command.create({'name': label, 'account_id': provision.id, 'partner_id': line.partner_id.id,
                                    'debit': amount}),
                    Command.create({'name': label, 'account_id': income.id, 'partner_id': line.partner_id.id,
                                    'credit': amount}),
                ],
            })
            move.action_post()
            line.recovery_move_ids = [Command.link(move.id)]
            moves |= move
        self.message_post(body=_('Recuperación registrada en %s asientos.', len(moves)))
        return True

    def action_print_files(self):
        """Expediente de cobranza de los deudores: el sustento de la provisión."""
        partners = self.line_ids.filtered('selected').partner_id
        return self.env.ref('al_l10n_pe_collection.action_report_collection_file').report_action(partners)


class L10nPeCollectionProvisionLine(models.Model):
    _name = 'l10n_pe.collection.provision.line'
    _description = 'Documento provisionado'
    _order = 'partner_id, date_maturity'

    provision_id = fields.Many2one('l10n_pe.collection.provision', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='provision_id.company_id', store=True)
    currency_id = fields.Many2one(related='provision_id.currency_id')
    state = fields.Selection(related='provision_id.state')
    selected = fields.Boolean(string='Provisionar', default=True)
    move_line_id = fields.Many2one('account.move.line', string='Cuota', required=True, readonly=True)
    move_id = fields.Many2one(related='move_line_id.move_id', string='Documento')
    date_maturity = fields.Date(related='move_line_id.date_maturity', string='Vencimiento', store=True)
    partner_id = fields.Many2one('res.partner', string='Deudor', required=True, readonly=True)
    days = fields.Integer(string='Días vencida', readonly=True)
    amount = fields.Monetary(string='Provisión', readonly=True)
    action_count = fields.Integer(string='Gestiones', readonly=True,
                                  help='Gestiones de cobro registradas después del vencimiento.')
    judicial = fields.Boolean(string='Proceso judicial',
                              help='Cobranza judicial iniciada: sustenta la provisión aunque no haya gestiones.')
    judicial_exhausted = fields.Boolean(
        string='Acciones judiciales agotadas',
        help='Requisito del castigo de deudas por deudor de más de 3 UIT (art. 21 g del Reglamento de la LIR).')
    supported = fields.Boolean(string='Sustentada', compute='_compute_supported')
    residual = fields.Monetary(related='move_line_id.amount_residual', string='Saldo actual')
    recovery_move_ids = fields.Many2many('account.move', string='Recuperaciones', readonly=True, copy=False)
    recovered_amount = fields.Monetary(string='Recuperado', compute='_compute_recovered')
    recoverable_amount = fields.Monetary(string='Por recuperar', compute='_compute_recovered')
    debtor_total = fields.Monetary(string='Deuda provisionada del deudor', compute='_compute_debtor_total')
    write_off_allowed = fields.Boolean(string='Castigo deducible', compute='_compute_debtor_total',
                                       help='Deuda del deudor de hasta 3 UIT o acciones judiciales agotadas.')
    write_off_move_id = fields.Many2one('account.move', string='Castigo', readonly=True, copy=False)
    write_off_amount = fields.Monetary(string='Castigado', readonly=True, copy=False)

    @api.depends('action_count', 'judicial', 'provision_id.min_actions')
    def _compute_supported(self):
        for line in self:
            line.supported = line.judicial or line.action_count >= line.provision_id.min_actions

    @api.depends('amount', 'move_line_id.amount_residual', 'recovery_move_ids')
    def _compute_recovered(self):
        for line in self:
            # Cada recuperación es un asiento de dos líneas: su debe es lo recuperado.
            recovered = sum(line.recovery_move_ids.filtered(lambda m: m.state == 'posted').line_ids.mapped('debit'))
            line.recovered_amount = recovered
            collected = line.amount - max(line.move_line_id.amount_residual, 0.0)
            line.recoverable_amount = max(collected - recovered, 0.0) if not line.write_off_move_id else 0.0

    @api.depends('partner_id', 'amount', 'judicial_exhausted', 'provision_id.line_ids.amount')
    def _compute_debtor_total(self):
        totals = defaultdict(float)
        for line in self.provision_id.line_ids.filtered('selected'):
            totals[(line.provision_id.id, line.partner_id.id)] += line.amount
        for line in self:
            line.debtor_total = totals.get((line.provision_id.id, line.partner_id.id), 0.0)
            uit = line.company_id.root_id.l10n_pe_collection_uit
            line.write_off_allowed = line.judicial_exhausted or (uit and line.debtor_total <= 3 * uit)

    def action_write_off(self):
        """Castigo: 19x contra la cuenta por cobrar, conciliado con el documento."""
        for line in self:
            provision = line.provision_id
            if provision.state != 'posted' or line.write_off_move_id:
                raise UserError(_('Solo se castiga un documento de una provisión contabilizada, una vez.'))
            if not line.write_off_allowed:
                raise UserError(_(
                    '%(partner)s debe más de 3 UIT: el castigo exige acciones judiciales agotadas. Márquelo '
                    'cuando lo estén.', partner=line.partner_id.name))
            receivable = line.move_line_id
            amount = receivable.amount_residual
            if receivable.currency_id.is_zero(receivable.amount_residual_currency) or amount <= 0:
                raise UserError(_('%s ya no tiene saldo por castigar.', line.move_id.name))
            _expense, provision_account = provision._accounts()
            label = _('Castigo de cobranza dudosa %s', line.move_id.name)
            move = self.env['account.move'].create({
                'move_type': 'entry', 'journal_id': provision.journal_id.id,
                'date': fields.Date.context_today(self), 'ref': label,
                'line_ids': [
                    Command.create({'name': label, 'account_id': provision_account.id,
                                    'partner_id': line.partner_id.id, 'debit': amount}),
                    Command.create({'name': label, 'account_id': receivable.account_id.id,
                                    'partner_id': receivable.partner_id.id, 'credit': amount,
                                    'currency_id': receivable.currency_id.id,
                                    'amount_currency': -receivable.amount_residual_currency}),
                ],
            })
            move.action_post()
            (move.line_ids.filtered(lambda l: l.account_id == receivable.account_id) | receivable).reconcile()
            line.write({'write_off_move_id': move.id, 'write_off_amount': amount})
            line.partner_id._l10n_pe_collection_log(_('Castigo de %(doc)s por %(amount)s.', doc=line.move_id.name,
                                                amount=line.currency_id.format(amount)))
        return True
