from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .collection_forecast import MONTHS


class L10nPeCollectionTarget(models.Model):
    """Meta de cobranza de un gestor para un periodo; el avance es lo cobrado de
    los clientes que tiene asignados."""
    _name = 'l10n_pe.collection.target'
    _description = 'Meta de cobranza'
    _order = 'date_from desc, user_id'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Compañía', required=True, readonly=True,
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    user_id = fields.Many2one('res.users', string='Gestor', required=True)
    date_from = fields.Date(string='Desde', required=True,
                            default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(string='Hasta', required=True,
                          default=lambda self: fields.Date.context_today(self).replace(day=1)
                          + relativedelta(months=1, days=-1))
    amount = fields.Monetary(string='Meta', required=True)
    collected_amount = fields.Monetary(string='Cobrado', compute='_compute_progress')
    progress = fields.Float(string='Avance (%)', compute='_compute_progress', digits=(5, 1))
    portfolio_amount = fields.Monetary(string='Cartera actual', compute='_compute_progress',
                                       help='Saldo por cobrar hoy de los clientes del gestor.')

    _user_period_uniq = models.Constraint(
        'unique(company_id, user_id, date_from)', 'El gestor ya tiene una meta que empieza en esa fecha.')

    @api.constrains('date_from', 'date_to', 'amount')
    def _check_values(self):
        for target in self:
            if target.date_to < target.date_from:
                raise ValidationError(_('La meta termina antes de empezar.'))
            if target.amount <= 0:
                raise ValidationError(_('La meta debe ser positiva.'))

    @api.depends('user_id', 'date_from', 'date_to', 'amount')
    def _compute_progress(self):
        tools = self.env['l10n_pe.collection.tools']
        for target in self:
            if not (target.user_id and target.date_from and target.date_to):
                target.collected_amount = target.progress = target.portfolio_amount = 0.0
                continue
            partners = tools._scope_partners(target.company_id, target.user_id)
            target.collected_amount = tools._collected(target.company_id, target.date_from, target.date_to, partners)
            target.progress = 100.0 * target.collected_amount / target.amount if target.amount else 0.0
            target.portfolio_amount = sum(self.env['l10n_pe.collection.portfolio'].search(
                [('user_id', '=', target.user_id.id), ('company_id', 'child_of', target.company_id.root_id.id),
                 ('account_id', 'not in', target.company_id._l10n_pe_collection_excluded_accounts().ids)]
            ).mapped('amount_residual'))

    @api.depends('user_id', 'date_from')
    def _compute_display_name(self):
        for target in self:
            period = '%s %s' % (MONTHS[target.date_from.month - 1], target.date_from.year) if target.date_from else ''
            target.display_name = '%s · %s' % (target.user_id.name or '', period)
