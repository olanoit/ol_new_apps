# -*- coding: utf-8 -*-
from odoo import models


class ConstructionResourcePlan(models.Model):
    _inherit = 'construction.resource.plan'

    def action_open_generate_wizard(self):
        self.ensure_one()
        self._check_draft()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Generar plan'),
            'res_model': 'construction.plan.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_plan_id': self.id},
        }
