# -*- coding: utf-8 -*-
"""Liquidación semanal de contrata (P-08): los avances validados de la
contrata en la obra en una semana de liquidación (jueves a miércoles por
defecto) más los validados de semanas anteriores que no entraron a ninguna.
Cada línea es driver de la semana × tarifa de la línea de la OC de servicio.
Al aprobarse se recibe en la OC y se crea la factura con vencimiento el día
de pago."""
from collections import defaultdict
from datetime import timedelta

from lxml import etree
from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date

from odoo.addons.al_construction_planner.models.common import (
    DRIVER_TYPES, EXEC_USER_GROUP, EXEC_VALIDATOR_GROUP, PROJECT_HEAD_GROUPS,
)
from odoo.addons.al_construction_planner.models.construction_exceed import REWORK_REASONS
from odoo.addons.al_construction_planner.models.construction_resource_plan import OPEN_STATES

SETTLEMENT_STATES = [
    ('draft', 'Borrador'),
    ('submitted', 'Presentada'),
    ('validated', 'Validada'),
    ('approved', 'Aprobada'),
    ('paid', 'Pagada'),
    ('cancel', 'Anulada'),
]
# Estado de pago de la factura que deja la liquidación en «Pagada»: el pago
# conciliado (especificación: «approved → paid: pago del sábado conciliado»).
PAID_STATES = ('paid',)


class ConstructionContractSettlement(models.Model):
    _name = 'construction.contract.settlement'
    _description = 'Liquidación semanal de contrata'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'tier.validation']
    _order = 'period_start desc, project_id, partner_id'
    _check_company_auto = True
    # Aprobación por niveles (jefatura de proyectos) sobre la liquidación
    # validada por el supervisor; la última aprobación recibe en la OC y
    # crea la factura.
    _state_from = ['validated']
    _state_to = ['approved']
    _cancel_state = 'cancel'
    _tier_validation_manual_config = False

    name = fields.Char(string='Número', required=True, readonly=True, copy=False, default='/')
    partner_id = fields.Many2one(
        'res.partner', string='Contrata', required=True, index=True, check_company=True,
        tracking=True)
    project_id = fields.Many2one(
        'project.project', string='Obra', required=True, index=True, check_company=True,
        domain=[('is_construction_site', '=', True)], tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', required=True, index=True, store=True,
        compute='_compute_company_id', precompute=True, readonly=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda', store=True)
    plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan', check_company=True, readonly=True,
        help='Plan vigente de la obra al preparar la liquidación.')
    purchase_order_id = fields.Many2one(
        'purchase.order', string='OC de servicio', check_company=True, readonly=True,
        help='La OC abierta de la contrata en la obra que recibe la liquidación.')
    period_start = fields.Date(string='Inicio del periodo', required=True, tracking=True)
    period_end = fields.Date(
        string='Fin del periodo', compute='_compute_dates', store=True,
        help='Inicio más seis días.')
    settlement_date = fields.Date(
        string='Fecha de liquidación', compute='_compute_dates', store=True,
        help='Primer día de liquidación de la obra después del cierre; si es feriado, el '
             'día hábil anterior.')
    payment_date = fields.Date(
        string='Fecha de pago', compute='_compute_dates', store=True,
        help='Vencimiento de la factura: primer día de pago desde la liquidación; si es '
             'feriado, el día hábil anterior.')
    state = fields.Selection(
        SETTLEMENT_STATES, string='Estado', required=True, default='draft', tracking=True,
        copy=False)
    progress_ids = fields.One2many(
        'construction.task.progress', 'settlement_id', string='Avances liquidados',
        readonly=True)
    progress_count = fields.Integer(string='Nº de avances', compute='_compute_progress_count')
    # Solo el porcentaje escrito y su motivo se editan (en la vista).
    line_ids = fields.One2many(
        'construction.contract.settlement.line', 'settlement_id', string='Líneas')
    amount_gross = fields.Monetary(
        string='Bruto', compute='_compute_amounts', store=True, currency_field='currency_id')
    retention_amount = fields.Monetary(
        string='Retención', compute='_compute_amounts', store=True,
        currency_field='currency_id', help='Según el porcentaje de la tarifa de cada línea.')
    amount_discount = fields.Monetary(
        string='Descuento por material extra', compute='_compute_amounts', store=True,
        currency_field='currency_id',
        help='Lo que se descuenta a la contrata (el material extra, con el puente de compras).')
    amount_net = fields.Monetary(
        string='Neto', compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_planned = fields.Monetary(
        string='Presupuestado', compute='_compute_progress', currency_field='currency_id',
        help='Monto planificado de las actividades de la contrata en la obra.')
    progress_pct = fields.Float(
        string='Avance', compute='_compute_progress',
        help='Acumulado valorizado entre presupuestado de las actividades liquidadas.')
    invoice_id = fields.Many2one(
        'account.move', string='Factura', readonly=True, copy=False, check_company=True)
    invoice_payment_state = fields.Selection(
        related='invoice_id.payment_state', string='Estado del pago')
    return_reason = fields.Text(string='Motivo de la devolución', readonly=True, copy=False)
    date_approved = fields.Datetime(string='Aprobada el', readonly=True, copy=False)
    # Pago repetido y porcentaje manual sobre el avance (v1.8, M18-21 y
    # M18-09): la liquidación espera la autorización de la jefatura.
    needs_head_authorization = fields.Boolean(
        string='Espera a la jefatura', compute='_compute_needs_head_authorization',
        help='Tiene un pago repetido (la misma actividad, módulo y unidad ya liquidados) o un '
             'porcentaje manual por encima del avance validado.')
    head_authorized_by = fields.Many2one('res.users', string='Autorizada por', readonly=True,
                                         copy=False, tracking=True)
    head_authorized_on = fields.Datetime(string='Autorizada el', readonly=True, copy=False)

    # Una por contrata, obra y semana; con condiciones, una por orden y
    # periodo (CREVAL v1.0, 3.5).
    _period_order_unique = models.UniqueIndex(
        '(partner_id, project_id, period_start, COALESCE(purchase_order_id, 0)) '
        'WHERE state != \'cancel\' AND settlement_type = \'periodic\'',
        'Ya hay una valorización de esta orden (o de esta contrata en la obra) para ese periodo.')

    @api.depends('project_id')
    def _compute_company_id(self):
        for settlement in self:
            settlement.company_id = settlement.project_id.company_id or settlement.company_id \
                or self.env.company

    @api.depends('period_start', 'project_id.construction_week_start_day',
                 'project_id.construction_settlement_day', 'project_id.construction_payment_day')
    def _compute_dates(self):
        for settlement in self:
            start = settlement.period_start
            if not start or not settlement.project_id:
                settlement.period_end = settlement.settlement_date = False
                settlement.payment_date = False
                continue
            settlement.period_end = start + timedelta(days=6)
            dates = settlement.project_id._construction_settlement_dates(start)
            settlement.settlement_date, settlement.payment_date = dates

    @api.constrains('period_start', 'project_id')
    def _check_period(self):
        for settlement in self:
            project = settlement.project_id
            start = settlement.period_start
            if start and project and project._construction_period(start)[0] != start:
                days = dict(project._fields['construction_week_start_day']._description_selection(
                    self.env))
                raise ValidationError(self.env._(
                    'La semana de liquidación de %(project)s empieza el %(day)s.',
                    project=project.display_name,
                    day=days[project.construction_week_start_day].lower()))

    @api.depends('line_ids.is_repeat', 'line_ids.manual_over', 'head_authorized_by')
    def _compute_needs_head_authorization(self):
        for settlement in self:
            settlement.needs_head_authorization = not settlement.head_authorized_by and any(
                line.is_repeat or line.manual_over for line in settlement.line_ids)

    def _compute_progress_count(self):
        counts = dict(self.env['construction.task.progress']._read_group(
            [('settlement_id', 'in', self.ids)], ['settlement_id'], ['__count']))
        for settlement in self:
            settlement.progress_count = counts.get(settlement, 0)

    @api.depends('line_ids.amount', 'line_ids.retention_pct')
    def _compute_amounts(self):
        for settlement in self:
            currency = settlement.currency_id
            gross = sum(settlement.line_ids.mapped('amount'))
            # La retención se calcula sobre el total de cada porcentaje (no
            # por línea) para no acumular redondeos: 10 % de 380.88 = 38.09.
            by_pct = defaultdict(float)
            for line in settlement.line_ids:
                by_pct[line.retention_pct] += line.amount
            retention = sum(currency.round(amount * pct / 100.0) for pct, amount in by_pct.items())
            discount = settlement._get_discount_amount()
            settlement.amount_gross = gross
            settlement.retention_amount = retention
            settlement.amount_discount = discount
            settlement.amount_net = gross - retention - discount

    def _compute_progress(self):
        for settlement in self:
            planned = executed = 0.0
            for line in settlement.line_ids:
                lines = line._get_plan_lines()
                planned += sum(lines.mapped('amount_planned'))
                executed += sum(l.qty_executed * l.price_unit_planned for l in lines)
            settlement.amount_planned = planned
            settlement.progress_pct = executed / planned if planned else 0.0

    @api.depends('name', 'partner_id')
    def _compute_display_name(self):
        for settlement in self:
            settlement.display_name = settlement.name if settlement.name != '/' else \
                self.env._('Liquidación nueva')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'construction.contract.settlement') or '/'
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        if self.filtered(lambda s: s.state not in ('draft', 'cancel')):
            raise UserError(self.env._('Solo se borran liquidaciones en borrador o anuladas.'))

    def unlink(self):
        self.progress_ids.write({'settlement_id': False})
        return super().unlink()

    # ------------------------------------------------------------------
    # Avances y líneas
    # ------------------------------------------------------------------
    def _get_progress_domain(self):
        """Avances que entran: validados de la contrata en la obra hasta el fin
        del periodo y aún sin liquidación (o en una anulada)."""
        self.ensure_one()
        return [
            ('project_id', '=', self.project_id.id),
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'validated'),
            ('date', '<=', self.period_end),
            '|', '|', ('settlement_id', '=', False), ('settlement_id.state', '=', 'cancel'),
            ('settlement_id', '=', self.id),
        ]

    @staticmethod
    def _get_service_line(progress):
        """Línea de la OC de servicio de la contrata para el avance: la de la
        asignación de su línea del plan."""
        allocations = progress.plan_line_id.allocation_ids.filtered(
            lambda a: a.kind == 'service_order' and a.state != 'cancel'
            and a.purchase_line_id.partner_id.commercial_partner_id
            == progress.partner_id.commercial_partner_id)
        return allocations[:1].purchase_line_id

    def _refresh_lines(self):
        """Toma los avances del periodo (más rezagados) y rehace las líneas:
        una por línea de la OC (actividad y tarifa). Solo en borrador."""
        Progress = self.env['construction.task.progress']
        for settlement in self.filtered(lambda s: s.state == 'draft'):
            # La OC de servicio se lee aunque quien prepara la liquidación no
            # tenga acceso a compras: solo para enlazar la línea y su tarifa.
            progresses_sudo = Progress.sudo().search(settlement._get_progress_domain())
            # Una línea por línea de la OC y, aparte, el re-trabajo con su
            # motivo (v1.8, M18-21).
            by_po_line = defaultdict(lambda: Progress.sudo())
            orphans = Progress.sudo()
            for progress in progresses_sudo:
                po_line = self._get_service_line(progress)
                # Los avances de una orden con condiciones van a la
                # valorización de esa orden (CREVAL v1.0, 3.5).
                if po_line.order_id.construction_uses_terms:
                    continue
                if po_line:
                    key = (po_line, progress.is_rework, progress.rework_reason or False)
                    by_po_line[key] |= progress
                else:
                    orphans |= progress
            included = Progress.sudo().union(*by_po_line.values()) if by_po_line \
                else Progress.sudo()
            settlement_sudo = settlement.sudo()
            (settlement_sudo.progress_ids - included).write({'settlement_id': False})
            included.write({'settlement_id': settlement.id})
            vals_list = []
            for (po_line, is_rework, rework_reason), progresses in sorted(
                    by_po_line.items(), key=lambda kv: (kv[0][0].sequence, kv[0][0].id,
                                                        kv[0][1], kv[0][2] or '')):
                activity = progresses.activity_id[:1]
                qty = sum(progresses.mapped('qty_weighted'))
                repeat = 0.0 if is_rework else settlement._repeat_qty(progresses)
                if po_line.uom_id and activity.uom_id \
                        and po_line.uom_id != activity.uom_id:
                    qty = activity.uom_id._compute_quantity(qty, po_line.uom_id)
                    repeat = activity.uom_id._compute_quantity(repeat, po_line.uom_id)
                vals_list.append({
                    'activity_id': activity.id,
                    'purchase_line_id': po_line.id,
                    'qty_period': qty,
                    'price_unit': po_line.price_unit,
                    'retention_pct': po_line.construction_retention_pct,
                    'is_rework': is_rework,
                    'rework_reason': rework_reason,
                    'qty_repeat': repeat,
                })
            po_lines = [key[0] for key in by_po_line]
            orders = Progress.env['purchase.order.line'].union(*po_lines).order_id \
                if po_lines else self.env['purchase.order']
            settlement._construction_refresh_discounts()
            settlement._sync_lines(vals_list)
            settlement_sudo.write({
                'purchase_order_id': orders.sorted('id', reverse=True)[:1].id
                or settlement.purchase_order_id.id,
                'plan_id': settlement.project_id._construction_current_plan().id,
            })
            if orphans:
                settlement.message_post(body=self.env._(
                    'Avances validados sin OC de servicio de la contrata (asigne la contrata '
                    'con «Asignar contrata»): %s.', ', '.join(orphans.mapped('name'))))

    def _sync_lines(self, vals_list):
        """Actualiza las líneas por su clave (línea de la OC, re-trabajo y su
        motivo) en vez de rehacerlas, para no perder las decisiones del
        validador (CREVAL, CR-15). La línea que se queda sin avances se borra,
        salvo que tenga una decisión: queda en 0 y con aviso."""
        self.ensure_one()
        # sudo: como al rehacer las líneas, quien prepara la valorización no
        # siempre puede escribirlas (lo controla el estado del documento).
        lines_sudo = self.sudo().line_ids
        existing = {}
        for line in lines_sudo:
            existing.setdefault(line._sync_key(), line)
        kept = lines_sudo.browse()
        to_create = []
        for vals in vals_list:
            line = existing.pop((vals['purchase_line_id'], vals['is_rework'],
                                 vals['rework_reason'] or False), None)
            if line:
                line.write(dict(vals, no_progress=False))
                kept |= line
            else:
                to_create.append(vals)
        leftover = lines_sudo - kept
        decided = leftover.filtered(lambda l: l._construction_has_decision())
        (leftover - decided).unlink()
        orphan_vals = {'qty_period': 0.0, 'qty_repeat': 0.0, 'no_progress': True}
        if 'progress_ids' in decided._fields:
            orphan_vals['progress_ids'] = [Command.clear()]
        decided.write(orphan_vals)
        (kept | decided)._sync_refresh()
        if to_create:
            self.sudo().write({'line_ids': [Command.create(vals) for vals in to_create]})

    def _repeat_qty(self, progresses):
        """Cantidad de ``progresses`` (no re-trabajo) que repite lo ya liquidado:
        la misma actividad en el mismo nivel (módulo, unidad) ya entró en otra
        liquidación por lo presupuestado, de esta o de otra contrata (M18-21)."""
        self.ensure_one()
        Progress = self.env['construction.task.progress'].sudo()
        Line = self.env['construction.resource.plan.line'].sudo()
        repeat = 0.0
        for (task, activity), group in progresses.grouped(
                lambda p: (p.task_id, p.activity_id)).items():
            plan = group.plan_line_id.plan_id[:1]
            planned = sum(Line.search([
                ('plan_id', '=', plan.id), ('task_id', '=', task.id),
                ('activity_id', '=', activity.id)]).mapped('qty_planned'))
            before = sum(Progress.search([
                ('task_id', '=', task.id), ('activity_id', '=', activity.id),
                ('is_rework', '=', False), ('state', '=', 'validated'),
                ('settlement_id', '!=', False), ('settlement_id', '!=', self.id),
                ('settlement_id.state', '!=', 'cancel')]).mapped('qty_weighted'))
            current = sum(group.mapped('qty_weighted'))
            over = before + current - planned
            uom = activity.uom_id
            if uom and uom.compare(over, 0.0) > 0:
                repeat += min(over, current)
        return repeat

    def action_head_authorize(self):
        """La jefatura autoriza el pago repetido y el porcentaje manual sobre
        el avance validado; cada uno queda registrado."""
        if not self.env.user.has_groups(PROJECT_HEAD_GROUPS):
            raise UserError(self.env._('Autoriza la jefatura de proyectos.'))
        Log = self.env['construction.exceed.log']
        for settlement in self.filtered('needs_head_authorization'):
            values = []
            for line in settlement.line_ids.filtered(lambda l: l.is_repeat or l.manual_over):
                plan_line = line._get_plan_lines()[:1]
                base = {
                    'plan_id': settlement.plan_id.id, 'project_id': settlement.project_id.id,
                    'company_id': settlement.company_id.id, 'plan_line_id': plan_line.id,
                    'task_id': plan_line.task_id.id, 'activity_id': line.activity_id.id,
                    'partner_id': settlement.partner_id.id, 'uom_id': line.uom_id.id,
                    'document': settlement.name, 'res_model': settlement._name,
                    'res_id': settlement.id,
                }
                if line.is_repeat:
                    values.append(dict(base, kind='repeat_payment', qty=line.qty_repeat,
                                       amount=line.qty_repeat * line.price_unit,
                                       reason=self.env._('Pago repetido autorizado')))
                if line.manual_over:
                    extra = line.qty_settle - line.qty_period
                    values.append(dict(base, kind='manual_pct', qty=extra,
                                       amount=extra * line.price_unit,
                                       reason=line.manual_reason))
            Log._log(values)
            settlement.write({'head_authorized_by': self.env.user.id,
                              'head_authorized_on': fields.Datetime.now()})
            settlement.message_post(body=self.env._(
                'Autorizada por la jefatura: pagos repetidos y porcentajes manuales sobre el '
                'avance validado.'))
        return True

    def action_refresh(self):
        if self.filtered(lambda s: s.state != 'draft'):
            raise UserError(self.env._('Solo se actualizan liquidaciones en borrador.'))
        self._refresh_lines()

    def _get_discount_amount(self):
        """Descuentos a la contrata en esta liquidación (gancho)."""
        self.ensure_one()
        return 0.0

    def _construction_refresh_discounts(self):
        """Toma los descuentos pendientes de la contrata en la obra (gancho)."""
        self.ensure_one()

    def _invoice_discount_line_values(self):
        """Líneas negativas de los descuentos en la factura (gancho)."""
        self.ensure_one()
        return []

    def _construction_release_discounts(self):
        """Libera los descuentos al anular la liquidación (gancho)."""

    @api.model
    def _prepare_settlements(self, today=None, projects=None):
        """Crea (o actualiza, si siguen en borrador) las liquidaciones de toda
        contrata con avances validados por liquidar, en el día de liquidación
        de cada obra. Los reportados sin validar esperan a la semana
        siguiente; los validados tarde entran como rezagados."""
        today = today or fields.Date.context_today(self)
        Progress = self.env['construction.task.progress']
        domain = [('state', '=', 'validated'), ('partner_id', '!=', False),
                  '|', ('settlement_id', '=', False), ('settlement_id.state', '=', 'cancel')]
        if projects is not None:
            domain.append(('project_id', 'in', projects.ids))
        pending = Progress._read_group(domain, ['project_id', 'partner_id'])
        created = self.browse()
        for project, partner in pending:
            current_start, _end = project._construction_period(today)
            for start in (current_start - timedelta(days=7), current_start):
                settlement_date = project._construction_settlement_dates(start)[0]
                if settlement_date > today:
                    continue
                if not Progress.search_count(domain + [
                        ('project_id', '=', project.id), ('partner_id', '=', partner.id),
                        ('date', '<=', start + timedelta(days=6))], limit=1):
                    continue
                settlement = self.search([
                    ('partner_id', '=', partner.id), ('project_id', '=', project.id),
                    ('period_start', '=', start), ('state', '!=', 'cancel')], limit=1)
                if settlement.state and settlement.state != 'draft':
                    continue
                if not settlement:
                    settlement = self.create({
                        'partner_id': partner.id, 'project_id': project.id,
                        'period_start': start})
                    created |= settlement
                settlement._refresh_lines()
                if not settlement.line_ids and settlement in created:
                    settlement.unlink()
                    created -= settlement
        return created

    @api.model
    def _cron_prepare_settlements(self):
        self._prepare_settlements()
        self.search([('state', '=', 'approved'), ('invoice_id', '!=', False)])._sync_paid()
        # Ruta del ingreso (fase 10): la entrega semanal se prepara el mismo
        # día de liquidación y la valorización, al pasar el corte de la obra.
        self.env['construction.weekly.delivery']._prepare_deliveries()
        self.env['construction.valuation']._prepare_valuations()

    # ------------------------------------------------------------------
    # Estados
    # ------------------------------------------------------------------
    def _check_state(self, states):
        labels = dict(SETTLEMENT_STATES)
        for settlement in self:
            if settlement.state not in states:
                raise UserError(self.env._(
                    'La liquidación %(name)s está %(state)s: no admite esta acción.',
                    name=settlement.display_name, state=labels[settlement.state].lower()))

    def _check_supervisor(self):
        if not self.env.user.has_group(EXEC_VALIDATOR_GROUP):
            raise UserError(self.env._(
                'Valida, devuelve o anula la valorización quien valida la ejecución (grupo '
                'Ejecución: valida).'))

    def _check_preparer(self):
        if not self.env.user.has_group(EXEC_USER_GROUP):
            raise UserError(self.env._(
                'Prepara y presenta la valorización quien ejecuta (grupo Ejecución: ejecuta).'))

    def action_submit(self):
        self._check_preparer()
        self._check_state(('draft',))
        for settlement in self:
            if not settlement.line_ids:
                raise UserError(self.env._(
                    'La liquidación %s no tiene líneas: actualice sus avances.',
                    settlement.display_name))
        self.write({'state': 'submitted', 'return_reason': False})
        self.filtered('needs_head_authorization')._notify_heads()

    def _notify_heads(self):
        """Actividad para la jefatura de proyectos: hay algo que autorizar."""
        group = self.env.ref('al_construction_planner.group_planner_exec_approver',
                             raise_if_not_found=False)
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for settlement in self:
            users = group.sudo().all_user_ids.filtered(
                lambda u: not u.share and settlement.company_id in u.company_ids) if group else []
            for user in users[:1]:
                settlement.activity_schedule(
                    activity_type_id=activity_type.id if activity_type else False,
                    summary=self.env._('Autorizar la liquidación'), user_id=user.id,
                    note=self.env._('Tiene pagos repetidos o porcentajes manuales sobre el avance '
                                    'validado.'))

    def action_open_return_wizard(self):
        self._check_supervisor()
        self._check_state(('submitted',))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Devolver a la contrata'),
            'res_model': 'construction.reason.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_model': self._name, 'active_ids': self.ids,
                        'construction_reason_action': 'return'},
        }

    def _action_return(self, reason):
        self._check_supervisor()
        self._check_state(('submitted',))
        self.write({'state': 'draft', 'return_reason': reason})
        for settlement in self:
            settlement.message_post(body=self.env._('Devuelta a la contrata: %s', reason))

    def action_validate(self):
        """El supervisor valida las cantidades; siguen las revisiones de la
        jefatura (tier validation). Sin reglas que apliquen, se aprueba. Con
        un pago repetido o un porcentaje manual sobre el avance validado,
        espera la autorización de la jefatura (M18-21, M18-09)."""
        self._check_supervisor()
        self._check_state(('submitted',))
        waiting = self.filtered('needs_head_authorization')
        if waiting:
            raise UserError(self.env._(
                'La liquidación %s tiene pagos repetidos o porcentajes manuales sobre el avance '
                'validado: espera la autorización de la jefatura de proyectos.',
                ', '.join(waiting.mapped('display_name'))))
        self.write({'state': 'validated'})
        for settlement in self:
            reviews = settlement.request_validation() if settlement.need_validation else False
            if not reviews:
                settlement._action_approve()

    def _validate_tier(self, tiers=False):
        res = super()._validate_tier(tiers)
        if not self.env.context.get('al_construction_approving'):
            for settlement in self:
                if settlement.state == 'validated' and settlement.validation_status == 'validated':
                    settlement._action_approve()
        return res

    def _rejected_tier(self, tiers=False):
        res = super()._rejected_tier(tiers)
        for settlement in self:
            if settlement.state == 'validated' and settlement.validation_status == 'rejected':
                # Lo escribe el revisor, que no puede editar la liquidación en
                # revisión: se omite ese control solo para el estado.
                settlement.with_context(skip_validation_check=True).write({'state': 'submitted'})
                settlement.message_post(body=self.env._(
                    'Rechazada por la jefatura: vuelve a presentada.'))
        return res

    def _action_approve(self):
        """Última aprobación: recibe en la OC de servicio lo de la semana y
        crea la factura con vencimiento el día de pago."""
        # need_validation no tiene depends: su caché conserva el valor de
        # antes de las revisiones.
        self.invalidate_recordset(['need_validation', 'review_ids', 'validation_status'])
        for settlement in self:
            # sudo: quien aprueba (jefatura de proyectos) no suele tener
            # permisos de compras ni de contabilidad; la recepción y la factura
            # son la consecuencia de su aprobación y salen de la liquidación.
            settlement_sudo = settlement.sudo()
            settlement_sudo._receive_on_purchase_order()
            invoice_sudo = settlement_sudo._create_invoice()
            settlement.with_context(al_construction_approving=True).write({
                'state': 'approved',
                'invoice_id': invoice_sudo.id,
                'date_approved': fields.Datetime.now(),
            })
            settlement._log_rework()
            settlement.message_post(body=Markup(self.env._(
                'Aprobada: recibido en %(order)s y factura %(invoice)s con vencimiento el '
                '%(due)s.')) % {
                    'order': settlement_sudo.purchase_order_id.name,
                    'invoice': invoice_sudo._get_html_link(),
                    'due': fields.Date.to_string(settlement.payment_date)})
            if settlement.plan_id:
                settlement.plan_id._mark_in_progress()

    def _log_rework(self):
        """El re-trabajo liquidado queda separado en el análisis (M18-21)."""
        self.ensure_one()
        values = []
        for line in self.line_ids.filtered('is_rework'):
            plan_line = line._get_plan_lines()[:1]
            values.append({
                'kind': 'rework', 'plan_id': self.plan_id.id, 'project_id': self.project_id.id,
                'company_id': self.company_id.id, 'plan_line_id': plan_line.id,
                'task_id': plan_line.task_id.id, 'activity_id': line.activity_id.id,
                'partner_id': self.partner_id.id, 'qty': line.qty_period,
                'uom_id': line.uom_id.id, 'amount': line.amount,
                'rework_reason': line.rework_reason,
                'reason': dict(REWORK_REASONS).get(line.rework_reason),
                'document': self.name, 'res_model': self._name, 'res_id': self.id,
            })
        if values:
            self.env['construction.exceed.log']._log(values)

    def _receive_on_purchase_order(self):
        """Suma lo de la semana a lo recibido de cada línea de la OC (recepción
        manual de servicios). No deja recibir más que lo ordenado. El
        re-trabajo y lo repetido autorizado se facturan sin recibirse: están
        fuera del alcance de la OC."""
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: not l.is_rework)
        orders = lines.purchase_line_id.order_id
        not_confirmed = orders.filtered(lambda o: o.state != 'purchase')
        if not_confirmed:
            raise UserError(self.env._(
                'Confirme la OC de servicio %s antes de aprobar la liquidación.',
                ', '.join(not_confirmed.mapped('name'))))
        for line in lines:
            po_line = line.purchase_line_id
            received = po_line.qty_received + line._qty_to_receive()
            if po_line.uom_id.compare(received, po_line.product_qty) > 0:
                raise UserError(self.env._(
                    '%(activity)s: con esta liquidación se recibirían %(received)s de '
                    '%(ordered)s %(uom)s ordenados en %(order)s. Amplíe la OC (Asignar '
                    'contrata) o corrija los avances.', activity=line.activity_id.display_name,
                    received=round(received, 2), ordered=round(po_line.product_qty, 2),
                    uom=po_line.uom_id.name, order=po_line.order_id.name))
        for line in lines:
            line.purchase_line_id.qty_received += line._qty_to_receive()

    def _create_invoice(self):
        """Factura de proveedor desde lo recibido de la semana, con
        vencimiento el día de pago (sin plazo de pago, que lo recalcularía).
        Si la compañía tiene cuenta de retención, una línea negativa deja el
        total en el neto."""
        self.ensure_one()
        order = self.purchase_order_id or self.line_ids.purchase_line_id.order_id[:1]
        vals = order.with_company(self.company_id)._prepare_invoice()
        vals.update({
            'invoice_payment_term_id': False,
            'invoice_date_due': self.payment_date,
            'ref': self.name,
            'invoice_origin': '%s, %s' % (order.name, self.name),
        })
        invoice = self.env['account.move'].with_company(self.company_id).with_context(
            default_move_type='in_invoice').create(vals)
        line_vals = []
        for line in self.line_ids.filtered(lambda l: not l.is_rework or l.rework_paid):
            values = line.purchase_line_id._prepare_account_move_line(invoice)
            values['quantity'] = line.qty_settle
            if line.is_rework:
                values['name'] = self.env._('Re-trabajo (%(reason)s): %(name)s',
                                            reason=dict(REWORK_REASONS).get(line.rework_reason, ''),
                                            name=values.get('name') or line.activity_id.name)
            line_vals.append(values)
        invoice.write({'invoice_line_ids': [Command.create(v) for v in line_vals]})
        # Las líneas negativas van en otra escritura: si todas las líneas
        # nuevas carecen de impuestos y alguna ya trae importe (las de la OC),
        # la sincronización de v19 no recalcula el asiento y una línea sin
        # producto queda con importe 0 (_sync_tax_lines).
        line_vals = []
        account = self.company_id.construction_retention_account_id
        if account and not self.currency_id.is_zero(self.retention_amount):
            line_vals.append({
                'display_type': 'product',
                'name': self.env._('Retención de la liquidación %s', self.name),
                'account_id': account.id,
                'quantity': 1.0,
                'price_unit': -self.retention_amount,
                'tax_ids': [Command.clear()],
            })
        line_vals += self._invoice_discount_line_values()
        if line_vals:
            invoice.write({'invoice_line_ids': [Command.create(v) for v in line_vals]})
        if invoice.invoice_date_due != self.payment_date:
            invoice.invoice_date_due = self.payment_date
        return invoice

    def _sync_paid(self):
        """Aprobada ↔ Pagada según el pago de su factura."""
        for settlement in self:
            paid = settlement.invoice_id.payment_state in PAID_STATES
            if settlement.state == 'approved' and paid:
                settlement.state = 'paid'
            elif settlement.state == 'paid' and not paid:
                settlement.state = 'approved'

    def action_cancel(self):
        self._check_supervisor()
        self._check_state(('draft', 'submitted', 'validated'))
        self.filtered(lambda s: s.state == 'validated').restart_validation()
        self.write({'state': 'cancel'})
        self.progress_ids.write({'settlement_id': False})
        self._construction_release_discounts()

    def action_draft(self):
        self._check_supervisor()
        self._check_state(('cancel',))
        self.write({'state': 'draft', 'return_reason': False})
        self._refresh_lines()

    def action_view_progress(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Avances de %s', self.display_name),
            'res_model': 'construction.task.progress',
            'view_mode': 'list,form',
            'domain': [('settlement_id', '=', self.id)],
            'context': {'create': False},
        }

    def action_view_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }

    def _get_to_validate_message(self):
        # El es.po de base_tier_validation no traduce este aviso.
        icon = Markup('<i class="oi oi-lg oi-filled" data-icon="info"></i>')
        pending = self.review_ids.filtered(lambda r: r.status == 'pending')[:1]
        if pending and pending.todo_by:
            text = self.env._('Pendiente de aprobación por %s', pending.todo_by)
        else:
            text = self.env._('Esta liquidación necesita aprobación')
        return Markup('%s %s') % (icon, text)

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        """Quita los botones OCA «Request/Restart Validation»: las revisiones
        se piden al validar."""
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type == 'form':
            doc = etree.XML(res['arch'])
            for node in doc.xpath(
                    "//button[@name='request_validation' or @name='restart_validation']"):
                node.getparent().remove(node)
            res['arch'] = etree.tostring(doc, encoding='unicode')
        return res


class ConstructionContractSettlementLine(models.Model):
    _name = 'construction.contract.settlement.line'
    _description = 'Línea de liquidación de contrata'
    _order = 'settlement_id, id'
    _check_company_auto = True

    settlement_id = fields.Many2one(
        'construction.contract.settlement', string='Liquidación', required=True,
        ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(
        related='settlement_id.company_id', string='Compañía', store=True, index=True)
    currency_id = fields.Many2one(related='settlement_id.currency_id', string='Moneda')
    activity_id = fields.Many2one(
        'construction.labor.activity', string='Actividad', required=True, check_company=True)
    uom_id = fields.Many2one(related='activity_id.uom_id', string='Unidad')
    purchase_line_id = fields.Many2one(
        'purchase.order.line', string='Línea de la OC', required=True, check_company=True)
    qty_period = fields.Float(string='Driver de la semana', digits='Product Unit')
    # El precio de la orden con sus decimales; el monto se redondea una vez y
    # la factura da lo mismo (CREVAL v1.0, CR-11).
    price_unit = fields.Float(string='Tarifa', digits='Product Price')
    amount = fields.Monetary(
        string='Monto', compute='_compute_amount', store=True, currency_field='currency_id')
    # Re-trabajo y pago repetido (v1.8, M18-21).
    is_rework = fields.Boolean(string='Re-trabajo', readonly=True)
    rework_reason = fields.Selection(REWORK_REASONS, string='Motivo del re-trabajo', readonly=True)
    qty_repeat = fields.Float(
        string='Repetido', digits='Product Unit', readonly=True,
        help='Parte del driver que repite lo ya liquidado de la misma actividad, módulo y '
             'unidad: espera la autorización de la jefatura.')
    is_repeat = fields.Boolean(string='Pago repetido', compute='_compute_is_repeat', store=True)
    # El re-trabajo entra con 0 a liquidar y queda en la revisión; solo se
    # paga si el validador lo decide con motivo (CREVAL v1.0, CR-08).
    rework_paid = fields.Boolean(
        string='Pagar el re-trabajo',
        help='Lo marca quien valida la ejecución, con su motivo. Sin marcar, el re-trabajo no se '
             'paga.')
    rework_pay_reason = fields.Text(string='Motivo del pago del re-trabajo')
    rework_paid_by = fields.Many2one('res.users', string='Pago decidido por', readonly=True)
    # Porcentaje manual (v1.8, M18-09): la línea propone el avance validado y
    # admite otro porcentaje con motivo, marcado como manual.
    pct_validated = fields.Float(
        string='% validado', compute='_compute_cumulative',
        help='Avance validado acumulado de la actividad en la contrata, con esta semana.')
    pct_manual = fields.Float(
        string='% escrito', digits=(5, 2),
        help='Porcentaje acumulado que se liquida en lugar del validado. Pide motivo; si supera '
             'el validado, lo aprueba la jefatura de proyectos.')
    manual_reason = fields.Text(string='Motivo del porcentaje')
    is_manual = fields.Boolean(string='Manual', compute='_compute_qty_settle', store=True)
    manual_user_id = fields.Many2one('res.users', string='Escrito por', readonly=True)
    manual_date = fields.Datetime(string='Escrito el', readonly=True)
    manual_over = fields.Boolean(
        string='Sobre lo validado', compute='_compute_qty_settle', store=True)
    qty_settled_before = fields.Float(
        string='Liquidado antes', digits='Product Unit', readonly=True,
        help='Lo ya liquidado de la actividad en liquidaciones anteriores.')
    qty_settle = fields.Float(
        string='A liquidar', compute='_compute_qty_settle', store=True, digits='Product Unit',
        help='El driver de la semana o, con un porcentaje escrito, lo que lleva el acumulado a '
             'ese porcentaje.')
    retention_pct = fields.Float(string='Retención (%)', digits=(5, 2))
    # Decisión del validador frente al avance (CR-15): «Actualizar avances»
    # la conserva y avisa si el avance cambió desde que se tomó.
    no_progress = fields.Boolean(
        string='Sin avances', readonly=True,
        help='Sus avances ya no están en el periodo; queda en 0 por tener una decisión del '
             'validador.')
    decision_qty = fields.Float(string='Avance al decidir', digits='Product Unit', readonly=True)
    decision_date = fields.Datetime(string='Decidido el', readonly=True)
    decision_warning = fields.Char(
        string='Aviso', compute='_compute_decision_warning', store=True,
        help='El avance cambió desde la decisión del validador: la decisión se mantiene hasta '
             'que la confirme o la quite.')
    qty_cumulative = fields.Float(
        string='Acumulado', compute='_compute_cumulative', digits='Product Unit')
    qty_planned = fields.Float(
        string='Presupuestado', compute='_compute_cumulative', digits='Product Unit')
    progress_pct = fields.Float(string='Avance', compute='_compute_cumulative')

    @api.depends('qty_repeat')
    def _compute_is_repeat(self):
        for line in self:
            line.is_repeat = bool(line.uom_id) and line.uom_id.compare(line.qty_repeat, 0.0) > 0 \
                if line.uom_id else line.qty_repeat > 0

    @api.depends('qty_period', 'pct_manual', 'qty_settled_before', 'is_rework', 'rework_paid',
                 'no_progress')
    def _compute_qty_settle(self):
        for line in self:
            if line.no_progress:
                line.qty_settle = 0.0
                line.is_manual = bool(line.pct_manual)
                line.manual_over = False
                continue
            if line.is_rework or not line.pct_manual:
                line.qty_settle = line.qty_period \
                    if not line.is_rework or line.rework_paid else 0.0
                line.is_manual = False
                line.manual_over = False
                continue
            planned = sum(line._get_plan_lines().mapped('qty_planned'))
            target = planned * line.pct_manual / 100.0 - line.qty_settled_before
            line.qty_settle = max(target, 0.0)
            line.is_manual = True
            uom = line.uom_id
            line.manual_over = bool(uom) and uom.compare(line.qty_settle, line.qty_period) > 0

    def _check_rework_payment(self, vals):
        """Pagar un re-trabajo lo decide quien valida la ejecución, con
        motivo y con la liquidación abierta (CR-08)."""
        if any(not line.is_rework for line in self):
            raise UserError(self.env._('Solo las líneas de re-trabajo se marcan para pagar.'))
        if any(line.settlement_id.state not in ('draft', 'submitted') for line in self):
            raise UserError(self.env._(
                'El pago del re-trabajo se decide con la liquidación en borrador o presentada.'))
        if not self.env.user.has_groups(EXEC_VALIDATOR_GROUP):
            raise UserError(self.env._('Pagar un re-trabajo lo decide quien valida la ejecución.'))
        if vals['rework_paid'] and not (vals.get('rework_pay_reason') or all(
                line.rework_pay_reason for line in self)):
            raise UserError(self.env._('Pagar un re-trabajo pide su motivo.'))
        return dict(vals, rework_paid_by=self.env.user.id if vals['rework_paid'] else False)

    def _sync_key(self):
        self.ensure_one()
        return (self.purchase_line_id.id, self.is_rework, self.rework_reason or False)

    def _construction_has_decision(self):
        """La línea tiene una decisión del validador que se conserva al
        actualizar (gancho: la liquidación agrega la cantidad final)."""
        self.ensure_one()
        return bool(self.rework_paid or self.pct_manual)

    def _sync_refresh(self):
        """Recalcula lo que la línea toma de otras liquidaciones después de
        actualizarla (al crearla lo hace ``create``)."""
        self._set_settled_before()

    @api.depends('qty_period', 'decision_qty', 'decision_date', 'no_progress')
    def _compute_decision_warning(self):
        for line in self:
            warning = False
            if line.decision_date and line._construction_has_decision():
                date = format_date(self.env, line.decision_date)
                uom = line.purchase_line_id.uom_id
                if line.no_progress:
                    warning = self.env._(
                        'Sin avances desde la decisión del %(date)s: la línea queda en 0.',
                        date=date)
                elif uom.compare(line.qty_period, line.decision_qty) if uom \
                        else line.qty_period != line.decision_qty:
                    warning = self.env._(
                        'El avance cambió desde la decisión del %(date)s: de %(before)s a '
                        '%(now)s.', date=date, before=round(line.decision_qty, 4),
                        now=round(line.qty_period, 4))
            line.decision_warning = warning

    @api.model
    def _decision_fields(self):
        """Campos con los que el validador decide sobre la línea (gancho)."""
        return {'rework_paid', 'pct_manual'}

    def _record_decision(self, vals):
        """Al tomar una decisión se guarda el avance de ese momento."""
        if not any(vals.get(name) for name in self._decision_fields()):
            return
        now = fields.Datetime.now()
        for line in self:
            # sudo: campos de solo lectura; la decisión ya pasó sus controles.
            line.sudo().write({'decision_qty': line.qty_period, 'decision_date': now})

    def action_confirm_decision(self):
        """El validador confirma su decisión con el avance actual (CR-15). Sin
        avances no hay qué confirmar: se quita la decisión."""
        if not self.env.user.has_groups(EXEC_VALIDATOR_GROUP):
            raise UserError(self.env._('Confirma la decisión quien valida la ejecución.'))
        lines = self.filtered(lambda l: l.decision_warning and not l.no_progress)
        if any(line.settlement_id.state not in ('draft', 'submitted') for line in lines):
            raise UserError(self.env._(
                'La decisión se confirma con la liquidación en borrador o presentada.'))
        for line in lines:
            line.settlement_id.message_post(body=self.env._(
                '%(activity)s: decisión confirmada con el avance actual (%(warning)s)',
                activity=line.activity_id.display_name, warning=line.decision_warning))
        lines._record_decision(dict.fromkeys(self._decision_fields(), True))
        return True

    def _qty_to_receive(self):
        """Lo que se recibe en la OC: lo liquidado menos lo repetido."""
        self.ensure_one()
        return max(self.qty_settle - self.qty_repeat, 0.0)

    @api.depends('qty_settle', 'price_unit')
    def _compute_amount(self):
        for line in self:
            currency = line.currency_id
            amount = line.qty_settle * line.price_unit
            line.amount = currency.round(amount) if currency else amount

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._set_settled_before()
        return lines

    def _set_settled_before(self):
        Progress = self.env['construction.task.progress'].sudo()
        for line in self:
            settlement = line.settlement_id
            before = sum(Progress.search([
                ('project_id', '=', settlement.project_id.id),
                ('partner_id', '=', settlement.partner_id.id),
                ('activity_id', '=', line.activity_id.id), ('is_rework', '=', False),
                ('settlement_id', '!=', False), ('settlement_id', '!=', settlement.id),
                ('settlement_id.state', 'in', ('approved', 'paid'))]).mapped('qty_weighted'))
            line.qty_settled_before = before

    def write(self, vals):
        if 'pct_manual' in vals:
            if any(line.settlement_id.state not in ('draft', 'submitted') for line in self):
                raise UserError(self.env._(
                    'El porcentaje se escribe con la liquidación en borrador o presentada.'))
            if vals.get('pct_manual') and not (vals.get('manual_reason') or all(
                    line.manual_reason for line in self)):
                raise UserError(self.env._('Un porcentaje escrito a mano pide su motivo.'))
            vals = dict(vals, manual_user_id=self.env.user.id if vals.get('pct_manual') else False,
                        manual_date=fields.Datetime.now() if vals.get('pct_manual') else False)
            self.settlement_id.filtered('head_authorized_by').write(
                {'head_authorized_by': False, 'head_authorized_on': False})
        if 'rework_paid' in vals:
            vals = self._check_rework_payment(vals)
        res = super().write(vals)
        self._record_decision(vals)
        if 'pct_manual' in vals:
            for line in self:
                line.settlement_id.message_post(body=self.env._(
                    '%(activity)s: liquidada al %(pct)s %% escrito a mano (validado %(validated)s '
                    '%%). Motivo: %(reason)s', activity=line.activity_id.display_name,
                    pct=round(line.pct_manual, 2), validated=round(line.pct_validated, 2),
                    reason=line.manual_reason or '—'))
        return res

    def _get_plan_lines(self):
        """Líneas de la contrata con esta actividad en el plan vigente de la obra."""
        self.ensure_one()
        settlement = self.settlement_id
        plan = settlement.plan_id if settlement.plan_id.state in OPEN_STATES else \
            settlement.project_id._construction_current_plan()
        return self.env['construction.resource.plan.line'].search([
            ('plan_id', '=', plan.id), ('activity_id', '=', self.activity_id.id),
            ('partner_id', '=', settlement.partner_id.id),
            ('resource_type', 'in', DRIVER_TYPES)])

    def _compute_cumulative(self):
        for line in self:
            plan_lines = line._get_plan_lines()
            executed = sum(plan_lines.mapped('qty_executed'))
            planned = sum(plan_lines.mapped('qty_planned'))
            line.qty_cumulative = executed
            line.qty_planned = planned
            line.progress_pct = min(executed / planned, 1.0) if planned else 0.0
            line.pct_validated = round(min(executed / planned, 1.0) * 100, 2) if planned else 0.0


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def _construction_check_cancellable(self):
        """Un plan en ejecución no se cancela con liquidaciones de contrata
        que no estén anuladas."""
        super()._construction_check_cancellable()
        # sudo: quien cancela el plan puede no ver las liquidaciones.
        settlements_sudo = self.env['construction.contract.settlement'].sudo().search(
            [('plan_id', '=', self.id), ('state', '!=', 'cancel')])
        if settlements_sudo:
            raise UserError(self.env._(
                'El plan %(plan)s tiene liquidaciones de contrata: %(docs)s. Anúlelas antes de '
                'cancelar el plan, o ciérrelo.', plan=self.display_name,
                docs=', '.join(settlements_sudo[:10].mapped('display_name'))))
