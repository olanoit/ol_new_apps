# -*- coding: utf-8 -*-
"""Líneas de crédito bancarias.

El banco aprueba a la empresa un límite (global o por producto) que consumen
los préstamos, las cartas fianza o el descuento de letras. El uso no se
registra aquí: lo informa cada módulo que consume la línea ampliando
``_l10n_pe_credit_usage``.
"""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

CREDIT_LINE_TYPES = [
    ('global', 'Global'),
    ('loan', 'Préstamos y pagarés'),
    ('guarantee', 'Cartas fianza'),
    ('discount', 'Descuento de letras y factoring'),
    ('overdraft', 'Sobregiro'),
]


class L10nPeTreasuryCreditLine(models.Model):
    _name = 'l10n_pe.treasury.credit.line'
    _description = 'Línea de crédito bancaria'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'partner_id, line_type, id'

    name = fields.Char(string='Línea', required=True, tracking=True)
    active = fields.Boolean(string='Activa', default=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    partner_id = fields.Many2one('res.partner', string='Banco', required=True, check_company=True,
                                 tracking=True)
    line_type = fields.Selection(CREDIT_LINE_TYPES, string='Tipo', required=True, default='global',
                                 tracking=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                  default=lambda self: self.env.company.currency_id)
    amount_limit = fields.Monetary(string='Límite aprobado', required=True, tracking=True)
    amount_used = fields.Monetary(string='Utilizado', compute='_compute_usage',
                                  help='Saldo de los préstamos y las cartas fianza vigentes asignados a la línea, '
                                       'convertidos a la moneda de la línea.')
    amount_available = fields.Monetary(string='Disponible', compute='_compute_usage')
    usage_percent = fields.Float(string='Uso (%)', compute='_compute_usage')
    date_start = fields.Date(string='Aprobada el', tracking=True)
    date_end = fields.Date(string='Vigente hasta', tracking=True)
    rate = fields.Float(string='Tasa de referencia (TEA %)', digits=(6, 4),
                        help='Tasa pactada para los desembolsos de la línea (informativa).')
    commission_rate = fields.Float(string='Comisión (%)', digits=(6, 4),
                                   help='Comisión pactada (p. ej. trimestral de las cartas fianza).')
    guarantee = fields.Char(string='Garantías', help='Garantías que respaldan la línea (hipoteca, fianza solidaria…).')
    user_id = fields.Many2one('res.users', string='Responsable', default=lambda self: self.env.user)
    notice_sent = fields.Boolean(string='Aviso enviado', readonly=True, copy=False)
    expired = fields.Boolean(string='Vencida', compute='_compute_expired')
    notes = fields.Html(string='Notas')

    _positive_limit = models.Constraint('CHECK(amount_limit >= 0)', 'El límite no puede ser negativo.')

    def _l10n_pe_credit_usage(self):
        """Uso de cada línea en su moneda: ``{line_id: importe}``. Los módulos que
        consumen líneas (préstamos, cartas fianza) suman lo suyo."""
        return {line.id: 0.0 for line in self}

    def _l10n_pe_invalidate_usage(self):
        """El uso no tiene ``depends`` (lo informan otros modelos): quien lo cambia
        lo invalida."""
        self.invalidate_recordset(['amount_used', 'amount_available', 'usage_percent'])

    def _compute_usage(self):
        usage = self._l10n_pe_credit_usage() if self.ids else {}
        for line in self:
            used = line.currency_id.round(usage.get(line.id, 0.0))
            line.amount_used = used
            line.amount_available = line.amount_limit - used
            line.usage_percent = (used / line.amount_limit * 100.0) if line.amount_limit else 0.0

    def _compute_expired(self):
        today = fields.Date.context_today(self)
        for line in self:
            line.expired = bool(line.date_end and line.date_end < today)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for line in self:
            if line.date_start and line.date_end and line.date_end < line.date_start:
                raise ValidationError(self.env._('La vigencia debe ser posterior a la aprobación.'))

    def _l10n_pe_convert(self, amount, currency, date=None):
        """``amount`` de ``currency`` a la moneda de la línea."""
        self.ensure_one()
        if currency == self.currency_id:
            return amount
        return currency._convert(amount, self.currency_id, self.company_id,
                                 date or fields.Date.context_today(self))

    @api.model
    def _cron_l10n_pe_credit_line_notice(self):
        today = fields.Date.context_today(self)
        for line in self.search([('date_end', '!=', False), ('notice_sent', '=', False)]):
            notice = line.company_id.l10n_pe_treasury_notice_days
            if line.date_end - timedelta(days=notice) <= today:
                line.activity_schedule(
                    'mail.mail_activity_data_todo', date_deadline=line.date_end,
                    summary=self.env._('Renovar la línea %s', line.name),
                    note=self.env._('La línea de crédito vence el %s: gestione su renovación con el banco.',
                                    line.date_end),
                    user_id=(line.user_id or self.env.user).id)
                line.notice_sent = True
        return True

    def write(self, vals):
        if 'date_end' in vals:
            vals['notice_sent'] = False
        return super().write(vals)
