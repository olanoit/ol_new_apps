# -*- coding: utf-8 -*-
"""Pedido de accesorios de armado (paquete 1.9, M19-02).

Lo pide el jefe de producción, o quien él asigne, desde la orden de
fabricación, sobre lo proyectado de sus módulos en la sub etapa Armado. Sin
cambios, lo pedido entra directo a los componentes de la orden y sale del
almacén con la preparación de componentes. Un cambio de material (otro
producto o uno que no está en el plan) o de cantidad (más que el saldo) va a
Oficina Técnica por Aprobaciones, con el jefe de proyectos como seguidor."""
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner_approvals.models.construction_approval_route import (
    CHANGE_TYPES)

REQUEST_STATES = [
    ('draft', 'Borrador'),
    ('to_approve', 'En aprobación'),
    ('done', 'Agregado a la orden'),
    ('cancel', 'Cancelado'),
]


class ConstructionAccessoryRequest(models.Model):
    _name = 'construction.accessory.request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'construction.approval.mixin',
                'construction.amounts.mixin']
    _description = 'Pedido de accesorios de armado'
    _order = 'id desc'
    _check_company_auto = True

    _construction_approval_document_type = 'accessories'

    name = fields.Char(string='Número', required=True, readonly=True, copy=False, default='/')
    production_id = fields.Many2one(
        'mrp.production', string='Orden de fabricación', required=True, index=True,
        check_company=True, ondelete='cascade')
    company_id = fields.Many2one(related='production_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    project_id = fields.Many2one(
        'project.project', string='Obra', compute='_compute_project_id', store=True,
        index=True)
    user_id = fields.Many2one(
        'res.users', string='Pedido por', required=True, default=lambda self: self.env.user)
    state = fields.Selection(
        REQUEST_STATES, string='Estado', required=True, default='draft', tracking=True,
        copy=False)
    line_ids = fields.One2many(
        'construction.accessory.request.line', 'request_id', string='Accesorios', copy=True)
    has_changes = fields.Boolean(string='Con cambios', compute='_compute_has_changes',
                                 store=True)
    amount_diff = fields.Monetary(
        string='Diferencia (monto)', currency_field='currency_id', compute='_compute_has_changes',
        store=True)
    note = fields.Text(string='Motivo del cambio')

    @api.depends('production_id.construction_plan_id')
    def _compute_project_id(self):
        for request in self:
            # La planta no lee el plan: solo se toma su obra.
            request.project_id = request.production_id.sudo().construction_plan_id.project_id

    @api.depends('line_ids.change_type', 'line_ids.amount_diff')
    def _compute_has_changes(self):
        for request in self:
            changed = request.line_ids.filtered('change_type')
            request.has_changes = bool(changed)
            request.amount_diff = sum(changed.mapped('amount_diff'))

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'amount_diff'}

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'construction.accessory.request') or '/'
        return super().create(vals_list)

    def _construction_project(self):
        self.ensure_one()
        return self.project_id

    # ------------------------------------------------------------------
    # Flujo
    # ------------------------------------------------------------------
    def action_submit(self):
        """Sin cambios va directo a la orden; con cambios, a Aprobaciones."""
        for request in self:
            if request.state != 'draft':
                raise UserError(self.env._('%s ya se envió.', request.name))
            request.production_id._construction_check_accessories_user()
            lines = request.line_ids.filtered(lambda l: l.qty > 0)
            if not lines:
                raise UserError(self.env._('%s no tiene accesorios por pedir.', request.name))
            if request.has_changes and not request.note:
                raise UserError(self.env._(
                    'Indique el motivo del cambio de %s: va a Oficina Técnica.', request.name))
            request.state = 'to_approve'
            if not request.has_changes:
                request._construction_apply()
                continue
            request.construction_approval_engine = 'approvals'
            if not request._construction_submit_approval():
                raise UserError(self.env._(
                    'No hay ruta de aprobación para los accesorios de armado: configure la tabla '
                    'de rutas en Planificación de obra › Configuración.'))
        return True

    def _construction_apply(self):
        """Agrega lo pedido a los componentes de la orden."""
        for request in self:
            quantities = {}
            for line in request.line_ids.filtered(lambda l: l.qty > 0):
                qty = line.uom_id._compute_quantity(line.qty, line.product_id.uom_id)
                quantities[line.product_id] = quantities.get(line.product_id, 0.0) + qty
            request.production_id._construction_add_components(quantities)
            request.state = 'done'
            request.production_id.message_post(body=Markup('%s <a href="#" data-oe-model="%s" '
                                                           'data-oe-id="%s">%s</a>') % (
                self.env._('Accesorios agregados desde'), request._name, request.id,
                request.name))

    def _construction_approval_info(self):
        self.ensure_one()
        changed = self.line_ids.filtered('change_type')
        values = {}
        for change in ('material', 'quantity'):
            own = changed.filtered(lambda l: l.change_type == change)
            if own:
                values[change] = {'percent': max(own.mapped('diff_pct')),
                                  'amount': sum(own.mapped('amount_diff'))}
        if values:
            values['all'] = {'percent': max(v['percent'] for v in values.values()),
                             'amount': sum(v['amount'] for v in values.values())}
        # Cifras de la solicitud (paquete 1.10, M110-08): como el requerimiento,
        # presupuestado del plan, ya pedido y saldo del accesorio en el nivel.
        planned = self.production_id._construction_accessory_planned()
        lines = []
        for line in changed:
            qty_planned = planned.get((line.task_id, line.planned_product_id), 0.0) \
                if line.planned_product_id else 0.0
            if line.planned_product_id and line.uom_id:
                qty_planned = line.planned_product_id.uom_id._compute_quantity(
                    qty_planned, line.uom_id)
            lines.append({
                'product_id': line.product_id.id,
                'description': '%s · %s' % (line.task_id.display_name or '',
                                             line.product_id.display_name),
                'quantity': line.qty,
                'product_uom_id': line.uom_id.id,
                'construction_change_type': line.change_type,
                'construction_level': line.task_id.display_name,
                'construction_qty_planned': qty_planned,
                'construction_qty_requested_before': qty_planned - line.qty_balance
                if line.planned_product_id else 0.0,
                'construction_qty_budget': line.qty_balance,
                'construction_qty_diff': line._construction_excess_qty(),
                'construction_diff_pct': line.diff_pct,
                'construction_amount_diff': line.amount_diff,
            })
        return {'values': values, 'lines': lines, 'amount': self.amount_diff,
                'reason': self.note or ''}

    def _construction_approval_granted(self, request):
        self.ensure_one()
        if self.state != 'to_approve':
            return
        self.message_post(body=self.env._('Aprobado en %s.', request.name))
        self._construction_apply()

    def action_draft(self):
        for request in self:
            if request.state not in ('to_approve', 'cancel'):
                raise UserError(self.env._('%s no se puede volver a borrador.', request.name))
        self.filtered(lambda r: r.state == 'to_approve')._construction_cancel_open_approvals()
        self.write({'state': 'draft'})

    def action_cancel(self):
        if self.filtered(lambda r: r.state == 'done'):
            raise UserError(self.env._('Un pedido ya agregado a la orden no se cancela.'))
        self.filtered(lambda r: r.state == 'to_approve')._construction_cancel_open_approvals()
        self.write({'state': 'cancel'})

    def action_open_production(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'mrp.production',
                'res_id': self.production_id.id, 'view_mode': 'form'}


class ConstructionAccessoryRequestLine(models.Model):
    _name = 'construction.accessory.request.line'
    _inherit = ['construction.amounts.mixin']
    _description = 'Accesorio pedido'
    _order = 'request_id, task_id, id'

    request_id = fields.Many2one(
        'construction.accessory.request', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='request_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda')
    task_id = fields.Many2one('project.task', string='Nivel')
    planned_product_id = fields.Many2one(
        'product.product', string='Proyectado', readonly=True,
        help='El accesorio del plan; vacío si no está en el plan.')
    product_id = fields.Many2one('product.product', string='Accesorio', required=True)
    uom_id = fields.Many2one(
        'uom.uom', string='Unidad', compute='_compute_uom_id', store=True, readonly=False)
    qty_balance = fields.Float(
        string='Saldo', digits='Product Unit', readonly=True,
        help='Lo que queda por pedir del accesorio proyectado para este nivel.')
    qty = fields.Float(string='Cantidad', digits='Product Unit', required=True)
    price_unit = fields.Float(string='Costo unitario', digits='Product Price', readonly=True)
    change_type = fields.Selection(
        [item for item in CHANGE_TYPES if item[0] != 'all'], string='Cambio',
        compute='_compute_change', store=True)
    diff_pct = fields.Float(string='Diferencia (%)', digits=(16, 2), compute='_compute_change',
                            store=True)
    amount_diff = fields.Monetary(
        string='Diferencia (monto)', currency_field='currency_id', compute='_compute_change',
        store=True)

    @api.depends('product_id')
    def _compute_uom_id(self):
        for line in self:
            line.uom_id = line.uom_id or line.product_id.uom_id

    @api.depends('product_id', 'planned_product_id', 'qty', 'qty_balance', 'price_unit')
    def _compute_change(self):
        for line in self:
            uom = line.uom_id or line.product_id.uom_id
            change, pct, amount = False, 0.0, 0.0
            if line.product_id and line.product_id != line.planned_product_id:
                change, pct = 'material', 100.0
                amount = line.qty * (line.price_unit or line.product_id.standard_price)
            elif uom and uom.compare(line.qty, line.qty_balance) > 0:
                change = 'quantity'
                diff = line._construction_excess_qty()
                pct = diff / line.qty_balance * 100 if line.qty_balance else 100.0
                amount = diff * line.price_unit
            line.change_type = change
            line.diff_pct = pct
            line.amount_diff = amount

    def _construction_excess_qty(self):
        """Lo pedido sobre el saldo, nunca más que lo pedido (M110-08)."""
        self.ensure_one()
        return min(self.qty, self.qty - self.qty_balance)

    @api.model
    def _construction_amount_fields(self):
        return super()._construction_amount_fields() | {'price_unit', 'amount_diff'}
