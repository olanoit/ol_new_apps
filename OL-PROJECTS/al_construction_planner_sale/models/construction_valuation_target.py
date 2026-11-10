# -*- coding: utf-8 -*-
"""Meta de valorización del mes, con aprobación (paquete 7 de CREVAL, CR-63).

El monto calculado es la suma de las valorizaciones previstas con corte en
el mes, más gastos generales, imprevistos, utilidad y descuento en proporción
(como la valorización): la suma de las metas de la obra cierra en la venta.
El planificador propone y la jefatura de proyectos aprueba con la validación
por niveles de OCA, como las demás aprobaciones de la aplicación. Cambiar una
meta aprobada la vuelve a «Propuesta»; mientras tanto vale la última
aprobada."""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner.models.common import PROJECT_HEAD_GROUPS

TARGET_STATES = [
    ('draft', 'Borrador'),
    ('proposed', 'Propuesta'),
    ('approved', 'Aprobada'),
    ('rejected', 'Rechazada'),
]


class ConstructionValuationTarget(models.Model):
    _name = 'construction.valuation.target'
    _description = 'Meta de valorización del mes'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'tier.validation']
    _order = 'project_id, month desc'
    _check_company_auto = True
    _state_from = ['proposed']
    _state_to = ['approved']
    _cancel_state = 'rejected'
    _tier_validation_manual_config = False

    name = fields.Char(string='Meta', compute='_compute_name', store=True)
    project_id = fields.Many2one('project.project', string='Obra', required=True, index=True,
                                 check_company=True, ondelete='cascade')
    company_id = fields.Many2one(related='project_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='project_id.company_id.currency_id', string='Moneda')
    month = fields.Date(string='Mes', required=True, help='Primer día del mes.')
    amount_computed = fields.Monetary(
        string='Monto calculado', compute='_compute_amount_computed',
        currency_field='currency_id',
        help='Valorizaciones previstas con corte en el mes, más gastos generales, imprevistos, '
             'utilidad y descuento en proporción.')
    amount_proposed = fields.Monetary(string='Monto propuesto', currency_field='currency_id',
                                      tracking=True)
    amount_approved = fields.Monetary(
        string='Meta aprobada', currency_field='currency_id', readonly=True, copy=False,
        tracking=True, help='La última aprobada: la cartera mide contra ella.')
    state = fields.Selection(TARGET_STATES, string='Estado', required=True, default='draft',
                             tracking=True, copy=False)
    proposed_by_id = fields.Many2one('res.users', string='Propuesta por', readonly=True,
                                     copy=False)
    date_proposed = fields.Datetime(string='Propuesta el', readonly=True, copy=False)
    approved_by_id = fields.Many2one('res.users', string='Aprobada por', readonly=True,
                                     copy=False)
    date_approved = fields.Datetime(string='Aprobada el', readonly=True, copy=False)
    deadline = fields.Date(string='Vence', compute='_compute_deadline', store=True)
    expired = fields.Boolean(string='Vencida sin aprobar', readonly=True, copy=False)

    _project_month_unique = models.Constraint(
        'unique(project_id, month)', 'La obra ya tiene la meta de ese mes.')

    @api.depends('project_id', 'month')
    def _compute_name(self):
        for target in self:
            target.name = '%s · %s' % (target.month.strftime('%m/%Y') if target.month else '',
                                       target.project_id.display_name or '')

    @api.depends('project_id', 'month')
    def _compute_amount_computed(self):
        for target in self:
            target.amount_computed = target.project_id._construction_month_target_amount(
                target.month) if target.project_id and target.month else 0.0

    @api.depends('month', 'project_id.construction_target_due_days')
    def _compute_deadline(self):
        for target in self:
            if not target.month:
                target.deadline = False
                continue
            end = target.month + relativedelta(day=31)
            target.deadline = end + relativedelta(days=target.project_id.construction_target_due_days)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('month'):
                vals['month'] = fields.Date.to_date(vals['month']).replace(day=1)
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Flujo
    # ------------------------------------------------------------------
    def action_propose(self):
        """«Proponer meta del mes»: el planificador; pide la aprobación."""
        for target in self:
            if target.state == 'proposed':
                raise UserError(self.env._('%s ya está propuesta.', target.display_name))
            if not target.amount_proposed:
                target.amount_proposed = target.amount_computed
            target.write({'state': 'proposed', 'proposed_by_id': self.env.user.id,
                          'date_proposed': fields.Datetime.now(), 'expired': False})
            target.restart_validation()
            reviews = target.request_validation() if target.need_validation else False
            if not reviews and target.validation_status != 'waiting':
                target._construction_approve()
        return True

    def _construction_approve(self):
        for target in self:
            previous = target.amount_approved
            target.with_context(al_construction_approving=True).write({
                'state': 'approved', 'amount_approved': target.amount_proposed,
                'approved_by_id': self.env.user.id, 'date_approved': fields.Datetime.now()})
            target.message_post(body=self.env._(
                'Meta aprobada: %(before)s → %(after)s.',
                before=target.currency_id.format(previous) if previous else '—',
                after=target.currency_id.format(target.amount_approved)))

    def _validate_tier(self, tiers=False):
        res = super()._validate_tier(tiers)
        if not self.env.context.get('al_construction_approving'):
            for target in self:
                if target.state == 'proposed' and target.validation_status == 'validated':
                    target._construction_approve()
        return res

    def _rejected_tier(self, tiers=False):
        res = super()._rejected_tier(tiers)
        for target in self:
            if target.state == 'proposed' and target.validation_status == 'rejected':
                # Rechazada: vuelve a borrador; la aprobada anterior sigue.
                target.with_context(skip_validation_check=True).write({'state': 'draft'})
                target.message_post(body=self.env._('Meta rechazada: vuelve a borrador.'))
        return res

    def action_approve(self):
        """Aprobar sin regla de niveles: solo la jefatura de proyectos."""
        if not self.env.user.has_groups(PROJECT_HEAD_GROUPS):
            raise UserError(self.env._('Aprueba la meta la jefatura de proyectos.'))
        self.filtered(lambda t: t.state == 'proposed')._construction_approve()
        return True

    @api.model
    def _cron_construction_target_expiry(self):
        """Meta que vence sin aprobar: se marca y llega una actividad a quien
        aprueba (la jefatura de proyectos)."""
        today = fields.Date.context_today(self)
        targets = self.search([('state', 'in', ('draft', 'proposed')), ('expired', '=', False),
                               ('deadline', '<', today)])
        group = self.env.ref('al_construction_planner.group_planner_project_head',
                             raise_if_not_found=False)
        for target in targets:
            target.expired = True
            for user in (group.user_ids if group else self.env['res.users'])[:5]:
                target.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=user.id,
                    summary=self.env._('Meta de valorización vencida sin aprobar'))


class ProjectProject(models.Model):
    _inherit = 'project.project'

    construction_target_due_days = fields.Integer(
        string='Vencimiento de la meta', default=0,
        help='Días después del último día del mes en que vence la meta de valorización (0: fin '
             'de mes; negativo: antes).')
    construction_valuation_target_ids = fields.One2many(
        'construction.valuation.target', 'project_id', string='Metas de valorización')

    def _construction_month_target_amount(self, month):
        """Valorizaciones previstas con corte en el mes × (venta ÷ partidas):
        gastos generales, imprevistos, utilidad y descuento en proporción."""
        self.ensure_one()
        first = month.replace(day=1)
        last = first + relativedelta(day=31)
        forecast = self._construction_get_valuation_forecast()
        amount = sum(row['amount'] for row in forecast['rows'] if first <= row['cutoff'] <= last)
        partidas = sum(line._construction_price() for line in self._construction_partida_lines())
        others = sum(line._construction_price() for line in self._construction_proportional_lines())
        factor = (partidas + others) / partidas if partidas else 1.0
        return forecast['currency'].round(amount * factor)

    def _construction_valuation_target(self, month):
        """(monto, aprobada) del mes: la última meta aprobada o, sin ella, el
        monto calculado («sin aprobar»)."""
        self.ensure_one()
        first = month.replace(day=1)
        target = self.construction_valuation_target_ids.filtered(lambda t: t.month == first)[:1]
        if target.amount_approved:
            return target.amount_approved, True
        return self._construction_month_target_amount(first), False

    def action_construction_valuation_targets(self):
        """Metas de la obra, una por mes de las valorizaciones previstas; el
        mes en curso primero."""
        self.ensure_one()
        Target = self.env['construction.valuation.target']
        months = {row['cutoff'].replace(day=1)
                  for row in self._construction_get_valuation_forecast()['rows']}
        months.add(date.today().replace(day=1))
        existing = set(self.construction_valuation_target_ids.mapped('month'))
        Target.create([{'project_id': self.id, 'month': month}
                       for month in sorted(months - existing)])
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Metas de valorización · %s', self.display_name),
            'res_model': 'construction.valuation.target',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
