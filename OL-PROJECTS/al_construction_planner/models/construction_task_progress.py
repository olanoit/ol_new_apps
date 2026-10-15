# -*- coding: utf-8 -*-
"""Avance reportado (P-06, P-07): unidades de driver de una actividad en un
módulo o ambiente, con fotos. La contrata (o el supervisor que transcribe)
reporta; el supervisor de obra valida. Solo lo validado suma al acumulado de
la línea del plan y entra a la liquidación semanal (fase 6)."""
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .construction_resource_plan import OPEN_STATES

PROGRESS_STATES = [
    ('draft', 'Reportado'),
    ('validated', 'Validado'),
    ('rejected', 'Rechazado'),
]
# Campos que solo cambian mientras el avance está reportado.
LOCKED_FIELDS = {'task_id', 'activity_id', 'plan_line_id', 'date', 'qty', 'attachment_ids'}


class ConstructionTaskProgress(models.Model):
    _name = 'construction.task.progress'
    _description = 'Avance reportado'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Número', required=True, readonly=True, copy=False, default='/')
    task_id = fields.Many2one(
        'project.task', string='Módulo o ambiente', required=True, index=True,
        check_company=True, domain="[('construction_level', 'in', ('space', 'module'))]")
    activity_id = fields.Many2one(
        'construction.labor.activity', string='Actividad (driver)', required=True,
        check_company=True, index=True)
    plan_line_id = fields.Many2one(
        'construction.resource.plan.line', string='Línea del plan', required=True, index=True,
        check_company=True, compute='_compute_plan_line_id', store=True, readonly=False,
        precompute=True, help='Línea del nivel y la actividad en el plan vigente.')
    plan_id = fields.Many2one(
        related='plan_line_id.plan_id', string='Plan', store=True, index=True)
    project_id = fields.Many2one(
        related='plan_line_id.project_id', string='Obra', store=True, index=True)
    company_id = fields.Many2one(
        related='plan_line_id.company_id', string='Compañía', store=True, index=True)
    currency_id = fields.Many2one(related='plan_line_id.currency_id', string='Moneda')
    partner_id = fields.Many2one(
        related='plan_line_id.partner_id', string='Contrata', store=True, index=True)
    stage = fields.Selection(related='plan_line_id.stage', string='Etapa', store=True)
    floor_task_id = fields.Many2one(
        related='plan_line_id.floor_task_id', string='Piso', store=True, index=True)
    apartment_task_id = fields.Many2one(
        related='plan_line_id.apartment_task_id', string='Departamento', store=True, index=True)
    space_task_id = fields.Many2one(
        related='plan_line_id.space_task_id', string='Ambiente', store=True, index=True)
    furniture_task_id = fields.Many2one(
        related='plan_line_id.furniture_task_id', string='Mueble', store=True, index=True)
    module_task_id = fields.Many2one(
        related='plan_line_id.module_task_id', string='Módulo', store=True, index=True)
    date = fields.Date(
        string='Fecha de ejecución', required=True, default=fields.Date.context_today,
        tracking=True, help='Decide a qué semana de liquidación pertenece.')
    qty = fields.Float(
        string='Unidades de driver', digits='Product Unit', required=True, tracking=True,
        help='Lo que reporta la contrata, en la unidad de la actividad.')
    uom_id = fields.Many2one(related='activity_id.uom_id', string='Unidad')
    tranche_id = fields.Many2one(
        'construction.activity.tranche', string='Tramo', index=True,
        domain="[('activity_id', '=', activity_id)]",
        help='Pase o tramo de la actividad que se reporta (p. ej. limpieza 45 %, acabado 50 %): '
             'cada unidad del tramo vale su % del pago.')
    possible_duplicate = fields.Boolean(
        string='Posible duplicado', compute='_compute_possible_duplicate',
        search='_search_possible_duplicate',
        help='Validación de datos (M15-11): hay otro avance vigente del mismo nivel, actividad, '
             'tramo y fecha; revise que no se pague dos veces.')
    qty_weighted = fields.Float(
        string='Unidades equivalentes', compute='_compute_qty_weighted', store=True,
        digits='Product Unit',
        help='Cantidad × % del tramo: lo que el avance suma a lo ejecutado de la línea.')
    amount = fields.Monetary(
        string='Valor', compute='_compute_amount', store=True, currency_field='currency_id',
        help='Unidades por el costo unitario de la línea del plan: pondera el avance de los '
             'niveles del árbol.')
    qty_planned = fields.Float(
        related='plan_line_id.qty_planned', string='Presupuestado')
    qty_executed = fields.Float(
        related='plan_line_id.qty_executed', string='Acumulado')
    attachment_ids = fields.Many2many(
        'ir.attachment', 'construction_task_progress_attachment_rel', 'progress_id',
        'attachment_id', string='Fotos', copy=False)
    photo_count = fields.Integer(string='Nº de fotos', compute='_compute_photo_count')
    reported_by_id = fields.Many2one(
        'res.users', string='Reportado por', required=True, default=lambda self: self.env.user,
        help='Capataz de la contrata o supervisor que transcribe.')
    # Portal de obra (v1.5, fase 16).
    source = fields.Selection(
        [('internal', 'Planificador'), ('portal', 'Portal de obra')], string='Origen',
        default='internal', required=True, readonly=True, copy=False)
    latitude = fields.Float(string='Latitud', digits=(10, 7), readonly=True, copy=False)
    longitude = fields.Float(string='Longitud', digits=(10, 7), readonly=True, copy=False)
    distance_m = fields.Float(
        string='Distancia a la obra (m)', digits=(12, 1), compute='_compute_distance_m',
        store=True, help='Del lugar donde se reportó a la sede de la obra (si tiene ubicación).')
    state = fields.Selection(
        PROGRESS_STATES, string='Estado', required=True, default='draft', tracking=True,
        copy=False)
    validator_id = fields.Many2one('res.users', string='Validado por', readonly=True, copy=False)
    validation_date = fields.Datetime(string='Fecha de validación', readonly=True, copy=False)
    reject_reason = fields.Text(string='Motivo del rechazo', readonly=True, copy=False)
    # Lo calcula el puente de contratas con la liquidación del avance.
    settled = fields.Boolean(
        string='Liquidado', readonly=True, copy=False,
        help='Entró a una liquidación aprobada: ya no se revierte.')
    period_start = fields.Date(
        string='Semana de liquidación', compute='_compute_period', store=True,
        help='Inicio de la semana a la que pertenece por su fecha de ejecución.')
    settlement_date_planned = fields.Date(
        string='Liquidación prevista', compute='_compute_period', store=True)

    _qty_positive = models.Constraint(
        'CHECK(qty > 0)', 'Las unidades del avance deben ser mayores que cero.')

    @api.depends('task_id', 'activity_id')
    def _compute_plan_line_id(self):
        Line = self.env['construction.resource.plan.line']
        for progress in self:
            if progress.plan_line_id and progress.plan_line_id.task_id == progress.task_id \
                    and progress.plan_line_id.activity_id == progress.activity_id:
                continue
            if not progress.task_id or not progress.activity_id:
                progress.plan_line_id = False
                continue
            progress.plan_line_id = Line.search([
                ('task_id', '=', progress.task_id.id),
                ('activity_id', '=', progress.activity_id.id),
                ('plan_id.state', 'in', OPEN_STATES)], limit=1)

    @api.depends('qty', 'tranche_id.pct')
    def _compute_qty_weighted(self):
        for progress in self:
            factor = progress.tranche_id.pct / 100.0 if progress.tranche_id else 1.0
            progress.qty_weighted = progress.qty * factor

    @api.depends('qty_weighted', 'plan_line_id.price_unit_planned')
    def _compute_amount(self):
        for progress in self:
            currency = progress.currency_id
            amount = progress.qty_weighted * progress.plan_line_id.price_unit_planned
            progress.amount = currency.round(amount) if currency else amount

    @api.depends('attachment_ids')
    def _compute_photo_count(self):
        for progress in self:
            progress.photo_count = len(progress.attachment_ids)

    @api.depends('latitude', 'longitude', 'project_id')
    def _compute_distance_m(self):
        for progress in self:
            progress.distance_m = progress.project_id._construction_distance_m(
                progress.latitude, progress.longitude) if progress.latitude or progress.longitude \
                else 0.0

    @api.depends('date', 'project_id.construction_week_start_day',
                 'project_id.construction_settlement_day')
    def _compute_period(self):
        for progress in self:
            project = progress.project_id
            if not progress.date or not project:
                progress.period_start = progress.settlement_date_planned = False
                continue
            start, _end = project._construction_period(progress.date)
            progress.period_start = start
            progress.settlement_date_planned = project._construction_settlement_dates(start)[0]

    def _duplicate_groups(self, domain=None):
        """Grupos (nivel, actividad, tramo, fecha) con más de un avance
        vigente (no rechazado)."""
        groups = self._read_group(
            [('state', '!=', 'rejected')] + (domain or []),
            groupby=['task_id', 'activity_id', 'tranche_id', 'date:day'],
            aggregates=['id:recordset'], having=[('__count', '>', 1)])
        return [records for *_keys, records in groups]

    @api.depends('task_id', 'activity_id', 'tranche_id', 'date', 'state')
    def _compute_possible_duplicate(self):
        records = self.filtered('id')
        duplicated = self.browse()
        if records:
            for group in self._duplicate_groups([('task_id', 'in', records.task_id.ids)]):
                duplicated |= group
        for progress in self:
            progress.possible_duplicate = progress.state != 'rejected' and progress in duplicated

    def _search_possible_duplicate(self, operator, value):
        if operator not in ('=', '!='):
            return NotImplemented
        ids = [i for group in self._duplicate_groups() for i in group.ids]
        positive = (operator == '=') == bool(value)
        return [('id', 'in' if positive else 'not in', ids)]

    @api.constrains('attachment_ids')
    def _check_photos(self):
        for progress in self:
            if not progress.attachment_ids:
                raise ValidationError(self.env._(
                    'El avance %s necesita al menos una foto.', progress.display_name))

    @api.constrains('task_id', 'activity_id', 'plan_line_id')
    def _check_plan_line(self):
        for progress in self:
            line = progress.plan_line_id
            if line.task_id != progress.task_id or line.activity_id != progress.activity_id:
                raise ValidationError(self.env._(
                    'La actividad %(activity)s no está planificada en %(task)s.',
                    activity=progress.activity_id.display_name,
                    task=progress.task_id.display_name))

    @api.constrains('qty', 'state', 'plan_line_id')
    def _check_balance(self):
        """No acepta más que lo presupuestado más la tolerancia del plan
        (especificación, «Control de saldo»: avance reportado)."""
        lines = self.filtered(lambda p: p.state != 'rejected').plan_line_id
        # Por tramo: cada tramo admite lo presupuestado de la línea.
        totals = {}
        for line, _tranche, qty in self._read_group(
                [('plan_line_id', 'in', lines.ids), ('state', '!=', 'rejected')],
                ['plan_line_id', 'tranche_id'], ['qty:sum']):
            totals[line] = max(totals.get(line, 0.0), qty or 0.0)
        for line in lines:
            reported = totals.get(line, 0.0)
            limit = line.qty_planned + line._get_tolerance_qty()
            if line.product_uom_id.compare(reported, limit) > 0:
                raise ValidationError(self.env._(
                    '%(task)s · %(activity)s: con este avance se reportan %(reported)s de '
                    '%(planned)s %(uom)s presupuestados (tolerancia %(tolerance)s %%).',
                    task=line.task_id.display_name, activity=line.activity_id.display_name,
                    reported=round(reported, 2), planned=round(line.qty_planned, 2),
                    uom=line.product_uom_id.name,
                    tolerance=round(line.plan_id.exceed_tolerance or 0.0, 2)))

    @api.depends('name', 'task_id', 'activity_id')
    def _compute_display_name(self):
        for progress in self:
            progress.display_name = progress.name if progress.name != '/' else self.env._(
                'Avance nuevo')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'construction.task.progress') or '/'
        progresses = super().create(vals_list)
        # La restricción de fotos solo corre si el campo viene en los valores.
        progresses._check_photos()
        for progress in progresses:
            if progress.plan_id.state not in OPEN_STATES:
                raise UserError(self.env._(
                    'El plan %s no está vigente: el avance se reporta sobre el plan aprobado.',
                    progress.plan_id.display_name))
        progresses.plan_line_id._refresh_control()
        return progresses

    def write(self, vals):
        if LOCKED_FIELDS & set(vals) and not self.env.context.get('construction_progress_force'):
            locked = self.filtered(lambda p: p.state != 'draft')
            if locked:
                raise UserError(self.env._(
                    'Solo se corrige un avance reportado; vuelva a reportado %s primero.',
                    ', '.join(locked.mapped('name'))))
        before = self.plan_line_id
        res = super().write(vals)
        # Lo validado es el ejecutado de la línea (estado y control).
        if {'state', 'qty', 'plan_line_id', 'settled'} & set(vals):
            (before | self.plan_line_id)._refresh_control()
        return res

    def unlink(self):
        lines = self.plan_line_id
        res = super().unlink()
        lines._refresh_control()
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        if self.filtered(lambda p: p.state == 'validated'):
            raise UserError(self.env._(
                'Un avance validado no se borra: reviértalo a reportado primero.'))

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def _check_validator(self):
        if not self.env.user.has_group('al_construction_planner.group_planner_planner'):
            raise UserError(self.env._(
                'Valida, rechaza o revierte avances el supervisor de obra (grupo Planificador).'))

    def action_validate(self):
        self._check_validator()
        if self.filtered(lambda p: p.state != 'draft'):
            raise UserError(self.env._('Solo se validan avances reportados.'))
        self.write({'state': 'validated', 'validator_id': self.env.user.id,
                    'validation_date': fields.Datetime.now(), 'reject_reason': False})
        self.task_id._construction_update_unit_state()

    def action_open_reject_wizard(self):
        self._check_validator()
        if self.filtered(lambda p: p.state != 'draft'):
            raise UserError(self.env._('Solo se rechazan avances reportados.'))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Rechazar avance'),
            'res_model': 'construction.reason.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_model': self._name, 'active_ids': self.ids,
                        'construction_reason_action': 'reject'},
        }

    def _action_reject(self, reason):
        self._check_validator()
        self.write({'state': 'rejected', 'reject_reason': reason,
                    'validator_id': self.env.user.id, 'validation_date': fields.Datetime.now()})
        for progress in self:
            progress.message_post(body=self.env._('Rechazado: %s', reason))

    def action_reset(self):
        """Vuelve a reportado: el rechazado para corregirlo y el validado si no
        está liquidado. Si estaba en una liquidación en borrador, sale de ella."""
        self._check_validator()
        settled = self.filtered('settled')
        if settled:
            raise UserError(self.env._(
                'Estos avances ya se liquidaron y no se revierten: %s.',
                ', '.join(settled.mapped('name'))))
        self._construction_check_resettable()
        validated = self.filtered(lambda p: p.state == 'validated')
        self.write(self._construction_reset_values())
        validated.task_id._construction_update_unit_state(revert=True)

    def _construction_check_resettable(self):
        """Gancho: el puente de contratas no deja revertir un avance de una
        liquidación presentada o validada."""

    def _construction_reset_values(self):
        return {'state': 'draft', 'validator_id': False, 'validation_date': False}

    def action_view_photos(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Fotos de %s', self.name),
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', self.attachment_ids.ids)],
            'context': {'create': False},
        }
