# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.al_construction_planner_approvals_mrp.models.mrp_production import (
    PRODUCTION_HEAD_GROUP)

LOGISTICS_GROUP = 'al_construction_material_request.group_construction_logistics'


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    construction_accessory_request_ids = fields.One2many(
        'construction.accessory.request', 'production_id', string='Pedidos de accesorios')
    construction_accessory_count = fields.Integer(
        string='Accesorios', compute='_compute_construction_accessory_count')
    construction_accessories_user_id = fields.Many2one(
        'res.users', string='Pide los accesorios', copy=False,
        domain=[('share', '=', False)],
        help='Quien pide los accesorios de armado de esta orden, además del jefe de producción.')
    construction_can_request_accessories = fields.Boolean(
        compute='_compute_construction_can_request_accessories')
    construction_analysis_ids = fields.One2many(
        'construction.production.analysis', 'production_id',
        string='Presupuestado frente a real por nivel')

    def _compute_construction_accessory_count(self):
        for production in self:
            production.construction_accessory_count = len(
                production.construction_accessory_request_ids)

    @api.depends_context('uid')
    @api.depends('construction_accessories_user_id', 'state', 'construction_plan_id')
    def _compute_construction_can_request_accessories(self):
        is_head = self.env.user.has_group(PRODUCTION_HEAD_GROUP)
        for production in self:
            production.construction_can_request_accessories = bool(
                production.construction_plan_id
                and production.state not in ('done', 'cancel')
                and (is_head or production.construction_accessories_user_id == self.env.user))

    # ------------------------------------------------------------------
    # Accesorios de armado (M19-02)
    # ------------------------------------------------------------------
    def _construction_check_accessories_user(self):
        for production in self:
            if not production.construction_can_request_accessories:
                raise AccessError(self.env._(
                    'Los accesorios de %s los pide el jefe de producción o quien él asigne.',
                    production.name))

    def action_construction_request_accessories(self):
        """Abre el pedido en borrador de la orden o crea uno con lo proyectado
        de Armado que queda por pedir."""
        self.ensure_one()
        self._construction_check_accessories_user()
        request = self.construction_accessory_request_ids.filtered(lambda r: r.state == 'draft')[:1]
        if not request:
            request = self.env['construction.accessory.request'].create({
                'production_id': self.id,
                'line_ids': [fields.Command.create(vals)
                             for vals in self._construction_proposed_accessories()],
            })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Pedir accesorios'),
            'res_model': 'construction.accessory.request',
            'res_id': request.id,
            'view_mode': 'form',
        }

    def _construction_proposed_accessories(self):
        """Por nivel y accesorio del plan (Armado): lo planificado menos lo ya
        pedido en otros pedidos de accesorios de la obra."""
        self.ensure_one()
        planned = defaultdict(lambda: [0.0, 0.0])
        for line in self._construction_assembly_plan_lines():
            key = (line.task_id, line.product_id)
            planned[key][0] += line._qty_to_product_uom(line.qty_planned)
            planned[key][1] += line.amount_planned
        # Los pedidos de otras órdenes de la obra pueden no ser de quien pide.
        previous_sudo = self.env['construction.accessory.request.line'].sudo().search([
            ('request_id.project_id', '=', self.sudo().construction_plan_id.project_id.id),
            ('request_id.state', 'in', ('to_approve', 'done')),
            ('planned_product_id', '!=', False)])
        asked = defaultdict(float)
        for line in previous_sudo:
            asked[(line.task_id, line.planned_product_id)] += line.uom_id._compute_quantity(
                line.qty, line.planned_product_id.uom_id)
        values = []
        for (task, product), (qty, amount) in sorted(
                planned.items(), key=lambda item: (item[0][0].display_name or '',
                                                   item[0][1].display_name)):
            balance = qty - asked[(task, product)]
            if product.uom_id.compare(balance, 0) <= 0:
                continue
            values.append({
                'task_id': task.id, 'planned_product_id': product.id,
                'product_id': product.id, 'uom_id': product.uom_id.id,
                'qty_balance': balance, 'qty': balance,
                'price_unit': amount / qty if qty else product.standard_price,
            })
        return values

    def action_view_construction_accessories(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': self.env._('Accesorios'),
            'res_model': 'construction.accessory.request',
            'domain': [('production_id', '=', self.id)],
            'view_mode': 'list,form',
        }
        if len(self.construction_accessory_request_ids) == 1:
            action.update(view_mode='form', res_id=self.construction_accessory_request_ids.id)
        return action

    def _construction_assembly_plan_lines(self):
        """Líneas de material de armado del plan en los ambientes de la orden."""
        self.ensure_one()
        production_sudo = self.sudo()
        return self.env['construction.resource.plan.line'].sudo().search([
            ('plan_id', '=', production_sudo.construction_plan_id.id),
            ('resource_type', '=', 'material'), ('product_id', '!=', False),
            ('stage', '=', 'assembly'),
            ('space_task_id', 'in', production_sudo.construction_space_task_ids.ids)])

    def _construction_add_components(self, quantities):
        """Suma {producto: cantidad en su UdM} a los componentes de la orden."""
        self.ensure_one()
        # La orden confirmada no la edita quien pide en planta: los
        # componentes salen del pedido de accesorios aprobado.
        production_sudo = self.sudo()
        Move_sudo = self.env['stock.move'].sudo()
        new_moves = Move_sudo
        for product, qty in quantities.items():
            if product.uom_id.compare(qty, 0) <= 0:
                continue
            move = production_sudo.move_raw_ids.filtered(
                lambda m: m.product_id == product and m.state not in ('done', 'cancel'))[:1]
            if move:
                move.product_uom_qty += product.uom_id._compute_quantity(qty, move.product_uom)
                continue
            new_moves |= Move_sudo.create(production_sudo._get_move_raw_values(
                product, qty, product.uom_id))
        if new_moves and production_sudo.state != 'draft':
            new_moves._action_confirm()
            new_moves._action_assign()
        if production_sudo.state != 'draft':
            production_sudo._construction_sync_allocations()
            production_sudo._construction_refresh_versus()

    def _construction_notify_missing_accessories(self):
        """Confirmada sin accesorios pedidos: avisa al jefe de proyectos y a
        Logística."""
        logistics = self.env.ref(LOGISTICS_GROUP, raise_if_not_found=False)
        for production in self:
            if production.construction_accessory_request_ids.filtered(
                    lambda r: r.state != 'cancel'):
                continue
            if not production._construction_assembly_plan_lines():
                continue
            partners = production.sudo().construction_plan_id.project_id.user_id.partner_id
            if logistics:
                partners |= logistics.all_user_ids.filtered(
                    lambda u: u.active and not u.share
                    and production.company_id in u.company_ids).partner_id
            production.message_post(
                body=self.env._('Orden confirmada sin pedir los accesorios de armado.'),
                partner_ids=partners.ids, subtype_xmlid='mail.mt_comment')

    def action_confirm(self):
        drafts = self.filtered(lambda p: p.construction_plan_id and p.state == 'draft')
        res = super().action_confirm()
        drafts.filtered(lambda p: p.state != 'draft')._construction_notify_missing_accessories()
        return res

    # ------------------------------------------------------------------
    # Presupuestado, requerido y consumido (M19-05)
    # ------------------------------------------------------------------
    def _construction_consumed(self):
        """{producto: (cantidad, valor)} de los componentes consumidos."""
        self.ensure_one()
        result = defaultdict(lambda: [0.0, 0.0])
        for move in self.sudo().move_raw_ids.filtered(lambda m: m.state == 'done'):
            result[move.product_id][0] += move.product_uom._compute_quantity(
                move.quantity, move.product_id.uom_id)
            result[move.product_id][1] += abs(move.value)
        return result

    def _construction_versus_values(self):
        """Suma lo consumido de cada material comparado. Los componentes de
        otras etapas (instalación, acabados) quedan fuera, como en lo
        requerido."""
        values = super()._construction_versus_values()
        consumed = self._construction_consumed()
        for row in values:
            product = self.env['product.product'].browse(row['product_id'])
            qty, amount = consumed.get(product, (0.0, 0.0))
            row.update(qty_consumed=qty, amount_consumed=amount)
        return values

    def _construction_refresh_versus(self):
        res = super()._construction_refresh_versus()
        self._construction_refresh_analysis()
        return res

    def _construction_refresh_analysis(self):
        Analysis_sudo = self.env['construction.production.analysis'].sudo()
        for production in self.filtered('construction_plan_id'):
            # El informe es un registro del sistema: lo rehace la orden.
            production.sudo().construction_analysis_ids.unlink()
            production_sudo = production.sudo()
            plan_lines = self.env['construction.resource.plan.line'].sudo().search([
                ('plan_id', '=', production_sudo.construction_plan_id.id),
                ('resource_type', '=', 'material'), ('product_id', '!=', False),
                ('stage', 'in', self.env['construction.stage']._production_codes()),
                ('space_task_id', 'in', production_sudo.construction_space_task_ids.ids)])
            budget = defaultdict(lambda: [0.0, 0.0])
            for line in plan_lines:
                key = (line.product_id, line.task_id, line.space_task_id, line.stage)
                budget[key][0] += line._qty_to_product_uom(line.qty_planned)
                budget[key][1] += line.amount_planned
            values = []
            spaces = production_sudo.construction_space_task_ids
            for row in production_sudo.construction_versus_ids:
                product = row.product_id
                keys = [key for key in budget if key[0] == product]
                total = sum(budget[key][0] for key in keys)
                if not keys:
                    keys = [(product, space, space, False) for space in spaces]
                for key in keys:
                    share = budget[key][0] / total if total else 1.0 / len(keys)
                    qty_budget, amount_budget = budget.get(key, (0.0, 0.0))
                    price = row.amount_required / row.qty_required if row.qty_required else 0.0
                    amount_required = row.qty_required * share * price
                    values.append({
                        'production_id': production.id,
                        'project_id': production_sudo.construction_plan_id.project_id.id,
                        'task_id': key[1].id, 'space_task_id': key[2].id, 'stage': key[3],
                        'product_id': product.id,
                        'qty_budget': qty_budget, 'amount_budget': amount_budget,
                        'qty_required': row.qty_required * share,
                        'amount_required': amount_required,
                        'qty_consumed': row.qty_consumed * share,
                        'amount_consumed': row.amount_consumed * share,
                        'amount_diff': amount_required - amount_budget,
                    })
            Analysis_sudo.create(values)

    def button_mark_done(self):
        res = super().button_mark_done()
        self.filtered(lambda p: p.state == 'done' and p.construction_versus_ids)\
            ._construction_refresh_versus()
        return res

    def action_cancel(self):
        if self.construction_accessory_request_ids.filtered(
                lambda r: r.state in ('draft', 'to_approve')):
            raise UserError(self.env._(
                'Cancele antes los pedidos de accesorios abiertos de la orden.'))
        return super().action_cancel()
