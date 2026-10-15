# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError


class ConstructionMeasurement(models.Model):
    _inherit = 'construction.measurement'

    def _construction_check_reopen(self):
        super()._construction_check_reopen()
        if self.env['mrp.production'].search_count([
                ('construction_space_task_ids', 'in', self.task_id.ids), ('state', '!=', 'cancel')]):
            raise UserError(self.env._(
                'El ambiente ya tiene una orden de fabricación: el metrado no se puede reabrir.'))
