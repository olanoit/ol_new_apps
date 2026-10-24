# -*- coding: utf-8 -*-
"""Valorización de contrata con condiciones (requerimiento CREVAL v1.0, 3.5 a
3.8 y 3.10). Sobre la liquidación semanal de siempre
(``construction.contract.settlement``): cuando la orden tiene condiciones, la
valorización es de esa orden, su periodo sigue la periodicidad pactada y su
resumen se arma con el esquema de cálculo (costo directo, adicionales,
ajustes de precio, deductivos, impuestos, adelanto y fondo de garantía).

Sin condiciones, todo sigue como antes: por contrata y semana, con la
retención de la tarifa."""
import calendar
from collections import defaultdict
from datetime import timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .construction_contract_condition import SCHEME_KINDS, compute_cascade

SETTLEMENT_TYPES = [
    ('periodic', 'Periódica'),
    ('settlement', 'Liquidación'),
    ('opening', 'Apertura'),
]
OPEN_SETTLEMENT_STATES = ('draft', 'submitted', 'validated')
VALUED_STATES = ('approved', 'paid')
# Orden de los grupos del resumen.
SUMMARY_GROUPS = {
    'direct': 0, 'additional': 1, 'price_adjustment': 2, 'deduction': 3, 'subtotal': 4,
    'tax': 5, 'total': 6, 'advance': 7, 'retention': 8, 'to_pay': 9,
}
TERMS_AMOUNT_FIELDS = (
    'amount_direct', 'amount_additional', 'amount_adjustments', 'amount_deductions',
    'amount_subtotal', 'amount_tax', 'amount_total', 'amount_advance', 'amount_retention',
    'amount_to_pay',
)


def _last_day(day):
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def _month_day(year, month, wanted):
    return min(wanted, calendar.monthrange(year, month)[1])


class ConstructionContractSettlement(models.Model):
    _name = 'construction.contract.settlement'
    _inherit = ['construction.contract.settlement', 'construction.sign.mixin']
    _description = 'Valorización de contrata'

    settlement_type = fields.Selection(
        SETTLEMENT_TYPES, string='Tipo', required=True, default='periodic', tracking=True,
        help='Periódica: el corte del periodo. Liquidación: el último corte, que cierra la orden. '
             'Apertura: lo valorizado antes de Odoo, sin efecto contable.')
    uses_terms = fields.Boolean(
        string='Con condiciones', readonly=True, copy=False,
        help='La orden tiene condiciones de contrata: la valorización es de la orden y su '
             'resumen sigue el esquema de cálculo.')
    terms_id = fields.Many2one(related='purchase_order_id.construction_terms_id',
                               string='Condiciones')
    terms_advance_method = fields.Selection(related='terms_id.advance_method',
                                            string='Forma de amortizar')
    number = fields.Integer(string='Nº de la orden', readonly=True, copy=False)
    title = fields.Char(string='Título', compute='_compute_title', store=True)
    date_cutoff = fields.Date(
        string='Corte', copy=False,
        help='Fin del periodo de la liquidación (o de una valorización «al término»).')
    submitted_by_id = fields.Many2one('res.users', string='Elaboró', readonly=True, copy=False)
    date_submitted = fields.Datetime(string='Presentada el', readonly=True, copy=False)
    validated_by_id = fields.Many2one('res.users', string='Validó', readonly=True, copy=False)
    date_validated = fields.Datetime(string='Validada el', readonly=True, copy=False)
    advance_manual_amount = fields.Monetary(
        string='Amortización manual', currency_field='currency_id', copy=False,
        help='Solo con la forma de amortizar «Manual».')
    deduction_ids = fields.One2many(
        'construction.contract.deduction', 'settlement_id', string='Deductivos del periodo',
        readonly=True)
    summary_ids = fields.One2many(
        'construction.contract.settlement.summary', 'settlement_id', string='Resumen',
        readonly=True)
    # Resumen del periodo con el esquema de la orden.
    amount_direct = fields.Monetary(string='Subtotal costo directo', readonly=True, copy=False,
                                    currency_field='currency_id')
    amount_additional = fields.Monetary(string='Adicionales', readonly=True, copy=False,
                                        currency_field='currency_id')
    amount_adjustments = fields.Monetary(string='Ajustes de precio', readonly=True, copy=False,
                                         currency_field='currency_id')
    amount_deductions = fields.Monetary(string='Deductivos', readonly=True, copy=False,
                                        currency_field='currency_id')
    amount_subtotal = fields.Monetary(string='Subtotal', readonly=True, copy=False,
                                      currency_field='currency_id')
    amount_tax = fields.Monetary(string='IGV', readonly=True, copy=False,
                                 currency_field='currency_id')
    amount_total = fields.Monetary(string='Total con IGV', readonly=True, copy=False,
                                   currency_field='currency_id')
    amount_advance = fields.Monetary(string='Amortización del adelanto', readonly=True,
                                     copy=False, currency_field='currency_id')
    amount_retention = fields.Monetary(string='Fondo de garantía', readonly=True, copy=False,
                                       currency_field='currency_id')
    amount_to_pay = fields.Monetary(string='Total a pagar', readonly=True, copy=False,
                                    currency_field='currency_id')
    # Revisar antes de aprobar.
    review_manual_count = fields.Integer(string='Metrados escritos a mano',
                                         compute='_compute_review')
    review_rework_count = fields.Integer(string='Re-trabajos', compute='_compute_review')
    review_over_count = fields.Integer(string='Líneas sobre lo contratado',
                                       compute='_compute_review')
    review_no_photo_count = fields.Integer(string='Avances sin fotos', compute='_compute_review')
    has_review_items = fields.Boolean(compute='_compute_review')
    additional_line_ids = fields.One2many(
        'construction.contract.settlement.line', 'settlement_id', string='Líneas de adicionales',
        domain=[('is_additional', '=', True)], readonly=True)

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------
    @api.depends('number', 'settlement_type', 'purchase_order_id.construction_specialty',
                 'uses_terms', 'name')
    def _compute_title(self):
        for settlement in self:
            if not settlement.uses_terms:
                settlement.title = settlement.name
                continue
            specialty = settlement.purchase_order_id.construction_specialty \
                or settlement.purchase_order_id.name or ''
            if settlement.settlement_type == 'settlement':
                head = self.env._('Liquidación')
            elif settlement.settlement_type == 'opening':
                head = self.env._('Apertura')
            else:
                head = self.env._('Valorizado %02d', settlement.number)
            settlement.title = '%s - %s' % (head, specialty) if specialty else head

    @api.depends('name', 'partner_id', 'title')
    def _compute_display_name(self):
        super()._compute_display_name()
        for settlement in self.filtered(lambda s: s.uses_terms and s.name != '/'):
            settlement.display_name = '%s · %s' % (settlement.name, settlement.title)

    @api.depends('date_cutoff', 'settlement_type', 'uses_terms',
                 'purchase_order_id.construction_terms_id.frequency',
                 'purchase_order_id.construction_terms_id.cutoff_weekday',
                 'purchase_order_id.construction_terms_id.monthly_cutoff',
                 'purchase_order_id.construction_terms_id.cutoff_day')
    def _compute_dates(self):
        legacy = self.filtered(lambda s: not s.uses_terms)
        super(ConstructionContractSettlement, legacy)._compute_dates()
        for settlement in self - legacy:
            start, project = settlement.period_start, settlement.project_id
            if not start or not project:
                settlement.period_end = settlement.settlement_date = False
                settlement.payment_date = False
                continue
            end = settlement.date_cutoff if settlement.settlement_type != 'periodic' \
                or settlement.purchase_order_id.construction_frequency == 'end' \
                else self._terms_period_end(settlement.purchase_order_id, start)
            end = end or settlement.date_cutoff or start
            settlement.period_end = end
            settlement.settlement_date, settlement.payment_date = \
                settlement._terms_settlement_dates(end)

    def _terms_settlement_dates(self, cutoff):
        """Valorización el día de corte; pago el primer día de pago de
        contratas de la obra desde ese día (días hábiles anteriores si caen en
        feriado)."""
        self.ensure_one()
        project = self.project_id
        company = project.company_id or self.env.company
        payment_day = int(project.construction_payment_day or '5')
        payment = cutoff + timedelta(days=(payment_day - cutoff.weekday()) % 7)
        return (company._construction_previous_working_day(cutoff),
                company._construction_previous_working_day(payment))

    @api.constrains('period_start', 'project_id')
    def _check_period(self):
        return super(ConstructionContractSettlement,
                     self.filtered(lambda s: not s.uses_terms))._check_period()

    @api.constrains('purchase_order_id', 'state', 'uses_terms')
    def _check_one_open(self):
        for settlement in self.filtered(lambda s: s.uses_terms and s.state in
                                        OPEN_SETTLEMENT_STATES):
            others = self.search_count([
                ('purchase_order_id', '=', settlement.purchase_order_id.id),
                ('state', 'in', OPEN_SETTLEMENT_STATES), ('id', '!=', settlement.id)])
            if others:
                raise ValidationError(self.env._(
                    'La orden %s ya tiene una valorización abierta: apruébela o anúlela antes.',
                    settlement.purchase_order_id.name))

    @api.model_create_multi
    def create(self, vals_list):
        Order = self.env['purchase.order']
        for vals in vals_list:
            order = Order.browse(vals.get('purchase_order_id'))
            if order and order.construction_uses_terms:
                vals.setdefault('uses_terms', True)
                vals.setdefault('partner_id', order.partner_id.id)
                vals.setdefault('project_id', order.construction_project_id.id)
                if vals.get('settlement_type', 'periodic') != 'opening' and not vals.get('number'):
                    vals['number'] = max(order.construction_settlement_ids.filtered(
                        lambda s: s.state != 'cancel').mapped('number') or [0]) + 1
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Periodo (3.10)
    # ------------------------------------------------------------------
    @api.model
    def _terms_period_end(self, order, start):
        """Fin del periodo de ``order`` que empieza en ``start``."""
        terms = order.construction_terms_id
        frequency = terms.frequency
        if frequency == 'weekly':
            if terms.cutoff_weekday:
                return start + timedelta(days=(int(terms.cutoff_weekday) - start.weekday()) % 7)
            return order.construction_project_id._construction_period(start)[1]
        if frequency == 'biweekly':
            return start.replace(day=15) if start.day <= 15 else _last_day(start)
        if frequency == 'monthly':
            if terms.monthly_cutoff != 'day':
                return _last_day(start)
            day = _month_day(start.year, start.month, terms.cutoff_day or 25)
            if start.day <= day:
                return start.replace(day=day)
            following = _last_day(start) + timedelta(days=1)
            return following.replace(day=_month_day(following.year, following.month,
                                                    terms.cutoff_day or 25))
        return False

    @api.model
    def _terms_period_start(self, order, day):
        """Inicio del periodo de ``order`` que contiene ``day``."""
        terms = order.construction_terms_id
        frequency = terms.frequency
        if frequency == 'weekly':
            if terms.cutoff_weekday:
                end = day + timedelta(days=(int(terms.cutoff_weekday) - day.weekday()) % 7)
                return end - timedelta(days=6)
            return order.construction_project_id._construction_period(day)[0]
        if frequency == 'biweekly':
            return day.replace(day=1) if day.day <= 15 else day.replace(day=16)
        if frequency == 'monthly':
            if terms.monthly_cutoff != 'day':
                return day.replace(day=1)
            cut = _month_day(day.year, day.month, terms.cutoff_day or 25)
            if day.day > cut:
                return day.replace(day=cut) + timedelta(days=1)
            previous = day.replace(day=1) - timedelta(days=1)
            return previous.replace(day=_month_day(previous.year, previous.month,
                                                   terms.cutoff_day or 25)) + timedelta(days=1)
        return day

    @api.model
    def _terms_next_start(self, order):
        """El día siguiente al fin de la última valorización de la orden o,
        sin valorizaciones, el inicio del periodo del primer avance validado."""
        previous = order.construction_settlement_ids.filtered(
            lambda s: s.state != 'cancel' and s.period_end)
        if previous:
            return max(previous.mapped('period_end')) + timedelta(days=1)
        progress = self.env['construction.task.progress'].sudo().search(
            order._construction_progress_domain(), order='date', limit=1)
        return self._terms_period_start(order, progress.date) if progress else False

    # ------------------------------------------------------------------
    # Líneas
    # ------------------------------------------------------------------
    def _refresh_lines(self):
        terms = self.filtered('uses_terms')
        super(ConstructionContractSettlement, self - terms)._refresh_lines()
        for settlement in terms.filtered(lambda s: s.state == 'draft'):
            settlement._refresh_terms_lines()

    def _refresh_terms_lines(self):
        """Avances validados de la orden hasta el corte (más los rezagados),
        sus deductivos pendientes y el resumen."""
        self.ensure_one()
        order = self.purchase_order_id
        Progress = self.env['construction.task.progress']
        # sudo: quien prepara la valorización no siempre tiene acceso a
        # compras; solo se enlazan los avances de las líneas de esta orden.
        domain = order._construction_progress_domain() + [
            ('date', '<=', self.period_end),
            '|', '|', ('settlement_id', '=', False), ('settlement_id.state', '=', 'cancel'),
            ('settlement_id', '=', self.id)]
        progresses_sudo = Progress.sudo().search(domain)
        groups = defaultdict(lambda: Progress.sudo())
        for progress in progresses_sudo:
            po_line = self._get_service_line(progress)
            # Los adicionales que esperan la aprobación de la ampliación no
            # se valorizan todavía (3.9).
            if po_line.order_id == order and not po_line.construction_additional_pending:
                groups[(po_line, progress.is_rework, progress.rework_reason or False)] |= progress
        included = Progress.sudo().union(*groups.values()) if groups else Progress.sudo()
        settlement_sudo = self.sudo()
        (settlement_sudo.progress_ids - included).write({'settlement_id': False})
        included.write({'settlement_id': self.id})
        commands = [Command.clear()]
        for (po_line, is_rework, reason), progresses in sorted(
                groups.items(), key=lambda kv: (kv[0][0].sequence, kv[0][0].id, kv[0][1],
                                                kv[0][2] or '')):
            activity = progresses.activity_id[:1] or po_line.construction_activity_id
            qty = sum(progresses.mapped('qty_weighted'))
            repeat = 0.0 if is_rework else self._repeat_qty(progresses)
            if po_line.product_uom_id and activity.uom_id \
                    and po_line.product_uom_id != activity.uom_id:
                qty = activity.uom_id._compute_quantity(qty, po_line.product_uom_id)
                repeat = activity.uom_id._compute_quantity(repeat, po_line.product_uom_id)
            commands.append(Command.create({
                'activity_id': activity.id, 'purchase_line_id': po_line.id, 'qty_period': qty,
                'price_unit': po_line.price_unit, 'retention_pct': 0.0, 'is_rework': is_rework,
                'rework_reason': reason, 'qty_repeat': repeat,
                'progress_ids': [Command.set(progresses.ids)],
            }))
        settlement_sudo.write({
            'line_ids': commands,
            'plan_id': self.project_id._construction_current_plan().id,
        })
        self._attach_deductions()
        self._terms_recompute()

    def _attach_deductions(self):
        """Deductivos pendientes de la orden hasta el corte."""
        self.ensure_one()
        Deduction = self.env['construction.contract.deduction'].sudo()
        pending = Deduction.search([
            ('purchase_order_id', '=', self.purchase_order_id.id), ('state', '=', 'pending'),
            ('date', '<=', self.period_end)])
        released = (self.sudo().deduction_ids - pending).filtered(
            lambda d: d.state == 'in_valuation')
        released.with_context(construction_deduction_sync=True).write(
            {'state': 'pending', 'settlement_id': False})
        pending.with_context(construction_deduction_sync=True).write(
            {'state': 'in_valuation', 'settlement_id': self.id})

    # ------------------------------------------------------------------
    # Resumen (3.5)
    # ------------------------------------------------------------------
    def _terms_previous(self):
        """Valorizaciones anteriores de la orden que ya cuentan."""
        self.ensure_one()
        return self.purchase_order_id.construction_settlement_ids.filtered(
            lambda s: s != self and (s.state in VALUED_STATES or (
                s.settlement_type == 'opening' and s.state != 'cancel'))
            and (not s.period_end or not self.period_end or s.period_end <= self.period_end
                 or s.settlement_type == 'opening' or self.settlement_type == 'settlement'))

    def _terms_advance_available(self):
        """Adelanto otorgado (facturas publicadas y apertura) menos lo
        amortizado por las demás valorizaciones."""
        self.ensure_one()
        order = self.purchase_order_id
        advances = order.construction_advance_move_ids.filtered(lambda m: m.state == 'posted')
        granted = order.construction_opening_advance_granted + sum(
            advances.mapped(lambda m: m.amount_total * (-1 if m.move_type == 'in_refund' else 1)))
        amortized = order.construction_opening_advance_amortized + sum(
            self._terms_previous().filtered(lambda s: s.settlement_type != 'opening').mapped(
                'amount_advance'))
        return max(self.currency_id.round(granted - amortized), 0.0)

    def _terms_amounts(self):
        """Cascada del periodo: (filas, totales)."""
        self.ensure_one()
        terms = self.terms_id
        currency = self.currency_id
        lines = self.line_ids
        direct = currency.round(sum(lines.filtered(lambda l: not l.is_additional).mapped('amount')))
        additional = currency.round(sum(lines.filtered('is_additional').mapped('amount')))
        deductions = currency.round(sum(self.deduction_ids.mapped('signed_amount')))
        if self.settlement_type == 'opening':
            # Lo que la orden traía: el adelanto amortizado y el fondo retenido
            # de la carga inicial (3.14).
            order = self.purchase_order_id
            rows, totals = compute_cascade(terms, currency, direct, additional, deductions,
                                           advance=order.construction_opening_advance_amortized)
            retention = currency.round(sum(order.construction_guarantee_fund_ids.filtered(
                'is_opening').mapped('amount')))
            retention_line = terms._scheme_lines('retention')[:1]
            if retention_line:
                rows[retention_line.id] = -retention
            totals.update(retention=retention, to_pay=currency.round(
                totals['total'] - totals['advance'] - retention))
            return rows, totals
        rows, totals = compute_cascade(terms, currency, direct, additional, deductions)
        available = self._terms_advance_available()
        if self.settlement_type == 'settlement':
            advance = available
        elif terms.advance_method == 'fixed':
            advance = min(terms.advance_fixed_amount, available)
        elif terms.advance_method == 'manual':
            advance = min(self.advance_manual_amount, available)
        else:
            advance = min(totals['advance'], available)
        if currency.compare_amounts(advance, totals['advance']) != 0:
            rows, totals = compute_cascade(terms, currency, direct, additional, deductions,
                                           advance=advance)
        return rows, totals

    def _terms_recompute(self):
        """Escribe el resumen del periodo y sus filas (contractual, anterior,
        actual, acumulado y saldo). Solo antes de aprobar."""
        Summary = self.env['construction.contract.settlement.summary']
        for settlement in self.filtered('uses_terms'):
            if settlement.state not in OPEN_SETTLEMENT_STATES \
                    and settlement.settlement_type != 'opening':
                continue
            rows, totals = settlement._terms_amounts()
            # Los totales los calcula el sistema: también se escriben con la
            # revisión por niveles abierta (al aprobarla).
            settlement.sudo().with_context(skip_validation_check=True).write({
                'amount_direct': totals['direct'], 'amount_additional': totals['additional'],
                'amount_adjustments': totals['adjustments'],
                'amount_deductions': totals['deductions'], 'amount_subtotal': totals['subtotal'],
                'amount_tax': totals['tax'], 'amount_total': totals['total'],
                'amount_advance': totals['advance'], 'amount_retention': totals['retention'],
                'amount_to_pay': totals['to_pay'],
            })
            contract_rows, contract_totals = settlement.purchase_order_id \
                .construction_contract_cascade()
            previous = defaultdict(float)
            for row in settlement._terms_previous().summary_ids:
                previous[row.key] += row.amount_current
            values = []
            for key, label, group, percent, current, contract in settlement._summary_rows(
                    rows, totals, contract_rows, contract_totals):
                values.append({
                    'settlement_id': settlement.id, 'key': key, 'name': label,
                    'sequence': SUMMARY_GROUPS[group] * 1000 + len(values),
                    'row_type': group, 'percent': percent, 'amount_contract': contract,
                    'amount_previous': previous[key], 'amount_current': current,
                })
            settlement.sudo().summary_ids.unlink()
            Summary.sudo().create(values)

    def _summary_rows(self, rows, totals, contract_rows, contract_totals):
        """(clave, concepto, grupo, %, actual, contractual) en el orden del
        resumen."""
        self.ensure_one()
        result = [('direct', self.env._('Subtotal costo directo'), 'direct', 0.0,
                   totals['direct'], contract_totals['direct'])]
        if totals['additional'] or contract_totals['additional']:
            result.append(('additional', self.env._('Adicionales'), 'additional', 0.0,
                           totals['additional'], contract_totals['additional']))
        lines = self.terms_id._scheme_lines()
        order = {kind: i for i, (kind, _l) in enumerate(SCHEME_KINDS)}

        def scheme(kinds):
            for line in lines.filtered(lambda l: l.kind in kinds).sorted(
                    lambda l: (order[l.kind], l.sequence, l.id)):
                yield ('scheme_%s' % line.id, line.name, line.kind, line.effective_percent,
                       rows.get(line.id, 0.0), contract_rows.get(line.id, 0.0))
        result += list(scheme(('price_adjustment', 'deduction')))
        result.append(('subtotal', self.env._('Subtotal'), 'subtotal', 0.0, totals['subtotal'],
                       contract_totals['subtotal']))
        result += list(scheme(('tax',)))
        result.append(('total', self.env._('Total con IGV'), 'total', 0.0, totals['total'],
                       contract_totals['total']))
        result += list(scheme(('advance', 'retention')))
        result.append(('to_pay', self.env._('Total a pagar'), 'to_pay', 0.0, totals['to_pay'],
                       contract_totals['to_pay']))
        return result

    @api.depends('line_ids.amount', 'line_ids.retention_pct', 'amount_to_pay',
                 'amount_retention', 'amount_deductions', 'uses_terms')
    def _compute_amounts(self):
        terms = self.filtered('uses_terms')
        super(ConstructionContractSettlement, self - terms)._compute_amounts()
        for settlement in terms:
            settlement.amount_gross = settlement.amount_direct + settlement.amount_additional \
                + settlement.amount_adjustments
            settlement.retention_amount = settlement.amount_retention
            settlement.amount_discount = settlement.amount_deductions
            settlement.amount_net = settlement.amount_to_pay

    @api.depends('line_ids.is_manual', 'line_ids.is_rework', 'line_ids.over_contract',
                 'progress_ids.attachment_ids')
    def _compute_review(self):
        for settlement in self:
            lines = settlement.line_ids
            settlement.review_manual_count = len(lines.filtered('is_manual'))
            settlement.review_rework_count = len(lines.filtered('is_rework'))
            settlement.review_over_count = len(lines.filtered('over_contract'))
            settlement.review_no_photo_count = len(settlement.progress_ids.filtered(
                lambda p: not p.attachment_ids))
            settlement.has_review_items = settlement.uses_terms and bool(
                settlement.review_manual_count or settlement.review_rework_count
                or settlement.review_over_count or settlement.review_no_photo_count)

    @api.depends('line_ids.is_repeat', 'line_ids.manual_over', 'line_ids.over_contract',
                 'head_authorized_by')
    def _compute_needs_head_authorization(self):
        super()._compute_needs_head_authorization()
        for settlement in self.filtered(lambda s: s.uses_terms and not s.head_authorized_by):
            if any(settlement.line_ids.mapped('over_contract')):
                settlement.needs_head_authorization = True

    def write(self, vals):
        res = super().write(vals)
        if 'advance_manual_amount' in vals:
            self.filtered('uses_terms')._terms_recompute()
        return res

    # ------------------------------------------------------------------
    # Estados
    # ------------------------------------------------------------------
    def action_submit(self):
        self.filtered('uses_terms')._terms_recompute()
        res = super().action_submit()
        self.write({'submitted_by_id': self.env.user.id,
                    'date_submitted': fields.Datetime.now()})
        return res

    def action_validate(self):
        self.filtered('uses_terms')._terms_recompute()
        self.write({'validated_by_id': self.env.user.id,
                    'date_validated': fields.Datetime.now()})
        return super().action_validate()

    # ------------------------------------------------------------------
    # Documento impreso (3.12)
    # ------------------------------------------------------------------
    def _construction_sign_boxes(self):
        self.ensure_one()
        boxes = [
            self._construction_sign_box(self.env._('Elaboró'), self.submitted_by_id,
                                        self.date_submitted),
            self._construction_sign_box(self.env._('Validó'), self.validated_by_id,
                                        self.date_validated),
        ]
        boxes += self._construction_review_boxes()
        representative = self.purchase_order_id.construction_representative_id
        boxes.append(self._construction_sign_box(
            self.env._('Conformidad del contratista'),
            name=self.partner_id.commercial_partner_id.name,
            job=representative.name or ''))
        return boxes

    def _report_groups(self, additional=False):
        """Líneas del impreso agrupadas por el nivel 1 del plan (con los
        rótulos de la plantilla de la obra)."""
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: l.is_additional == additional)
        groups = {}
        for line in lines.sorted(lambda l: (l.level_1_id.construction_path or '',
                                            l.task_id.construction_path or '', l.id)):
            groups.setdefault(line.level_1_id, self.env['construction.contract.settlement.line'])
            groups[line.level_1_id] |= line
        return list(groups.items())

    def _report_payments(self):
        """Pagos de la orden: el adelanto y cada valorizado con su factura."""
        self.ensure_one()
        order = self.purchase_order_id
        rows = []
        state_labels = dict(self.env['account.move']._fields['payment_state']._description_selection(
            self.env))
        for move in order.construction_advance_move_ids.filtered(lambda m: m.state != 'cancel'):
            rows.append({'name': self.env._('Adelanto'), 'amount': move.amount_total,
                         'pct': move.amount_total / order.amount_total if order.amount_total else 0,
                         'invoice': move.name, 'state': state_labels.get(move.payment_state, '')})
        for settlement in order._construction_valued_settlements().sorted(
                lambda s: (s.period_end or s.period_start, s.id)):
            invoice = settlement.invoice_id
            rows.append({
                'name': settlement.title or settlement.name, 'amount': settlement.amount_to_pay,
                'pct': settlement.amount_total / order.amount_total if order.amount_total else 0,
                'invoice': invoice.name or (self.env._('Apertura') if settlement.settlement_type
                                            == 'opening' else ''),
                'state': state_labels.get(invoice.payment_state, '') if invoice else '',
            })
        return rows

    def _report_site_address(self):
        """Dirección y distrito de la sede de la obra (o del contacto de la
        obra si no tiene sede)."""
        self.ensure_one()
        project = self.project_id
        partner = self.env['res.partner']
        if 'construction_hr_site_ids' in project._fields:
            # sudo: las sedes son de Nómina; solo se imprime su dirección.
            site = project.sudo().construction_hr_site_ids[:1]
            for name in ('address_id', 'partner_id'):
                if name in site._fields and site[name]:
                    partner = site[name]
                    break
        partner = partner or project.partner_id
        district = 'l10n_pe_district' in partner._fields and partner.l10n_pe_district.name
        return ', '.join(p for p in (partner.street, district, partner.city) if p)

    def _report_level_label(self, depth):
        """Rótulo del nivel ``depth`` en la plantilla de la obra."""
        template = self.project_id.construction_level_template_id
        line = template.line_ids.sorted('sequence')[depth - 1:depth]
        return (line.label if 'label' in line._fields and line.label else line.name) \
            or self.env._('Nivel %s', depth)

    def action_send_valuation(self):
        """Envía el valorizado impreso al contratista."""
        self.ensure_one()
        template = self.env.ref(
            'al_construction_planner_subcontract.mail_template_contract_valuation',
            raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window', 'res_model': 'mail.compose.message',
            'view_mode': 'form', 'target': 'new',
            'context': {'default_model': self._name, 'default_res_ids': self.ids,
                        'default_template_id': template.id if template else False,
                        'default_composition_mode': 'comment'},
        }

    def _receive_on_purchase_order(self):
        if not self.uses_terms:
            return super()._receive_on_purchase_order()
        self.ensure_one()
        order = self.purchase_order_id
        if order.state != 'purchase':
            raise UserError(self.env._(
                'Confirme la orden de contrata %s antes de aprobar la valorización.', order.name))
        tolerance = self.terms_id.progress_tolerance_pct
        lines = self.line_ids.filtered(lambda l: not l.is_rework)
        for line in lines:
            po_line = line.purchase_line_id
            received = po_line.qty_received + line._qty_to_receive()
            limit = po_line.product_qty * (1 + tolerance / 100.0)
            if po_line.product_uom_id.compare(received, limit) > 0 and not self.head_authorized_by:
                raise UserError(self.env._(
                    '%(activity)s: con esta valorización se recibirían %(received)s de '
                    '%(ordered)s %(uom)s contratados (tolerancia %(tol)s %%). Amplíe la orden o '
                    'pida la autorización del exceso.', activity=line.activity_id.display_name,
                    received=round(received, 2), ordered=round(po_line.product_qty, 2),
                    uom=po_line.product_uom_id.name, tol=round(tolerance, 2)))
        for line in lines:
            line.purchase_line_id.qty_received += line._qty_to_receive()

    def _action_approve(self):
        terms = self.filtered('uses_terms')
        for settlement in terms:
            # sudo: la jefatura que aprueba no suele leer compras ni
            # contabilidad, y el resumen suma los adelantos publicados.
            settlement_sudo = settlement.sudo()
            settlement_sudo._terms_recompute()
        res = super()._action_approve()
        terms.deduction_ids.with_context(construction_deduction_sync=True).write(
            {'state': 'applied'})
        return res

    def action_cancel(self):
        res = super().action_cancel()
        self.sudo().deduction_ids.with_context(construction_deduction_sync=True).write(
            {'state': 'pending', 'settlement_id': False})
        return res

    # ------------------------------------------------------------------
    # Factura (3.6 a 3.8)
    # ------------------------------------------------------------------
    def _create_invoice(self):
        if not self.uses_terms:
            return super()._create_invoice()
        self.ensure_one()
        order = self.purchase_order_id
        company = self.company_id
        vals = order.with_company(company)._prepare_invoice()
        vals.update({
            'invoice_payment_term_id': False,
            'invoice_date_due': self.payment_date,
            'ref': self.title or self.name,
            'invoice_origin': '%s, %s' % (order.name, self.name),
        })
        invoice = self.env['account.move'].with_company(company).with_context(
            default_move_type='in_invoice').create(vals)
        service_vals = []
        for line in self.line_ids:
            values = line.purchase_line_id._prepare_account_move_line(invoice)
            values['quantity'] = line.qty_settle
            service_vals.append(values)
        invoice.write({'invoice_line_ids': [Command.create(v) for v in service_vals]})
        services = invoice.invoice_line_ids.filtered(lambda l: l.purchase_line_id)
        main = services.sorted(lambda l: -abs(l.price_subtotal))[:1]
        # Las líneas negativas y los ajustes van en otra escritura (ver la
        # liquidación semanal: _sync_tax_lines de v19).
        extra = self._invoice_adjustment_values(main, services)
        extra += self._invoice_deduction_values(main)
        extra += self._invoice_regularization_values()
        if extra:
            invoice.write({'invoice_line_ids': [Command.create(v) for v in extra]})
        if not self.currency_id.is_zero(self.amount_retention):
            invoice.write({
                'construction_guarantee_amount': self.amount_retention,
                'construction_guarantee_date': self._guarantee_date(),
            })
        if invoice.invoice_date_due != self.payment_date:
            invoice.invoice_date_due = self.payment_date
        self._create_payment_discount_entry(invoice)
        return invoice

    def _weighted_distribution(self, lines):
        """Distribución analítica de las líneas del servicio ponderada por su
        importe (los ajustes de precio se reparten como el servicio)."""
        total = sum(abs(line.price_subtotal) for line in lines)
        result = defaultdict(float)
        for line in lines:
            weight = abs(line.price_subtotal) / total if total else 1.0 / len(lines)
            for key, pct in (line.analytic_distribution or {}).items():
                result[key] += pct * weight
        return {key: round(pct, 2) for key, pct in result.items()} or False

    def _invoice_adjustment_values(self, main, services):
        self.ensure_one()
        values = []
        summary = {row.key: row for row in self.summary_ids}
        distribution = self._weighted_distribution(services) if services else False
        for line in self.terms_id._scheme_lines('price_adjustment'):
            row = summary.get('scheme_%s' % line.id)
            if not row or self.currency_id.is_zero(row.amount_current):
                continue
            vals = {
                'display_type': 'product',
                'name': '%s (%s %%)' % (line.name, round(line.percent, 6)),
                'quantity': 1.0,
                'price_unit': row.amount_current,
                'tax_ids': [Command.set(main.tax_ids.ids)],
                'analytic_distribution': distribution,
            }
            if line.invoice_mode == 'service_line' and main.product_id:
                vals.update(product_id=main.product_id.id, account_id=main.account_id.id)
            else:
                vals['account_id'] = (line.account_id or main.account_id).id
            values.append(vals)
        return values

    def _deduction_mode(self):
        return self.terms_id._scheme_lines('deduction')[:1].invoice_mode or 'own_line'

    def _invoice_deduction_values(self, main):
        self.ensure_one()
        if self._deduction_mode() != 'own_line':
            return []
        account = self.company_id.construction_deduction_account_id or main.account_id
        return [{
            'display_type': 'product',
            'name': self.env._('Deductivo a contrata %(name)s: %(text)s', name=deduction.name,
                               text=deduction.description),
            'account_id': account.id,
            'quantity': 1.0,
            'price_unit': -deduction.signed_amount,
            'tax_ids': [Command.set(main.tax_ids.ids)],
            'analytic_distribution': deduction._analytic_distribution(),
        } for deduction in self.deduction_ids]

    def _invoice_regularization_values(self):
        """Regularización del adelanto: línea negativa del producto de
        anticipo por la amortización sin IGV."""
        self.ensure_one()
        amount = self.amount_advance
        if self.currency_id.is_zero(amount):
            return []
        product = self.company_id.construction_advance_product_id
        if not product:
            raise UserError(self.env._(
                'Configure el producto de anticipo a contratistas en Ajustes › Planificación de '
                'obra para aprobar %s.', self.display_name))
        taxes = product.supplier_taxes_id.filtered(
            lambda t: t.company_id in self.company_id.parent_ids | self.company_id)
        rate = sum(t.amount for t in taxes if t.amount_type == 'percent'
                   and not t.price_include) / 100.0
        account = self.project_id.account_id
        return [{
            'display_type': 'product',
            'product_id': product.id,
            'name': self.env._('Regularización del adelanto (%s)', self.title or self.name),
            'quantity': 1.0,
            'price_unit': -self.currency_id.round(amount / (1.0 + rate)),
            'tax_ids': [Command.set(taxes.ids)],
            'analytic_distribution': {str(account.id): 100.0} if account else False,
        }]

    def _guarantee_date(self):
        """Inicio del plazo más los días de devolución: desde la factura (el
        día de la valorización) o desde la liquidación de la orden."""
        self.ensure_one()
        terms = self.terms_id
        start = self.settlement_date or fields.Date.context_today(self)
        if terms.guarantee_from == 'settlement' and self.settlement_type != 'settlement':
            order = self.purchase_order_id
            liquidation = order.construction_settlement_ids.filtered(
                lambda s: s.settlement_type == 'settlement' and s.state in VALUED_STATES)[:1]
            planned = order.order_line.mapped('date_planned')
            # Sin liquidación, el fin previsto de la orden; la liquidación
            # corre después los vencimientos (_update_guarantee_dates).
            start = liquidation.settlement_date or (max(planned).date() if planned else start)
        return start + timedelta(days=terms.guarantee_days or 0)

    def _create_payment_discount_entry(self, invoice):
        """Deductivos descontados al pago: asiento de la contrata (cuenta por
        pagar contra la cuenta de deductivos) que se concilia con la factura."""
        self.ensure_one()
        if self._deduction_mode() != 'payment_discount' or not self.deduction_ids:
            return False
        company = self.company_id
        journal = company.construction_deduction_journal_id
        account = company.construction_deduction_account_id
        if not journal or not account:
            raise UserError(self.env._(
                'Configure el diario y la cuenta de deductivos a contratas en Ajustes › '
                'Planificación de obra para descontar al pago.'))
        partner = self.partner_id.commercial_partner_id.with_company(company)
        amount = sum(self.deduction_ids.mapped('signed_amount'))
        entry = self.env['account.move'].with_company(company).create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'ref': self.env._('Deductivos de %s', self.title or self.name),
            'line_ids': [
                Command.create({'name': self.env._('Deductivos descontados al pago'),
                                'account_id': partner.property_account_payable_id.id,
                                'partner_id': partner.id, 'debit': amount}),
                Command.create({'name': self.env._('Deductivos descontados al pago'),
                                'account_id': account.id, 'partner_id': partner.id,
                                'credit': amount}),
            ],
        })
        self.message_post(body=self.env._(
            'Deductivos descontados al pago: asiento %s por conciliar con la factura.',
            entry.display_name))
        return entry

    # ------------------------------------------------------------------
    # Preparación (cron y botón de la lista)
    # ------------------------------------------------------------------
    @api.model
    def _prepare_terms_settlements(self, today=None, projects=None):
        """Valorización en borrador de cada orden con condiciones cuyo corte
        ya pasó y tiene avances validados por valorizar; avisa al residente."""
        today = today or fields.Date.context_today(self)
        domain = [('construction_uses_terms', '=', True), ('state', '=', 'purchase'),
                  ('construction_closed', '=', False),
                  ('construction_terms_id.frequency', '!=', 'end')]
        if projects is not None:
            domain.append(('construction_project_id', 'in', projects.ids))
        created = self.browse()
        # sudo: el cron y el residente preparan valorizaciones de órdenes de
        # compra que no administran.
        for order in self.env['purchase.order'].sudo().search(domain):
            if order.construction_settlement_ids.filtered(
                    lambda s: s.state in OPEN_SETTLEMENT_STATES):
                order.construction_settlement_ids.filtered(
                    lambda s: s.state == 'draft')._refresh_lines()
                continue
            start = self._terms_next_start(order)
            if not start:
                continue
            end = self._terms_period_end(order, start)
            if not end or end > today:
                continue
            settlement = self.create({'purchase_order_id': order.id, 'period_start': start})
            settlement._refresh_lines()
            if not settlement.line_ids and not settlement.deduction_ids:
                settlement.unlink()
                continue
            created |= settlement
            settlement._schedule_prepare_activity()
        return created

    def _schedule_prepare_activity(self):
        """El día de corte: «Preparar valorizado» al responsable de la obra."""
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for settlement in self:
            user = settlement.project_id.user_id
            if user and not user.share:
                settlement.activity_schedule(
                    activity_type_id=activity_type.id if activity_type else False,
                    summary=self.env._('Preparar valorizado'), user_id=user.id,
                    date_deadline=settlement.settlement_date)

    @api.model
    def _cron_prepare_settlements(self):
        self._prepare_terms_settlements()
        return super()._cron_prepare_settlements()

    @api.model
    def action_prepare_project_settlements(self, project_id=None, date=None):
        """Botón de la lista: genera las valorizaciones de todas las órdenes
        de la obra (o de todas las obras) que vencen en el corte."""
        projects = self.env['project.project'].browse(project_id) if project_id else None
        created = self._prepare_terms_settlements(
            today=fields.Date.to_date(date) if date else None, projects=projects)
        created |= self._prepare_settlements(projects=projects)
        return {
            'type': 'ir.actions.act_window', 'name': self.env._('Valorizaciones preparadas'),
            'res_model': self._name, 'view_mode': 'list,form',
            'domain': [('id', 'in', created.ids)],
        }


class ConstructionContractSettlementLine(models.Model):
    _inherit = 'construction.contract.settlement.line'

    is_additional = fields.Boolean(related='purchase_line_id.construction_is_additional',
                                   string='Adicional', store=True)
    task_id = fields.Many2one(related='purchase_line_id.construction_task_id', string='Partida',
                              store=True, index='btree_not_null')
    level_1_id = fields.Many2one('project.task', string='Nivel 1', compute='_compute_levels',
                                 store=True)
    level_2_id = fields.Many2one('project.task', string='Nivel 2', compute='_compute_levels',
                                 store=True)
    progress_ids = fields.Many2many(
        'construction.task.progress', 'construction_settlement_line_progress_rel', 'line_id',
        'progress_id', string='Avances', readonly=True)
    # Columnas del valorizado (3.5): contratado, anterior, actual, acumulado
    # y saldo, en metrado, porcentaje e importe.
    qty_contracted = fields.Float(related='purchase_line_id.product_qty', string='Contratado',
                                  digits='Product Unit')
    amount_contracted = fields.Monetary(
        string='Importe contratado', compute='_compute_columns', currency_field='currency_id')
    qty_previous = fields.Float(string='Anterior', digits='Product Unit', readonly=True,
                                help='Valorizado antes en la orden (incluye la apertura).')
    amount_previous = fields.Monetary(string='Importe anterior', compute='_compute_columns',
                                      currency_field='currency_id')
    qty_accumulated = fields.Float(string='Acumulado valorizado', compute='_compute_columns',
                                   digits='Product Unit')
    amount_accumulated = fields.Monetary(string='Importe acumulado', compute='_compute_columns',
                                         currency_field='currency_id')
    pct_accumulated = fields.Float(string='% acumulado', compute='_compute_columns')
    qty_balance = fields.Float(string='Saldo', compute='_compute_columns', digits='Product Unit')
    amount_balance = fields.Monetary(string='Importe del saldo', compute='_compute_columns',
                                     currency_field='currency_id')
    over_contract = fields.Boolean(
        string='Sobre lo contratado', compute='_compute_over_contract', store=True,
        help='El acumulado pasa lo contratado más la tolerancia de las condiciones.')

    @api.depends('purchase_line_id.construction_allocation_ids.plan_line_id.level_1_id',
                 'purchase_line_id.construction_allocation_ids.plan_line_id.level_2_id')
    def _compute_levels(self):
        for line in self:
            plan_line = line.purchase_line_id.sudo().construction_allocation_ids.plan_line_id[:1]
            line.level_1_id = plan_line.level_1_id
            line.level_2_id = plan_line.level_2_id

    @api.depends('qty_settle', 'qty_previous', 'purchase_line_id.product_qty',
                 'settlement_id.terms_id.progress_tolerance_pct', 'is_rework')
    def _compute_over_contract(self):
        for line in self:
            settlement = line.settlement_id
            if not settlement.uses_terms or line.is_rework:
                line.over_contract = False
                continue
            tolerance = settlement.terms_id.progress_tolerance_pct
            limit = line.purchase_line_id.product_qty * (1 + tolerance / 100.0)
            uom = line.purchase_line_id.product_uom_id
            line.over_contract = uom.compare(line.qty_previous + line.qty_settle, limit) > 0

    def _compute_columns(self):
        for line in self:
            price = line.price_unit
            currency = line.currency_id
            contracted = line.qty_contracted
            accumulated = line.qty_previous + (0.0 if line.is_rework else line.qty_settle)
            line.amount_contracted = currency.round(contracted * price)
            line.amount_previous = currency.round(line.qty_previous * price)
            line.qty_accumulated = accumulated
            line.amount_accumulated = currency.round(accumulated * price)
            line.pct_accumulated = accumulated / contracted if contracted else 0.0
            line.qty_balance = contracted - accumulated
            line.amount_balance = currency.round((contracted - accumulated) * price)

    def _set_settled_before(self):
        super()._set_settled_before()
        for line in self.filtered(lambda l: l.settlement_id.uses_terms):
            settlement = line.settlement_id
            previous = settlement._terms_previous().line_ids.filtered(
                lambda l: l.purchase_line_id == line.purchase_line_id and not l.is_rework)
            line.qty_previous = sum(previous.mapped('qty_settle'))

    def write(self, vals):
        res = super().write(vals)
        if 'pct_manual' in vals:
            self.settlement_id._terms_recompute()
        return res

    def _get_plan_lines(self):
        """Con condiciones, las líneas del plan de la línea de la orden (su
        partida)."""
        if not self.settlement_id.uses_terms:
            return super()._get_plan_lines()
        self.ensure_one()
        # sudo: quien valoriza no siempre lee las asignaciones de compras.
        return self.purchase_line_id.sudo().construction_allocation_ids.filtered(
            lambda a: a.state != 'cancel').plan_line_id.sudo(False)


class ConstructionContractSettlementSummary(models.Model):
    _name = 'construction.contract.settlement.summary'
    _description = 'Fila del resumen del valorizado'
    _order = 'settlement_id, sequence, id'

    settlement_id = fields.Many2one('construction.contract.settlement', string='Valorización',
                                    required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='settlement_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='settlement_id.currency_id')
    sequence = fields.Integer()
    key = fields.Char(required=True)
    name = fields.Char(string='Concepto', required=True)
    row_type = fields.Selection(
        [('direct', 'Costo directo'), ('additional', 'Adicionales'),
         ('subtotal', 'Subtotal'), ('total', 'Total'), ('to_pay', 'Total a pagar')]
        + SCHEME_KINDS, string='Tipo de fila')
    percent = fields.Float(string='%', digits=(16, 6))
    amount_contract = fields.Monetary(string='Contractual', currency_field='currency_id')
    amount_previous = fields.Monetary(string='Anterior', currency_field='currency_id')
    amount_current = fields.Monetary(string='Actual', currency_field='currency_id')
    amount_accumulated = fields.Monetary(string='Acumulado', compute='_compute_accumulated',
                                         currency_field='currency_id')
    amount_balance = fields.Monetary(string='Saldo', compute='_compute_accumulated',
                                     currency_field='currency_id')
    is_total = fields.Boolean(compute='_compute_accumulated')

    @api.depends('amount_previous', 'amount_current', 'amount_contract', 'row_type')
    def _compute_accumulated(self):
        for row in self:
            row.amount_accumulated = row.amount_previous + row.amount_current
            row.amount_balance = row.amount_contract - row.amount_accumulated
            row.is_total = row.row_type in ('direct', 'subtotal', 'total', 'to_pay')
