# -*- coding: utf-8 -*-
"""Entrega semanal (P-19, fase 10): una por obra y semana, con una línea por
partida del contrato (línea de la OV). El avance de la partida es el
ejecutado valorizado de contratas, personal propio y material consumido
entre el monto planificado de la partida; el ingreso devengado de la semana
es el precio de la partida × (avance al cierre − avance anterior), sin
redondear el avance, y el costo devengado, lo ejecutado en la semana."""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .construction_resource_plan import OPEN_STATES

DELIVERY_STATES = [
    ('draft', 'Borrador'),
    ('confirmed', 'Confirmada'),
    ('valued', 'Valorizada'),
]
# Tipos del ejecutado valorizado (numerador del avance de la partida).
EXECUTION_KINDS = ('contract', 'labor', 'material')


class ConstructionWeeklyDelivery(models.Model):
    _name = 'construction.weekly.delivery'
    _description = 'Entrega semanal de obra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_start desc, project_id'
    _check_company_auto = True

    name = fields.Char(string='Número', required=True, readonly=True, copy=False, default='/')
    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, index=True, check_company=True,
        domain=[('is_construction_site', '=', True)], tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True, store=True,
        compute='_compute_company_id', precompute=True, readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda', store=True)
    sale_order_id = fields.Many2one(
        'sale.order', string='Contrato', check_company=True, readonly=True,
        help='Orden de venta del contrato de la obra al preparar la entrega.')
    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan', check_company=True, readonly=True,
        help='Plan vigente de la obra al preparar la entrega.')
    period_start = fields.Date(string='Inicio de la semana', required=True, tracking=True)
    period_end = fields.Date(
        string='Fin de la semana', compute='_compute_period_end', store=True,
        help='Inicio más seis días.')
    state = fields.Selection(
        DELIVERY_STATES, string='Estado', required=True, default='draft', tracking=True,
        copy=False)
    progress_ids = fields.Many2many(
        'construction.task.progress', 'construction_weekly_delivery_progress_rel',
        'delivery_id', 'progress_id', string='Avances de la semana', readonly=True,
        help='Validados con fecha hasta el cierre de la semana que no entraron en otra entrega '
             'confirmada: un avance validado después de confirmar cae en la siguiente.')
    progress_count = fields.Integer(string='Nº de avances', compute='_compute_progress_count')
    line_ids = fields.One2many(
        'construction.weekly.delivery.line', 'delivery_id', string='Líneas por partida',
        readonly=True)
    cost_contract = fields.Monetary(
        string='Costo de contratas', compute='_compute_amounts', store=True)
    cost_labor = fields.Monetary(
        string='Costo de personal propio', compute='_compute_amounts', store=True)
    cost_material = fields.Monetary(
        string='Costo de materiales', compute='_compute_amounts', store=True)
    cost_amount = fields.Monetary(string='Costo devengado', compute='_compute_amounts', store=True)
    revenue_amount = fields.Monetary(
        string='Ingreso devengado', compute='_compute_amounts', store=True)
    margin_amount = fields.Monetary(string='Margen', compute='_compute_amounts', store=True)
    valuation_id = fields.Many2one(
        'construction.valuation', string='Valorización', readonly=True, copy=False,
        check_company=True, index='btree_not_null', help='La que la incluyó.')
    confirmed_by_id = fields.Many2one(
        'res.users', string='Confirmada por', readonly=True, copy=False)
    date_confirmed = fields.Datetime(string='Confirmada el', readonly=True, copy=False)

    _period_unique = models.UniqueIndex(
        '(project_id, period_start)', 'La obra ya tiene una entrega para esa semana.')

    @api.depends('project_id')
    def _compute_company_id(self):
        for delivery in self:
            delivery.company_id = delivery.project_id.company_id or delivery.company_id \
                or self.env.company

    @api.depends('period_start')
    def _compute_period_end(self):
        for delivery in self:
            delivery.period_end = delivery.period_start and \
                delivery.period_start + timedelta(days=6)

    @api.constrains('period_start', 'project_id')
    def _check_period(self):
        for delivery in self:
            project = delivery.project_id
            start = delivery.period_start
            if start and project and project._construction_period(start)[0] != start:
                days = dict(project._fields['construction_week_start_day']._description_selection(
                    self.env))
                raise ValidationError(self.env._(
                    'La semana de %(project)s empieza el %(day)s.',
                    project=project.display_name,
                    day=days[project.construction_week_start_day].lower()))

    def _compute_progress_count(self):
        for delivery in self:
            delivery.progress_count = len(delivery.progress_ids)

    @api.depends('line_ids.cost_contract', 'line_ids.cost_labor', 'line_ids.cost_material',
                 'line_ids.revenue_amount')
    def _compute_amounts(self):
        for delivery in self:
            lines = delivery.line_ids
            delivery.cost_contract = sum(lines.mapped('cost_contract'))
            delivery.cost_labor = sum(lines.mapped('cost_labor'))
            delivery.cost_material = sum(lines.mapped('cost_material'))
            delivery.cost_amount = sum(lines.mapped('cost_amount'))
            delivery.revenue_amount = sum(lines.mapped('revenue_amount'))
            delivery.margin_amount = delivery.revenue_amount - delivery.cost_amount

    @api.depends('name', 'period_start', 'period_end')
    def _compute_display_name(self):
        for delivery in self:
            delivery.display_name = delivery.name if delivery.name != '/' else \
                self.env._('Entrega nueva')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'construction.weekly.delivery') or '/'
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        if self.filtered(lambda d: d.state != 'draft'):
            raise UserError(self.env._('Solo se borran entregas semanales en borrador.'))

    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    def _get_previous(self):
        """La entrega anterior de la obra (la de la semana más reciente antes
        de esta): su avance al cierre es el avance anterior de esta."""
        self.ensure_one()
        return self.search([('project_id', '=', self.project_id.id),
                            ('period_start', '<', self.period_start)],
                           order='period_start desc', limit=1)

    def _get_progress_domain(self):
        """Avances que entran: validados de la obra con fecha hasta el cierre
        que no están en otra entrega confirmada o valorizada."""
        self.ensure_one()
        taken = self.search([('project_id', '=', self.project_id.id), ('id', '!=', self.id),
                             ('state', '!=', 'draft')]).progress_ids
        return [('project_id', '=', self.project_id.id), ('state', '=', 'validated'),
                ('date', '<=', self.period_end), ('id', 'not in', taken.ids)]

    def _refresh_lines(self):
        """Recalcula las líneas por partida con lo ejecutado hasta el cierre
        de la semana. El avance anterior es el de la entrega previa."""
        for delivery in self:
            project = delivery.project_id
            plan = project._construction_current_plan()
            order = project.construction_sale_order_id
            if not order:
                raise UserError(self.env._(
                    'La obra %s no tiene orden de venta del contrato (pestaña «Calendario e '
                    'ingresos»).', project.display_name))
            lines_by_partida = project._construction_lines_by_partida(plan)
            all_lines = self.env['construction.resource.plan.line'].union(
                *lines_by_partida.values())
            execution = all_lines._construction_valued_execution(delivery.period_end)
            previous = {line.sale_line_id: line for line in delivery._get_previous().line_ids}
            commands = [fields.Command.clear()]
            for sale_line, plan_lines in lines_by_partida.items():
                prev = previous.get(sale_line)
                vals = {
                    'sale_line_id': sale_line.id,
                    'price': sale_line._construction_price(delivery.period_end),
                    'amount_planned': sum(plan_lines.mapped('amount_planned')),
                    'progress_prev': prev.progress_end if prev else 0.0,
                }
                for kind in EXECUTION_KINDS:
                    vals[f'executed_{kind}_end'] = sum(
                        execution[line][kind] for line in plan_lines)
                    vals[f'executed_{kind}_prev'] = prev[f'executed_{kind}_end'] if prev else 0.0
                commands.append(fields.Command.create(vals))
            progresses = self.env['construction.task.progress'].search(
                delivery._get_progress_domain())
            delivery.write({
                'line_ids': commands,
                'plan_id': plan.id,
                'sale_order_id': order.id,
                'progress_ids': [fields.Command.set(progresses.ids)],
            })

    @api.model
    def _prepare_deliveries(self, today=None, projects=None):
        """En el día de liquidación de cada obra con contrato y plan vigente,
        crea en borrador la entrega de la semana que cerró (o la actualiza si
        sigue en borrador). Corre con la acción programada de las
        liquidaciones."""
        today = today or fields.Date.context_today(self)
        if projects is None:
            projects = self.env['project.project'].search([
                ('is_construction_site', '=', True), ('construction_sale_order_id', '!=', False)])
        created = self.browse()
        for project in projects:
            if not project.construction_sale_order_id or not self.env[
                    'construction.resource.plan'].search_count([
                    ('project_id', '=', project.id), ('state', 'in', OPEN_STATES)], limit=1):
                continue
            current_start, _end = project._construction_period(today)
            start = current_start - timedelta(days=7)
            if project._construction_settlement_dates(start)[0] > today:
                continue
            delivery = self.search([('project_id', '=', project.id),
                                    ('period_start', '=', start)], limit=1)
            if delivery and delivery.state != 'draft':
                continue
            if not delivery:
                delivery = self.create({'project_id': project.id, 'period_start': start})
                created |= delivery
            delivery._refresh_lines()
            if delivery in created:
                delivery.message_post(body=self.env._(
                    'Entrega preparada por la acción programada del día de liquidación.'))
        return created

    # ------------------------------------------------------------------
    # Estados
    # ------------------------------------------------------------------
    def _check_manager(self):
        if not self.env.user.has_group('al_construction_planner.group_planner_manager'):
            raise UserError(self.env._(
                'Confirma o reabre la entrega semanal la Jefatura de Proyectos (grupo '
                'Administrador).'))

    def action_refresh(self):
        if self.filtered(lambda d: d.state != 'draft'):
            raise UserError(self.env._('Solo se actualizan entregas en borrador.'))
        self._refresh_lines()

    def action_confirm(self):
        self._check_manager()
        for delivery in self.sorted('period_start'):
            if delivery.state != 'draft':
                raise UserError(self.env._(
                    'La entrega %s no está en borrador.', delivery.display_name))
            earlier = self.search([('project_id', '=', delivery.project_id.id),
                                   ('period_start', '<', delivery.period_start),
                                   ('state', '=', 'draft')])
            if earlier:
                raise UserError(self.env._(
                    'Confirme primero las entregas anteriores de la obra: %s.',
                    ', '.join(earlier.mapped('name'))))
            # Lo confirmado fija el ingreso y el costo: se recalcula una
            # última vez con lo validado hasta ahora.
            delivery._refresh_lines()
            delivery.write({'state': 'confirmed', 'confirmed_by_id': self.env.user.id,
                            'date_confirmed': fields.Datetime.now()})

    def action_draft(self):
        """Reabre una entrega confirmada que no entró a una valorización y
        sin entregas posteriores confirmadas."""
        self._check_manager()
        for delivery in self:
            if delivery.state != 'confirmed' or delivery.valuation_id:
                raise UserError(self.env._(
                    'La entrega %s ya está en una valorización o no está confirmada.',
                    delivery.display_name))
            later = self.search([('project_id', '=', delivery.project_id.id),
                                 ('period_start', '>', delivery.period_start),
                                 ('state', '!=', 'draft')])
            if later:
                raise UserError(self.env._(
                    'Reabra primero las entregas posteriores de la obra: %s.',
                    ', '.join(later.mapped('name'))))
        self.write({'state': 'draft', 'confirmed_by_id': False, 'date_confirmed': False})

    def action_view_progress(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Avances de %s', self.display_name),
            'res_model': 'construction.task.progress',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.progress_ids.ids)],
            'context': {'create': False},
        }


class ConstructionWeeklyDeliveryLine(models.Model):
    _name = 'construction.weekly.delivery.line'
    _description = 'Línea de la entrega semanal (partida)'
    _order = 'delivery_id, sale_line_id'
    _check_company_auto = True

    delivery_id = fields.Many2one(
        'construction.weekly.delivery', string='Entrega', required=True, ondelete='cascade',
        index=True, check_company=True)
    company_id = fields.Many2one(
        related='delivery_id.company_id', string='Compañía', store=True, index=True)
    currency_id = fields.Many2one(related='delivery_id.currency_id', string='Moneda')
    period_start = fields.Date(related='delivery_id.period_start', string='Semana', store=True)
    sale_line_id = fields.Many2one(
        'sale.order.line', string='Partida del contrato', required=True, index=True,
        check_company=True)
    price = fields.Monetary(string='Precio de la partida')
    amount_planned = fields.Monetary(
        string='Monto planificado', help='Suma de las líneas del plan de la partida.')
    # El avance se guarda sin redondear (especificación: «el sistema calcula
    # con el avance sin redondear»).
    progress_prev = fields.Float(string='Avance anterior')
    progress_end = fields.Float(
        string='Avance al cierre', compute='_compute_progress', store=True,
        help='(Contratas y personal propio ejecutados a tarifa + material consumido a costo '
             'del plan) ÷ monto planificado de la partida.')
    progress_period = fields.Float(
        string='Del periodo', compute='_compute_progress', store=True)
    executed_contract_prev = fields.Monetary(string='Contratas ejecutadas antes')
    executed_labor_prev = fields.Monetary(string='Personal propio ejecutado antes')
    executed_material_prev = fields.Monetary(string='Material consumido antes')
    executed_contract_end = fields.Monetary(string='Contratas ejecutadas al cierre')
    executed_labor_end = fields.Monetary(string='Personal propio ejecutado al cierre')
    executed_material_end = fields.Monetary(string='Material consumido al cierre')
    cost_contract = fields.Monetary(
        string='Costo de contratas', compute='_compute_progress', store=True)
    cost_labor = fields.Monetary(
        string='Costo de personal propio', compute='_compute_progress', store=True)
    cost_material = fields.Monetary(
        string='Costo de materiales', compute='_compute_progress', store=True)
    cost_amount = fields.Monetary(
        string='Costo devengado', compute='_compute_progress', store=True,
        help='Contratas y personal propio ejecutados en la semana más los materiales '
             'consumidos de la partida.')
    revenue_amount = fields.Monetary(
        string='Ingreso devengado', compute='_compute_progress', store=True,
        help='Precio de la partida × (avance al cierre − avance anterior).')
    margin_amount = fields.Monetary(string='Margen', compute='_compute_progress', store=True)

    @api.depends('price', 'amount_planned', 'progress_prev', 'executed_contract_prev',
                 'executed_labor_prev', 'executed_material_prev', 'executed_contract_end',
                 'executed_labor_end', 'executed_material_end')
    def _compute_progress(self):
        for line in self:
            executed = line.executed_contract_end + line.executed_labor_end + \
                line.executed_material_end
            planned = line.amount_planned
            line.progress_end = executed / planned if planned else 0.0
            line.progress_period = line.progress_end - line.progress_prev
            currency = line.currency_id
            line.cost_contract = line.executed_contract_end - line.executed_contract_prev
            line.cost_labor = line.executed_labor_end - line.executed_labor_prev
            line.cost_material = line.executed_material_end - line.executed_material_prev
            line.cost_amount = line.cost_contract + line.cost_labor + line.cost_material
            revenue = line.price * line.progress_period
            line.revenue_amount = currency.round(revenue) if currency else revenue
            line.margin_amount = line.revenue_amount - line.cost_amount
