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

from .common import DRIVER_TYPES
from .construction_resource_plan import OPEN_STATES

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
    line_ids = fields.One2many(
        'construction.contract.settlement.line', 'settlement_id', string='Líneas',
        readonly=True)
    amount_gross = fields.Monetary(
        string='Bruto', compute='_compute_amounts', store=True, currency_field='currency_id')
    retention_amount = fields.Monetary(
        string='Retención', compute='_compute_amounts', store=True,
        currency_field='currency_id', help='Según el porcentaje de la tarifa de cada línea.')
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

    _period_unique = models.UniqueIndex(
        '(partner_id, project_id, period_start) WHERE state != \'cancel\'',
        'Ya hay una liquidación de esta contrata en la obra para esa semana.')

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
            settlement.amount_gross = gross
            settlement.retention_amount = retention
            settlement.amount_net = gross - retention

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
            by_po_line = defaultdict(lambda: Progress.sudo())
            orphans = Progress.sudo()
            for progress in progresses_sudo:
                po_line = self._get_service_line(progress)
                if po_line:
                    by_po_line[po_line] |= progress
                else:
                    orphans |= progress
            included = Progress.sudo().union(*by_po_line.values()) if by_po_line \
                else Progress.sudo()
            settlement_sudo = settlement.sudo()
            (settlement_sudo.progress_ids - included).write({'settlement_id': False})
            included.write({'settlement_id': settlement.id})
            commands = [Command.clear()]
            for po_line, progresses in sorted(
                    by_po_line.items(), key=lambda kv: (kv[0].sequence, kv[0].id)):
                activity = progresses.activity_id[:1]
                qty = sum(progresses.mapped('qty'))
                if po_line.product_uom_id and activity.uom_id \
                        and po_line.product_uom_id != activity.uom_id:
                    qty = activity.uom_id._compute_quantity(qty, po_line.product_uom_id)
                commands.append(Command.create({
                    'activity_id': activity.id,
                    'purchase_line_id': po_line.id,
                    'qty_period': qty,
                    'price_unit': po_line.price_unit,
                    'retention_pct': po_line.construction_retention_pct,
                }))
            orders = Progress.env['purchase.order.line'].union(*by_po_line).order_id \
                if by_po_line else self.env['purchase.order']
            settlement_sudo.write({
                'line_ids': commands,
                'purchase_order_id': orders.sorted('id', reverse=True)[:1].id
                or settlement.purchase_order_id.id,
                'plan_id': settlement.project_id._construction_current_plan().id,
            })
            if orphans:
                settlement.message_post(body=self.env._(
                    'Avances validados sin OC de servicio de la contrata (asigne la contrata '
                    'con «Asignar contrata»): %s.', ', '.join(orphans.mapped('name'))))

    def action_refresh(self):
        if self.filtered(lambda s: s.state != 'draft'):
            raise UserError(self.env._('Solo se actualizan liquidaciones en borrador.'))
        self._refresh_lines()

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
        if not self.env.user.has_group('al_construction_planner.group_planner_planner'):
            raise UserError(self.env._(
                'Presenta, valida o devuelve la liquidación el supervisor de obra (grupo '
                'Planificador).'))

    def action_submit(self):
        self._check_supervisor()
        self._check_state(('draft',))
        for settlement in self:
            if not settlement.line_ids:
                raise UserError(self.env._(
                    'La liquidación %s no tiene líneas: actualice sus avances.',
                    settlement.display_name))
        self.write({'state': 'submitted', 'return_reason': False})

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
        jefatura (tier validation). Sin reglas que apliquen, se aprueba."""
        self._check_supervisor()
        self._check_state(('submitted',))
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
            settlement.message_post(body=Markup(self.env._(
                'Aprobada: recibido en %(order)s y factura %(invoice)s con vencimiento el '
                '%(due)s.')) % {
                    'order': settlement_sudo.purchase_order_id.name,
                    'invoice': invoice_sudo._get_html_link(),
                    'due': fields.Date.to_string(settlement.payment_date)})
            if settlement.plan_id:
                settlement.plan_id._mark_in_progress()

    def _receive_on_purchase_order(self):
        """Suma lo de la semana a lo recibido de cada línea de la OC (recepción
        manual de servicios). No deja recibir más que lo ordenado."""
        self.ensure_one()
        lines = self.line_ids
        orders = lines.purchase_line_id.order_id
        not_confirmed = orders.filtered(lambda o: o.state != 'purchase')
        if not_confirmed:
            raise UserError(self.env._(
                'Confirme la OC de servicio %s antes de aprobar la liquidación.',
                ', '.join(not_confirmed.mapped('name'))))
        for line in lines:
            po_line = line.purchase_line_id
            received = po_line.qty_received + line.qty_period
            if po_line.product_uom_id.compare(received, po_line.product_qty) > 0:
                raise UserError(self.env._(
                    '%(activity)s: con esta liquidación se recibirían %(received)s de '
                    '%(ordered)s %(uom)s ordenados en %(order)s. Amplíe la OC (Asignar '
                    'contrata) o corrija los avances.', activity=line.activity_id.display_name,
                    received=round(received, 2), ordered=round(po_line.product_qty, 2),
                    uom=po_line.product_uom_id.name, order=po_line.order_id.name))
        for line in lines:
            line.purchase_line_id.qty_received += line.qty_period

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
        for line in self.line_ids:
            values = line.purchase_line_id._prepare_account_move_line(invoice)
            values['quantity'] = line.qty_period
            line_vals.append(values)
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
        icon = Markup('<i class="fa fa-lg fa-info-circle"></i>')
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
    price_unit = fields.Monetary(string='Tarifa', currency_field='currency_id')
    amount = fields.Monetary(
        string='Monto', compute='_compute_amount', store=True, currency_field='currency_id')
    retention_pct = fields.Float(string='Retención (%)', digits=(5, 2))
    qty_cumulative = fields.Float(
        string='Acumulado', compute='_compute_cumulative', digits='Product Unit')
    qty_planned = fields.Float(
        string='Presupuestado', compute='_compute_cumulative', digits='Product Unit')
    progress_pct = fields.Float(string='Avance', compute='_compute_cumulative')

    @api.depends('qty_period', 'price_unit')
    def _compute_amount(self):
        for line in self:
            currency = line.currency_id
            amount = line.qty_period * line.price_unit
            line.amount = currency.round(amount) if currency else amount

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
