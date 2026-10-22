from odoo import _, api, fields, models
from odoo.exceptions import UserError

DISPUTE_STATES = [
    ('open', 'Abierto'),
    ('customer', 'A favor del cliente'),
    ('company', 'A favor de la empresa'),
    ('cancel', 'Cancelado'),
]


class L10nPeCollectionDisputeReason(models.Model):
    _name = 'l10n_pe.collection.dispute.reason'
    _description = 'Motivo de reclamo'
    _order = 'sequence, name'

    name = fields.Char(string='Motivo', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class L10nPeCollectionDispute(models.Model):
    """Reclamo del cliente sobre uno o más documentos: precio, cantidad, calidad,
    documento no recibido…

    Mientras está abierto, sus documentos salen del seguimiento nativo
    (``no_followup``), no cuentan como deuda exigible y no se pueden reportar a
    una central de riesgo: cobrar o reportar una deuda discutida es lo que
    Indecopi sanciona. Al cerrarse, vuelven al seguimiento los que sigan
    abiertos; si se resolvió a favor del cliente, lo que corresponde es emitir
    la nota de crédito.
    """
    _name = 'l10n_pe.collection.dispute'
    _description = 'Reclamo de cobranza'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True, tracking=True, check_company=True, index=True,
        domain="['|', ('parent_id', '=', False), ('is_company', '=', True)]")
    user_id = fields.Many2one('res.users', string='Gestor', required=True, tracking=True,
                              default=lambda self: self.env.user)
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today, tracking=True)
    reason_id = fields.Many2one('l10n_pe.collection.dispute.reason', string='Motivo', required=True)
    line_ids = fields.Many2many(
        'account.move.line', string='Documentos', check_company=True, required=True,
        relation='account_move_line_l10n_pe_collection_dispute_rel', column1='l10n_pe_collection_dispute_id',
        column2='account_move_line_id',
        domain="[('partner_id', 'child_of', partner_id), ('reconciled', '=', False),"
               " ('parent_state', '=', 'posted'), ('account_id.account_type', '=', 'asset_receivable'),"
               " ('amount_residual', '>', 0)]")
    amount = fields.Monetary(string='Importe en disputa', compute='_compute_amount', store=True)
    description = fields.Text(string='Detalle del reclamo')
    resolution = fields.Text(string='Solución')
    state = fields.Selection(DISPUTE_STATES, string='Estado', default='open', required=True, readonly=True,
                             tracking=True, copy=False)
    date_closed = fields.Date(string='Cerrado el', readonly=True, copy=False)
    action_id = fields.Many2one('l10n_pe.collection.action', string='Gestión', readonly=True, copy=False)

    @api.depends('line_ids.amount_residual')
    def _compute_amount(self):
        for dispute in self:
            dispute.amount = sum(dispute.line_ids.mapped('amount_residual'))

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        responsible = self.partner_id.commercial_partner_id.with_company(self.company_id).followup_responsible_id
        if responsible:
            self.user_id = responsible

    @api.depends('name', 'partner_id')
    def _compute_display_name(self):
        for dispute in self:
            dispute.display_name = '%s · %s' % (dispute.name, dispute.partner_id.name or '')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].with_company(
                    vals.get('company_id') or self.env.company.id).next_by_code('l10n_pe.collection.dispute') or '/'
        disputes = super().create(vals_list)
        disputes._l10n_pe_sync_followup()
        for dispute in disputes:
            dispute.partner_id._l10n_pe_collection_log(_(
                'Reclamo %(name)s (%(reason)s) por %(amount)s: sus documentos salen del seguimiento.',
                name=dispute._get_html_link(), reason=dispute.reason_id.name,
                amount=dispute.currency_id.format(dispute.amount)))
        return disputes

    def write(self, vals):
        old_lines = self.line_ids
        res = super().write(vals)
        if 'line_ids' in vals or 'state' in vals:
            (old_lines | self.line_ids)._l10n_pe_collection_sync_dispute()
        return res

    def _l10n_pe_sync_followup(self):
        self.line_ids._l10n_pe_collection_sync_dispute()

    def _l10n_pe_close(self, state):
        if self.filtered(lambda d: d.state != 'open'):
            raise UserError(_('Solo se cierra un reclamo abierto.'))
        if state != 'cancel' and self.filtered(lambda d: not d.resolution):
            raise UserError(_('Indique la solución antes de cerrar el reclamo.'))
        self.write({'state': state, 'date_closed': fields.Date.context_today(self)})
        for dispute in self:
            dispute.partner_id._l10n_pe_collection_log(_(
                'Reclamo %(name)s cerrado: %(state)s. Sus documentos vuelven al seguimiento.',
                name=dispute._get_html_link(), state=dict(DISPUTE_STATES)[state].lower()))
        return True

    def action_resolve_customer(self):
        return self._l10n_pe_close('customer')

    def action_resolve_company(self):
        return self._l10n_pe_close('company')

    def action_cancel(self):
        return self._l10n_pe_close('cancel')

    def action_reopen(self):
        if not self.env.user.has_group('al_l10n_pe_collection.group_collection_manager'):
            raise UserError(_('Solo el administrador de cobranza reabre un reclamo.'))
        self.write({'state': 'open', 'date_closed': False})
        return True

    def action_credit_note(self):
        """Nota de crédito de la factura reclamada (asistente nativo)."""
        self.ensure_one()
        moves = self.line_ids.move_id.filtered(lambda m: m.move_type == 'out_invoice')
        if not moves:
            raise UserError(_('El reclamo no tiene facturas a las que emitir una nota de crédito.'))
        return {
            'type': 'ir.actions.act_window', 'name': _('Nota de crédito'),
            'res_model': 'account.move.reversal', 'view_mode': 'form', 'target': 'new',
            'context': {'active_model': 'account.move', 'active_ids': moves.ids,
                        'default_reason': self.reason_id.name},
        }


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_pe_collection_dispute_ids = fields.Many2many(
        'l10n_pe.collection.dispute', string='Reclamos', copy=False,
        relation='account_move_line_l10n_pe_collection_dispute_rel', column1='account_move_line_id',
        column2='l10n_pe_collection_dispute_id')
    l10n_pe_collection_in_dispute = fields.Boolean(
        string='En disputa', compute='_compute_l10n_pe_collection_in_dispute', store=True)

    @api.depends('l10n_pe_collection_dispute_ids.state')
    def _compute_l10n_pe_collection_in_dispute(self):
        for line in self:
            line.l10n_pe_collection_in_dispute = any(
                d.state == 'open' for d in line.l10n_pe_collection_dispute_ids)

    def _l10n_pe_collection_sync_dispute(self):
        """Saca del seguimiento las cuotas con un reclamo abierto o en cobranza
        judicial y devuelve las demás (solo las que la app sacó)."""
        active_lawsuit = ('filed', 'admitted', 'judgment', 'enforcement')
        for line in self:
            out = any(d.state == 'open' for d in line.l10n_pe_collection_dispute_ids) \
                or any(l.state in active_lawsuit for l in line.l10n_pe_collection_lawsuit_ids)
            touched = line.l10n_pe_collection_dispute_ids or line.l10n_pe_collection_lawsuit_ids
            if out and not line.no_followup:
                line.no_followup = True
            elif not out and line.no_followup and touched:
                line.no_followup = False
