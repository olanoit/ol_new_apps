from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

PROMISE_STATES = [
    ('pending', 'Pendiente'),
    ('kept', 'Cumplido'),
    ('partial', 'Parcial'),
    ('broken', 'Incumplido'),
    ('cancel', 'Cancelado'),
]


class L10nPeCollectionPromise(models.Model):
    """Compromiso de pago del cliente: fecha, importe y, si se indican, los
    documentos que cubre.

    Se evalúa solo (cron diario): lo cobrado es cuánto bajó el saldo de esos
    documentos desde que se pactó (o, sin documentos, lo que el cliente pagó
    desde entonces). Al alcanzar el importe queda **cumplido** aunque no haya
    llegado la fecha; pasada la fecha y la tolerancia, **parcial** si cobró algo
    e **incumplido** si no.
    """
    _name = 'l10n_pe.collection.promise'
    _description = 'Compromiso de pago'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', readonly=True, copy=False, default='/')
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True, tracking=True, check_company=True,
        domain="['|', ('parent_id', '=', False), ('is_company', '=', True)]")
    user_id = fields.Many2one('res.users', string='Gestor', required=True, tracking=True,
                              default=lambda self: self.env.user)
    date = fields.Date(string='Fecha comprometida', required=True, tracking=True)
    amount = fields.Monetary(string='Importe comprometido', required=True, tracking=True)
    line_ids = fields.Many2many(
        'account.move.line', string='Documentos', check_company=True,
        domain="[('partner_id', 'child_of', partner_id), ('reconciled', '=', False),"
               " ('parent_state', '=', 'posted'), ('account_id.account_type', '=', 'asset_receivable')]",
        help='Cuotas que cubre el compromiso. Sin documentos, cuenta todo lo que el cliente pague '
             'desde la fecha en que se pactó.')
    action_id = fields.Many2one('l10n_pe.collection.action', string='Gestión', readonly=True, copy=False)
    note = fields.Text(string='Notas')
    state = fields.Selection(PROMISE_STATES, string='Estado', default='pending', required=True,
                             readonly=True, tracking=True, copy=False)
    date_agreed = fields.Date(string='Pactado el', required=True, default=fields.Date.context_today,
                              readonly=True, copy=False)
    residual_at_agreement = fields.Monetary(
        string='Saldo al pactar', readonly=True, copy=False,
        help='Saldo de los documentos cuando se pactó: lo cobrado se mide contra él.')
    collected_amount = fields.Monetary(string='Cobrado', readonly=True, copy=False)
    collected_percent = fields.Float(string='% cumplido', compute='_compute_collected_percent', digits=(5, 1))
    reminder_sent = fields.Boolean(string='Recordatorio enviado', readonly=True, copy=False)
    evaluated_on = fields.Date(string='Evaluado el', readonly=True, copy=False)

    @api.depends('collected_amount', 'amount')
    def _compute_collected_percent(self):
        for promise in self:
            promise.collected_percent = 100.0 * promise.collected_amount / promise.amount if promise.amount else 0.0

    @api.constrains('amount')
    def _check_amount(self):
        for promise in self:
            if promise.amount <= 0:
                raise ValidationError(_('El importe comprometido debe ser positivo.'))

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        responsible = self.partner_id.commercial_partner_id.with_company(self.company_id).followup_responsible_id
        if responsible:
            self.user_id = responsible

    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        if self.line_ids and not self.amount:
            self.amount = sum(self.line_ids.mapped('amount_residual'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].with_company(
                    vals.get('company_id') or self.env.company.id).next_by_code('l10n_pe.collection.promise') or '/'
        promises = super().create(vals_list)
        for promise in promises:
            promise.residual_at_agreement = sum(promise.line_ids.mapped('amount_residual'))
            promise.partner_id.message_post(body=_(
                'Compromiso de pago %(name)s: %(amount)s para el %(date)s.', name=promise._get_html_link(),
                amount=promise.currency_id.format(promise.amount), date=promise.date.strftime('%d/%m/%Y')))
        return promises

    # ------------------------------------------------------------------
    # Evaluación
    # ------------------------------------------------------------------

    def _l10n_pe_collected(self):
        """Lo cobrado contra el compromiso, en moneda de la compañía."""
        self.ensure_one()
        if self.line_ids:
            return max(self.residual_at_agreement - sum(self.line_ids.mapped('amount_residual')), 0.0)
        company = self.company_id
        lines = self.env['account.move.line'].search([
            ('partner_id', 'child_of', self.partner_id.commercial_partner_id.id),
            ('company_id', 'child_of', company.root_id.id),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('account_id', 'not in', company._l10n_pe_collection_excluded_accounts().ids),
            ('journal_id.type', 'in', ('bank', 'cash')),
            ('balance', '<', 0),
            ('date', '>=', self.date_agreed),
        ])
        return -sum(lines.mapped('balance'))

    def _l10n_pe_evaluate(self, today=None):
        """Actualiza lo cobrado y el estado; devuelve los que quedaron incumplidos."""
        today = today or fields.Date.context_today(self)
        broken = self.browse()
        for promise in self.filtered(lambda p: p.state == 'pending'):
            company = promise.company_id.root_id
            collected = promise.currency_id.round(promise._l10n_pe_collected())
            threshold = promise.amount * (company.l10n_pe_collection_promise_min_percent or 100.0) / 100.0
            values = {'collected_amount': collected}
            if promise.currency_id.compare_amounts(collected, threshold) >= 0:
                values.update(state='kept', evaluated_on=today)
            elif today > promise.date + timedelta(days=company.l10n_pe_collection_promise_tolerance):
                values.update(state='partial' if collected > 0 else 'broken', evaluated_on=today)
            promise.write(values)
            if promise.state in ('partial', 'broken'):
                broken |= promise
        broken._l10n_pe_notify_broken()
        return broken

    def _l10n_pe_notify_broken(self):
        for promise in self:
            label = dict(PROMISE_STATES)[promise.state].lower()
            promise.activity_schedule(
                'mail.mail_activity_data_todo', user_id=promise.user_id.id,
                summary=_('Compromiso %s', label),
                note=_('%(partner)s se comprometió a pagar %(amount)s el %(date)s y se cobró %(collected)s.',
                       partner=promise.partner_id.name, amount=promise.currency_id.format(promise.amount),
                       date=promise.date.strftime('%d/%m/%Y'),
                       collected=promise.currency_id.format(promise.collected_amount)))
            promise.message_post(body=_('Compromiso %(state)s: se cobró %(collected)s de %(amount)s.',
                                        state=label, collected=promise.currency_id.format(promise.collected_amount),
                                        amount=promise.currency_id.format(promise.amount)))

    def action_evaluate(self):
        self._l10n_pe_evaluate()
        return True

    def action_cancel(self):
        self.filtered(lambda p: p.state == 'pending').write({'state': 'cancel'})
        return True

    def action_reset(self):
        if not self.env.user.has_group('al_l10n_pe_collection.group_collection_manager'):
            raise UserError(_('Solo el administrador de cobranza reabre un compromiso.'))
        self.write({'state': 'pending', 'evaluated_on': False})
        return True

    # ------------------------------------------------------------------
    # Recordatorio y cron
    # ------------------------------------------------------------------

    def _l10n_pe_send_reminders(self, today=None):
        """Recordatorio al cliente N días antes de la fecha comprometida."""
        today = today or fields.Date.context_today(self)
        template = self.env.ref('al_l10n_pe_collection.mail_template_promise_reminder')
        sent = self.browse()
        for promise in self.filtered(lambda p: p.state == 'pending' and not p.reminder_sent):
            days = promise.company_id.root_id.l10n_pe_collection_promise_reminder_days
            if not days or not promise.partner_id.email or promise.date - timedelta(days=days) > today \
                    or promise.date < today:
                continue
            template.send_mail(promise.id)
            promise.reminder_sent = True
            promise.message_post(body=_('Recordatorio del compromiso enviado a %s.', promise.partner_id.email))
            sent |= promise
        return sent

    @api.model
    def _cron_collection_promises(self):
        pending = self.search([('state', '=', 'pending')])
        pending._l10n_pe_evaluate()
        pending._l10n_pe_send_reminders()
