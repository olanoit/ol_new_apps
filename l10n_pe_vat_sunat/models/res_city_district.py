# -*- coding: utf-8 -*-
from odoo import api, models


class L10nPeResCityDistrict(models.Model):
    _inherit = 'l10n_pe.res.city.district'

    @api.depends('name', 'city_id.name')
    def _compute_display_name(self):
        for district in self:
            if district.city_id:
                district.display_name = '%s (%s)' % (
                    district.name, district.city_id.name,
                )
            else:
                district.display_name = district.name or ''
