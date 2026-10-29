# -*- coding: utf-8 -*-
"""Adicionales de la contrata (requerimiento CREVAL v1.0, 3.9): aprobado el
cambio de obra, «Agregar a la orden de contrata» añade sus líneas de contrata a
la orden del contratista en la obra, marcadas como adicional y con referencia
al cambio. Si la orden pasa su monto aprobado, la diferencia vuelve a
aprobación (ver al_construction_planner_subcontract)."""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.al_construction_planner.models.common import EXEC_USER_GROUP


class ConstructionChangeOrder(models.Model):
    _inherit = 'construction.change.order'

    construction_contractor_id = fields.Many2one(
        'res.partner', string='Contratista', check_company=True, tracking=True,
        help='Quien ejecuta el adicional: obligatorio para agregarlo a su orden de contrata.')
    construction_purchase_line_ids = fields.One2many(
        'purchase.order.line', 'construction_change_id', string='En orden de contrata',
        readonly=True)
    construction_purchase_order_id = fields.Many2one(
        'purchase.order', string='Orden de contrata',
        compute='_compute_construction_purchase_order_id')
    construction_can_add_to_order = fields.Boolean(
        compute='_compute_construction_purchase_order_id')

    @api.depends('construction_purchase_line_ids', 'state', 'construction_contractor_id')
    def _compute_construction_purchase_order_id(self):
        for change in self:
            # sudo: quien registra el cambio no siempre lee compras.
            lines_sudo = change.sudo().construction_purchase_line_ids
            change.construction_purchase_order_id = lines_sudo.order_id[:1].id
            change.construction_can_add_to_order = (
                change.state == 'approved' and not lines_sudo
                and bool(change.line_ids.filtered(lambda l: l.resource_type == 'contract')))

    def action_add_to_contract_order(self):
        """Suma las líneas de contrata del cambio aprobado a la orden del
        contratista en la obra (o a una nueva en borrador)."""
        self.ensure_one()
        if not self.env.user.has_group(EXEC_USER_GROUP):
            raise UserError(self.env._('Agrega adicionales a la orden quien ejecuta la obra.'))
        if self.state != 'approved':
            raise UserError(self.env._('Solo un cambio aprobado se agrega a la orden de contrata.'))
        if not self.construction_contractor_id:
            raise UserError(self.env._('Indique el contratista que ejecuta el adicional.'))
        plan_lines = self.plan_line_ids.filtered(lambda l: l.resource_type == 'contract')
        if not plan_lines:
            raise UserError(self.env._('El cambio %s no tiene líneas de contrata.', self.name))
        if self.sudo().construction_purchase_line_ids:
            raise UserError(self.env._('El cambio %s ya está en una orden de contrata.', self.name))
        partner = self.construction_contractor_id
        project = self.project_id
        # sudo: el adicional nace del cambio aprobado; quien lo agrega no
        # necesita permisos de compras.
        Order_sudo = self.env['purchase.order'].sudo()
        order_sudo = Order_sudo._construction_open_service_order(partner, project)
        if not order_sudo:
            order_sudo = Order_sudo.create({
                'partner_id': partner.id, 'company_id': self.company_id.id,
                'construction_is_service_order': True, 'construction_project_id': project.id,
                'construction_plan_id': self.plan_id.id,
                'origin': '%s · %s' % (project.display_name, self.name)})
        Wizard = self.env['construction.plan.contract.wizard']
        allocations = []
        line_values = []
        for plan_line in plan_lines:
            activity = plan_line.activity_id
            product = Wizard._get_service_product(activity)
            taxes = product.supplier_taxes_id.filtered(lambda t: t.company_id == self.company_id) \
                or (order_sudo.construction_terms_id.scheme_line_ids.filtered(
                    lambda l: l.kind == 'tax') and self.company_id.account_purchase_tax_id)
            account = project.account_id
            line_values.append((plan_line, {
                'order_id': order_sudo.id,
                'product_id': product.id,
                'name': self.env._('Adicional %(change)s · %(task)s · %(activity)s',
                                   change=self.name, task=plan_line.task_id.display_name,
                                   activity=activity.display_name),
                'product_qty': plan_line.qty_planned,
                'uom_id': plan_line.product_uom_id.id,
                'price_unit': plan_line.price_unit_planned,
                'tax_ids': [Command.set(taxes.ids)] if taxes else [Command.clear()],
                'date_planned': fields.Datetime.now(),
                'construction_activity_id': activity.id,
                'construction_task_id': plan_line.task_id.id,
                'construction_is_additional': True,
                'construction_change_id': self.id,
                'analytic_distribution': plan_line.analytic_distribution
                or ({str(account.id): 100.0} if account else False),
            }))
        po_lines_sudo = self.env['purchase.order.line'].sudo().create(
            [vals for _plan_line, vals in line_values])
        for (plan_line, _vals), po_line_sudo in zip(line_values, po_lines_sudo):
            allocations.append({'plan_line_id': plan_line.id, 'kind': 'service_order',
                                'purchase_line_id': po_line_sudo.id,
                                'qty_allocated': plan_line.qty_planned})
        plan_lines.with_context(construction_plan_force=True).write({'partner_id': partner.id})
        self.env['construction.resource.plan.allocation'].sudo().create(allocations)
        self.message_post(body=self.env._(
            'Adicional agregado a la orden de contrata %s.', order_sudo.name))
        order_sudo.message_post(body=self.env._('Adicional del cambio %s.', self.name))
        if order_sudo.sudo(False).has_access('read'):
            return {'type': 'ir.actions.act_window', 'res_model': 'purchase.order',
                    'res_id': order_sudo.id, 'view_mode': 'form'}
        return True

    def action_view_construction_purchase_order(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'purchase.order',
                'res_id': self.construction_purchase_order_id.id, 'view_mode': 'form'}


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    construction_change_id = fields.Many2one(
        'construction.change.order', string='Cambio de obra', copy=False,
        index='btree_not_null', check_company=True)
