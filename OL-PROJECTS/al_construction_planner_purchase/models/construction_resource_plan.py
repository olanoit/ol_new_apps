# -*- coding: utf-8 -*-
from odoo import Command, models
from odoo.exceptions import UserError


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def action_open_price_wizard(self):
        self.ensure_one()
        self._check_draft()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Aplicar costo'),
            'res_model': 'construction.plan.price.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_plan_id': self.id},
        }


class ConstructionResourcePlanLine(models.Model):
    _inherit = 'construction.resource.plan.line'

    def action_open_price_wizard(self):
        """«Aplicar costo» desde la lista de líneas: las seleccionadas, que
        deben ser de un solo plan y un solo producto."""
        plan = self.plan_id
        if len(plan) != 1 or len(self.product_id) != 1 or not all(self.mapped('product_id')):
            raise UserError(self.env._(
                'Seleccione líneas de un solo plan y de un solo producto.'))
        action = plan.action_open_price_wizard()
        action['context'] = {
            'default_plan_id': plan.id,
            'default_product_id': self.product_id.id,
            'default_line_ids': [Command.set(self.ids)],
        }
        return action
