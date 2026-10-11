# -*- coding: utf-8 -*-
from odoo import api, models


class ResourceCalendarLeaves(models.Model):
    _inherit = 'resource.calendar.leaves'

    # Los feriados de la obra se leen una vez por transacción
    # (res.company._construction_holidays): un cambio en las ausencias
    # globales los vuelve a leer.
    @api.model_create_multi
    def create(self, vals_list):
        self.env.cr.cache.pop('al_construction_holidays', None)
        return super().create(vals_list)

    def write(self, vals):
        self.env.cr.cache.pop('al_construction_holidays', None)
        return super().write(vals)

    def unlink(self):
        self.env.cr.cache.pop('al_construction_holidays', None)
        return super().unlink()
