from datetime import timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .collection_config import CHANNELS, GUARDED_CHANNELS


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
    is_dispute = fields.Boolean(related='result_id.is_dispute')
    dispute_reason_id = fields.Many2one('l10n_pe.collection.dispute.reason', string='Motivo del reclamo')
    dispute_id = fields.Many2one('l10n_pe.collection.dispute', string='Reclamo', readonly=True, copy=False)
    is_consumer = fields.Boolean(string='Consumidor', compute='_compute_is_consumer',
                                 help='Protegido por el art. 62 del Código de Protección al Consumidor.')
    next_action_date = fields.Date(string='Próxima acción', compute='_compute_next_action_date',
                                   store=True, readonly=False)
    next_action_summary = fields.Char(string='Qué hacer')

    @api.depends('result_id', 'date')
    def _compute_next_action_date(self):
        for action in self:
            days = action.result_id.next_action_days
            action.next_action_date = (action.date.date() + timedelta(days=days)) if days and action.date else False

    @api.depends('partner_id')
    def _compute_is_consumer(self):
        for action in self:
            action.is_consumer = bool(action.partner_id) and action.partner_id._l10n_pe_collection_is_consumer()

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

    @api.constrains('result_id', 'dispute_reason_id', 'line_ids')
    def _check_dispute(self):
        for action in self.filtered('is_dispute'):
            if not action.dispute_reason_id or not action.line_ids:
                raise ValidationError(_('Un reclamo necesita el motivo y los documentos reclamados.'))

    @api.constrains('partner_id', 'channel', 'date')
    def _check_consumer_contact_time(self):
        """Art. 62 de la Ley 29571: con consumidores, sin llamadas, visitas ni
        mensajes entre las 20:00 y las 07:00, ni sábados, domingos o feriados."""
        for action in self.filtered(lambda a: a.channel in GUARDED_CHANNELS and a.date and a.partner_id):
            company = action.company_id.root_id
            if not company.l10n_pe_collection_consumer_guard or not action.is_consumer:
                continue
            problem = action._l10n_pe_contact_time_problem()
            if problem:
                raise ValidationError(_(
                    '%(partner)s es consumidor: el art. 62 del Código de Protección al Consumidor prohíbe '
                    'contactarlo %(problem)s.', partner=action.partner_id.name, problem=problem))

    def _l10n_pe_contact_time_problem(self):
        """Por qué la fecha de la gestión no está permitida (o '' si lo está)."""
        self.ensure_one()
        company = self.company_id.root_id
        tz = pytz.timezone(self.user_id.tz or self.env.user.tz or 'America/Lima')
        local = pytz.utc.localize(self.date).astimezone(tz)
        hour = local.hour + local.minute / 60.0
        if local.weekday() >= 5:
            return _('en sábado o domingo')
        if not company.l10n_pe_collection_hour_from <= hour < company.l10n_pe_collection_hour_to:
            return _('antes de las %(start)s o después de las %(end)s',
                     start='%02d:%02d' % divmod(round(company.l10n_pe_collection_hour_from * 60), 60),
                     end='%02d:%02d' % divmod(round(company.l10n_pe_collection_hour_to * 60), 60))
        if self._l10n_pe_is_holiday(local.date()):
            return _('en un feriado')
        return ''

    def _l10n_pe_is_holiday(self, day):
        """Feriados = ausencias globales (sin recurso) del calendario laboral de
        la compañía, si está instalado ``resource``."""
        Leaves = self.env.get('resource.calendar.leaves')
        if Leaves is None:
            return False
        calendar = self.company_id.resource_calendar_id if 'resource_calendar_id' in self.company_id._fields \
            else False
        start = fields.Datetime.to_datetime(day)
        return bool(Leaves.sudo().search_count([
            # sudo: el gestor no necesita acceso al calendario para consultar los feriados.
            ('resource_id', '=', False),
            ('calendar_id', 'in', [False, calendar.id] if calendar else [False]),
            ('company_id', 'in', [False, self.company_id.id]),
            ('date_from', '<', start + timedelta(days=1)),
            ('date_to', '>', start),
        ], limit=1))

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
        if self.is_dispute:
            self.dispute_id = self.env['l10n_pe.collection.dispute'].create({
                'partner_id': partner.id,
                'user_id': self.user_id.id,
                'reason_id': self.dispute_reason_id.id,
                'line_ids': [fields.Command.set(self.line_ids.ids)],
                'description': self.note,
                'action_id': self.id,
                'company_id': self.company_id.id,
            })
        if self.next_action_date:
            # sudo: ver _l10n_pe_collection_log; la actividad es del gestor.
            partner_sudo = partner.sudo()
            partner_sudo.activity_schedule(
                'mail.mail_activity_data_call' if self.channel == 'call' else 'mail.mail_activity_data_todo',
                date_deadline=self.next_action_date, user_id=self.user_id.id,
                summary=self.next_action_summary or _('Seguimiento de cobranza'),
                note=self.note or '')
        partner._l10n_pe_collection_log(_(
            'Gestión de cobranza (%(channel)s): %(result)s. %(note)s',
            channel=dict(CHANNELS)[self.channel].lower(), result=self.result_id.name, note=self.note or ''))
