# -*- coding: utf-8 -*-
"""Exceso en la orden de fabricación y aprobación del jefe de producción
(paquete 1.9, M19-04).

Con el motor «Aplicación Aprobaciones», la orden del plan se confirma sin el
asistente de la política de exceso y compara, por material, lo presupuestado
en el plan con lo requerido en sus componentes. Si hay exceso:

* dentro del margen del jefe de producción, él lo aprueba en la orden;
* por encima, «Solicitar aprobación» lo envía a Aprobaciones con los tramos
  de la tabla de rutas (documento «Orden de fabricación»).

Mientras el exceso esté pendiente, la orden no empieza."""
from collections import defaultdict

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

PRODUCTION_HEAD_GROUP = 'al_construction_planner_approvals_mrp.group_planner_production_head'


class MrpProduction(models.Model):
    _name = 'mrp.production'
    _inherit = ['mrp.production', 'construction.approval.mixin']

    _construction_approval_document_type = 'production'

    construction_currency_id = fields.Many2one(
        related='company_id.currency_id', string='Moneda de la compañía')
    construction_versus_ids = fields.One2many(
        'construction.production.versus', 'production_id',
        string='Presupuestado frente a requerido', readonly=True)
    construction_excess_amount = fields.Monetary(
        string='Exceso (monto)', currency_field='construction_currency_id', readonly=True,
        copy=False, help='Según la base del margen: el de la orden o el de los materiales que '
                         'exceden.')
    construction_excess_pct = fields.Float(
        string='Exceso (%)', digits=(16, 2), readonly=True, copy=False)
    construction_excess_material = fields.Boolean(
        string='Con cambio de material', readonly=True, copy=False,
        help='Requiere un material que no está en el plan.')
    construction_excess_approved_amount = fields.Monetary(
        string='Exceso aprobado', currency_field='construction_currency_id', readonly=True,
        copy=False)
    construction_excess_approved_by = fields.Many2one(
        'res.users', string='Exceso aprobado por', readonly=True, copy=False)
    construction_excess_approved_date = fields.Datetime(
        string='Fecha de aprobación del exceso', readonly=True, copy=False)
    construction_excess_action = fields.Selection(
        [('approve', 'Aprobar exceso'), ('request', 'Solicitar aprobación')],
        compute='_compute_construction_excess_action',
        help='Qué hace el usuario con el exceso pendiente: aprobarlo dentro de su margen o '
             'pedirlo en Aprobaciones.')

    def _construction_excess_pending(self):
        self.ensure_one()
        return self.construction_approval_engine == 'approvals' \
            and self.construction_exceed_state == 'exceeded'

    def _construction_within_margin(self):
        self.ensure_one()
        company = self.company_id
        margin = company.construction_production_margin
        if margin <= 0:
            return False
        if self.construction_excess_material and not company.construction_production_margin_material:
            return False
        return self.construction_excess_pct <= margin

    @api.depends_context('uid')
    @api.depends('construction_exceed_state', 'construction_approval_engine',
                 'construction_excess_pct', 'construction_excess_material')
    def _compute_construction_excess_action(self):
        is_head = self.env.user.has_group(PRODUCTION_HEAD_GROUP)
        for production in self:
            action = False
            if production._construction_excess_pending() \
                    and not production.construction_approval_id:
                within = production._construction_within_margin()
                action = 'approve' if within and is_head else 'request'
            production.construction_excess_action = action

    # ------------------------------------------------------------------
    # Comparación
    # ------------------------------------------------------------------
    def _construction_versus_values(self):
        """Filas por material: presupuestado del plan en los ambientes y las
        etapas que fabrica la orden (paquete 1.10, M110-04: el corte solo lo
        de producción de piezas), frente a sus componentes."""
        self.ensure_one()
        # La planta no ve el plan: el presupuesto se lee sin sus permisos.
        production_sudo = self.sudo()
        plan_lines = self.env['construction.resource.plan.line'].sudo().search([
            ('plan_id', '=', production_sudo.construction_plan_id.id),
            ('resource_type', '=', 'material'), ('product_id', '!=', False),
            ('stage', 'in', production_sudo._construction_order_stages()),
            ('space_task_id', 'in', production_sudo.construction_space_task_ids.ids)])
        budget = defaultdict(lambda: [0.0, 0.0])
        for line in plan_lines:
            budget[line.product_id][0] += line._qty_to_product_uom(line.qty_planned)
            budget[line.product_id][1] += line.amount_planned
        required = production_sudo._construction_component_qty()
        rounding = production_sudo._construction_rounding_by_product()
        values = []
        for product in sorted(set(budget) | set(required), key=lambda p: p.display_name):
            qty_budget, amount_budget = budget.get(product, (0.0, 0.0))
            qty_required = required.get(product, 0.0)
            uom = product.uom_id
            price = amount_budget / qty_budget if qty_budget else \
                product.with_company(self.company_id).standard_price
            diff = qty_required - qty_budget
            if uom.is_zero(qty_budget) and uom.compare(qty_required, 0) > 0:
                change = 'material'
            elif uom.compare(diff, 0) > 0:
                change = 'quantity'
            else:
                change = False
            values.append({
                'production_id': self.id,
                'product_id': product.id,
                'uom_id': uom.id,
                'change_type': change,
                'qty_budget': qty_budget,
                'qty_required': qty_required,
                'qty_diff': diff,
                'diff_pct': diff / qty_budget * 100 if qty_budget else (100.0 if change else 0.0),
                'amount_budget': amount_budget,
                'amount_required': qty_required * price,
                'amount_diff': qty_required * price - amount_budget,
                'qty_rounding': rounding.get(product, 0.0),
            })
        return values

    def _construction_rounding_by_product(self):
        """{producto: entregado − necesidad} de los tableros en planchas
        enteras (M111-12), en la UdM del producto."""
        self.ensure_one()
        result = defaultdict(float)
        for move in self.move_raw_ids.filtered('construction_need_qty'):
            uom = move.product_id.uom_id
            delivered = 0.0 if move.state == 'cancel' else move.product_uom_qty
            result[move.product_id] += move.product_uom._compute_quantity(
                delivered + move._construction_covered_qty() - move.construction_need_qty,
                uom, round=False)
        return result

    def _construction_refresh_versus(self):
        """Rehace la comparación y el estado del exceso. Un exceso aprobado
        vuelve a pendiente si crece."""
        Versus_sudo = self.env['construction.production.versus'].sudo()
        for production in self.filtered('construction_plan_id'):
            values = production._construction_versus_values()
            # La comparación es un registro de la orden: la escribe el sistema.
            production.sudo().construction_versus_ids.unlink()
            Versus_sudo.create(values)
            basis = production.company_id.construction_production_margin_basis
            over = [v for v in values if v['change_type']]
            if basis == 'order':
                budget_total = sum(v['amount_budget'] for v in values)
                amount = sum(v['amount_diff'] for v in values)
                percent = amount / budget_total * 100 if budget_total else (100.0 if over else 0.0)
            else:
                amount = sum(v['amount_diff'] for v in over)
                percent = max((v['diff_pct'] for v in over), default=0.0)
            material = any(v['change_type'] == 'material' for v in over)
            currency = production.company_id.currency_id
            needs = material or currency.compare_amounts(amount, 0) > 0 \
                if basis == 'order' else bool(over)
            state = production.construction_exceed_state
            if not needs:
                state = 'ok'
            elif state != 'approved' or currency.compare_amounts(
                    amount, production.construction_excess_approved_amount) > 0:
                state = 'exceeded'
            production.write({
                'construction_excess_amount': max(amount, 0.0),
                'construction_excess_pct': max(percent, 0.0),
                'construction_excess_material': material,
                'construction_exceed_state': state,
            })

    def action_construction_refresh_versus(self):
        self._construction_refresh_versus()
        return True

    # ------------------------------------------------------------------
    # Confirmar
    # ------------------------------------------------------------------
    def action_confirm(self):
        approvals = self.filtered(
            lambda p: p.construction_plan_id and p.state == 'draft'
            and p.company_id.construction_approval_engine == 'approvals')
        if not approvals:
            return super().action_confirm()
        approvals._construction_set_approval_engine()
        # El exceso no pasa por el asistente de la política ni por la
        # autorización de la receta real: lo controla la orden.
        res = super(MrpProduction, self.with_context(
            construction_exceed_checked=True,
            construction_skip_recipe_authorization=True)).action_confirm()
        approvals._construction_refresh_versus()
        for production in approvals.filtered(lambda p: p._construction_excess_pending()):
            production.message_post(body=self.env._(
                'Excede lo presupuestado en %(amount)s (%(pct)s %%): no empieza hasta que se '
                'apruebe el exceso.',
                amount=formatLang(self.env, production.construction_excess_amount,
                                  currency_obj=production.company_id.currency_id),
                pct=formatLang(self.env, production.construction_excess_pct, digits=2)))
        return res

    # ------------------------------------------------------------------
    # Aprobar el exceso
    # ------------------------------------------------------------------
    def action_construction_approve_excess(self):
        self.ensure_one()
        if self.construction_excess_action != 'approve':
            raise UserError(self.env._(
                'El exceso de %s no está dentro de su margen: solicite la aprobación.',
                self.name))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Aprobar exceso'),
            'res_model': 'construction.excess.approve.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_production_id': self.id},
        }

    def _construction_excess_approved(self, reason, approver=None):
        """Registra la aprobación: quién, cuándo, motivo y cada exceso."""
        self.ensure_one()
        approver = approver or self.env.user
        values = {
            'construction_exceed_state': 'approved',
            'construction_excess_approved_amount': self.construction_excess_amount,
            'construction_excess_approved_by': approver.id,
            'construction_excess_approved_date': fields.Datetime.now(),
        }
        if reason:
            values['construction_exceed_reason'] = reason
        self.write(values)
        plan_sudo = self.sudo().construction_plan_id
        self.env['construction.exceed.log']._log([{
            'kind': 'excess', 'plan_id': plan_sudo.id, 'project_id': plan_sudo.project_id.id,
            'company_id': self.company_id.id, 'product_id': row.product_id.id,
            'qty': row.qty_diff, 'uom_id': row.uom_id.id, 'amount': row.amount_diff,
            'reason': reason or self.construction_exceed_reason, 'user_id': approver.id,
            'document': self.name, 'res_model': self._name, 'res_id': self.id,
        } for row in self.construction_versus_ids.filtered('change_type')])
        self.message_post(body=Markup('%s<br/>%s') % (
            self.env._('Exceso aprobado por %s.', approver.name), reason or ''))

    def action_construction_request_excess_approval(self):
        self.ensure_one()
        if not self._construction_excess_pending():
            raise UserError(self.env._('%s no tiene un exceso pendiente.', self.name))
        if self.construction_approval_id:
            raise UserError(self.env._('%s ya tiene una solicitud abierta.', self.name))
        if not self._construction_submit_approval():
            raise UserError(self.env._(
                'No hay ruta de aprobación para la orden de fabricación: configure la tabla de '
                'rutas en Planificación de obra › Configuración.'))
        return True

    def _construction_approval_info(self):
        self.ensure_one()
        rows = self.construction_versus_ids.filtered('change_type')
        values = {}
        for change in ('material', 'quantity'):
            own = rows.filtered(lambda r: r.change_type == change)
            if not own:
                continue
            values[change] = {
                'percent': 100.0 if change == 'material' else self.construction_excess_pct,
                'amount': sum(own.mapped('amount_diff')),
            }
        if values:
            values['all'] = {'percent': self.construction_excess_pct,
                             'amount': self.construction_excess_amount}
        # Paquete 1.10, M110-08: la orden se compara con lo presupuestado de sus
        # ambientes, no con un saldo: «Ya pedido» y «Saldo» quedan vacíos.
        lines = [{
            'product_id': row.product_id.id,
            'description': row.product_id.display_name,
            'quantity': row.qty_required,
            'product_uom_id': row.uom_id.id,
            'construction_change_type': row.change_type,
            'construction_qty_planned': row.qty_budget,
            'construction_qty_diff': min(row.qty_required, row.qty_diff),
            'construction_diff_pct': row.diff_pct,
            'construction_amount_diff': row.amount_diff,
        } for row in rows]
        # M111-05: la solicitud muestra el % de la orden (según la base del
        # margen), no el mayor de sus materiales.
        return {'values': values, 'lines': lines, 'amount': self.construction_excess_amount,
                'percent': self.construction_excess_pct,
                'reason': self.construction_exceed_reason or ''}

    def _construction_project(self):
        self.ensure_one()
        return self.sudo().construction_plan_id.project_id

    def _construction_awaiting_approval(self):
        """La orden espera lo que diga su solicitud mientras el exceso siga
        pendiente (M110-08)."""
        self.ensure_one()
        return self.construction_exceed_state == 'exceeded'

    def _construction_approval_granted(self, request):
        self.ensure_one()
        if self.construction_exceed_state != 'exceeded':
            return
        self.message_post(body=self.env._('Exceso aprobado en %s.', request.name))
        approver = request.approver_ids.filtered(lambda a: a.status == 'approved')[-1:].user_id
        self._construction_excess_approved(False, approver=approver)

    def _construction_approval_refused(self, request):
        """La orden sigue con el exceso pendiente: se corrigen los componentes
        y se vuelve a pedir."""
        self.ensure_one()
        if request.request_status == 'refused':
            body = self.env._('Exceso rechazado en %(request)s: %(reason)s', request=request.name,
                              reason=request.construction_refuse_reason or self.env._('sin motivo'))
        else:
            body = self.env._('La solicitud %s se canceló.', request.name)
        self.message_post(body=body)

    # ------------------------------------------------------------------
    # Sin empezar con el exceso pendiente
    # ------------------------------------------------------------------
    def _construction_check_can_start(self):
        pending = self.filtered(lambda p: p._construction_excess_pending())
        if pending:
            raise UserError(self.env._(
                '%s tiene un exceso sobre lo presupuestado pendiente de aprobación: no puede '
                'empezar.', ', '.join(pending.mapped('name'))))

    def write(self, vals):
        if vals.get('qty_producing'):
            self._construction_check_can_start()
        return super().write(vals)

    def action_cancel(self):
        self._construction_cancel_open_approvals()
        return super().action_cancel()

    def button_mark_done(self):
        self._construction_check_can_start()
        return super().button_mark_done()


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    def button_start(self, *args, **kwargs):
        self.production_id._construction_check_can_start()
        return super().button_start(*args, **kwargs)


class StockMove(models.Model):
    _inherit = 'stock.move'

    def write(self, vals):
        if vals.get('picked'):
            self.raw_material_production_id._construction_check_can_start()
        return super().write(vals)
