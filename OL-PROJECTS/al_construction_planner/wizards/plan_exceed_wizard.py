# -*- coding: utf-8 -*-
"""W-10 «Exceso sobre plan»: se abre al pedir la aprobación de un
requerimiento de obra o al confirmar una OF que piden más de lo que queda en
el plan. Con la política «avisar» basta confirmar; con «pedir aprobación» la
justificación es obligatoria y el requerimiento recibe una revisión más (la
OF la confirma la jefatura del planificador)."""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class ConstructionPlanExceedWizard(models.TransientModel):
    _name = 'construction.plan.exceed.wizard'
    _description = 'Exceso sobre el plan'

    material_request_id = fields.Many2one(
        'construction.material.request', string='Requerimiento de obra', readonly=True)
    production_id = fields.Many2one(
        'mrp.production', string='Orden de fabricación', readonly=True)
    policy = fields.Selection(
        [('warn', 'Avisar'), ('approval', 'Pedir aprobación'), ('block', 'Bloquear')],
        string='Política', compute='_compute_lines', store=True)
    reason = fields.Text(string='Justificación')
    line_ids = fields.One2many(
        'construction.plan.exceed.wizard.line', 'wizard_id', string='Exceso',
        compute='_compute_lines', store=True)

    # El residente o la planta no ven el plan: la política y el saldo se leen
    # sin sus permisos, solo para mostrarlos.
    @api.depends('material_request_id', 'production_id')
    def _compute_lines(self):
        for wizard in self:
            commands = [Command.clear()]
            request_sudo = wizard.material_request_id.sudo()
            production_sudo = wizard.production_id.sudo()
            if request_sudo:
                wizard.policy = request_sudo.construction_plan_id.exceed_policy
                for line in request_sudo._construction_exceeding_lines():
                    uom = line.product_id.uom_id
                    excess = uom._compute_quantity(
                        line._construction_get_excess(), line.product_uom_id)
                    commands.append(Command.create({
                        'product_id': line.product_id.id,
                        'product_uom_id': line.product_uom_id.id,
                        'qty_remaining': line.construction_plan_remaining,
                        'qty_requested': line.product_qty,
                        'qty_excess': excess,
                    }))
            elif production_sudo:
                wizard.policy = production_sudo.construction_plan_id.exceed_policy
                for product, balance, qty, excess in production_sudo._construction_get_excess():
                    commands.append(Command.create({
                        'product_id': product.id,
                        'product_uom_id': product.uom_id.id,
                        'qty_remaining': balance,
                        'qty_requested': qty,
                        'qty_excess': excess,
                    }))
            else:
                wizard.policy = False
            wizard.line_ids = commands

    def _get_action(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Exceso sobre el plan'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_confirm(self):
        self.ensure_one()
        reason = (self.reason or '').strip()
        if self.policy == 'approval' and not reason:
            raise UserError(self.env._('Escriba la justificación del exceso.'))
        if self.material_request_id:
            request = self.material_request_id
            request.construction_exceed_reason = reason or request.construction_exceed_reason
            res = request.with_context(construction_exceed_checked=True).action_request_approval()
        else:
            production = self.production_id
            if self.policy == 'approval' and not self.env.user.has_group(
                    'al_construction_planner.group_planner_manager'):
                raise UserError(self.env._(
                    'El exceso de una OF lo aprueba la jefatura del planificador: pídale que '
                    'confirme la orden %s.', production.name))
            production.write({
                'construction_exceed_reason': reason or production.construction_exceed_reason,
                'construction_exceed_state': (
                    'approved' if self.policy == 'approval' else 'exceeded'),
            })
            res = production.with_context(construction_exceed_checked=True).action_confirm()
        return res if isinstance(res, dict) else {'type': 'ir.actions.act_window_close'}


class ConstructionPlanExceedWizardLine(models.TransientModel):
    _name = 'construction.plan.exceed.wizard.line'
    _description = 'Material que excede el plan'

    wizard_id = fields.Many2one(
        'construction.plan.exceed.wizard', string='Asistente', required=True,
        ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Producto')
    product_uom_id = fields.Many2one('uom.uom', string='Unidad')
    qty_remaining = fields.Float(string='Saldo', digits='Product Unit')
    qty_requested = fields.Float(string='Pedido', digits='Product Unit')
    qty_excess = fields.Float(string='Exceso', digits='Product Unit')
