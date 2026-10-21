from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .collection_config import CHANNELS


class L10nPeCollectionAction(models.Model):
    """Gestión de cobranza: un contacto con el cliente (llamada, visita, correo…)
    y su resultado. Deja constancia en el historial del cliente, programa la
    próxima acción del gestor y, si el resultado es un compromiso, lo crea."""
    _name = 'l10n_pe.collection.action'
    _description = 'Gestión de cobranza'
    _order = 'date desc, id desc'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True, check_company=True, index=True,
        domain="['|', ('parent_id', '=', False), ('is_company', '=', True)]")
    contact_id = fields.Many2one('res.partner', string='Contacto',
                                 domain="[('parent_id', '=', partner_id)]",
                                 help='Persona con la que se habló.')
    user_id = fields.Many2one('res.users', string='Gestor', required=True, default=lambda self: self.env.user)
    date = fields.Datetime(string='Fecha', required=True, default=fields.Datetime.now)
    channel = fields.Selection(CHANNELS, string='Canal', required=True, default='call')
    result_id = fields.Many2one('l10n_pe.collection.result', string='Resultado', required=True)
    is_promise = fields.Boolean(related='result_id.is_promise')
    note = fields.Text(string='Detalle')
    line_ids = fields.Many2many(
        'account.move.line', string='Documentos', check_company=True,
        domain="[('partner_id', 'child_of', partner_id), ('reconciled', '=', False),"
               " ('parent_state', '=', 'posted'), ('account_id.account_type', '=', 'asset_receivable')]")
    promise_date = fields.Date(string='Fecha comprometida')
    promise_amount = fields.Monetary(string='Importe comprometido')
    promise_id = fields.Many2one('l10n_pe.collection.promise', string='Compromiso', readonly=True, copy=False)
    next_action_date = fields.Date(string='Próxima acción', compute='_compute_next_action_date',
                                   store=True, readonly=False)
    next_action_summary = fields.Char(string='Qué hacer')

    @api.depends('result_id', 'date')
    def _compute_next_action_date(self):
        for action in self:
            days = action.result_id.next_action_days
            action.next_action_date = (action.date.date() + timedelta(days=days)) if days and action.date else False

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        responsible = self.partner_id.commercial_partner_id.with_company(self.company_id).followup_responsible_id
        if responsible:
            self.user_id = responsible

    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        if self.line_ids and not self.promise_amount:
            self.promise_amount = sum(self.line_ids.mapped('amount_residual'))

    @api.constrains('result_id', 'promise_date', 'promise_amount')
    def _check_promise(self):
        for action in self.filtered('is_promise'):
            if not action.promise_date or action.promise_amount <= 0:
                raise ValidationError(_('Un compromiso de pago necesita fecha e importe.'))

    @api.depends('partner_id', 'channel', 'date')
    def _compute_display_name(self):
        channels = dict(CHANNELS)
        for action in self:
            action.display_name = '%s · %s · %s' % (
                channels.get(action.channel, ''), action.partner_id.name or '',
                action.date.strftime('%d/%m/%Y') if action.date else '')

    @api.model_create_multi
    def create(self, vals_list):
        actions = super().create(vals_list)
        for action in actions:
            action._l10n_pe_after_create()
        return actions

    def _l10n_pe_after_create(self):
        self.ensure_one()
        partner = self.partner_id.commercial_partner_id
        if self.is_promise:
            self.promise_id = self.env['l10n_pe.collection.promise'].create({
                'partner_id': partner.id,
                'user_id': self.user_id.id,
                'date': self.promise_date,
                'amount': self.promise_amount,
                'line_ids': [fields.Command.set(self.line_ids.ids)],
                'action_id': self.id,
                'company_id': self.company_id.id,
                'note': self.note,
            })
        if self.next_action_date:
            partner.activity_schedule(
                'mail.mail_activity_data_call' if self.channel == 'call' else 'mail.mail_activity_data_todo',
                date_deadline=self.next_action_date, user_id=self.user_id.id,
                summary=self.next_action_summary or _('Seguimiento de cobranza'),
                note=self.note or '')
        partner.message_post(body=_(
            'Gestión de cobranza (%(channel)s): %(result)s. %(note)s',
            channel=dict(CHANNELS)[self.channel].lower(), result=self.result_id.name, note=self.note or ''))
