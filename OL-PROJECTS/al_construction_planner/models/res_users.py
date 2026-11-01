# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    # CREVAL, CR-21: el Cronograma abre desde el menú con el último plan que
    # usó cada usuario.
    construction_schedule_plan_id = fields.Many2one(
        'construction.resource.plan', string='Último plan del Cronograma', ondelete='set null',
        copy=False)
