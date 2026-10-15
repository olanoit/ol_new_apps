# -*- coding: utf-8 -*-
"""Requerimiento de obra con control del plan (P-11, W-10).

El documento sigue siendo de al_construction_material_request: aquí se le
agrega el plan vigente de la obra, el saldo del plan por línea y el control
de exceso al «Solicitar aprobación» según la política del plan (avisar, pedir
aprobación o bloquear)."""
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang

from .common import EXCEED_STATES
from .construction_resource_plan import OPEN_STATES

SUPPLY_TYPES = ('material', 'service', 'production')


class ConstructionMaterialRequest(models.Model):
    _inherit = 'construction.material.request'

    construction_plan_id = fields.Many2one(
        'construction.resource.plan', string='Plan de recursos', copy=False,
        compute='_compute_construction_plan_id', store=True, index='btree_not_null',
        check_company=True, help='Plan vigente de la obra al pedir la aprobación.')
    construction_exceed_state = fields.Selection(
        EXCEED_STATES, string='Control de plan', default='ok', copy=False, readonly=True,
        tracking=True)
    construction_exceed_reason = fields.Text(
        string='Justificación del exceso', copy=False, tracking=True,
        help='Por qué se pide más de lo que queda en el plan.')
    # Descuento del material extra a una contrata (v1.6, M16-08): lo decide
    # la jefatura de proyectos al aprobar el extra; entra como línea negativa
    # en la siguiente liquidación semanal de esa contrata en la obra.
    construction_discount = fields.Boolean(
        string='Descontar a la contrata', copy=False, tracking=True)
    construction_discount_partner_id = fields.Many2one(
        'res.partner', string='Contrata a descontar', copy=False, tracking=True,
        help='La contrata responsable del extra: su siguiente liquidación en la obra lleva el '
             'descuento.')
    construction_discount_amount = fields.Monetary(
        string='Monto a descontar', copy=False, tracking=True, currency_field='currency_id',
        compute='_compute_construction_discount_amount', store=True, readonly=False,
        help='Por defecto, el valor estimado del requerimiento.')
    construction_discount_settlement_id = fields.Many2one(
        'construction.contract.settlement', string='Descontado en', copy=False, readonly=True,
        index='btree_not_null', check_company=True)

    @api.depends('project_id')
    def _compute_construction_plan_id(self):
        for request in self:
            request.construction_plan_id = request._construction_open_plan()

    def _construction_open_plan(self):
        self.ensure_one()
        if not self.project_id:
            return self.env['construction.resource.plan']
        # El residente no ve los planes: solo se busca el vigente de su obra.
        plans_sudo = self.env['construction.resource.plan'].sudo()
        return plans_sudo.search([
            ('project_id', '=', self.project_id.id), ('state', 'in', OPEN_STATES)],
            limit=1).sudo(False)

    @api.depends('construction_discount', 'amount_estimated')
    def _compute_construction_discount_amount(self):
        for request in self:
            if not request.construction_discount:
                request.construction_discount_amount = 0.0
            elif not request.construction_discount_amount:
                request.construction_discount_amount = request.amount_estimated

    @api.constrains('construction_discount', 'construction_discount_partner_id',
                    'construction_discount_amount')
    def _check_construction_discount(self):
        for request in self.filtered('construction_discount'):
            if not request.construction_discount_partner_id:
                raise ValidationError(self.env._(
                    'Indique la contrata a la que se descuenta el extra %s.', request.name))
            if request.currency_id.compare_amounts(request.construction_discount_amount, 0) <= 0:
                raise ValidationError(self.env._(
                    'El monto a descontar del extra %s debe ser mayor que cero.', request.name))

    def _check_discount_manager(self):
        if not self.env.su and not self.env.user.has_group(
                'al_construction_planner.group_planner_manager'):
            raise UserError(self.env._(
                'El descuento a la contrata lo decide la jefatura de proyectos.'))

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('construction_discount') for vals in vals_list):
            self._check_discount_manager()
        return super().create(vals_list)

    def write(self, vals):
        discount_fields = {'construction_discount', 'construction_discount_partner_id',
                           'construction_discount_amount'}
        if discount_fields & set(vals):
            self._check_discount_manager()
            if self.filtered('construction_discount_settlement_id'):
                raise UserError(self.env._(
                    'El extra ya se descontó en una liquidación: no se puede cambiar el descuento.'))
        res = super().write(vals)
        if 'state' in vals:
            self._construction_refresh_plan()
        return res

    @api.model
    def _get_under_validation_exceptions(self):
        # El descuento a la contrata lo decide la jefatura mientras revisa el
        # extra (v1.6, M16-08).
        return super()._get_under_validation_exceptions() + [
            'construction_exceed_state', 'construction_plan_id', 'construction_discount',
            'construction_discount_partner_id', 'construction_discount_amount']

    @api.model
    def _get_all_validation_exceptions(self):
        # Sin esto, OCA los deja de solo lectura en la vista durante la revisión.
        return super()._get_all_validation_exceptions() + [
            'construction_discount', 'construction_discount_partner_id',
            'construction_discount_amount']

    # ------------------------------------------------------------------
    # Control al solicitar la aprobación
    # ------------------------------------------------------------------
    def _construction_exceeding_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda l: not l.cancelled and l.product_id and l._construction_get_excess() > 0)

    def action_request_approval(self):
        """Antes de pedir las revisiones: plan vigente, control del saldo y
        reparto de cada línea entre las líneas del plan (asignaciones)."""
        self._check_state(('draft',))
        for request in self:
            plan = request._construction_open_plan()
            if plan != request.construction_plan_id:
                request.construction_plan_id = plan
        checked = self.env.context.get('construction_exceed_checked')
        for request in self:
            plan = request.construction_plan_id
            exceeding = plan and request._construction_exceeding_lines()
            if not exceeding:
                request.construction_exceed_state = 'ok'
                continue
            if plan.exceed_policy == 'block':
                raise UserError(self.env._(
                    'El requerimiento %(request)s pide más de lo que queda en el plan '
                    '%(plan)s y su política es bloquear:\n\n%(lines)s',
                    request=request.name, plan=plan.display_name,
                    lines=exceeding._construction_excess_text()))
            if not checked and (plan.exceed_policy == 'approval'
                                and not request.construction_exceed_reason
                                or plan.exceed_policy == 'warn'):
                return request._construction_open_exceed_wizard()
            request.construction_exceed_state = 'exceeded'
        self._construction_sync_allocations()
        res = super().action_request_approval()
        # El residente no edita el plan: el primer documento solo lo pasa a
        # «En ejecución».
        plans_sudo = self.construction_plan_id.sudo()
        plans_sudo._mark_in_progress()
        return res

    def action_process(self):
        res = super().action_process()
        self._construction_refresh_plan()
        return res

    def _construction_refresh_plan(self):
        """Estado y montos de control de las líneas del plan asignadas."""
        self.env['construction.resource.plan.allocation']._refresh_for_documents(
            'material_request_line_id', self.line_ids)

    def _construction_open_exceed_wizard(self):
        self.ensure_one()
        wizard = self.env['construction.plan.exceed.wizard'].create({
            'material_request_id': self.id,
            'reason': self.construction_exceed_reason,
        })
        return wizard._get_action()

    def _write_approved(self):
        res = super()._write_approved()
        approved = self.filtered(
            lambda r: r.construction_exceed_state == 'exceeded'
            and r.construction_plan_id.exceed_policy == 'approval')
        if approved:
            approved.with_context(al_construction_approving=True).write(
                {'construction_exceed_state': 'approved'})
        return res

    def _construction_sync_allocations(self):
        """Reparte cada línea entre las líneas del plan (las ya asignadas o las
        del mismo material bajo su nivel) por fecha de necesidad."""
        # El residente que pide no tiene acceso al plan: solo se registran las
        # asignaciones de su propio requerimiento.
        Allocation_sudo = self.env['construction.resource.plan.allocation'].sudo()
        for request in self:
            plan = request.construction_plan_id
            for line in request.line_ids.filtered(lambda l: not l.cancelled and l.product_id):
                line_sudo = line.sudo()
                own = line_sudo.construction_allocation_ids
                plan_lines = line_sudo._construction_candidate_plan_lines(plan)
                if not plan_lines:
                    own.unlink()
                    continue
                shares = plan_lines._supply_split(line.product_uom_qty, own)
                own.unlink()
                Allocation_sudo.create([{
                    'plan_line_id': plan_line.id,
                    'kind': 'material_request',
                    'material_request_line_id': line.id,
                    'qty_allocated': qty,
                } for plan_line, qty in shares.items()
                    if not plan_line.product_uom_id.is_zero(qty)])


class ConstructionMaterialRequestLine(models.Model):
    _inherit = 'construction.material.request.line'

    construction_allocation_ids = fields.One2many(
        'construction.resource.plan.allocation', 'material_request_line_id',
        string='Asignaciones del plan')
    # El residente no ve el plan: el saldo se lee sin sus permisos y solo se
    # muestra.
    construction_plan_remaining = fields.Float(
        string='Saldo del plan', compute='_compute_construction_plan_control',
        digits='Product Unit', compute_sudo=True,
        help='Lo que queda por pedir de este material en el plan vigente, bajo el nivel de '
             'la línea, sin contar este requerimiento.')
    construction_out_of_plan = fields.Boolean(
        string='Fuera de plan', compute='_compute_construction_plan_control',
        compute_sudo=True)
    construction_plan_control = fields.Char(
        string='Control', compute='_compute_construction_plan_control', compute_sudo=True)
    construction_plan_exceeded = fields.Boolean(
        string='Excede el plan', compute='_compute_construction_plan_control',
        compute_sudo=True)

    def write(self, vals):
        res = super().write(vals)
        if {'cancelled', 'product_qty', 'product_uom_id'} & set(vals):
            self.env['construction.resource.plan.allocation']._refresh_for_documents(
                'material_request_line_id', self)
        return res

    def _construction_candidate_plan_lines(self, plan):
        """Líneas del plan que cubre esta línea: las ya asignadas en ese plan
        o, si no hay, las del mismo material bajo su nivel."""
        self.ensure_one()
        PlanLine = self.env['construction.resource.plan.line']
        if not plan or not self.product_id:
            return PlanLine
        assigned = self.construction_allocation_ids.plan_line_id.filtered(
            lambda l: l.plan_id == plan)
        if assigned:
            return assigned
        domain = [('plan_id', '=', plan.id), ('product_id', '=', self.product_id.id),
                  ('resource_type', 'in', SUPPLY_TYPES)]
        task = self.task_id or self.request_id.task_id
        if task:
            domain.append(('task_id', 'child_of', task.id))
        return PlanLine.search(domain)

    def _construction_get_excess(self):
        """Exceso sobre el saldo más la tolerancia, en la UdM del producto
        (0 si cabe o si la obra no tiene plan vigente)."""
        self.ensure_one()
        plan = self.request_id.construction_plan_id
        if not plan or not self.product_id:
            return 0.0
        line_sudo = self.sudo()
        plan_lines = line_sudo._construction_candidate_plan_lines(plan.sudo())
        _balance, tolerance, excess = plan_lines._supply_check(
            line_sudo.product_uom_qty, line_sudo.construction_allocation_ids)
        uom = self.product_id.uom_id
        return excess if uom.compare(excess, tolerance) > 0 else 0.0

    def _construction_excess_text(self):
        rows = []
        for line in self:
            excess = line.product_id.uom_id._compute_quantity(
                line._construction_get_excess(), line.product_uom_id)
            rows.append('   · %s: %s %s' % (
                line.product_id.display_name, formatLang(self.env, excess, digits=2),
                line.product_uom_id.name))
        return '\n'.join(rows)

    @api.depends('product_id', 'product_uom_qty', 'task_id', 'request_id.construction_plan_id',
                 'request_id.task_id')
    def _compute_construction_plan_control(self):
        for line in self:
            plan = line.request_id.construction_plan_id
            line.construction_plan_remaining = 0.0
            line.construction_out_of_plan = False
            line.construction_plan_control = False
            line.construction_plan_exceeded = False
            if not plan or not line.product_id or not line.product_uom_id:
                continue
            own = line.construction_allocation_ids
            plan_lines = line._construction_candidate_plan_lines(plan)
            if not plan_lines:
                line.construction_out_of_plan = True
                line.construction_plan_exceeded = True
                line.construction_plan_control = self.env._('Fuera de plan')
                continue
            balance, tolerance, excess = plan_lines._supply_check(line.product_uom_qty, own)
            uom = line.product_id.uom_id
            line.construction_plan_remaining = uom._compute_quantity(balance, line.product_uom_id)
            if uom.compare(excess, tolerance) > 0:
                line.construction_plan_exceeded = True
                line.construction_plan_control = self.env._(
                    'Excede %s', formatLang(
                        self.env, uom._compute_quantity(excess, line.product_uom_id), digits=2))
            else:
                line.construction_plan_control = self.env._('En plan')
